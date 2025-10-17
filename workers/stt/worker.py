import os, asyncio, base64, time, math, orjson
import redis.asyncio as redis
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

# optional VAD
USE_WEBRTCVAD = os.getenv("VAD","true").lower() in ("1","true","yes","y")
if USE_WEBRTCVAD:
    try:
        import webrtcvad
        VAD = webrtcvad.Vad(2)  # 0..3 aggressiveness
    except Exception:
        VAD = None
else:
    VAD = None

REDIS_URL = os.getenv("REDIS_URL","redis://redis:6379/0")
AUDIO_DIR = os.getenv("AUDIO_DIR","/data/audio")
MODEL_NAME = os.getenv("WHISPER_MODEL","base-int8")
NUM_THREADS = int(os.getenv("NUM_THREADS","2"))
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE","int8")
CHUNK_MS = int(os.getenv("CHUNK_MS","400"))
MAX_REDECODE_SEC = float(os.getenv("MAX_REDECODE_SEC","3"))
COND_PREV = os.getenv("CONDITION_ON_PREVIOUS_TEXT","true").lower() in ("1","true","yes","y")
SAMPLE_RATE = 16000
SIL_MS_FINAL = 1000

class Session:
    __slots__ = ("room","device","buf","sil_ms","segment_id","revision","final_prefix")
    def __init__(self, room, device):
        self.room = room
        self.device = device
        self.buf: np.ndarray = np.zeros(0, dtype=np.float32)
        self.sil_ms = 0.0
        self.segment_id = 0
        self.revision = 0
        self.final_prefix = ""

def dbfs(x: np.ndarray) -> float:
    if x.size == 0: return -120.0
    m = np.maximum(np.abs(x), 1e-7).mean()
    return 20 * math.log10(m)

def pcm16_b64_to_f32(b64: str) -> np.ndarray:
    b = base64.b64decode(b64)
    pcm = np.frombuffer(b, dtype=np.int16).astype(np.float32) / 32768.0
    return pcm

def vad_silent(pcm_f32: np.ndarray) -> bool:
    if VAD is None:
        return dbfs(pcm_f32) < -45.0
    # webrtcvad needs 16-bit mono 20/30 ms frames at 16kHz
    pcm16 = (np.clip(pcm_f32, -1, 1) * 32768).astype(np.int16).tobytes()
    frame_ms = 30
    frame_len = SAMPLE_RATE * frame_ms // 1000 * 2  # bytes per frame
    voiced = False
    for i in range(0, len(pcm16) - frame_len + 1, frame_len):
        frame = pcm16[i:i+frame_len]
        if VAD.is_speech(frame, SAMPLE_RATE):
            voiced = True
            break
    return not voiced

async def publish(r: redis.Redis, payload: dict):
    await r.publish("stt_events", orjson.dumps(payload))

async def run():
    r = redis.from_url(REDIS_URL, decode_responses=False)
    pubsub = r.pubsub()
    await pubsub.subscribe("stt_input")

    os.makedirs(AUDIO_DIR, exist_ok=True)
    model = WhisperModel(
        MODEL_NAME,
        device="cpu",
        compute_type=COMPUTE_TYPE,
        num_workers=NUM_THREADS,
        cpu_threads=NUM_THREADS,
    )

    sessions: dict[tuple[str,str], Session] = {}

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        data = orjson.loads(msg["data"])
        if data.get("type") != "audio_chunk":
            continue
        room = data["room_id"]; dev = data.get("device","dev")
        key = (room, dev)
        s = sessions.get(key) or Session(room, dev); sessions[key] = s

        chunk = pcm16_b64_to_f32(data.get("pcm16_base64",""))
        s.buf = np.concatenate([s.buf, chunk])

        if vad_silent(chunk):
            s.sil_ms += CHUNK_MS
        else:
            s.sil_ms = 0.0

        # incremental window
        win = int(SAMPLE_RATE * MAX_REDECODE_SEC)
        audio_win = s.buf[-win:] if s.buf.size > win else s.buf

        segments, _ = model.transcribe(
            audio=audio_win,
            language=None,
            beam_size=1,
            best_of=1,
            vad_filter=False,  # we control VAD externally
            condition_on_previous_text=COND_PREV,
            initial_prompt=s.final_prefix[-200:] if COND_PREV and s.final_prefix else None,
        )
        parts = [seg.text.strip() for seg in segments]
        partial_text = " ".join(p for p in parts if p).strip()

        s.revision += 1
        await publish(r, {
            "type": "partial",
            "room_id": room,
            "device": dev,
            "segment_id": s.segment_id,
            "revision": s.revision,
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "text": partial_text,
            "lang": None,
        })

        if s.sil_ms >= SIL_MS_FINAL:
            await publish(r, {
                "type": "final",
                "room_id": room,
                "device": dev,
                "segment_id": s.segment_id,
                "revision": -1,
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "text": partial_text,
                "lang": None,
                "final": True,
            })
            s.segment_id += 1
            s.revision = 0
            s.final_prefix = (s.final_prefix + " " + partial_text).strip()
            s.sil_ms = 0.0
            s.buf = s.buf[-int(SAMPLE_RATE*5):]  # keep 5s tail

if __name__ == "__main__":
    asyncio.run(run())

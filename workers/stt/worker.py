import os, asyncio, base64, time, math
from collections import deque, defaultdict

import numpy as np
import redis.asyncio as redis
from aiohttp import web
from faster_whisper import WhisperModel

# ---------- env ----------
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
AUDIO_DIR = os.getenv("AUDIO_DIR", "/data/audio")
MODEL_NAME = os.getenv("WHISPER_MODEL", "base-int8")
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")
NUM_THREADS = int(os.getenv("NUM_THREADS", "2"))
CHUNK_MS = int(os.getenv("CHUNK_MS", "400"))
MAX_REDECODE_SEC = float(os.getenv("MAX_REDECODE_SEC", "3"))
COND_PREV = os.getenv("CONDITION_ON_PREVIOUS_TEXT", "true").lower() == "true"
VAD = os.getenv("VAD", "true").lower() == "true"
SILENCE_MS = 1000  # end of segment after ~1s silence
SAMPLE_RATE = 16000

os.makedirs(AUDIO_DIR, exist_ok=True)

# ---------- utils ----------
def b64pcm16_to_float32(b64: str) -> np.ndarray:
    """decode base64 little-endian int16 PCM to float32 [-1,1]"""
    b = base64.b64decode(b64)
    if len(b) % 2 != 0:
        b = b[:-1]
    pcm = np.frombuffer(b, dtype="<i2")
    if pcm.size == 0:
        return np.zeros(0, dtype=np.float32)
    return (pcm.astype(np.float32) / 32768.0).copy()

def rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(x))))

# ---------- state ----------
class RoomState:
    __slots__ = ("buf", "last_activity_ts", "segment_id", "prev_text")
    def __init__(self):
        self.buf: deque[np.ndarray] = deque(maxlen= int( (SAMPLE_RATE * 60) / (SAMPLE_RATE*CHUNK_MS/1000) ))  # ~1 min ring
        self.last_activity_ts: float = time.time()
        self.segment_id: int = 1
        self.prev_text: str = ""

class STTWorker:
    def __init__(self):
        self.r: redis.Redis = redis.from_url(REDIS_URL, decode_responses=False)
        self.pub = "stt_events"
        self.sub = "stt_input"
        self.state: dict[tuple[str,str], RoomState] = defaultdict(RoomState)
        self.model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE_TYPE, num_workers=NUM_THREADS, download_root=os.getenv("HF_HOME","/tmp/hf_home"))

    # ---------- core loop ----------
    async def run(self):
        asyncio.create_task(self._gc_loop())
        pubsub = self.r.pubsub()
        await pubsub.subscribe(self.sub)
        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue
            try:
                payload = msg["data"]  # bytes
                data = __import__("orjson").loads(payload)  # faster than json
            except Exception:
                continue
            if data.get("type") != "audio_chunk":
                continue
            room = data.get("room_id") or "room"
            dev = data.get("device") or "dev"
            key = (room, dev)
            pcmf = b64pcm16_to_float32(data.get("pcm16_base64",""))
            if pcmf.size == 0:
                continue

            st = self.state[key]
            st.buf.append(pcmf)
            st.last_activity_ts = time.time()

            # partial every ~1.2s of audio accumulated
            seg = np.concatenate(list(st.buf)[- max(1, int((1200/CHUNK_MS))) : ])  # last ~1.2s
            if seg.size >= int(SAMPLE_RATE*0.8):  # gate
                txt = self._transcribe_tail(key, seg, partial=True)
                if txt:
                    await self._publish(room, dev, st.segment_id, revision=st.segment_id, text=txt, final=False, lang=self._lang_or_auto(txt))

            # silence detection -> final
            if VAD:
                tail = np.concatenate(list(st.buf)[- max(1, int((SILENCE_MS/CHUNK_MS))) : ])
                if rms(tail) < 0.01:  # simple energy gate
                    full = np.concatenate(list(st.buf))
                    if full.size >= int(SAMPLE_RATE*0.6):
                        txt = self._transcribe_tail(key, full, partial=False)
                        if txt:
                            await self._publish(room, dev, st.segment_id, revision=-1, text=txt, final=True, lang=self._lang_or_auto(txt))
                    # reset segment
                    st.buf.clear()
                    st.prev_text = ""
                    st.segment_id += 1

    def _transcribe_tail(self, key, audio: np.ndarray, partial: bool) -> str:
        st = self.state[key]
        # limit context for re-decode
        max_len = int(SAMPLE_RATE * max(1.0, min(MAX_REDECODE_SEC, 6.0)))
        if audio.size > max_len:
            audio = audio[-max_len:]
        segments, _ = self.model.transcribe(
            audio,
            language=None,                 # auto
            beam_size=1 if partial else 4,
            best_of=1 if partial else 2,
            vad_filter=True,
            condition_on_previous_text=COND_PREV,
            initial_prompt=st.prev_text or None,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0 if partial else -1.2,
            compression_ratio_threshold=2.6,
        )
        out = "".join(s.text for s in segments).strip()
        if partial:
            # keep short context to stabilize
            st.prev_text = (st.prev_text + " " + out).strip()[:256]
        else:
            st.prev_text = out[:256]
        return out

    async def _publish(self, room: str, device: str, segment_id: int, revision: int, text: str, final: bool, lang: str):
        msg = {
            "type": "final" if final else "partial",
            "room_id": room,
            "device": device,
            "segment_id": segment_id,
            "revision": revision,
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "text": text,
            "lang": lang,
            "final": final,
        }
        await self.r.publish(self.pub, __import__("orjson").dumps(msg))

    def _lang_or_auto(self, txt: str) -> str:
        # cheap heuristic; real language id can be added later
        return "auto"

    # cleanup stale states
    async def _gc_loop(self):
        while True:
            now = time.time()
            for k, st in list(self.state.items()):
                if now - st.last_activity_ts > 300:
                    self.state.pop(k, None)
            await asyncio.sleep(60)

# ---------- health ----------
async def _health(_):
    return web.json_response({"ok": True})

async def _main():
    worker = STTWorker()
    app = web.Application()
    app.add_routes([web.get("/health", _health)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass

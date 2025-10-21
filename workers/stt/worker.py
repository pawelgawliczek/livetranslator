import os, asyncio, base64, time, math
import numpy as np
import redis.asyncio as redis
try:
    import orjson as jsonmod
    def jdumps(x): return jsonmod.dumps(x)
    def jloads(b): return jsonmod.loads(b)
except Exception:
    import json as jsonmod
    def jdumps(x): return jsonmod.dumps(x).encode()
    def jloads(b):  return jsonmod.loads(b if isinstance(b,str) else b.decode())

from faster_whisper import WhisperModel

# ---- config
REDIS_URL   = os.getenv("REDIS_URL", "redis://redis:6379/0")
MODEL_NAME  = os.getenv("WHISPER_MODEL", "base")
COMPUTE_TY  = os.getenv("COMPUTE_TYPE", "int8")
NUM_THREADS = int(os.getenv("NUM_THREADS", "2"))
CHUNK_MS    = int(os.getenv("CHUNK_MS", "400"))
MAX_TAIL_S  = float(os.getenv("MAX_REDECODE_SEC", "3"))
COND_PREV   = os.getenv("CONDITION_ON_PREVIOUS_TEXT", "true").lower() == "true"

# ---- model
model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE_TY, num_workers=NUM_THREADS)

# per stream buffers (room+device) of float32 mono @16k
buffers = {}

def _key(room, device): return f"{room}::{device}"

def pcm16_b64_to_float32(b64: str) -> np.ndarray:
    if not b64: return np.zeros(0, dtype=np.float32)
    raw = base64.b64decode(b64)
    pcm = np.frombuffer(raw, dtype=np.int16)
    return (pcm.astype(np.float32) / 32768.0)

async def stt_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("stt_local_in")
    print("STT local listening on stt_local_in")

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        try:
            data = jloads(msg["data"])
            msg_type = data.get("type", "")
            room  = data.get("room_id") or data.get("roomId") or "demo"
            dev   = data.get("device") or data.get("deviceId") or "dev"
            seq   = int(data.get("seq", 0))

            print(f"[STT Worker] Received {msg_type} for room={room} device={dev} seq={seq}")

            audio = pcm16_b64_to_float32(data.get("pcm16_base64", ""))  # expected 16k mono

            k = _key(room, dev)
            buf = buffers.get(k, np.zeros(0, dtype=np.float32))
            # append
            if audio.size:
                buf = np.concatenate([buf, audio])
                # keep only last N seconds to cap compute
                keep = int(MAX_TAIL_S * 16000)
                if buf.size > keep:
                    buf = buf[-keep:]
                buffers[k] = buf
                print(f"[STT Worker] Buffer size: {buf.size} samples ({buf.size/16000:.1f}s)")

            # no audio → nothing to do
            if buf.size < 12800:  # need at least 1s
                print(f"[STT Worker] Buffer too small ({buf.size} < 12800), skipping transcription")
                continue

            print(f"[STT Worker] Starting transcription of {buf.size/16000:.1f}s buffer...")
            # transcribe last window; beam_size=3 for better quality (vs beam_size=1)
            segments, _ = model.transcribe(
                buf,
                language=None,  # auto
                vad_filter=True,
                condition_on_previous_text=COND_PREV,
                beam_size=3,  # Increased from 1 for better quality (still fast)
                temperature=0.0,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4,
            )

            print(f"[STT Worker] Transcription complete, processing segments...")
            # pick the last segment text if any
            last_text = None
            for seg in segments:
                last_text = seg.text.strip()
                print(f"[STT Worker] Segment: {seg.text.strip()}")

            if last_text:
                print(f"[STT Worker] Publishing result: {last_text}")
                payload = {
                    "type": "partial",
                    "room_id": room,
                    "segment_id": seq,         # simple mapping for demo
                    "revision": 1,
                    "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "text": last_text,
                    "lang": "auto"
                }
                await r.publish("stt_events", jdumps(payload).decode())
                print(f"[STT Worker] ✓ Published to stt_events")
            else:
                print(f"[STT Worker] No text detected in audio")

        except Exception as e:
            print(f"[STT Worker] ERROR: {repr(e)}")
            import traceback
            traceback.print_exc()

# minimal health (optional: keep)
if __name__ == "__main__":
    try:
        asyncio.run(stt_loop())
    except KeyboardInterrupt:
        pass

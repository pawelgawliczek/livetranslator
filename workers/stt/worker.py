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
REDIS_URL   = os.getenv("REDIS_URL", "redis://redis:6379/5")
MODEL_NAME  = os.getenv("WHISPER_MODEL", "base")
COMPUTE_TY  = os.getenv("COMPUTE_TYPE", "int8")
NUM_THREADS = int(os.getenv("NUM_THREADS", "2"))
CHUNK_MS    = int(os.getenv("CHUNK_MS", "400"))
MAX_TAIL_S  = float(os.getenv("MAX_REDECODE_SEC", "3"))
COND_PREV   = os.getenv("CONDITION_ON_PREVIOUS_TEXT", "true").lower() == "true"

# ---- model
model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE_TY, num_workers=NUM_THREADS)

# per stream buffers (room+device) of float32 mono @16k
buffers = {}  # Rolling 3-second buffer for partials
full_buffers = {}  # Full audio accumulation for finals
# track if current segment has been finalized (to avoid double-increment)
segment_finalized = {}

def _key(room, device): return f"{room}::{device}"

async def get_or_create_segment_id(room, redis_client):
    """Get current segment ID for room from Redis (synchronized with OpenAI router)"""
    key = f"room:{room}:segment_counter"
    segment_id = await redis_client.get(key)
    if segment_id is None:
        # Initialize counter
        await redis_client.set(key, "1")
        return 1
    return int(segment_id)

async def increment_segment_id(room, redis_client):
    """Increment segment ID for next segment in Redis"""
    key = f"room:{room}:segment_counter"
    new_id = await redis_client.incr(key)
    return new_id

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

            # Always use full accumulated audio for incremental transcription
            # This way partials build up the complete text progressively
            is_final_message = msg_type == "audio_chunk" or msg_type == "audio_end"

            # Accumulate all audio in full buffer
            full_buf = full_buffers.get(k, np.zeros(0, dtype=np.float32))
            if audio.size:
                full_buf = np.concatenate([full_buf, audio])
                full_buffers[k] = full_buf

            # Use full buffer for BOTH partials and finals (incremental transcription)
            buf = full_buf
            transcription_type = "Final" if is_final_message else "Partial"
            print(f"[STT Worker] {transcription_type} - Full buffer: {buf.size} samples ({buf.size/16000:.1f}s)")

            # no audio → nothing to do
            # Special case: audio_end with empty buffer means final was already sent
            if buf.size < 12800:  # need at least 1s
                print(f"[STT Worker] Buffer too small ({buf.size} < 12800), skipping transcription")
                # Don't increment segment here - only increment when we actually publish a final
                # This avoids double-increment when multiple audio_end messages arrive
                continue

            print(f"[STT Worker] Starting transcription of {buf.size/16000:.1f}s buffer...")
            # transcribe; beam_size=3 for better quality (vs beam_size=1)
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
            # Combine ALL segments into complete text
            all_segments = []
            for seg in segments:
                seg_text = seg.text.strip()
                if seg_text:
                    all_segments.append(seg_text)
                    print(f"[STT Worker] Segment: {seg_text}")

            full_text = " ".join(all_segments) if all_segments else None

            if full_text:
                print(f"[STT Worker] Publishing result: {full_text}")

                # Determine if this is a partial or final based on message type
                is_final = msg_type == "audio_chunk" or msg_type == "audio_end"
                event_type = "stt_final" if is_final else "stt_partial"

                # Get current segment ID from Redis (synchronized with OpenAI router)
                segment_id = await get_or_create_segment_id(room, r)

                # Reset finalized flag when publishing partials (new utterance started)
                if not is_final and segment_finalized.get(room, False):
                    segment_finalized[room] = False
                    print(f"[STT Worker] → New utterance started, reset finalized flag")

                payload = {
                    "type": event_type,
                    "room_id": room,
                    "segment_id": segment_id,
                    "revision": seq,  # Use seq as revision number
                    "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "text": full_text,
                    "lang": "auto",
                    "final": is_final,
                    "speaker": data.get("speaker", "system"),
                    "target_lang": data.get("target_lang", "en"),
                    "device": dev
                }
                await r.publish("stt_events", jdumps(payload).decode())
                print(f"[STT Worker] ✓ Published {event_type} to stt_events (segment={segment_id}, rev={seq})")

                # Increment segment ID for next utterance when we finalize
                # Only increment ONCE per segment (multiple audio_end messages can arrive)
                if is_final:
                    if not segment_finalized.get(room, False):
                        segment_finalized[room] = True
                        next_segment_id = await increment_segment_id(room, r)
                        # Clear full buffer for next utterance
                        if k in full_buffers:
                            del full_buffers[k]
                        print(f"[STT Worker] → Finalized segment {segment_id}, next will be {next_segment_id}")
                    else:
                        print(f"[STT Worker] → Segment already finalized, skipping increment")
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

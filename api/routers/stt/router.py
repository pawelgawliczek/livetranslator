import os
import asyncio
import base64
import redis.asyncio as redis
try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

from openai_backend import transcribe_audio_chunk

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
INPUT_CHANNEL = os.getenv("STT_INPUT_CHANNEL", "stt_input")
OUTPUT_CHANNEL = os.getenv("STT_OUTPUT_CHANNEL", "stt_local_in")
STT_MODE = os.getenv("LT_STT_PARTIAL_MODE", "local")
STT_OUTPUT_EVENTS = os.getenv("STT_OUTPUT_EVENTS", "stt_events")
COST_TRACKING_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")

print(f"[STT Router] Starting...")
print(f"  Mode:   {STT_MODE}")
print(f"  Input:  {INPUT_CHANNEL}")
print(f"  Output: {OUTPUT_CHANNEL if STT_MODE == 'local' else STT_OUTPUT_EVENTS}")

# Track current partial accumulation per room
partial_sessions = {}  # room -> {segment_id, accumulated_text, speaker, target_lang}

async def get_next_segment_id(r: redis.Redis, room: str) -> int:
    """Get and increment segment counter for a room, stored in Redis"""
    key = f"room:{room}:segment_counter"
    segment_id = await r.incr(key)
    return segment_id

async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(INPUT_CHANNEL)
    
    print(f"[STT Router] Listening on {INPUT_CHANNEL}")
    
    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        
        try:
            data = jloads(msg["data"])
            msg_type = data.get("type", "")
            room = data.get("room_id", "unknown")
            speaker = data.get("speaker", "system")
            target_lang = data.get("target_lang", "en")
            
            if msg_type == "audio_chunk_partial" and STT_MODE == "openai_chunked":
                # Handle partial transcription - accumulate in same segment
                seq = data.get("seq", 0)
                audio_b64 = data.get("pcm16_base64", "")
                device = data.get("device", "web")
                
                audio_bytes = base64.b64decode(audio_b64)
                duration_sec = len(audio_bytes) / (16000 * 2)
                
                # Initialize or get existing partial session
                if room not in partial_sessions:
                    segment_id = await get_next_segment_id(r, room)
                    partial_sessions[room] = {
                        "segment_id": segment_id,
                        "accumulated_text": "",
                        "chunk_count": 0,
                        "speaker": speaker,
                        "target_lang": target_lang
                    }
                
                session = partial_sessions[room]
                session["chunk_count"] += 1
                session["target_lang"] = target_lang  # Update if changed
                
                print(f"[STT Router] Processing PARTIAL: room={room} speaker={speaker} segment={session['segment_id']} chunk={session['chunk_count']} target={target_lang}")
                
                try:
                    result = await transcribe_audio_chunk(audio_b64)
                    new_text = result["text"].strip()
                    
                    # Accumulate text
                    if session["accumulated_text"]:
                        session["accumulated_text"] += " " + new_text
                    else:
                        session["accumulated_text"] = new_text
                    
                    stt_event = {
                        "type": "stt_partial",
                        "room_id": room,
                        "segment_id": session["segment_id"],
                        "revision": session["chunk_count"],
                        "text": session["accumulated_text"],
                        "lang": result.get("language", "auto"),
                        "final": False,
                        "ts_iso": None,
                        "device": device,
                        "speaker": speaker,
                        "target_lang": target_lang
                    }
                    
                    await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                    print(f"[STT Router] ✓ Partial {session['segment_id']}: {session['accumulated_text'][:80]}...")
                    
                    # Track cost
                    cost_event = {
                        "room_id": room,
                        "pipeline": "stt",
                        "mode": "openai_whisper_partial",
                        "units": duration_sec,
                        "unit_type": "seconds"
                    }
                    await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                    
                except Exception as e:
                    print(f"[STT Router] ✗ Partial transcription failed: {e}")
                    
            elif msg_type == "audio_chunk" and STT_MODE == "openai_chunked":
                # Handle final transcription (from VAD) - clears partial session
                seq = data.get("seq", 0)
                audio_b64 = data.get("pcm16_base64", "")
                device = data.get("device", "web")
                
                audio_bytes = base64.b64decode(audio_b64)
                duration_sec = len(audio_bytes) / (16000 * 2)
                
                # Use existing segment if we have partials, otherwise create new
                if room in partial_sessions:
                    segment_id = partial_sessions[room]["segment_id"]
                    stored_speaker = partial_sessions[room]["speaker"]
                    stored_target_lang = partial_sessions[room]["target_lang"]
                    print(f"[STT Router] Processing FINAL (finalizing partial): room={room} speaker={stored_speaker} segment={segment_id} target={stored_target_lang}")
                else:
                    segment_id = await get_next_segment_id(r, room)
                    stored_speaker = speaker
                    stored_target_lang = target_lang
                    print(f"[STT Router] Processing FINAL (no partials): room={room} speaker={speaker} segment={segment_id} target={target_lang}")
                
                try:
                    result = await transcribe_audio_chunk(audio_b64)
                    
                    stt_event = {
                        "type": "stt_final",
                        "room_id": room,
                        "segment_id": segment_id,
                        "revision": 1,
                        "text": result["text"],
                        "lang": result.get("language", "auto"),
                        "final": True,
                        "ts_iso": None,
                        "device": device,
                        "speaker": stored_speaker,
                        "target_lang": stored_target_lang
                    }
                    
                    await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                    print(f"[STT Router] ✓ Final segment {segment_id}: {result['text'][:80]}...")
                    
                    # Track cost
                    cost_event = {
                        "room_id": room,
                        "pipeline": "stt",
                        "mode": "openai_whisper",
                        "units": duration_sec,
                        "unit_type": "seconds"
                    }
                    await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                    print(f"[STT Router] 💰 Cost tracked: {duration_sec:.1f}s audio")
                    
                    # Clear partial session
                    if room in partial_sessions:
                        del partial_sessions[room]
                    
                except Exception as e:
                    print(f"[STT Router] ✗ Final transcription failed: {e}")
                    
            elif msg_type == "audio_end":
                print(f"[STT Router] Audio session ended for room={room}")
                # Clear partial session
                if room in partial_sessions:
                    del partial_sessions[room]
                
        except Exception as e:
            print(f"[STT Router] Error processing message: {e}")

if __name__ == "__main__":
    asyncio.run(router_loop())

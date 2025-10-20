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

# Track audio buffers and segment counters per room
audio_buffers = {}
segment_counters = {}

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
            
            if msg_type == "audio_chunk" and STT_MODE == "openai_chunked":
                seq = data.get("seq", 0)
                audio_b64 = data.get("pcm16_base64", "")
                
                # Decode and store raw PCM bytes
                if room not in audio_buffers:
                    audio_buffers[room] = b''
                    segment_counters[room] = 0
                
                audio_buffers[room] += base64.b64decode(audio_b64)
                print(f"[STT Router] Buffered chunk: room={room} seq={seq} total_bytes={len(audio_buffers[room])}")
                
            elif msg_type == "audio_end" and STT_MODE == "openai_chunked":
                audio_bytes = audio_buffers.get(room, b'')
                if audio_bytes:
                    # Increment segment counter
                    segment_counters[room] = segment_counters.get(room, 0) + 1
                    segment_id = segment_counters[room]
                    
                    # Calculate audio duration
                    sample_rate = 16000
                    duration_sec = len(audio_bytes) / (sample_rate * 2)
                    
                    print(f"[STT Router] Sending {len(audio_bytes)} bytes ({duration_sec:.1f}s) to OpenAI for room={room} segment={segment_id}")
                    
                    # Re-encode combined bytes to base64
                    combined_b64 = base64.b64encode(audio_bytes).decode()
                    
                    try:
                        result = await transcribe_audio_chunk(combined_b64)
                        
                        stt_event = {
                            "type": "stt_final",
                            "room_id": room,
                            "segment_id": segment_id,
                            "revision": 1,
                            "lang": result["language"],
                            "text": result["text"],
                            "final": True,
                            "ts_iso": None,
                            "backend": "openai_chunked"
                        }
                        
                        await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                        print(f"[STT Router] ✓ Transcribed segment {segment_id}: {result['text'][:80]}...")
                        
                        # Publish cost event
                        cost_event = {
                            "type": "cost_event",
                            "room_id": room,
                            "pipeline": "stt_final",
                            "mode": "openai",
                            "units": int(duration_sec),
                            "unit_type": "audio_sec"
                        }
                        await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                        print(f"[STT Router] 💰 Cost tracked: {duration_sec:.1f}s audio")
                        
                    except Exception as e:
                        print(f"[STT Router] ✗ OpenAI error: {e}")
                    
                    audio_buffers[room] = b''
                    
            elif STT_MODE == "local":
                await r.publish(OUTPUT_CHANNEL, jdumps(data))
                if msg_type == "audio_chunk":
                    seq = data.get("seq", 0)
                    print(f"[STT Router] Routed to local: room={room} seq={seq}")
                
        except Exception as e:
            print(f"[STT Router] Error: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    asyncio.run(router_loop())

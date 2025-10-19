import os
import asyncio
import redis.asyncio as redis
try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
INPUT_CHANNEL = os.getenv("STT_INPUT_CHANNEL", "stt_input")
OUTPUT_CHANNEL = os.getenv("STT_OUTPUT_CHANNEL", "stt_local_in")

print(f"[STT Router] Starting...")
print(f"  Input:  {INPUT_CHANNEL}")
print(f"  Output: {OUTPUT_CHANNEL}")

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
            
            # For now, just pass through all messages
            await r.publish(OUTPUT_CHANNEL, jdumps(data))
            
            if msg_type == "audio_chunk":
                room = data.get("room_id", "unknown")
                seq = data.get("seq", 0)
                print(f"[STT Router] Routed audio chunk: room={room} seq={seq}")
            else:
                print(f"[STT Router] Routed message: type={msg_type}")
                
        except Exception as e:
            print(f"[STT Router] Error: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(router_loop())

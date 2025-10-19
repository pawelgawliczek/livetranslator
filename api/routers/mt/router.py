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
INPUT_CHANNEL = os.getenv("MT_INPUT_CHANNEL", "mt_requests")
OUTPUT_CHANNEL = os.getenv("MT_OUTPUT_CHANNEL", "mt_events")

print(f"[MT Router] Starting...")
print(f"  Input:  {INPUT_CHANNEL}")
print(f"  Output: {OUTPUT_CHANNEL}")

async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(INPUT_CHANNEL)
    
    print(f"[MT Router] Listening on {INPUT_CHANNEL}")
    
    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        
        try:
            data = jloads(msg["data"])
            room = data.get("room_id", "unknown")
            segment = data.get("segment_id", 0)
            
            # For now, just pass through
            # Future: route to OpenAI or local MT worker
            await r.publish(OUTPUT_CHANNEL, jdumps(data))
            
            print(f"[MT Router] Routed translation request: room={room} segment={segment}")
                
        except Exception as e:
            print(f"[MT Router] Error: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(router_loop())

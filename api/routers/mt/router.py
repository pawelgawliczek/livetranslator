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

from openai_backend import translate_text

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
STT_EVENTS = os.getenv("STT_EVENTS_CHANNEL", "stt_events")
MT_OUTPUT = os.getenv("MT_OUTPUT_CHANNEL", "mt_events")
MT_MODE = os.getenv("LT_MT_MODE", "local")
DEFAULT_TGT = os.getenv("LT_DEFAULT_TGT", "en")

print(f"[MT Router] Starting...")
print(f"  Mode:       {MT_MODE}")
print(f"  Input:      {STT_EVENTS}")
print(f"  Output:     {MT_OUTPUT}")
print(f"  Target:     {DEFAULT_TGT}")

async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(STT_EVENTS)
    
    print(f"[MT Router] Listening on {STT_EVENTS}")
    
    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        
        try:
            data = jloads(msg["data"])
            msg_type = data.get("type", "")
            
            # Only translate final STT events
            if msg_type != "stt_final":
                continue
            
            room = data.get("room_id", "unknown")
            segment = data.get("segment_id", 0)
            src_lang = data.get("lang", "auto")
            text = data.get("text", "").strip()
            
            if not text:
                continue
            
            print(f"[MT Router] Translating: room={room} seg={segment} lang={src_lang}")
            
            if MT_MODE == "openai":
                try:
                    translated = await translate_text(text, src_lang, DEFAULT_TGT)
                    
                    mt_event = {
                        "type": "translation_final",
                        "room_id": room,
                        "segment_id": segment,
                        "src": src_lang,
                        "tgt": DEFAULT_TGT,
                        "text": translated,
                        "final": True,
                        "ts_iso": data.get("ts_iso"),
                        "backend": "openai"
                    }
                    
                    await r.publish(MT_OUTPUT, jdumps(mt_event))
                    print(f"[MT Router] ✓ Translated: {translated[:80]}...")
                    
                except Exception as e:
                    print(f"[MT Router] ✗ OpenAI error: {e}")
            
        except Exception as e:
            print(f"[MT Router] Error: {e}")
            import traceback
            traceback.print_exc()
            continue

if __name__ == "__main__":
    asyncio.run(router_loop())

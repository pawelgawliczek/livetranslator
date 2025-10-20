import os
import asyncio
import httpx
import redis.asyncio as redis
try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

from openai_backend import translate_text as openai_translate

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
STT_EVENTS = os.getenv("STT_EVENTS_CHANNEL", "stt_events")
MT_OUTPUT = os.getenv("MT_OUTPUT_CHANNEL", "mt_events")
MT_MODE_PARTIAL = os.getenv("LT_MT_MODE_PARTIAL", "local")  # local for partials
MT_MODE_FINAL = os.getenv("LT_MT_MODE_FINAL", "openai")     # openai for finals
DEFAULT_TGT = os.getenv("LT_DEFAULT_TGT", "en")
COST_TRACKING_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")
MT_WORKER_URL = os.getenv("LT_MT_BASE_URL", "http://mt_worker:8081")

print(f"[MT Router] Starting...")
print(f"  Partial Mode: {MT_MODE_PARTIAL}")
print(f"  Final Mode:   {MT_MODE_FINAL}")
print(f"  Input:        {STT_EVENTS}")
print(f"  Output:       {MT_OUTPUT}")
print(f"  Target:       {DEFAULT_TGT}")
print(f"  MT Worker:    {MT_WORKER_URL}")

def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token"""
    return max(1, len(text) // 4)

async def local_translate(client: httpx.AsyncClient, text: str, src: str, tgt: str, is_final: bool) -> str:
    """Call local mt_worker"""
    endpoint = "/translate/final" if is_final else "/translate/fast"
    url = f"{MT_WORKER_URL}{endpoint}"
    
    response = await client.post(url, json={"src": src, "tgt": tgt, "text": text})
    response.raise_for_status()
    result = response.json()
    return result.get("text", "")

async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(STT_EVENTS)
    
    print(f"[MT Router] Listening on {STT_EVENTS}")
    
    timeout = httpx.Timeout(30.0, read=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue
            
            try:
                data = jloads(msg["data"])
                msg_type = data.get("type", "")
                
                # Translate both partials and finals
                if msg_type not in ["stt_partial", "stt_final"]:
                    continue
                
                room = data.get("room_id", "unknown")
                segment = data.get("segment_id", 0)
                src_lang = data.get("lang", "auto")
                text = data.get("text", "").strip()
                is_final = data.get("final", False)
                
                if not text:
                    continue
                
                kind = "final" if is_final else "partial"
                mt_mode = MT_MODE_FINAL if is_final else MT_MODE_PARTIAL
                
                print(f"[MT Router] Translating {kind} ({mt_mode}): room={room} seg={segment} lang={src_lang}")
                
                try:
                    # Use appropriate backend
                    if mt_mode == "openai":
                        translated = await openai_translate(text, src_lang, DEFAULT_TGT)
                        backend_name = "openai"
                    else:
                        # Local mt_worker
                        # Map language codes
                        src_code = "pl" if "pl" in src_lang.lower() or src_lang == "auto" else "en"
                        tgt_code = "en" if DEFAULT_TGT == "en" else "pl"
                        translated = await local_translate(client, text, src_code, tgt_code, is_final)
                        backend_name = "local"
                    
                    mt_event = {
                        "type": f"translation_{kind}",
                        "room_id": room,
                        "segment_id": segment,
                        "src": src_lang,
                        "tgt": DEFAULT_TGT,
                        "text": translated,
                        "final": is_final,
                        "ts_iso": data.get("ts_iso"),
                        "backend": backend_name
                    }
                    
                    await r.publish(MT_OUTPUT, jdumps(mt_event))
                    print(f"[MT Router] ✓ Translated {kind} ({backend_name}): {translated[:80]}...")
                    
                    # Track cost only for OpenAI
                    if mt_mode == "openai":
                        input_tokens = estimate_tokens(text)
                        output_tokens = estimate_tokens(translated)
                        total_tokens = input_tokens + output_tokens
                        
                        cost_event = {
                            "type": "cost_event",
                            "room_id": room,
                            "pipeline": "mt",
                            "mode": f"openai_{kind}",
                            "units": total_tokens,
                            "unit_type": "tokens"
                        }
                        await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                        print(f"[MT Router] 💰 Cost tracked: {total_tokens} tokens ({kind})")
                    
                except Exception as e:
                    print(f"[MT Router] ✗ Translation error ({kind}): {e}")
                
            except Exception as e:
                print(f"[MT Router] Error: {e}")

if __name__ == "__main__":
    asyncio.run(router_loop())

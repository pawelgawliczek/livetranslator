import os
import asyncio
import asyncpg
import redis.asyncio as redis
from datetime import datetime

try:
    import orjson
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
POSTGRES_DSN = os.getenv("POSTGRES_DSN")
STT_EVENTS = "stt_events"
MT_EVENTS = "mt_events"

print("[Persistence] Starting...")

room_cache = {}

async def persist_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(STT_EVENTS, MT_EVENTS)
    
    db_pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=2, max_size=10)
    
    print(f"[Persistence] Listening on {STT_EVENTS}, {MT_EVENTS}")
    
    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        
        try:
            data = jloads(msg["data"])
            msg_type = data.get("type")
            room_code = data.get("room_id")
            
            if not room_code:
                continue
            
            async with db_pool.acquire() as conn:
                # Get or create room
                if room_code not in room_cache:
                    room_row = await conn.fetchrow(
                        "SELECT id FROM rooms WHERE code = $1", room_code
                    )
                    if not room_row:
                        room_id = await conn.fetchval(
                            """
                            INSERT INTO rooms (code, owner_id, created_at, recording)
                            VALUES ($1, 1, NOW(), true)
                            RETURNING id
                            """,
                            room_code
                        )
                        room_cache[room_code] = room_id
                        print(f"[Persistence] Created room: {room_code} -> {room_id}")
                    else:
                        room_cache[room_code] = room_row["id"]
                
                room_id = room_cache[room_code]
                
                # Persist STT final
                if msg_type == "stt_final":
                    segment_id = int(data.get("segment_id", 0))
                    text = data.get("text", "").strip()
                    lang = data.get("lang", "auto")
                    speaker = data.get("speaker", "system")
                    
                    if text:
                        await conn.execute(
                            """
                            INSERT INTO segments (room_id, speaker_id, segment_id, revision, ts_iso, text, lang, final)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            """,
                            room_id, speaker, str(segment_id), 1, 
                            datetime.utcnow().isoformat(), text, lang, True
                        )
                        print(f"[Persistence] ✓ STT saved: room={room_code} seg={segment_id} speaker={speaker}")
                
                # Persist translation final - allow multiple per segment (one per target lang)
                elif msg_type == "translation_final":
                    segment_id = int(data.get("segment_id", 0))
                    src_lang = data.get("src", "auto")
                    tgt_lang = data.get("tgt", "en")
                    text = data.get("text", "").strip()
                    
                    if text:
                        # Check if this specific translation (segment + target_lang) exists
                        exists = await conn.fetchval(
                            """
                            SELECT id FROM translations 
                            WHERE room_id = $1 AND segment_id = $2 AND tgt_lang = $3
                            """,
                            room_code, segment_id, tgt_lang
                        )
                        
                        if not exists:
                            await conn.execute(
                                """
                                INSERT INTO translations (room_id, segment_id, src_lang, tgt_lang, text, is_final, ts_iso, created_at)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                                """,
                                room_code, segment_id, src_lang, tgt_lang, text, True,
                                datetime.utcnow()
                            )
                            print(f"[Persistence] ✓ Translation saved: room={room_code} seg={segment_id} {src_lang}→{tgt_lang}")
                        else:
                            # Update existing translation
                            await conn.execute(
                                """
                                UPDATE translations 
                                SET text = $1, ts_iso = $2
                                WHERE room_id = $3 AND segment_id = $4 AND tgt_lang = $5
                                """,
                                text, datetime.utcnow(), room_code, segment_id, tgt_lang
                            )
                            print(f"[Persistence] ↻ Translation updated: room={room_code} seg={segment_id} {src_lang}→{tgt_lang}")
                
        except Exception as e:
            print(f"[Persistence] Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(persist_loop())

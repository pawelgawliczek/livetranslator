import os
import asyncio
import asyncpg
import redis.asyncio as redis
from decimal import Decimal

try:
    import orjson
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:password@postgres:5432/livetranslator")
COST_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")

# Pricing
WHISPER_PER_MIN = Decimal(os.getenv("OPENAI_PRICE_WHISPER_PER_MIN", "0.006"))
GPT4O_MINI_INPUT = Decimal(os.getenv("OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K", "0.00015"))
GPT4O_MINI_OUTPUT = Decimal(os.getenv("OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K", "0.0006"))

print(f"[Cost Tracker] Starting...")
print(f"  Listening: {COST_CHANNEL}")
print(f"  Whisper: ${WHISPER_PER_MIN}/min")
print(f"  GPT-4o-mini: ${GPT4O_MINI_INPUT}/${GPT4O_MINI_OUTPUT} per 1K tokens")

def calculate_cost(pipeline: str, units: float, unit_type: str) -> Decimal:
    """Calculate cost based on pipeline and units"""
    if pipeline == "stt" and unit_type == "seconds":
        minutes = Decimal(units) / Decimal(60)
        return minutes * WHISPER_PER_MIN
    elif pipeline == "mt" and unit_type == "tokens":
        # Assume 50/50 split input/output for simplicity
        tokens_per_1k = Decimal(units) / Decimal(1000)
        return tokens_per_1k * ((GPT4O_MINI_INPUT + GPT4O_MINI_OUTPUT) / 2)
    return Decimal(0)

async def track_loop():
    # Connect to Redis
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(COST_CHANNEL)
    
    # Connect to Postgres
    db_pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=5)
    
    print(f"[Cost Tracker] Listening on {COST_CHANNEL}")
    
    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue
        
        try:
            data = jloads(msg["data"])
            
            # Removed type filter - all messages on cost_events channel are cost events
            
            room_id = data.get("room_id")
            pipeline = data.get("pipeline")
            mode = data.get("mode")
            units = data.get("units", 0)
            unit_type = data.get("unit_type")
            
            if not room_id or not pipeline:
                continue
            
            # Calculate cost
            cost = calculate_cost(pipeline, float(units), unit_type)
            
            # Store in database
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO room_costs (room_id, pipeline, mode, units, unit_type, amount_usd, ts)
                    VALUES ($1, $2, $3, $4, $5, $6, NOW())
                    """,
                    room_id, pipeline, mode, units, unit_type, float(cost)
                )
            
            print(f"[Cost Tracker] ✓ Recorded: room={room_id} pipeline={pipeline} cost=${cost:.6f}")
            
        except Exception as e:
            print(f"[Cost Tracker] Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(track_loop())

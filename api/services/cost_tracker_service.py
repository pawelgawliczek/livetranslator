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

print(f"[Cost Tracker] Starting multi-provider cost tracking...")
print(f"  Listening: {COST_CHANNEL}")
print(f"  Provider pricing loaded from database (provider_pricing table)")

async def load_pricing(db_pool) -> dict:
    """Load all provider pricing from database"""
    pricing = {}
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT service, provider, pricing_model, unit_price
            FROM provider_pricing
            WHERE effective_date <= NOW()
            ORDER BY service, provider, effective_date DESC
        """)

        for row in rows:
            key = (row['service'], row['provider'])
            if key not in pricing:  # Use most recent pricing
                pricing[key] = {
                    'model': row['pricing_model'],
                    'price': Decimal(str(row['unit_price']))
                }

    print(f"[Cost Tracker] Loaded pricing for {len(pricing)} provider combinations:")
    for (service, provider), info in sorted(pricing.items()):
        print(f"  - {service}/{provider}: ${info['price']} ({info['model']})")

    return pricing

def calculate_cost(service: str, provider: str, units: float, unit_type: str, pricing: dict) -> Decimal:
    """Calculate cost based on service, provider, and units"""
    key = (service, provider)

    # Get pricing info
    if key not in pricing:
        print(f"[Cost Tracker] ⚠️  No pricing for {service}/{provider}, using $0")
        return Decimal(0)

    price_info = pricing[key]
    model = price_info['model']
    unit_price = price_info['price']

    # Convert units to pricing model units
    if model == 'per_hour':
        # Convert seconds to hours
        if unit_type == 'seconds':
            hours = Decimal(units) / Decimal(3600)
            return hours * unit_price
        elif unit_type == 'minutes':
            hours = Decimal(units) / Decimal(60)
            return hours * unit_price

    elif model == 'per_minute':
        # Convert seconds to minutes
        if unit_type == 'seconds':
            minutes = Decimal(units) / Decimal(60)
            return minutes * unit_price
        elif unit_type == 'minutes':
            return Decimal(units) * unit_price

    elif model == 'per_1k_tokens':
        if unit_type == 'tokens':
            tokens_per_1k = Decimal(units) / Decimal(1000)
            return tokens_per_1k * unit_price

    elif model == 'per_1m_chars':
        if unit_type == 'characters':
            chars_per_1m = Decimal(units) / Decimal(1_000_000)
            return chars_per_1m * unit_price

    print(f"[Cost Tracker] ⚠️  Unknown conversion: {unit_type} to {model}")
    return Decimal(0)

async def track_loop():
    # Connect to Redis
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(COST_CHANNEL)

    # Connect to Postgres
    db_pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=5)

    # Load provider pricing
    pricing = await load_pricing(db_pool)

    print(f"[Cost Tracker] ✓ Ready - Listening on {COST_CHANNEL}")

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue

        try:
            data = jloads(msg["data"])

            # Extract fields (support multiple event formats)
            room_id = data.get("room_id")
            pipeline = data.get("pipeline") or data.get("service")  # 'stt' or 'mt'
            provider = data.get("provider") or data.get("mode")  # Provider name
            mode = data.get("mode") or provider  # For backward compatibility
            units = data.get("units", 0)
            unit_type = data.get("unit_type", "seconds")
            segment_id = data.get("segment_id")  # NEW: Extract segment_id for per-message tracking

            # Validate required fields
            if not room_id:
                print(f"[Cost Tracker] ⚠️  Missing room_id in event: {data}")
                continue

            if not pipeline or not provider:
                print(f"[Cost Tracker] ⚠️  Missing pipeline/provider in event: {data}")
                continue

            # Calculate cost
            cost = calculate_cost(pipeline, provider, float(units), unit_type, pricing)

            # Store in database with segment_id
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, segment_id, ts)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                    """,
                    room_id, pipeline, mode, provider, units, unit_type, float(cost), segment_id
                )

            # Log success with segment_id
            seg_info = f" seg={segment_id}" if segment_id else ""
            print(f"[Cost Tracker] ✓ {room_id}: {pipeline}/{provider} {units}{unit_type} = ${cost:.6f}{seg_info}")

        except Exception as e:
            print(f"[Cost Tracker] ✗ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(track_loop())

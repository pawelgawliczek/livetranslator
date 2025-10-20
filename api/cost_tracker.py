"""
Cost tracking for OpenAI usage
Pricing can be overridden via environment variables
"""
import os
from decimal import Decimal
from typing import Dict, Any
import asyncpg

# Default OpenAI Pricing (can override via env vars)
# Format: OPENAI_PRICE_WHISPER_PER_MIN, OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K, etc.
def get_pricing():
    return {
        "whisper-1": {
            "per_minute": Decimal(os.getenv("OPENAI_PRICE_WHISPER_PER_MIN", "0.006"))
        },
        "gpt-4o-mini": {
            "input_per_1k": Decimal(os.getenv("OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K", "0.00015")),
            "output_per_1k": Decimal(os.getenv("OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K", "0.0006"))
        }
    }

def calculate_stt_cost(audio_duration_sec: float, model: str = "whisper-1") -> Decimal:
    """Calculate cost for STT transcription"""
    pricing = get_pricing()
    minutes = Decimal(audio_duration_sec) / Decimal(60)
    return minutes * pricing[model]["per_minute"]

def calculate_mt_cost(input_tokens: int, output_tokens: int, model: str = "gpt-4o-mini") -> Decimal:
    """Calculate cost for translation"""
    pricing = get_pricing()
    input_cost = (Decimal(input_tokens) / Decimal(1000)) * pricing[model]["input_per_1k"]
    output_cost = (Decimal(output_tokens) / Decimal(1000)) * pricing[model]["output_per_1k"]
    return input_cost + output_cost

# Estimate tokens (rough approximation: 1 token ≈ 4 chars)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

async def track_cost(
    db_pool: asyncpg.Pool,
    room_id: str,
    pipeline: str,
    mode: str,
    units: int,
    unit_type: str,
    amount_usd: Decimal
):
    """Record a cost entry"""
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO room_costs (room_id, pipeline, mode, units, unit_type, amount_usd, ts)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """,
            room_id, pipeline, mode, units, unit_type, float(amount_usd)
        )

async def get_room_costs(db_pool: asyncpg.Pool, room_id: str) -> Dict[str, Any]:
    """Get aggregated costs for a room"""
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """
            SELECT 
                SUM(amount_usd) FILTER (WHERE pipeline = 'stt_final') as stt_cost,
                SUM(amount_usd) FILTER (WHERE pipeline = 'mt') as mt_cost,
                SUM(amount_usd) as total_cost,
                COUNT(*) FILTER (WHERE pipeline = 'stt_final') as stt_count,
                COUNT(*) FILTER (WHERE pipeline = 'mt') as mt_count
            FROM room_costs
            WHERE room_id = $1
            """,
            room_id
        )
        
        return {
            "stt_cost_usd": float(result["stt_cost"] or 0),
            "mt_cost_usd": float(result["mt_cost"] or 0),
            "total_cost_usd": float(result["total_cost"] or 0),
            "stt_count": result["stt_count"] or 0,
            "mt_count": result["mt_count"] or 0
        }

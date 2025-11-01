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

def calculate_multi_speaker_translation_count(num_speakers: int) -> int:
    """
    Calculate the number of translations required for N speakers.
    Formula: N × (N-1) translations per message

    Examples:
    - 2 speakers: 2 translations
    - 3 speakers: 6 translations
    - 4 speakers: 12 translations
    - 5 speakers: 20 translations

    Args:
        num_speakers: Number of speakers in the room

    Returns:
        int: Total translations required per message
    """
    if num_speakers < 2:
        return 0
    return num_speakers * (num_speakers - 1)

async def get_multi_speaker_cost_breakdown(db_pool: asyncpg.Pool, room_id: str) -> Dict[str, Any]:
    """
    Get detailed cost breakdown for multi-speaker rooms.

    Returns:
        dict: Cost breakdown by speaker and translation pair
    """
    async with db_pool.acquire() as conn:
        # Get per-speaker costs (speaker as source)
        speaker_costs = await conn.fetch(
            """
            SELECT
                speaker_id,
                SUM(amount_usd) as total_cost,
                COUNT(*) as translation_count
            FROM room_costs
            WHERE room_id = $1 AND speaker_id IS NOT NULL AND pipeline = 'mt'
            GROUP BY speaker_id
            ORDER BY speaker_id
            """,
            room_id
        )

        # Get per-translation-pair costs
        pair_costs = await conn.fetch(
            """
            SELECT
                speaker_id,
                target_speaker_id,
                SUM(amount_usd) as pair_cost,
                COUNT(*) as translation_count
            FROM room_costs
            WHERE room_id = $1 AND speaker_id IS NOT NULL AND target_speaker_id IS NOT NULL AND pipeline = 'mt'
            GROUP BY speaker_id, target_speaker_id
            ORDER BY pair_cost DESC
            """,
            room_id
        )

        # Get total multi-speaker MT cost
        total_mt_cost = await conn.fetchval(
            """
            SELECT COALESCE(SUM(amount_usd), 0)
            FROM room_costs
            WHERE room_id = $1 AND speaker_id IS NOT NULL AND pipeline = 'mt'
            """,
            room_id
        )

        return {
            "speaker_costs": [dict(row) for row in speaker_costs],
            "translation_pair_costs": [dict(row) for row in pair_costs],
            "total_multi_speaker_mt_cost": float(total_mt_cost),
            "total_translation_pairs": len(pair_costs)
        }

async def estimate_multi_speaker_hourly_cost(
    db_pool: asyncpg.Pool,
    room_id: str,
    session_duration_seconds: float
) -> Dict[str, Any]:
    """
    Estimate hourly cost for a multi-speaker room based on current session.

    Args:
        db_pool: Database connection pool
        room_id: Room code
        session_duration_seconds: Duration of current session in seconds

    Returns:
        dict: Estimated costs per hour
    """
    if session_duration_seconds <= 0:
        return {
            "estimated_stt_cost_per_hour": 0,
            "estimated_mt_cost_per_hour": 0,
            "estimated_total_cost_per_hour": 0
        }

    costs = await get_room_costs(db_pool, room_id)

    # Calculate hourly rate
    hours = session_duration_seconds / 3600.0
    stt_per_hour = costs["stt_cost_usd"] / hours if hours > 0 else 0
    mt_per_hour = costs["mt_cost_usd"] / hours if hours > 0 else 0
    total_per_hour = costs["total_cost_usd"] / hours if hours > 0 else 0

    return {
        "estimated_stt_cost_per_hour": round(stt_per_hour, 6),
        "estimated_mt_cost_per_hour": round(mt_per_hour, 6),
        "estimated_total_cost_per_hour": round(total_per_hour, 6),
        "session_duration_seconds": session_duration_seconds,
        "session_duration_hours": round(hours, 2)
    }

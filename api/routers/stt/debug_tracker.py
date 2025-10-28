"""
Debug Tracker Service

Tracks per-message debug information in Redis for admin diagnostics.
Stores STT/MT processing details, routing decisions, costs, and latencies.

Redis key format: debug:segment:{segment_id}
TTL: 24 hours (86400 seconds)
"""

import json
from typing import Optional
from datetime import datetime
from redis.asyncio import Redis


# TTL for debug data in Redis (24 hours)
DEBUG_TTL_SECONDS = 86400


# STT Provider Pricing (per second unless noted)
STT_PRICING = {
    "speechmatics": {"per_second": 0.00012},     # $0.50/hour = $0.00012/sec
    "google_v2": {"per_second": 0.0001},         # $0.006/minute = $0.0001/sec
    "azure": {"per_second": 0.001},              # $1/1000 seconds
    "soniox": {"per_second": 0.00003},           # Budget option
    "openai": {"per_minute": 0.006},             # $0.006/minute
    "local": {"per_second": 0.0},                # Free (local Whisper)
}


# MT Provider Pricing
MT_PRICING = {
    # Character-based providers (per 1M characters)
    "deepl": {"per_1m_chars": 20.00},
    "azure_translator": {"per_1m_chars": 10.00},
    "google_translate": {"per_1m_chars": 20.00},

    # Token-based providers (per 1k tokens)
    "gpt-4o-mini": {
        "input_per_1k": 0.00015,   # $0.15/1M tokens
        "output_per_1k": 0.0006    # $0.60/1M tokens
    },
    "gpt-4o": {
        "input_per_1k": 0.005,     # $5/1M tokens
        "output_per_1k": 0.015     # $15/1M tokens
    },
}


def calculate_stt_cost(provider: str, duration_sec: float) -> float:
    """
    Calculate STT cost based on provider rates.

    Args:
        provider: STT provider name (e.g., "speechmatics", "google_v2")
        duration_sec: Audio duration in seconds

    Returns:
        Cost in USD
    """
    if provider not in STT_PRICING:
        print(f"[Debug Tracker] ⚠️  Unknown STT provider: {provider}, assuming $0")
        return 0.0

    pricing = STT_PRICING[provider]

    if "per_second" in pricing:
        return duration_sec * pricing["per_second"]
    elif "per_minute" in pricing:
        return (duration_sec / 60.0) * pricing["per_minute"]
    else:
        return 0.0


def calculate_mt_cost(
    provider: str,
    units: int,
    unit_type: str,
    input_tokens: int = 0,
    output_tokens: int = 0
) -> dict:
    """
    Calculate MT cost based on provider rates.

    Args:
        provider: MT provider name (e.g., "deepl", "gpt-4o-mini")
        units: Number of units (characters or total tokens)
        unit_type: "characters" or "tokens"
        input_tokens: Input token count (for token-based providers)
        output_tokens: Output token count (for token-based providers)

    Returns:
        Dictionary with cost_usd and cost_breakdown
    """
    if provider not in MT_PRICING:
        print(f"[Debug Tracker] ⚠️  Unknown MT provider: {provider}, assuming $0")
        return {
            "cost_usd": 0.0,
            "cost_breakdown": {
                "unit_type": unit_type,
                "units": units,
                "rate": 0.0
            }
        }

    pricing = MT_PRICING[provider]

    # Character-based providers (DeepL, Azure Translator, Google Translate)
    if "per_1m_chars" in pricing:
        cost = (units / 1_000_000) * pricing["per_1m_chars"]
        return {
            "cost_usd": cost,
            "cost_breakdown": {
                "unit_type": "characters",
                "units": units,
                "rate_per_1000_chars": pricing["per_1m_chars"] / 1000
            }
        }

    # Token-based providers (GPT-4o, GPT-4o-mini)
    elif "input_per_1k" in pricing:
        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
        total_cost = input_cost + output_cost

        return {
            "cost_usd": total_cost,
            "cost_breakdown": {
                "unit_type": "tokens",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "rate_input_per_1k": pricing["input_per_1k"],
                "rate_output_per_1k": pricing["output_per_1k"]
            }
        }

    else:
        return {
            "cost_usd": 0.0,
            "cost_breakdown": {
                "unit_type": unit_type,
                "units": units,
                "rate": 0.0
            }
        }


async def create_stt_debug_info(
    redis: Redis,
    segment_id: int,
    room_code: str,
    stt_data: dict,
    routing_info: dict
) -> None:
    """
    Create initial debug info with STT data.

    Args:
        redis: Redis client
        segment_id: Unique segment identifier
        room_code: Room code
        stt_data: Dictionary containing:
            - provider: STT provider name
            - language: Language code (e.g., "pl-PL")
            - mode: "partial" or "final"
            - latency_ms: Processing latency in milliseconds
            - audio_duration_sec: Audio duration in seconds
            - text: Transcribed text
        routing_info: Dictionary containing:
            - routing_reason: Human-readable routing decision
            - fallback_triggered: Boolean indicating if fallback was used
    """
    try:
        # Calculate STT cost
        stt_cost = calculate_stt_cost(
            stt_data["provider"],
            stt_data["audio_duration_sec"]
        )

        # Build debug info structure
        debug_info = {
            "segment_id": segment_id,
            "room_code": room_code,
            "timestamp": datetime.utcnow().isoformat() + "Z",

            "stt": {
                "provider": stt_data["provider"],
                "language": stt_data["language"],
                "mode": stt_data["mode"],
                "latency_ms": stt_data["latency_ms"],
                "audio_duration_sec": stt_data["audio_duration_sec"],
                "cost_usd": stt_cost,
                "cost_breakdown": {
                    "unit_type": "seconds",
                    "units": stt_data["audio_duration_sec"],
                    "rate_per_unit": stt_cost / stt_data["audio_duration_sec"] if stt_data["audio_duration_sec"] > 0 else 0
                },
                "routing_reason": routing_info["routing_reason"],
                "fallback_triggered": routing_info["fallback_triggered"],
                "text": stt_data["text"]
            },

            "mt": [],  # Will be populated by append_mt_debug_info()
            "mt_skip_reasons": [],  # Will be populated by append_mt_skip_reason()

            "totals": {
                "stt_cost_usd": stt_cost,
                "mt_cost_usd": 0.0,
                "total_cost_usd": stt_cost,
                "mt_translations": 0
            }
        }

        # Store in Redis with 24h TTL
        key = f"debug:segment:{segment_id}"
        await redis.set(key, json.dumps(debug_info), ex=DEBUG_TTL_SECONDS)

        print(f"[Debug Tracker] ✓ Created debug info: segment={segment_id}, room={room_code}, provider={stt_data['provider']}")

    except Exception as e:
        print(f"[Debug Tracker] ⚠️  Failed to create STT debug info for segment {segment_id}: {e}")
        # Don't raise - debug tracking is optional


async def append_mt_debug_info(
    redis: Redis,
    segment_id: int,
    mt_data: dict,
    routing_info: dict
) -> None:
    """
    Append MT translation data to existing debug info.

    Args:
        redis: Redis client
        segment_id: Unique segment identifier
        mt_data: Dictionary containing:
            - src_lang: Source language code
            - tgt_lang: Target language code
            - provider: MT provider name
            - latency_ms: Processing latency in milliseconds
            - text: Translated text
            - char_count: Character count (for character-based providers)
            - input_tokens: Input token count (for token-based providers)
            - output_tokens: Output token count (for token-based providers)
        routing_info: Dictionary containing:
            - routing_reason: Human-readable routing decision
            - fallback_triggered: Boolean indicating if fallback was used
            - throttled: Boolean indicating if request was throttled
            - throttle_delay_ms: Throttle delay in milliseconds (if throttled)
            - throttle_reason: Human-readable throttle reason (if throttled)
    """
    try:
        # Retrieve existing debug info
        key = f"debug:segment:{segment_id}"
        data = await redis.get(key)

        if not data:
            print(f"[Debug Tracker] ⚠️  No existing debug info for segment {segment_id}, cannot append MT data")
            return

        debug_info = json.loads(data)

        # Calculate MT cost
        unit_type = "characters" if mt_data.get("char_count") is not None else "tokens"
        units = mt_data.get("char_count", 0) if unit_type == "characters" else mt_data.get("input_tokens", 0) + mt_data.get("output_tokens", 0)

        cost_info = calculate_mt_cost(
            mt_data["provider"],
            units,
            unit_type,
            input_tokens=mt_data.get("input_tokens", 0),
            output_tokens=mt_data.get("output_tokens", 0)
        )

        # Build MT entry
        mt_entry = {
            "src_lang": mt_data["src_lang"],
            "tgt_lang": mt_data["tgt_lang"],
            "provider": mt_data["provider"],
            "latency_ms": mt_data["latency_ms"],
            "cost_usd": cost_info["cost_usd"],
            "cost_breakdown": cost_info["cost_breakdown"],
            "routing_reason": routing_info["routing_reason"],
            "fallback_triggered": routing_info["fallback_triggered"],
            "throttled": routing_info.get("throttled", False),
            "text": mt_data["text"]
        }

        # Add throttle details if applicable
        if mt_entry["throttled"]:
            mt_entry["throttle_delay_ms"] = routing_info.get("throttle_delay_ms", 0)
            mt_entry["throttle_reason"] = routing_info.get("throttle_reason", "Unknown")

        # Append to MT array
        debug_info["mt"].append(mt_entry)

        # Update totals
        debug_info["totals"]["mt_cost_usd"] += cost_info["cost_usd"]
        debug_info["totals"]["total_cost_usd"] = debug_info["totals"]["stt_cost_usd"] + debug_info["totals"]["mt_cost_usd"]
        debug_info["totals"]["mt_translations"] = len(debug_info["mt"])

        # Update Redis with extended TTL
        await redis.set(key, json.dumps(debug_info), ex=DEBUG_TTL_SECONDS)

        print(f"[Debug Tracker] ✓ Appended MT debug info: segment={segment_id}, {mt_data['src_lang']}→{mt_data['tgt_lang']}, provider={mt_data['provider']}")

    except Exception as e:
        print(f"[Debug Tracker] ⚠️  Failed to append MT debug info for segment {segment_id}: {e}")
        # Don't raise - debug tracking is optional


async def append_mt_skip_reason(
    redis: Redis,
    segment_id: int,
    src_lang: str,
    tgt_lang: str,
    reason: str
) -> None:
    """
    Record why an MT translation was skipped.

    Args:
        redis: Redis client
        segment_id: Unique segment identifier
        src_lang: Source language code
        tgt_lang: Target language code
        reason: Human-readable reason for skipping
    """
    try:
        # Retrieve existing debug info
        key = f"debug:segment:{segment_id}"
        data = await redis.get(key)

        if not data:
            print(f"[Debug Tracker] ⚠️  No existing debug info for segment {segment_id}, cannot append skip reason")
            return

        debug_info = json.loads(data)

        # Add skip reason
        skip_entry = {
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "reason": reason
        }

        debug_info["mt_skip_reasons"].append(skip_entry)

        # Update Redis with extended TTL
        await redis.set(key, json.dumps(debug_info), ex=DEBUG_TTL_SECONDS)

        print(f"[Debug Tracker] ✓ Recorded MT skip: segment={segment_id}, {src_lang}→{tgt_lang}, reason={reason}")

    except Exception as e:
        print(f"[Debug Tracker] ⚠️  Failed to append MT skip reason for segment {segment_id}: {e}")
        # Don't raise - debug tracking is optional


async def get_debug_info(redis: Redis, segment_id: int) -> Optional[dict]:
    """
    Retrieve debug info from Redis.

    Args:
        redis: Redis client
        segment_id: Unique segment identifier

    Returns:
        Debug info dictionary or None if not found
    """
    try:
        key = f"debug:segment:{segment_id}"
        data = await redis.get(key)

        if not data:
            print(f"[Debug Tracker] ℹ️  No debug info found for segment {segment_id} (may have expired)")
            return None

        debug_info = json.loads(data)
        print(f"[Debug Tracker] ✓ Retrieved debug info: segment={segment_id}")
        return debug_info

    except Exception as e:
        print(f"[Debug Tracker] ⚠️  Failed to retrieve debug info for segment {segment_id}: {e}")
        return None

"""
Tier-based routing helpers for STT/MT/TTS provider selection.

This module provides tier checking and quota management for all services.
Used by STT/MT/TTS routers to enforce tier-based access control.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class QuotaExhaustedError(Exception):
    """Raised when both participant and admin quota are exhausted."""
    pass


async def get_user_tier(user_email: str, db_pool) -> Optional[Dict[str, Any]]:
    """
    Get user's current subscription tier.

    Args:
        user_email: User's email address
        db_pool: asyncpg database pool

    Returns:
        dict: {
            'tier_name': 'free' | 'plus' | 'pro',
            'provider_tier': 'free' | 'standard' | 'premium',
            'monthly_quota_hours': Decimal,
            'quota_available_seconds': int
        }
        None if user not found or no active subscription
    """
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    st.tier_name,
                    st.provider_tier,
                    st.monthly_quota_hours,
                    us.user_id
                FROM user_subscriptions us
                JOIN subscription_tiers st ON us.tier_id = st.id
                JOIN users u ON us.user_id = u.id
                WHERE u.email = $1 AND us.status = 'active'
            """, user_email)

            if not row:
                logger.warning(f"No active subscription found for {user_email}")
                return None

            # Get available quota using database function
            quota_result = await conn.fetchval(
                "SELECT get_user_quota_available($1)",
                row['user_id']
            )

            return {
                'tier_name': row['tier_name'],
                'provider_tier': row['provider_tier'],
                'monthly_quota_hours': row['monthly_quota_hours'],
                'quota_available_seconds': quota_result or 0,
                'user_id': row['user_id']
            }
    except Exception as e:
        logger.error(f"Error getting user tier for {user_email}: {e}")
        return None


async def get_room_owner_tier(room_code: str, db_pool) -> Optional[Dict[str, Any]]:
    """
    Get room owner's subscription tier.

    Args:
        room_code: Room code
        db_pool: asyncpg database pool

    Returns:
        dict: Tier information (same as get_user_tier)
        None if room not found or owner has no subscription
    """
    try:
        async with db_pool.acquire() as conn:
            # Get room owner's email
            owner_row = await conn.fetchrow("""
                SELECT u.email
                FROM rooms r
                JOIN users u ON r.owner_id = u.id
                WHERE r.code = $1
            """, room_code)

            if not owner_row:
                logger.warning(f"Room {room_code} not found")
                return None

            # Get owner's tier
            return await get_user_tier(owner_row['email'], db_pool)
    except Exception as e:
        logger.error(f"Error getting room owner tier for {room_code}: {e}")
        return None


def get_allowed_stt_providers(tier_name: str, platform: str = 'web') -> list:
    """
    Get allowed STT providers based on tier and platform.

    Args:
        tier_name: 'free', 'plus', 'pro'
        platform: 'web' or 'ios'

    Returns:
        list: Allowed provider names
    """
    if tier_name == 'free':
        if platform == 'ios':
            # iOS free tier: Client-side Apple Speech Framework only
            return []  # Empty = use transcript_direct messages
        else:
            # Web free tier: Speechmatics basic tier only
            return ['speechmatics']  # Basic config only

    elif tier_name == 'plus':
        # Plus tier: All premium STT providers
        return ['speechmatics', 'google_v2', 'azure', 'soniox']

    elif tier_name == 'pro':
        # Pro tier: All providers + priority routing
        return ['speechmatics', 'google_v2', 'azure', 'soniox', 'deepgram']

    # Default fallback
    return ['speechmatics']


def get_allowed_mt_providers(tier_name: str, platform: str = 'web') -> list:
    """
    Get allowed MT providers based on tier and platform.

    Args:
        tier_name: 'free', 'plus', 'pro'
        platform: 'web' or 'ios'

    Returns:
        list: Allowed provider names
    """
    if tier_name == 'free':
        if platform == 'ios':
            # iOS free tier: Client-side Apple Translation API
            return []  # Client-side only
        else:
            # Web free tier: LibreTranslate (self-hosted, free)
            # TODO: Implement LibreTranslate backend
            return ['libretranslate']  # Free, self-hosted

    elif tier_name == 'plus':
        # Plus tier: Premium MT providers
        return ['deepl', 'google_translate', 'amazon_translate', 'openai_gpt4o_mini']

    elif tier_name == 'pro':
        # Pro tier: All providers including GPT-4
        return ['deepl', 'google_translate', 'amazon_translate', 'openai_gpt4o_mini', 'openai_gpt4o', 'claude']

    # Default fallback
    return ['google_translate']


def supports_server_tts(tier_name: str) -> bool:
    """
    Check if tier supports server-side TTS.

    Args:
        tier_name: 'free', 'plus', 'pro'

    Returns:
        bool: True if server TTS is available
    """
    # Only Pro tier gets server-side TTS
    return tier_name == 'pro'


async def deduct_quota_waterfall(
    user_email: str,
    room_code: str,
    seconds: float,
    service_type: str,  # 'stt', 'mt', 'tts'
    provider: str,
    db_pool
) -> Dict[str, Any]:
    """
    Deduct quota with waterfall logic: participant → admin → free providers.

    Waterfall order:
    1. Try participant's quota
    2. If exhausted, use admin's quota
    3. If both exhausted, raise QuotaExhaustedError

    Args:
        user_email: User speaking/requesting translation
        room_code: Room code
        seconds: Seconds to deduct
        service_type: 'stt', 'mt', 'tts'
        provider: Provider name used
        db_pool: asyncpg database pool

    Returns:
        dict: {
            'source': 'participant' | 'admin',
            'remaining': int (seconds remaining),
            'transaction_id': int
        }

    Raises:
        QuotaExhaustedError: When both participant and admin quota are exhausted
    """
    try:
        async with db_pool.acquire() as conn:
            # 1. Get user and room info
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE email = $1",
                user_email
            )

            if not user_row:
                logger.error(f"User {user_email} not found")
                raise QuotaExhaustedError("User not found")

            user_id = user_row['id']

            room_row = await conn.fetchrow("""
                SELECT r.id as room_id, u.id as owner_id, u.email as owner_email
                FROM rooms r
                JOIN users u ON r.owner_id = u.id
                WHERE r.code = $1
            """, room_code)

            if not room_row:
                logger.error(f"Room {room_code} not found")
                raise QuotaExhaustedError("Room not found")

            room_id = room_row['room_id']
            admin_id = room_row['owner_id']
            admin_email = room_row['owner_email']

            # 2. Check participant quota
            participant_quota = await conn.fetchval(
                "SELECT get_user_quota_available($1)",
                user_id
            )

            if participant_quota and participant_quota >= seconds:
                # Use participant's quota
                result = await conn.fetchrow("""
                    INSERT INTO quota_transactions
                    (user_id, room_id, room_code, transaction_type, amount_seconds,
                     quota_type, provider_used, service_type, description)
                    VALUES ($1, $2, $3, 'deduct', $4, 'own', $5, $6, $7)
                    RETURNING id
                """, user_id, room_id, room_code, -int(seconds), provider, service_type,
                    f"{service_type.upper()} usage via {provider} (own quota)")

                remaining = participant_quota - seconds
                logger.info(
                    f"Quota deducted from participant: user={user_email}, "
                    f"amount={seconds:.1f}s, remaining={remaining:.1f}s"
                )

                return {
                    'source': 'participant',
                    'remaining': remaining,
                    'transaction_id': result['id']
                }

            # 3. Participant exhausted - try admin quota
            admin_quota = await conn.fetchval(
                "SELECT get_user_quota_available($1)",
                admin_id
            )

            if admin_quota and admin_quota >= seconds:
                # Use admin's quota
                result = await conn.fetchrow("""
                    INSERT INTO quota_transactions
                    (user_id, room_id, room_code, transaction_type, amount_seconds,
                     quota_type, provider_used, service_type, description)
                    VALUES ($1, $2, $3, 'deduct', $4, 'admin_fallback', $5, $6, $7)
                    RETURNING id
                """, admin_id, room_id, room_code, -int(seconds), provider, service_type,
                    f"{service_type.upper()} usage via {provider} (admin fallback for {user_email})")

                remaining = admin_quota - seconds
                logger.warning(
                    f"Quota deducted from admin: participant={user_email}, "
                    f"admin={admin_email}, amount={seconds:.1f}s, remaining={remaining:.1f}s"
                )

                # TODO: Send WebSocket notification to admin
                # await notify_admin_quota_used(room_code, user_email, seconds)

                return {
                    'source': 'admin',
                    'remaining': remaining,
                    'transaction_id': result['id']
                }

            # 4. Both exhausted - raise error
            logger.error(
                f"Quota exhausted: participant={user_email} ({participant_quota:.1f}s), "
                f"admin={admin_email} ({admin_quota:.1f}s), needed={seconds:.1f}s"
            )
            raise QuotaExhaustedError(
                f"Both participant and admin quota exhausted "
                f"(participant: {participant_quota:.1f}s, admin: {admin_quota:.1f}s)"
            )

    except QuotaExhaustedError:
        raise
    except Exception as e:
        logger.error(f"Error in quota waterfall deduction: {e}")
        raise QuotaExhaustedError(f"Quota deduction failed: {str(e)}")


async def get_tier_routing_info(room_code: str, user_email: Optional[str], db_pool) -> Dict[str, Any]:
    """
    Get comprehensive tier routing information for a room.

    Determines which providers to use based on room owner's tier.

    Args:
        room_code: Room code
        user_email: User email (for participant quota checking)
        db_pool: asyncpg database pool

    Returns:
        dict: {
            'tier_name': str,
            'provider_tier': str,
            'allowed_stt_providers': list,
            'allowed_mt_providers': list,
            'supports_server_tts': bool,
            'quota_available': int,
            'admin_email': str
        }
    """
    # Get room owner's tier (determines routing)
    owner_tier = await get_room_owner_tier(room_code, db_pool)

    if not owner_tier:
        # Fallback to free tier if no subscription found
        logger.warning(f"No tier found for room {room_code}, defaulting to free tier")
        return {
            'tier_name': 'free',
            'provider_tier': 'free',
            'allowed_stt_providers': ['speechmatics'],
            'allowed_mt_providers': ['libretranslate'],
            'supports_server_tts': False,
            'quota_available': 0,
            'admin_email': None
        }

    # Get participant's quota (if provided)
    participant_quota = 0
    if user_email:
        participant_tier = await get_user_tier(user_email, db_pool)
        if participant_tier:
            participant_quota = participant_tier['quota_available_seconds']

    return {
        'tier_name': owner_tier['tier_name'],
        'provider_tier': owner_tier['provider_tier'],
        'allowed_stt_providers': get_allowed_stt_providers(owner_tier['tier_name']),
        'allowed_mt_providers': get_allowed_mt_providers(owner_tier['tier_name']),
        'supports_server_tts': supports_server_tts(owner_tier['tier_name']),
        'quota_available': participant_quota + owner_tier['quota_available_seconds'],
        'admin_quota': owner_tier['quota_available_seconds'],
        'admin_email': None  # TODO: Get from room owner
    }

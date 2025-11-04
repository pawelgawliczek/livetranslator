"""
Integration tests for tier-based provider routing.

Tests:
- Free tier routes to basic providers (Speechmatics basic, LibreTranslate, client TTS)
- Plus tier routes to premium providers (all STT/MT, client TTS)
- Pro tier routes to all providers + server TTS
- Quota waterfall (participant → admin → free fallback)
- Quota exhaustion handling
"""

import pytest
import pytest_asyncio
import asyncpg
from datetime import datetime, timedelta
from decimal import Decimal

from api.routers.tier_helpers import (
    get_user_tier,
    get_room_owner_tier,
    get_allowed_stt_providers,
    get_allowed_mt_providers,
    supports_server_tts,
    deduct_quota_waterfall,
    get_tier_routing_info,
    QuotaExhaustedError
)


@pytest_asyncio.fixture
async def db_pool():
    """Create asyncpg connection pool for tests."""
    import os
    dsn = os.getenv("DATABASE_URL", "postgresql://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator")
    pool = await asyncpg.create_pool(dsn)
    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def test_users(db_pool):
        """Create test users with different tiers."""
        async with db_pool.acquire() as conn:
            # Clean up existing test data
            await conn.execute("DELETE FROM quota_transactions WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test_%@tier-test.com')")
            await conn.execute("DELETE FROM user_subscriptions WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test_%@tier-test.com')")
            await conn.execute("DELETE FROM rooms WHERE owner_id IN (SELECT id FROM users WHERE email LIKE 'test_%@tier-test.com')")
            await conn.execute("DELETE FROM users WHERE email LIKE 'test_%@tier-test.com'")

            # Create test users
            free_user = await conn.fetchrow("""
                INSERT INTO users (email, display_name, password_hash, preferred_lang)
                VALUES ('test_free@tier-test.com', 'Free User', 'dummy_hash', 'en')
                RETURNING id
            """)

            plus_user = await conn.fetchrow("""
                INSERT INTO users (email, display_name, password_hash, preferred_lang)
                VALUES ('test_plus@tier-test.com', 'Plus User', 'dummy_hash', 'en')
                RETURNING id
            """)

            pro_user = await conn.fetchrow("""
                INSERT INTO users (email, display_name, password_hash, preferred_lang)
                VALUES ('test_pro@tier-test.com', 'Pro User', 'dummy_hash', 'en')
                RETURNING id
            """)

            # Get tier IDs
            free_tier = await conn.fetchval("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
            plus_tier = await conn.fetchval("SELECT id FROM subscription_tiers WHERE tier_name = 'plus'")
            pro_tier = await conn.fetchval("SELECT id FROM subscription_tiers WHERE tier_name = 'pro'")

            # Create subscriptions
            await conn.execute("""
                INSERT INTO user_subscriptions
                (user_id, tier_id, plan, status, billing_period_start, billing_period_end)
                VALUES
                ($1, $2, 'free', 'active', NOW(), NOW() + INTERVAL '1 month'),
                ($3, $4, 'plus', 'active', NOW(), NOW() + INTERVAL '1 month'),
                ($5, $6, 'pro', 'active', NOW(), NOW() + INTERVAL '1 month')
            """, free_user['id'], free_tier, plus_user['id'], plus_tier, pro_user['id'], pro_tier)

            # Create test rooms
            free_room = await conn.fetchrow("""
                INSERT INTO rooms (code, owner_id, recording)
                VALUES ('FREETST', $1, false)
                RETURNING id
            """, free_user['id'])

            plus_room = await conn.fetchrow("""
                INSERT INTO rooms (code, owner_id, recording)
                VALUES ('PLUSTST', $1, false)
                RETURNING id
            """, plus_user['id'])

            pro_room = await conn.fetchrow("""
                INSERT INTO rooms (code, owner_id, recording)
                VALUES ('PROTST', $1, false)
                RETURNING id
            """, pro_user['id'])

            yield {
                'free_user': {'id': free_user['id'], 'email': 'test_free@tier-test.com', 'room_code': 'FREETST'},
                'plus_user': {'id': plus_user['id'], 'email': 'test_plus@tier-test.com', 'room_code': 'PLUSTST'},
                'pro_user': {'id': pro_user['id'], 'email': 'test_pro@tier-test.com', 'room_code': 'PROTST'}
            }

            # Cleanup
            await conn.execute("DELETE FROM quota_transactions WHERE user_id IN ($1, $2, $3)",
                             free_user['id'], plus_user['id'], pro_user['id'])
            await conn.execute("DELETE FROM user_subscriptions WHERE user_id IN ($1, $2, $3)",
                             free_user['id'], plus_user['id'], pro_user['id'])
            await conn.execute("DELETE FROM rooms WHERE id IN ($1, $2, $3)",
                             free_room['id'], plus_room['id'], pro_room['id'])
            await conn.execute("DELETE FROM users WHERE id IN ($1, $2, $3)",
                             free_user['id'], plus_user['id'], pro_user['id'])


class TestTierBasedRouting:
    """Test tier-based provider routing logic."""

    @pytest.mark.asyncio
    async def test_free_tier_uses_basic_providers(self, db_pool, test_users):
        """Free tier should only route to Speechmatics basic for Web, nothing for iOS."""
        free_user = test_users['free_user']

        # Get tier info
        tier = await get_user_tier(free_user['email'], db_pool)
        assert tier is not None
        assert tier['tier_name'] == 'free'
        assert tier['provider_tier'] == 'free'

        # Check allowed providers
        stt_providers = get_allowed_stt_providers('free', platform='web')
        assert stt_providers == ['speechmatics']  # Basic tier only

        mt_providers = get_allowed_mt_providers('free', platform='web')
        assert mt_providers == ['libretranslate']  # Free, self-hosted

        # iOS should use client-side only
        ios_stt = get_allowed_stt_providers('free', platform='ios')
        assert ios_stt == []  # Empty = client-side Apple STT

        ios_mt = get_allowed_mt_providers('free', platform='ios')
        assert ios_mt == []  # Empty = client-side Apple Translation

        # TTS should be client-side only
        assert not supports_server_tts('free')

    @pytest.mark.asyncio
    async def test_plus_tier_uses_premium_providers(self, db_pool, test_users):
        """Plus tier should access all premium STT/MT providers."""
        plus_user = test_users['plus_user']

        tier = await get_user_tier(plus_user['email'], db_pool)
        assert tier is not None
        assert tier['tier_name'] == 'plus'
        assert tier['provider_tier'] == 'standard'

        # Check STT providers
        stt_providers = get_allowed_stt_providers('plus')
        assert 'speechmatics' in stt_providers
        assert 'google_v2' in stt_providers
        assert 'azure' in stt_providers
        assert 'soniox' in stt_providers

        # Check MT providers
        mt_providers = get_allowed_mt_providers('plus')
        assert 'deepl' in mt_providers
        assert 'google_translate' in mt_providers
        assert 'amazon_translate' in mt_providers
        assert 'openai_gpt4o_mini' in mt_providers

        # No GPT-4 for Plus tier
        assert 'openai_gpt4o' not in mt_providers

        # No server TTS for Plus tier
        assert not supports_server_tts('plus')

    @pytest.mark.asyncio
    async def test_pro_tier_server_tts_enabled(self, db_pool, test_users):
        """Pro tier should get server-side TTS."""
        pro_user = test_users['pro_user']

        tier = await get_user_tier(pro_user['email'], db_pool)
        assert tier is not None
        assert tier['tier_name'] == 'pro'
        assert tier['provider_tier'] == 'premium'

        # Pro tier gets all providers
        stt_providers = get_allowed_stt_providers('pro')
        assert len(stt_providers) >= 4  # All premium STT providers

        mt_providers = get_allowed_mt_providers('pro')
        assert 'openai_gpt4o' in mt_providers  # GPT-4 available
        assert 'deepl' in mt_providers

        # Pro tier gets server TTS
        assert supports_server_tts('pro')

    @pytest.mark.asyncio
    async def test_quota_waterfall_participant_first(self, db_pool, test_users):
        """Participant quota should be used before admin quota."""
        plus_user = test_users['plus_user']
        pro_user = test_users['pro_user']

        # Pro user joins Plus user's room
        # Quota waterfall: Pro user's quota → Plus user's quota (admin)

        result = await deduct_quota_waterfall(
            user_email=pro_user['email'],
            room_code=plus_user['room_code'],  # Plus user's room
            seconds=30,
            service_type='stt',
            provider='speechmatics',
            db_pool=db_pool
        )

        assert result['source'] == 'participant'  # Pro user's quota used first
        assert result['remaining'] >= 0

    @pytest.mark.asyncio
    async def test_quota_exhausted_uses_admin(self, db_pool, test_users):
        """When participant exhausted, use admin quota."""
        free_user = test_users['free_user']
        plus_user = test_users['plus_user']

        # Exhaust free user's quota first
        async with db_pool.acquire() as conn:
            # Deduct all quota (free tier = 10 minutes = 600 seconds)
            await conn.execute("""
                INSERT INTO quota_transactions
                (user_id, room_id, transaction_type, amount_seconds, quota_type, provider_used, service_type)
                VALUES ($1, (SELECT id FROM rooms WHERE code = $2), 'deduct', -600, 'own', 'test', 'stt')
            """, free_user['id'], free_user['room_code'])

        # Free user joins Plus user's room (should use Plus user's admin quota)
        result = await deduct_quota_waterfall(
            user_email=free_user['email'],
            room_code=plus_user['room_code'],  # Plus user's room
            seconds=30,
            service_type='stt',
            provider='speechmatics',
            db_pool=db_pool
        )

        assert result['source'] == 'admin'  # Plus user's quota used (admin fallback)
        assert result['remaining'] >= 0

    @pytest.mark.asyncio
    async def test_quota_exhausted_raises_error(self, db_pool, test_users):
        """When both participant and admin exhausted, raise error."""
        free_user = test_users['free_user']
        plus_user = test_users['plus_user']

        # Exhaust both quotas
        async with db_pool.acquire() as conn:
            # Exhaust free user
            await conn.execute("""
                INSERT INTO quota_transactions
                (user_id, room_id, transaction_type, amount_seconds, quota_type, provider_used, service_type)
                VALUES ($1, (SELECT id FROM rooms WHERE code = $2), 'deduct', -600, 'own', 'test', 'stt')
            """, free_user['id'], free_user['room_code'])

            # Exhaust plus user (2 hours = 7200 seconds)
            await conn.execute("""
                INSERT INTO quota_transactions
                (user_id, room_id, transaction_type, amount_seconds, quota_type, provider_used, service_type)
                VALUES ($1, (SELECT id FROM rooms WHERE code = $2), 'deduct', -7200, 'own', 'test', 'stt')
            """, plus_user['id'], plus_user['room_code'])

        # Should raise QuotaExhaustedError
        with pytest.raises(QuotaExhaustedError):
            await deduct_quota_waterfall(
                user_email=free_user['email'],
                room_code=plus_user['room_code'],
                seconds=30,
                service_type='stt',
                provider='speechmatics',
                db_pool=db_pool
            )

    @pytest.mark.asyncio
    async def test_room_owner_determines_routing(self, db_pool, test_users):
        """Room owner's tier should determine provider routing (not participant's)."""
        free_user = test_users['free_user']
        pro_user = test_users['pro_user']

        # Free user joins Pro user's room
        # Routing should use Pro tier providers (admin determines routing)

        routing_info = await get_tier_routing_info(
            room_code=pro_user['room_code'],  # Pro user's room
            user_email=free_user['email'],  # Free user joins
            db_pool=db_pool
        )

        assert routing_info['tier_name'] == 'pro'  # Pro tier routing
        assert routing_info['supports_server_tts'] is True  # Pro features available
        assert 'deepgram' in routing_info['allowed_stt_providers']  # Pro-only provider

    @pytest.mark.asyncio
    async def test_tier_routing_fallback_to_free(self, db_pool):
        """Unknown room should fall back to free tier routing."""
        routing_info = await get_tier_routing_info(
            room_code='NONEXISTENT',
            user_email=None,
            db_pool=db_pool
        )

        assert routing_info['tier_name'] == 'free'
        assert routing_info['allowed_stt_providers'] == ['speechmatics']
        assert routing_info['allowed_mt_providers'] == ['libretranslate']
        assert routing_info['supports_server_tts'] is False


class TestQuotaTransactions:
    """Test quota transaction recording."""

    @pytest.mark.asyncio
    async def test_quota_transaction_recorded(self, db_pool):
        """Quota deductions should be recorded in quota_transactions table."""
        # TODO: Implement after creating test fixtures
        pass

    @pytest.mark.asyncio
    async def test_quota_source_attribution(self, db_pool):
        """Quota transactions should track whether own or admin quota was used."""
        # TODO: Implement after creating test fixtures
        pass

"""
Integration tests for admin debug tracking feature.

Tests the complete debug tracking flow:
- STT router creates debug info in Redis
- MT router appends translations to debug info
- Admin API endpoint returns debug data
- Skip reasons are tracked correctly
"""

import pytest
import pytest_asyncio
import json
import os
import redis.asyncio as redis
from sqlalchemy.sql import text

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")


@pytest_asyncio.fixture
async def async_redis():
    """Create a Redis client for testing."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.integration
class TestDebugTrackingIntegration:
    """Integration tests for debug tracking with Redis and database"""

    @pytest.mark.asyncio
    async def test_stt_creates_debug_info_in_redis(self, async_redis):
        """Test that STT processing creates debug:{room_code}:segment:{id} key in Redis"""
        from api.services.debug_tracker import create_stt_debug_info

        segment_id = 12345
        room_code = "test-room-123"

        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "final",
            "latency_ms": 450,
            "audio_duration_sec": 3.5,
            "text": "Test transcription"
        }

        routing_info = {
            "routing_reason": "pl/final/standard → speechmatics (primary)",
            "fallback_triggered": False
        }

        # Create debug info
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)

        # Verify Redis key exists
        key = f"debug:{room_code}:segment:{segment_id}"
        data = await async_redis.get(key)
        assert data is not None

        # Verify TTL is 24 hours (86400 seconds)
        ttl = await async_redis.ttl(key)
        assert 86000 < ttl <= 86400  # Allow some margin

        # Verify structure
        debug_info = json.loads(data)
        assert debug_info["segment_id"] == segment_id
        assert debug_info["room_code"] == room_code
        assert debug_info["stt"]["provider"] == "speechmatics"
        assert debug_info["stt"]["latency_ms"] == 450
        assert debug_info["mt"] == []
        assert debug_info["totals"]["stt_cost_usd"] > 0


    @pytest.mark.asyncio
    async def test_mt_appends_to_existing_debug_info(self, async_redis):
        """Test that MT router appends translations to existing debug info"""
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info

        segment_id = 12346
        room_code = "test-room-124"

        # First, create STT debug info
        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "final",
            "latency_ms": 0,
            "audio_duration_sec": 2.0,
            "text": "Dzień dobry"
        }
        routing_info = {
            "routing_reason": "pl/streaming/standard → speechmatics (streaming)",
            "fallback_triggered": False
        }
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)

        # Now append MT translation
        mt_data = {
            "src_lang": "pl",
            "tgt_lang": "en",
            "provider": "deepl",
            "latency_ms": 235,
            "text": "Good morning",
            "char_count": 11,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_routing_info = {
            "routing_reason": "pl→en/standard → deepl (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_data, mt_routing_info)

        # Verify MT data was appended
        key = f"debug:{room_code}:segment:{segment_id}"
        data = await async_redis.get(key)
        debug_info = json.loads(data)

        assert len(debug_info["mt"]) == 1
        assert debug_info["mt"][0]["provider"] == "deepl"
        assert debug_info["mt"][0]["src_lang"] == "pl"
        assert debug_info["mt"][0]["tgt_lang"] == "en"
        assert debug_info["mt"][0]["latency_ms"] == 235
        assert debug_info["totals"]["mt_translations"] == 1
        assert debug_info["totals"]["mt_cost_usd"] > 0


    @pytest.mark.asyncio
    async def test_multiple_mt_translations_tracked(self, async_redis):
        """Test tracking multiple MT translations for same segment"""
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info

        segment_id = 12347
        room_code = "test-room-125"

        # Create STT debug info
        stt_data = {
            "provider": "google_v2",
            "language": "en",
            "mode": "final",
            "latency_ms": 180,
            "audio_duration_sec": 4.2,
            "text": "Hello everyone"
        }
        routing_info = {"routing_reason": "en/final/standard → google_v2 (primary)", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)

        # Append first translation (en→pl)
        mt_data_1 = {
            "src_lang": "en",
            "tgt_lang": "pl",
            "provider": "google_translate",
            "latency_ms": 120,
            "text": "Witam wszystkich",
            "char_count": 14,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_routing_1 = {
            "routing_reason": "en→pl/standard → google_translate (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_data_1, mt_routing_1)

        # Append second translation (en→ar)
        mt_data_2 = {
            "src_lang": "en",
            "tgt_lang": "ar",
            "provider": "gpt-4o-mini",
            "latency_ms": 890,
            "text": "مرحبا الجميع",
            "char_count": None,
            "input_tokens": 12,
            "output_tokens": 8
        }
        mt_routing_2 = {
            "routing_reason": "en→ar/standard → gpt-4o-mini (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_data_2, mt_routing_2)

        # Verify both translations tracked
        key = f"debug:{room_code}:segment:{segment_id}"
        data = await async_redis.get(key)
        debug_info = json.loads(data)

        assert len(debug_info["mt"]) == 2
        assert debug_info["mt"][0]["tgt_lang"] == "pl"
        assert debug_info["mt"][1]["tgt_lang"] == "ar"
        assert debug_info["totals"]["mt_translations"] == 2

        # Verify costs summed correctly
        total_mt_cost = debug_info["mt"][0]["cost_usd"] + debug_info["mt"][1]["cost_usd"]
        assert abs(debug_info["totals"]["mt_cost_usd"] - total_mt_cost) < 0.000001


    @pytest.mark.asyncio
    async def test_skip_reason_tracked_for_same_language(self, async_redis):
        """Test that skip reasons are tracked when source=target language"""
        from api.services.debug_tracker import create_stt_debug_info, append_mt_skip_reason

        segment_id = 12348
        room_code = "test-room-126"

        # Create STT debug info
        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "streaming",
            "latency_ms": 0,
            "audio_duration_sec": 1.5,
            "text": "Test"
        }
        routing_info = {"routing_reason": "pl/streaming/standard → speechmatics (streaming)", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)

        # Record skip reason
        await append_mt_skip_reason(
            redis=async_redis,
            room_code=room_code,
            segment_id=segment_id,
            src_lang="pl",
            tgt_lang="pl",
            reason="No translation needed - source and target are both 'pl'"
        )

        # Verify skip reason recorded
        key = f"debug:{room_code}:segment:{segment_id}"
        data = await async_redis.get(key)
        debug_info = json.loads(data)

        assert "mt_skip_reasons" in debug_info
        assert len(debug_info["mt_skip_reasons"]) == 1
        assert debug_info["mt_skip_reasons"][0]["src_lang"] == "pl"
        assert debug_info["mt_skip_reasons"][0]["tgt_lang"] == "pl"
        assert "No translation needed" in debug_info["mt_skip_reasons"][0]["reason"]


    @pytest.mark.asyncio
    async def test_skip_reason_tracked_for_auto_language(self, async_redis):
        """Test that skip reasons are tracked when source language is 'auto'"""
        from api.services.debug_tracker import create_stt_debug_info, append_mt_skip_reason

        segment_id = 12349
        room_code = "test-room-127"

        # Create STT debug info with auto language
        stt_data = {
            "provider": "local",
            "language": "auto",
            "mode": "final",
            "latency_ms": 2500,
            "audio_duration_sec": 3.0,
            "text": "Unknown language text"
        }
        routing_info = {"routing_reason": "auto/final/standard → local (primary)", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)

        # Record skip reason for auto
        await append_mt_skip_reason(
            redis=async_redis,
            room_code=room_code,
            segment_id=segment_id,
            src_lang="auto",
            tgt_lang="en",
            reason="Source language unknown (auto-detected as 'auto')"
        )

        # Verify skip reason recorded
        key = f"debug:{room_code}:segment:{segment_id}"
        data = await async_redis.get(key)
        debug_info = json.loads(data)

        assert len(debug_info["mt_skip_reasons"]) == 1
        assert debug_info["mt_skip_reasons"][0]["src_lang"] == "auto"
        assert "Source language unknown" in debug_info["mt_skip_reasons"][0]["reason"]


    @pytest.mark.skip(reason="Requires HTTP client fixture - move to E2E tests")
    @pytest.mark.asyncio
    async def test_admin_api_endpoint_returns_redis_data(self, client, async_redis):
        """Test GET /api/admin/message-debug/{room_code}/{segment_id} returns data from Redis"""
        from api.services.debug_tracker import create_stt_debug_info

        # Create admin user
        admin_token = await self._create_admin_user(client)

        segment_id = 12350
        room_code = "test-room-128"

        # Create debug info in Redis
        stt_data = {
            "provider": "azure",
            "language": "en",
            "mode": "final",
            "latency_ms": 320,
            "audio_duration_sec": 5.0,
            "text": "Testing admin API"
        }
        routing_info = {"routing_reason": "en/final/standard → azure (primary)", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)

        # Call API endpoint
        response = await client.get(
            f"/api/admin/message-debug/{room_code}/{segment_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "redis"
        assert data["room_code"] == room_code
        assert data["segment_id"] == segment_id
        assert data["data"]["room_code"] == room_code
        assert data["data"]["stt"]["provider"] == "azure"


    @pytest.mark.skip(reason="Requires HTTP client fixture - move to E2E tests")
    @pytest.mark.asyncio
    async def test_admin_api_requires_admin_role(self, client):
        """Test that regular users get 403 when accessing debug API"""
        # Create regular user (non-admin)
        user_token = await self._create_regular_user(client)

        # Try to access debug endpoint
        response = await client.get(
            "/api/admin/message-debug/test-room/12345",
            headers={"Authorization": f"Bearer {user_token}"}
        )

        assert response.status_code == 403


    @pytest.mark.skip(reason="Requires HTTP client fixture - move to E2E tests")
    @pytest.mark.asyncio
    async def test_admin_api_returns_404_for_missing_segment(self, client):
        """Test API returns 404 for non-existent segment"""
        admin_token = await self._create_admin_user(client)

        # Request non-existent segment
        response = await client.get(
            "/api/admin/message-debug/nonexistent-room/999999",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 404


    @pytest.mark.asyncio
    async def test_debug_tracking_doesnt_block_pipeline_on_redis_failure(self, async_redis, monkeypatch):
        """Test that STT/MT continues if debug tracking fails"""
        from api.services.debug_tracker import create_stt_debug_info

        segment_id = 12351
        room_code = "test-room-129"

        # Mock Redis failure
        async def mock_redis_set_failure(*args, **kwargs):
            raise Exception("Redis connection failed")

        monkeypatch.setattr(async_redis, "set", mock_redis_set_failure)

        # Attempt to create debug info - should not raise exception
        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "final",
            "latency_ms": 450,
            "audio_duration_sec": 3.5,
            "text": "Test transcription"
        }
        routing_info = {
            "routing_reason": "pl/final/standard → speechmatics (primary)",
            "fallback_triggered": False
        }

        # Should complete without raising exception
        try:
            await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, routing_info)
            # Success - no exception raised
        except Exception as e:
            pytest.fail(f"Debug tracking should not raise exception on Redis failure: {e}")


    @pytest.mark.asyncio
    async def test_room_isolation_prevents_key_collision(self, async_redis):
        """
        CRITICAL: Test that two separate rooms with same segment_id don't collide.

        This test verifies the fix for the Redis key collision bug where:
        - Room A segment_id=1 would overwrite Room B segment_id=1
        - Keys must include room_code: debug:{room_code}:segment:{id}
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info, get_debug_info

        # Create debug info for Room A, segment_id=1
        room_a = "room-a"
        segment_id = 1

        stt_data_a = {
            "provider": "speechmatics",
            "language": "en",
            "mode": "final",
            "latency_ms": 100,
            "audio_duration_sec": 2.0,
            "text": "Message from Room A"
        }
        routing_info_a = {"routing_reason": "en/final/standard → speechmatics", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_a, stt_data_a, routing_info_a)

        # Create debug info for Room B, same segment_id=1
        room_b = "room-b"

        stt_data_b = {
            "provider": "google_v2",
            "language": "pl",
            "mode": "final",
            "latency_ms": 200,
            "audio_duration_sec": 3.0,
            "text": "Message from Room B"
        }
        routing_info_b = {"routing_reason": "pl/final/standard → google_v2", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_b, stt_data_b, routing_info_b)

        # Verify Room A data is still intact (not overwritten by Room B)
        debug_a = await get_debug_info(async_redis, room_a, segment_id)
        assert debug_a is not None, "Room A debug info should exist"
        assert debug_a["room_code"] == room_a
        assert debug_a["stt"]["text"] == "Message from Room A"
        assert debug_a["stt"]["provider"] == "speechmatics"
        assert debug_a["stt"]["latency_ms"] == 100

        # Verify Room B data exists separately
        debug_b = await get_debug_info(async_redis, room_b, segment_id)
        assert debug_b is not None, "Room B debug info should exist"
        assert debug_b["room_code"] == room_b
        assert debug_b["stt"]["text"] == "Message from Room B"
        assert debug_b["stt"]["provider"] == "google_v2"
        assert debug_b["stt"]["latency_ms"] == 200

        # Verify keys are different in Redis
        key_a = f"debug:{room_a}:segment:{segment_id}"
        key_b = f"debug:{room_b}:segment:{segment_id}"

        data_a = await async_redis.get(key_a)
        data_b = await async_redis.get(key_b)

        assert data_a is not None, "Room A Redis key should exist"
        assert data_b is not None, "Room B Redis key should exist"
        assert data_a != data_b, "Room A and Room B should have different data"

        # Append MT to Room A
        mt_data_a = {
            "src_lang": "en",
            "tgt_lang": "pl",
            "provider": "deepl",
            "latency_ms": 150,
            "text": "Wiadomość z pokoju A",
            "char_count": 21,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_routing_a = {"routing_reason": "en→pl/standard → deepl", "fallback_triggered": False, "throttled": False}
        await append_mt_debug_info(async_redis, room_a, segment_id, mt_data_a, mt_routing_a)

        # Verify MT was only added to Room A, not Room B
        debug_a_updated = await get_debug_info(async_redis, room_a, segment_id)
        debug_b_unchanged = await get_debug_info(async_redis, room_b, segment_id)

        assert len(debug_a_updated["mt"]) == 1, "Room A should have 1 MT translation"
        assert debug_a_updated["mt"][0]["text"] == "Wiadomość z pokoju A"

        assert len(debug_b_unchanged["mt"]) == 0, "Room B should have 0 MT translations"

        print("✅ Room isolation test passed - no key collision!")


    # Helper methods
    async def _create_admin_user(self, client):
        """Create admin user and return auth token"""
        # Register user
        response = await client.post("/api/register", json={
            "email": "admin@test.com",
            "password": "adminpass123",
            "display_name": "Admin User"
        })
        assert response.status_code == 200

        # Set as admin in database
        from api.database import SessionLocal, User
        db = SessionLocal()
        user = db.query(User).filter(User.email == "admin@test.com").first()
        user.is_admin = True
        db.commit()
        db.close()

        # Login and get token
        response = await client.post("/api/login", json={
            "email": "admin@test.com",
            "password": "adminpass123"
        })
        return response.json()["token"]


    async def _create_regular_user(self, client):
        """Create regular (non-admin) user and return auth token"""
        response = await client.post("/api/register", json={
            "email": "user@test.com",
            "password": "userpass123",
            "display_name": "Regular User"
        })
        assert response.status_code == 200

        response = await client.post("/api/login", json={
            "email": "user@test.com",
            "password": "userpass123"
        })
        return response.json()["token"]

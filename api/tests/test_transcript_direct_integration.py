"""
Integration tests for iOS Transcript Direct endpoint.

Tests POST /api/transcript-direct for pre-transcribed text from Apple STT.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from api.models import (
    User,
    Room,
    RoomParticipant,
    SubscriptionTier,
    UserSubscription,
    QuotaTransaction
)


@pytest.mark.asyncio
async def test_transcript_direct_success(test_db_session, test_user, test_room, mock_redis):
    """Test successful transcript submission with sufficient quota"""
    # Setup: User is participant in room with Plus tier
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)

    participant = RoomParticipant(
        room_id=test_room.id,
        user_id=test_user.id,
        display_name="Test User",
        spoken_language="en",
        is_active=True
    )
    test_db_session.add(participant)
    await test_db_session.commit()

    # Mock quota deduction HTTP call
    mock_quota_response = {
        "transaction_id": 123,
        "remaining_seconds": 7197,
        "quota_exhausted": False
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_quota_response

        # Test: Submit transcript
        from api.routers.transcript import submit_transcript_direct, TranscriptDirectRequest

        request = TranscriptDirectRequest(
            room_code=test_room.code,
            text="Hello, this is a test from iOS app.",
            speaker_email=test_user.email,
            is_final=True,
            estimated_seconds=3,
            source_lang="en"
        )

        response = await submit_transcript_direct(
            request=request,
            current_user_id=test_user.id,
            db=test_db_session
        )

        # Assert
        assert response.success == True
        assert response.segment_id.startswith("ios_")
        assert response.quota_deducted_seconds == 3
        assert response.quota_remaining_seconds == 7197

        # Verify Redis publish was called
        assert mock_redis.publish.called
        publish_args = mock_redis.publish.call_args
        assert publish_args[0][0] == "stt_events"

        # Verify published event structure
        event_data = json.loads(publish_args[0][1])
        assert event_data["type"] == "transcript"
        assert event_data["room_code"] == test_room.code
        assert event_data["text"] == "Hello, this is a test from iOS app."
        assert event_data["source_lang"] == "en"
        assert event_data["provider"] == "apple_stt"
        assert event_data["platform"] == "ios"


@pytest.mark.asyncio
async def test_transcript_direct_estimate_quota_from_sentences(test_db_session, test_user, test_room):
    """Test quota estimation based on sentence count"""
    # Setup
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)

    participant = RoomParticipant(
        room_id=test_room.id,
        user_id=test_user.id,
        display_name="Test User",
        spoken_language="en",
        is_active=True
    )
    test_db_session.add(participant)
    await test_db_session.commit()

    # Test: 3 sentences = 9 seconds estimated
    text_with_sentences = "First sentence. Second sentence! Third sentence?"

    mock_quota_response = {
        "transaction_id": 456,
        "remaining_seconds": 7191,
        "quota_exhausted": False
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_quota_response

        from api.routers.transcript import submit_transcript_direct, TranscriptDirectRequest

        request = TranscriptDirectRequest(
            room_code=test_room.code,
            text=text_with_sentences,
            speaker_email=test_user.email,
            is_final=True,
            estimated_seconds=3,  # Default - will be overridden
            source_lang="en"
        )

        response = await submit_transcript_direct(
            request=request,
            current_user_id=test_user.id,
            db=test_db_session
        )

        # Assert: 3 sentences * 3 seconds = 9 seconds
        assert response.quota_deducted_seconds == 9


@pytest.mark.asyncio
async def test_transcript_direct_quota_exhausted(test_db_session, test_user, test_room):
    """Test 402 Payment Required when quota exhausted"""
    # Setup: Free tier with exhausted quota
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    billing_start = datetime.utcnow()
    subscription = UserSubscription(
        user_id=test_user.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=billing_start,
        billing_period_end=billing_start + timedelta(days=30)
    )
    test_db_session.add(subscription)

    participant = RoomParticipant(
        room_id=test_room.id,
        user_id=test_user.id,
        display_name="Test User",
        spoken_language="en",
        is_active=True
    )
    test_db_session.add(participant)

    # Exhaust quota
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-600,  # All 10 minutes used
        quota_type="monthly",
        provider_used="apple_stt",
        service_type="stt"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Test: Submit transcript (should fail with 402)
    from api.routers.transcript import submit_transcript_direct, TranscriptDirectRequest
    from fastapi import HTTPException

    request = TranscriptDirectRequest(
        room_code=test_room.code,
        text="This should fail due to quota.",
        speaker_email=test_user.email,
        is_final=True,
        estimated_seconds=3,
        source_lang="en"
    )

    with pytest.raises(HTTPException) as exc_info:
        await submit_transcript_direct(
            request=request,
            current_user_id=test_user.id,
            db=test_db_session
        )

    # Assert: 402 Payment Required
    assert exc_info.value.status_code == 402
    assert "Quota exhausted" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_transcript_direct_admin_fallback(test_db_session, test_user, test_room):
    """Test admin quota fallback when participant quota exhausted"""
    # Setup: Participant (guest) with exhausted free tier
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    guest_subscription = UserSubscription(
        user_id=test_user.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(guest_subscription)

    # Exhaust guest quota
    guest_transaction = QuotaTransaction(
        user_id=test_user.id,
        transaction_type="deduct",
        amount_seconds=-600,
        quota_type="monthly",
        provider_used="apple_stt",
        service_type="stt"
    )
    test_db_session.add(guest_transaction)

    # Room owner (admin) with Plus tier and available quota
    admin = User(
        email="admin@example.com",
        display_name="Admin",
        preferred_lang="en"
    )
    test_db_session.add(admin)
    await test_db_session.flush()

    # Update room owner
    test_room.owner_id = admin.id

    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    admin_subscription = UserSubscription(
        user_id=admin.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(admin_subscription)

    # Guest participant
    participant = RoomParticipant(
        room_id=test_room.id,
        user_id=test_user.id,
        display_name="Guest User",
        spoken_language="en",
        is_active=True
    )
    test_db_session.add(participant)
    await test_db_session.commit()

    # Mock quota deduction for admin
    mock_quota_response = {
        "transaction_id": 789,
        "remaining_seconds": 7197,
        "quota_exhausted": False
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = mock_quota_response

        # Test: Submit transcript (should use admin quota)
        from api.routers.transcript import submit_transcript_direct, TranscriptDirectRequest

        request = TranscriptDirectRequest(
            room_code=test_room.code,
            text="Using admin quota fallback.",
            speaker_email=test_user.email,
            is_final=True,
            estimated_seconds=3,
            source_lang="en"
        )

        response = await submit_transcript_direct(
            request=request,
            current_user_id=test_user.id,
            db=test_db_session
        )

        # Assert: Success using admin quota
        assert response.success == True
        assert response.quota_deducted_seconds == 3

        # Verify participant marked as using admin quota
        await test_db_session.refresh(participant)
        assert participant.is_using_admin_quota == True
        assert participant.quota_source == "admin"


@pytest.mark.asyncio
async def test_transcript_direct_not_participant(test_db_session, test_user, test_room):
    """Test 403 Forbidden when user is not participant in room"""
    # Setup: User with subscription but not in room
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Test: Submit transcript without being participant
    from api.routers.transcript import submit_transcript_direct, TranscriptDirectRequest
    from fastapi import HTTPException

    request = TranscriptDirectRequest(
        room_code=test_room.code,
        text="I'm not in this room.",
        speaker_email=test_user.email,
        is_final=True,
        estimated_seconds=3,
        source_lang="en"
    )

    with pytest.raises(HTTPException) as exc_info:
        await submit_transcript_direct(
            request=request,
            current_user_id=test_user.id,
            db=test_db_session
        )

    # Assert: 403 Forbidden
    assert exc_info.value.status_code == 403
    assert "not an active participant" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_transcript_direct_room_not_found(test_db_session, test_user):
    """Test 404 Not Found when room doesn't exist"""
    # Setup: User with subscription
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Test: Submit to non-existent room
    from api.routers.transcript import submit_transcript_direct, TranscriptDirectRequest
    from fastapi import HTTPException

    request = TranscriptDirectRequest(
        room_code="INVALID",
        text="Room doesn't exist.",
        speaker_email=test_user.email,
        is_final=True,
        estimated_seconds=3,
        source_lang="en"
    )

    with pytest.raises(HTTPException) as exc_info:
        await submit_transcript_direct(
            request=request,
            current_user_id=test_user.id,
            db=test_db_session
        )

    # Assert: 404 Not Found
    assert exc_info.value.status_code == 404
    assert "Room not found" in str(exc_info.value.detail)


# ========================================
# Fixtures
# ========================================

@pytest.fixture
async def test_user(test_db_session):
    """Create test user"""
    user = User(
        email="test@example.com",
        display_name="Test User",
        preferred_lang="en"
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture
async def test_room(test_db_session, test_user):
    """Create test room"""
    room = Room(
        code="TEST123",
        owner_id=test_user.id,
        recording=False
    )
    test_db_session.add(room)
    await test_db_session.commit()
    await test_db_session.refresh(room)
    return room


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client for pub/sub"""
    mock = mocker.AsyncMock()
    mocker.patch("api.routers.transcript.redis_client", mock)
    return mock

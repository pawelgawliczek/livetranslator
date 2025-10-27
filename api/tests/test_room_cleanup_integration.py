"""
Integration tests for room cleanup service.

These tests verify the complete flow:
1. Admin creates and leaves a room
2. admin_left_at is set correctly in the database
3. Cleanup service finds and deletes the room after 30 minutes
4. Related data is handled correctly (CASCADE deletes, preserved billing)

These tests require a test database and should be run with pytest-asyncio.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Import models and services
from api.models import Room, RoomCost, User, Device, Event, RoomParticipant
from api.services.room_cleanup_service import cleanup_abandoned_rooms, archive_room


@pytest.mark.integration
class TestRoomCleanupIntegration:
    """Integration tests for room cleanup with real database."""

    @pytest.fixture
    async def test_db_session(self):
        """Create a test database session."""
        # Use a test database
        import os
        test_db_dsn = os.getenv(
            "TEST_POSTGRES_DSN",
            "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test"
        )

        engine = create_async_engine(test_db_dsn, echo=False)
        AsyncTestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with AsyncTestSession() as session:
            yield session

        await engine.dispose()

    @pytest.fixture
    async def test_user(self, test_db_session):
        """Create a test user."""
        user = User(
            email="test@example.com",
            hashed_password="hashed",
            stt_quota_minutes=100.0
        )
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)
        return user

    @pytest.fixture
    async def abandoned_room(self, test_db_session, test_user):
        """Create a room where admin left 45 minutes ago."""
        room = Room(
            code="test-abandoned",
            owner_id=test_user.id,
            admin_left_at=datetime.utcnow() - timedelta(minutes=45),
            recording=False,
            is_public=True,
            requires_login=False,
            max_participants=10
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)
        return room

    @pytest.fixture
    async def empty_room_with_admin_left(self, test_db_session, test_user):
        """Create an empty room where admin left 40 minutes ago."""
        room = Room(
            code="test-empty",
            owner_id=test_user.id,
            admin_left_at=datetime.utcnow() - timedelta(minutes=40),
            recording=False,
            is_public=False,
            requires_login=False,
            max_participants=5
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)
        return room

    @pytest.fixture
    async def active_room(self, test_db_session, test_user):
        """Create an active room where admin is present."""
        room = Room(
            code="test-active",
            owner_id=test_user.id,
            admin_left_at=None,  # Admin is present
            recording=True,
            is_public=True,
            requires_login=True,
            max_participants=20
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)
        return room

    @pytest.mark.asyncio
    async def test_cleanup_deletes_abandoned_room(self, test_db_session, abandoned_room):
        """Test that cleanup deletes a room where admin has been absent for 30+ minutes."""
        room_id = abandoned_room.id
        room_code = abandoned_room.code

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room was deleted
        result = await test_db_session.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        assert room is None, "Room should have been deleted"

        # Verify room was archived
        result = await test_db_session.execute(
            text("SELECT * FROM room_archive WHERE room_code = :code"),
            {"code": room_code}
        )
        archived = result.first()
        assert archived is not None, "Room should have been archived"
        assert archived.archive_reason == "cleanup"

    @pytest.mark.asyncio
    async def test_cleanup_deletes_empty_room(self, test_db_session, empty_room_with_admin_left):
        """Test that cleanup deletes an empty room where admin left."""
        room_id = empty_room_with_admin_left.id

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room was deleted
        result = await test_db_session.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        assert room is None, "Empty room should have been deleted"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_active_room(self, test_db_session, active_room):
        """Test that cleanup does NOT delete active rooms."""
        room_id = active_room.id

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room still exists
        result = await test_db_session.execute(
            select(Room).where(Room.id == room_id)
        )
        room = result.scalar_one_or_none()
        assert room is not None, "Active room should NOT be deleted"
        assert room.admin_left_at is None

    @pytest.mark.skip(reason="Segment model not implemented yet")
    @pytest.mark.asyncio
    async def test_cleanup_cascades_to_segments(self, test_db_session, abandoned_room, test_user):
        """Test that deleting a room cascades to delete segments."""
        # NOTE: This test is skipped because the Segment model has not been implemented yet.
        # The Segment model would track individual speech segments/transcripts in a room.
        # Once implemented, this test should verify CASCADE deletion works correctly.
        pass

    @pytest.mark.asyncio
    async def test_cleanup_cascades_to_devices(self, test_db_session, abandoned_room):
        """Test that deleting a room cascades to delete devices."""
        # Create a device for the room
        device = Device(
            room_id=abandoned_room.id,
            device_id="device-001",
            device_type="browser",
            user_agent="Mozilla/5.0"
        )
        test_db_session.add(device)
        await test_db_session.commit()

        room_id = abandoned_room.id

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify devices were deleted
        result = await test_db_session.execute(
            select(Device).where(Device.room_id == room_id)
        )
        devices = result.all()
        assert len(devices) == 0, "Devices should be deleted via CASCADE"

    @pytest.mark.asyncio
    async def test_cleanup_cascades_to_room_participants(self, test_db_session, abandoned_room, test_user):
        """Test that deleting a room cascades to delete room_participants."""
        # Create room participants
        participant = RoomParticipant(
            room_id=abandoned_room.id,
            user_id=test_user.id,
            display_name="Test User"
        )
        test_db_session.add(participant)
        await test_db_session.commit()

        room_id = abandoned_room.id

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room_participants were deleted
        result = await test_db_session.execute(
            select(RoomParticipant).where(RoomParticipant.room_id == room_id)
        )
        participants = result.all()
        assert len(participants) == 0, "Room participants should be deleted via CASCADE"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_user(self, test_db_session, abandoned_room, test_user):
        """Test that deleting a room does NOT delete the user who owned it."""
        user_id = test_user.id
        room_id = abandoned_room.id

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room was deleted
        result = await test_db_session.execute(
            select(Room).where(Room.id == room_id)
        )
        assert result.scalar_one_or_none() is None

        # Verify user still exists
        result = await test_db_session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        assert user is not None, "User should NOT be deleted when their room is cleaned up"

    @pytest.mark.asyncio
    async def test_cleanup_preserves_room_costs(self, test_db_session, abandoned_room):
        """Test that deleting a room PRESERVES room_costs for billing history."""
        room_code = abandoned_room.code

        # Create room costs
        cost = RoomCost(
            room_id=room_code,  # Note: room_costs uses room_code (string), not FK
            pipeline="stt_final",
            provider="speechmatics",
            units=120,  # 120 seconds
            amount_usd=0.012
        )
        test_db_session.add(cost)
        await test_db_session.commit()

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room was deleted
        result = await test_db_session.execute(
            select(Room).where(Room.code == room_code)
        )
        assert result.scalar_one_or_none() is None

        # Verify room_costs still exist
        result = await test_db_session.execute(
            select(RoomCost).where(RoomCost.room_id == room_code)
        )
        costs = result.all()
        assert len(costs) > 0, "Room costs should be preserved after room deletion"

    @pytest.mark.asyncio
    async def test_archive_includes_cost_data(self, test_db_session, abandoned_room):
        """Test that room archive includes cost and usage data."""
        room_code = abandoned_room.code

        # Create room costs
        cost1 = RoomCost(
            room_id=room_code,
            pipeline="stt_final",
            provider="speechmatics",
            units=180,  # 3 minutes
            amount_usd=0.018
        )
        cost2 = RoomCost(
            room_id=room_code,
            pipeline="mt",
            provider="google",
            units=1000,  # 1000 tokens
            amount_usd=0.002
        )
        test_db_session.add(cost1)
        test_db_session.add(cost2)
        await test_db_session.commit()

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify archive includes cost data
        result = await test_db_session.execute(
            text("SELECT stt_minutes, stt_cost_usd, mt_cost_usd, total_cost_usd FROM room_archive WHERE room_code = :code"),
            {"code": room_code}
        )
        archive = result.first()
        assert archive is not None
        assert float(archive.stt_minutes) == 3.0  # 180 seconds = 3 minutes
        assert float(archive.stt_cost_usd) == 0.018
        assert float(archive.mt_cost_usd) == 0.002
        assert float(archive.total_cost_usd) == 0.020


@pytest.mark.integration
class TestAdminLeftAtBugFix:
    """
    Integration tests specifically for the admin_left_at bug fix.

    These tests verify that admin_left_at is set correctly in ALL scenarios:
    1. Empty rooms (admin leaves, no one else present)
    2. Rooms with only authenticated users
    3. Rooms with only guest users
    4. Mixed rooms
    """

    @pytest.fixture
    async def test_db_session(self):
        """Create a test database session."""
        import os
        test_db_dsn = os.getenv(
            "TEST_POSTGRES_DSN",
            "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test"
        )

        engine = create_async_engine(test_db_dsn, echo=False)
        AsyncTestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with AsyncTestSession() as session:
            yield session

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_empty_room_admin_left_at_is_set(self, test_db_session):
        """
        REGRESSION TEST: Verify admin_left_at is set when admin leaves empty room.

        This was the original bug - admin_left_at was NOT set for empty rooms.
        """
        from api.ws_manager import WSManager

        # Create a test room
        from api.models import Room, User

        user = User(email="admin@test.com", hashed_password="hash", stt_quota_minutes=100)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        room = Room(
            code="empty-test",
            owner_id=user.id,
            admin_left_at=None
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)

        # Simulate admin check with empty room
        ws_manager = WSManager()
        ws_manager.rooms["empty-test"] = set()  # Empty room

        # This should set admin_left_at
        await ws_manager._do_admin_check("empty-test")

        # Verify admin_left_at was set
        await test_db_session.refresh(room)
        assert room.admin_left_at is not None, "BUG: admin_left_at should be set for empty rooms"

    @pytest.mark.asyncio
    async def test_room_with_authenticated_users_admin_left_at_is_set(self, test_db_session):
        """
        REGRESSION TEST: Verify admin_left_at is set when only authenticated users remain.

        This was the original bug - admin_left_at was only set if guest users were present.
        """
        from api.ws_manager import WSManager
        from api.models import Room, User
        from unittest.mock import Mock

        # Create test users
        admin = User(email="admin@test.com", hashed_password="hash", stt_quota_minutes=100)
        user1 = User(email="user1@test.com", hashed_password="hash", stt_quota_minutes=50)
        user2 = User(email="user2@test.com", hashed_password="hash", stt_quota_minutes=50)
        test_db_session.add(admin)
        test_db_session.add(user1)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(admin)
        await test_db_session.refresh(user1)
        await test_db_session.refresh(user2)

        room = Room(
            code="auth-users-test",
            owner_id=admin.id,
            admin_left_at=None
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)

        # Simulate admin check with authenticated users (not admin)
        ws_manager = WSManager()

        ws1 = Mock()
        ws1.state.user = str(user1.id)
        ws2 = Mock()
        ws2.state.user = str(user2.id)

        ws_manager.rooms["auth-users-test"] = {ws1, ws2}

        # This should set admin_left_at (THIS WAS THE BUG)
        await ws_manager._do_admin_check("auth-users-test")

        # Verify admin_left_at was set
        await test_db_session.refresh(room)
        assert room.admin_left_at is not None, "BUG FIX: admin_left_at should be set when only authenticated users remain"

    @pytest.mark.asyncio
    async def test_cleanup_deletes_room_after_30_minutes(self, test_db_session):
        """
        END-TO-END TEST: Verify rooms are cleaned up 30 minutes after admin leaves.

        This tests the complete flow:
        1. Room is created
        2. Admin leaves (admin_left_at is set)
        3. 30+ minutes pass
        4. Cleanup service runs
        5. Room is deleted and archived
        """
        from api.models import Room, User

        # Create test user and room
        user = User(email="cleanup@test.com", hashed_password="hash", stt_quota_minutes=100)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)

        room = Room(
            code="cleanup-e2e-test",
            owner_id=user.id,
            admin_left_at=datetime.utcnow() - timedelta(minutes=35)  # 35 minutes ago
        )
        test_db_session.add(room)
        await test_db_session.commit()
        await test_db_session.refresh(room)

        room_id = room.id
        room_code = room.code

        # Run cleanup
        await cleanup_abandoned_rooms()

        # Verify room was deleted
        result = await test_db_session.execute(
            select(Room).where(Room.id == room_id)
        )
        deleted_room = result.scalar_one_or_none()
        assert deleted_room is None, "Room should be deleted after 30+ minutes"

        # Verify room was archived
        result = await test_db_session.execute(
            text("SELECT * FROM room_archive WHERE room_code = :code"),
            {"code": room_code}
        )
        archived = result.first()
        assert archived is not None, "Room should be archived before deletion"
        assert archived.archive_reason == "cleanup"

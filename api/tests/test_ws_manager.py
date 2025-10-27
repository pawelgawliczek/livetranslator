"""
Unit tests for WebSocket manager admin presence tracking.

Tests cover:
- Admin left detection when room becomes empty
- Admin left detection when admin leaves but other users remain
- Admin left detection when admin leaves with only authenticated users
- Admin left detection when admin leaves with only guest users
- Admin rejoin clearing the admin_left_at timestamp
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime


class TestWSManagerAdminPresence:
    """Test suite for WebSocket manager admin presence tracking."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = Mock()
        session.query = Mock()
        session.commit = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_room(self):
        """Create a mock room object."""
        room = Mock()
        room.id = 1
        room.code = "test-room"
        room.owner_id = 100
        room.admin_left_at = None
        return room

    @pytest.fixture
    def mock_ws_manager(self):
        """Create a mock WebSocket manager."""
        from api.ws_manager import WSManager
        manager = WSManager(
            redis_url="redis://localhost:6379",
            mt_base_url="http://localhost:8000"
        )
        manager.rooms = {}
        manager.log = Mock()
        return manager

    @pytest.mark.asyncio
    async def test_admin_left_when_room_becomes_empty(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin_left_at is set when all users disconnect."""
        room_id = "test-room"
        mock_ws_manager.rooms[room_id] = set()  # Empty room

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify admin_left_at was set
        assert mock_room.admin_left_at is not None
        assert isinstance(mock_room.admin_left_at, datetime)
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_left_when_only_guests_remain(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin_left_at is set when admin leaves but guests remain."""
        room_id = "test-room"

        # Create mock websockets for guests
        guest_ws1 = Mock()
        guest_ws1.state.user = "guest:abc123"
        guest_ws2 = Mock()
        guest_ws2.state.user = "guest:def456"

        mock_ws_manager.rooms[room_id] = {guest_ws1, guest_ws2}

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify admin_left_at was set
        assert mock_room.admin_left_at is not None
        assert isinstance(mock_room.admin_left_at, datetime)
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_left_when_only_authenticated_users_remain(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin_left_at is set when admin leaves but authenticated users remain."""
        room_id = "test-room"
        mock_room.owner_id = 100

        # Create mock websockets for authenticated users (not the admin)
        auth_ws1 = Mock()
        auth_ws1.state.user = "200"  # Different user ID, not the owner
        auth_ws2 = Mock()
        auth_ws2.state.user = "300"

        mock_ws_manager.rooms[room_id] = {auth_ws1, auth_ws2}

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify admin_left_at was set (THIS IS THE BUG FIX)
        assert mock_room.admin_left_at is not None
        assert isinstance(mock_room.admin_left_at, datetime)
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_present_clears_admin_left_at(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin_left_at is cleared when admin rejoins."""
        room_id = "test-room"
        mock_room.owner_id = 100
        mock_room.admin_left_at = datetime.utcnow()  # Admin was previously marked as left

        # Create mock websocket for admin
        admin_ws = Mock()
        admin_ws.state.user = "100"  # Owner ID

        mock_ws_manager.rooms[room_id] = {admin_ws}

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify admin_left_at was cleared
        assert mock_room.admin_left_at is None
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_present_does_not_set_admin_left_at(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin_left_at is NOT set when admin is present."""
        room_id = "test-room"
        mock_room.owner_id = 100
        mock_room.admin_left_at = None

        # Create mock websocket for admin and a guest
        admin_ws = Mock()
        admin_ws.state.user = "100"  # Owner ID
        guest_ws = Mock()
        guest_ws.state.user = "guest:abc123"

        mock_ws_manager.rooms[room_id] = {admin_ws, guest_ws}

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify admin_left_at remains None
        assert mock_room.admin_left_at is None
        # Commit should NOT be called since no changes were made
        assert not mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_left_at_not_reset_if_already_set(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin_left_at is not updated if already set and admin still absent."""
        room_id = "test-room"
        mock_room.owner_id = 100
        original_timestamp = datetime(2025, 10, 21, 12, 0, 0)
        mock_room.admin_left_at = original_timestamp

        # Create mock websocket for guest
        guest_ws = Mock()
        guest_ws.state.user = "guest:abc123"

        mock_ws_manager.rooms[room_id] = {guest_ws}

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify admin_left_at was NOT changed
        assert mock_room.admin_left_at == original_timestamp
        # Commit should NOT be called since no changes were made
        assert not mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_check_handles_room_not_found(self, mock_ws_manager, mock_db_session):
        """Test that admin check handles missing room gracefully."""
        room_id = "nonexistent-room"

        # Mock database query to return None
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            # Should not raise exception
            await mock_ws_manager._do_admin_check(room_id)

        # Should not commit anything
        assert not mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_admin_check_handles_invalid_user_id(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin check handles invalid user IDs gracefully."""
        room_id = "test-room"
        mock_room.owner_id = 100

        # Create mock websocket with invalid user ID
        invalid_ws = Mock()
        invalid_ws.state.user = "not-a-number"

        mock_ws_manager.rooms[room_id] = {invalid_ws}

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Should mark admin as left since invalid ID is not the admin
        assert mock_room.admin_left_at is not None

    @pytest.mark.asyncio
    async def test_admin_check_logs_correctly(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that admin check logs the correct information."""
        room_id = "test-room"
        mock_room.owner_id = 100

        mock_ws_manager.rooms[room_id] = set()  # Empty room

        # Mock database query
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_room

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._do_admin_check(room_id)

        # Verify logging was called
        assert mock_ws_manager.log.info.called
        # Check that admin_left was logged
        log_calls = [call[0][0] for call in mock_ws_manager.log.info.call_args_list]
        assert "admin_left" in log_calls or "admin_check_complete" in log_calls


class TestWSManagerDebouncing:
    """Test suite for admin presence check debouncing."""

    @pytest.fixture
    def mock_ws_manager(self):
        """Create a mock WebSocket manager."""
        from api.ws_manager import WSManager
        manager = WSManager(
            redis_url="redis://localhost:6379",
            mt_base_url="http://localhost:8000"
        )
        manager._pending_admin_checks = {}
        manager.log = Mock()
        return manager

    @pytest.mark.asyncio
    async def test_admin_check_debouncing(self, mock_ws_manager):
        """Test that rapid admin checks are debounced."""
        room_id = "test-room"

        with patch.object(mock_ws_manager, '_do_admin_check', new_callable=AsyncMock) as mock_do_check:
            # Call check multiple times rapidly
            await mock_ws_manager._check_admin_presence(room_id)
            await mock_ws_manager._check_admin_presence(room_id)
            await mock_ws_manager._check_admin_presence(room_id)

            # Give time for the debounced check to execute
            import asyncio
            await asyncio.sleep(3.5)

            # Should only call _do_admin_check once due to debouncing
            assert mock_do_check.call_count == 1
            mock_do_check.assert_called_with(room_id)

    @pytest.mark.asyncio
    async def test_admin_check_cancels_pending_checks(self, mock_ws_manager):
        """Test that new admin checks cancel pending ones."""
        room_id = "test-room"

        with patch.object(mock_ws_manager, '_do_admin_check', new_callable=AsyncMock):
            # Start first check
            await mock_ws_manager._check_admin_presence(room_id)
            first_task = mock_ws_manager._pending_admin_checks.get(room_id)

            # Start second check (should cancel first)
            await mock_ws_manager._check_admin_presence(room_id)
            second_task = mock_ws_manager._pending_admin_checks.get(room_id)

            # Verify first task was cancelled
            assert first_task.cancelled() or first_task != second_task
            assert second_task is not None

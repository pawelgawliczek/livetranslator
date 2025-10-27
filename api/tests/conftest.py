"""
Shared pytest fixtures for LiveTranslator tests.

This module provides common fixtures for:
- Database sessions (test database with automatic cleanup)
- Redis connections (test Redis instance)
- Mock services (external API mocks)
- WebSocket managers
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import Mock, AsyncMock
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set TEST_POSTGRES_DSN for all tests
os.environ.setdefault(
    "TEST_POSTGRES_DSN",
    "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test"
)


# Database Fixtures
@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """Create a test database engine."""
    test_db_dsn = os.getenv("TEST_POSTGRES_DSN")
    engine = create_async_engine(test_db_dsn, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db_session(test_db_engine):
    """
    Create a test database session with automatic cleanup.

    Each test gets a fresh session, and all data is cleaned up before and after the test.
    """
    AsyncTestSession = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with AsyncTestSession() as session:
        # Clean up all data BEFORE the test
        try:
            await session.execute(
                text("TRUNCATE users, rooms, devices, room_participants, "
                     "room_costs, room_archive CASCADE")
            )
            await session.commit()
        except Exception as e:
            print(f"Pre-test cleanup error: {e}")
            await session.rollback()

        yield session

        # Clean up all data after the test
        try:
            await session.execute(
                text("TRUNCATE users, rooms, devices, room_participants, "
                     "room_costs, room_archive CASCADE")
            )
            await session.commit()
        except Exception as e:
            print(f"Post-test cleanup error: {e}")
            await session.rollback()


# Redis Fixtures
@pytest.fixture(scope="function")
def mock_redis():
    """Create a mock Redis client for testing."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.hget = AsyncMock(return_value=None)
    redis.hset = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})
    redis.hdel = AsyncMock()
    redis.setex = AsyncMock()
    redis.publish = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    redis.scan_iter = AsyncMock(return_value=iter([]))

    # Mock pubsub
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()

    async def mock_listen():
        """Mock async generator for pubsub messages."""
        yield {"type": "subscribe"}

    pubsub.listen = mock_listen
    redis.pubsub = Mock(return_value=pubsub)

    return redis


# WebSocket Manager Fixtures
@pytest.fixture(scope="function")
def mock_ws_manager(mock_redis):
    """Create a mock WebSocket manager with Redis."""
    from api.ws_manager import WSManager

    manager = WSManager(
        redis_url="redis://localhost:6379",
        mt_base_url="http://localhost:8000"
    )
    manager.redis = mock_redis
    manager.rooms = {}
    manager.log = Mock()
    manager.broadcast = AsyncMock()

    return manager


# External Service Mocks
@pytest.fixture(scope="function")
def mock_google_stt():
    """Mock Google STT service."""
    mock = AsyncMock()
    mock.transcribe = AsyncMock(return_value={
        "text": "test transcription",
        "confidence": 0.95
    })
    return mock


@pytest.fixture(scope="function")
def mock_deepgram_stt():
    """Mock Deepgram STT service."""
    mock = AsyncMock()
    mock.transcribe = AsyncMock(return_value={
        "text": "test transcription",
        "confidence": 0.95
    })
    return mock


@pytest.fixture(scope="function")
def mock_mt_service():
    """Mock Machine Translation service."""
    mock = AsyncMock()
    mock.translate = AsyncMock(return_value={
        "translated_text": "test translation",
        "source_language": "en",
        "target_language": "es"
    })
    return mock


# User Fixtures
@pytest_asyncio.fixture(scope="function")
async def test_user(test_db_session):
    """Create a test user."""
    from api.models import User

    user = User(
        email="test@example.com",
        password_hash="hashed"
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_user(test_db_session):
    """Create an admin test user."""
    from api.models import User

    user = User(
        email="admin@example.com",
        password_hash="hashed",
        is_admin=True
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


# Room Fixtures
@pytest_asyncio.fixture(scope="function")
async def test_room(test_db_session, test_user):
    """Create a test room."""
    from api.models import Room

    room = Room(
        code="test-room",
        owner_id=test_user.id,
        recording=False,
        is_public=False,
        requires_login=False,
        max_participants=10
    )
    test_db_session.add(room)
    await test_db_session.commit()
    await test_db_session.refresh(room)
    return room


# Pytest Configuration
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Ensure TEST_POSTGRES_DSN is set
    if not os.getenv("TEST_POSTGRES_DSN"):
        os.environ["TEST_POSTGRES_DSN"] = (
            "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@"
            "postgres:5432/livetranslator_test"
        )


def pytest_collection_modifyitems(config, items):
    """
    Modify test items during collection.

    Adds markers to tests based on naming conventions.
    """
    for item in items:
        # Add integration marker to integration test files
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # Add unit marker to test files without integration/e2e
        elif "e2e" not in item.nodeid and "integration" not in item.nodeid:
            item.add_marker(pytest.mark.unit)

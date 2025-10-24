"""
Global pytest fixtures and configuration for LiveTranslator tests.

This file provides shared fixtures for:
- Test database setup/teardown
- Test Redis connections
- Mock providers
- Test data factories
- WebSocket test clients
"""
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import redis.asyncio as aioredis
from redis.asyncio import Redis

# Test database configuration
TEST_DB_URL = "postgresql://lt_test_user:test_password_changeme@localhost:5433/livetranslator_test"
TEST_REDIS_URL = "redis://localhost:6380/5"


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_db_engine():
    """
    Create test database engine (session-scoped).
    Runs migrations once per test session.
    """
    engine = create_engine(TEST_DB_URL, echo=False)

    # TODO: Run database migrations here
    # from alembic import command
    # from alembic.config import Config
    # alembic_cfg = Config("alembic.ini")
    # command.upgrade(alembic_cfg, "head")

    yield engine

    # Cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def test_db_session(test_db_engine) -> Generator[Session, None, None]:
    """
    Create isolated test database session with automatic rollback.
    Each test gets a clean database state.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    # Rollback transaction - no data persists between tests
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def clean_test_db(test_db_engine):
    """
    Clean all tables in test database.
    Use this for integration tests that need a fresh database.
    """
    with test_db_engine.connect() as conn:
        # Truncate all tables
        conn.execute(text("TRUNCATE TABLE users, rooms, segments, translations, room_costs CASCADE"))
        conn.commit()

    yield

    # Cleanup after test
    with test_db_engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE users, rooms, segments, translations, room_costs CASCADE"))
        conn.commit()


# ============================================================================
# Redis Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def test_redis() -> AsyncGenerator[Redis, None]:
    """
    Create test Redis connection with automatic cleanup.
    Flushes database after each test.
    """
    redis = await aioredis.from_url(TEST_REDIS_URL, decode_responses=True)

    yield redis

    # Cleanup all test keys
    await redis.flushdb()
    await redis.close()


@pytest.fixture(scope="function")
async def clean_test_redis():
    """
    Clean test Redis database before and after test.
    """
    redis = await aioredis.from_url(TEST_REDIS_URL, decode_responses=True)

    # Clean before test
    await redis.flushdb()

    yield redis

    # Clean after test
    await redis.flushdb()
    await redis.close()


# ============================================================================
# Mock Provider Fixtures
# ============================================================================

@pytest.fixture
def mock_stt_response():
    """Mock STT provider response."""
    return {
        "type": "stt_final",
        "segment_id": 1,
        "text": "This is a test transcription",
        "lang": "en",
        "final": True,
        "processing": False,
        "speaker": "test@example.com",
        "ts_iso": "2025-10-24T12:00:00.000000",
        "provider": "mock"
    }


@pytest.fixture
def mock_mt_response():
    """Mock MT provider response."""
    return {
        "type": "translation_final",
        "segment_id": 1,
        "text": "To jest testowa transkrypcja",
        "src": "en",
        "tgt": "pl",
        "final": True,
        "ts_iso": "2025-10-24T12:00:01.000000",
        "provider": "mock"
    }


# ============================================================================
# Test Data Factories
# ============================================================================

@pytest.fixture
def create_test_user(test_db_session):
    """Factory to create test users."""
    from api.models import User

    def _create_user(email="test@example.com", password_hash="hashed", **kwargs):
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=kwargs.get("display_name", "Test User"),
            preferred_lang=kwargs.get("preferred_lang", "en"),
            is_admin=kwargs.get("is_admin", False)
        )
        test_db_session.add(user)
        test_db_session.commit()
        test_db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def create_test_room(test_db_session):
    """Factory to create test rooms."""
    from api.models import Room

    def _create_room(code="test-room", owner_id=1, **kwargs):
        room = Room(
            code=code,
            owner_id=owner_id,
            is_public=kwargs.get("is_public", False),
            requires_login=kwargs.get("requires_login", False),
            max_participants=kwargs.get("max_participants", 10)
        )
        test_db_session.add(room)
        test_db_session.commit()
        test_db_session.refresh(room)
        return room

    return _create_room


# ============================================================================
# WebSocket Test Fixtures
# ============================================================================

@pytest.fixture
async def websocket_test_client():
    """Create WebSocket test client for testing real-time communication."""
    import websockets

    async def _connect(room_code="test-room", token=None):
        uri = f"ws://localhost:9004/ws/rooms/{room_code}"
        if token:
            uri += f"?token={token}"

        return await websockets.connect(uri)

    return _connect


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Test Markers and Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Create logs directory if it doesn't exist
    import os
    os.makedirs("tests/logs", exist_ok=True)


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on location."""
    for item in items:
        # Auto-mark based on path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Auto-mark based on test name
        if "websocket" in item.name.lower():
            item.add_marker(pytest.mark.websocket)
        if "database" in item.name.lower() or "db" in item.name.lower():
            item.add_marker(pytest.mark.database)
        if "redis" in item.name.lower():
            item.add_marker(pytest.mark.redis)

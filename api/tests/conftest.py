"""
Shared pytest fixtures for LiveTranslator tests.

This module provides common fixtures for:
- Database sessions (test database with automatic cleanup)
- Redis connections (test Redis instance)
- Mock services (external API mocks)
- WebSocket managers
"""

import os
import sys
import subprocess
import pytest
import pytest_asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Set TEST_POSTGRES_DSN for all tests
os.environ.setdefault(
    "TEST_POSTGRES_DSN",
    "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test"
)

# Track if migrations have been verified this session
_migrations_verified = False


def verify_test_database_schema():
    """
    Verify test database has all migrations applied.
    Runs once per test session.
    """
    global _migrations_verified

    if _migrations_verified:
        return

    print("\n🔍 Verifying test database schema...")

    # Run migration script to check and apply migrations
    result = subprocess.run(
        [
            sys.executable,
            "/app/scripts/db/migrate.py",
            "--database", "livetranslator_test",
            "--user", "lt_user",
            "--password", os.getenv("POSTGRES_PASSWORD", "CHANGE_ME_BEFORE_DEPLOY"),
            "--host", "postgres"
        ],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"\n❌ Failed to apply migrations:\n{result.stdout}\n{result.stderr}")
        raise RuntimeError("Test database migration failed")

    # Check if there were any pending migrations
    if "Pending: 0" in result.stdout or "Database is up to date" in result.stdout:
        print("✅ Test database schema is up to date")
    else:
        print("✅ Applied pending migrations to test database")

    _migrations_verified = True


# Session-scoped fixture to verify migrations once
@pytest_asyncio.fixture(scope="session")
async def verify_migrations():
    """Session-scoped fixture to verify migrations once before all tests."""
    verify_test_database_schema()

    # Ensure seed data exists after migrations
    test_db_dsn = os.getenv("TEST_POSTGRES_DSN")
    engine = create_async_engine(test_db_dsn, echo=False)
    async with engine.begin() as conn:
        # Insert subscription tiers seed data
        await conn.execute(text("""
            INSERT INTO subscription_tiers (tier_name, display_name, monthly_price_usd, monthly_quota_hours, features, provider_tier, stripe_price_id, apple_product_id)
            VALUES
            ('free', 'Free', 0, 0.167, '["10 minutes per month", "Apple STT/MT/TTS (iOS)", "Speechmatics STT (Web)", "Browser Web Speech API (Web)", "Basic support"]', 'free', NULL, NULL),
            ('plus', 'Plus', 29, 2, '["2 hours per month", "Premium STT providers", "Premium MT providers", "Client-side TTS only", "Email support", "History export (PDF/TXT)"]', 'standard', 'price_plus_monthly_prod', 'com.livetranslator.plus.monthly'),
            ('pro', 'Pro', 199, 10, '["10 hours per month", "All premium providers", "Server-side TTS (Google/AWS/Azure)", "Priority support", "Advanced analytics", "API access", "History export (PDF/TXT)"]', 'premium', 'price_pro_monthly_prod', 'com.livetranslator.pro.monthly')
            ON CONFLICT (tier_name) DO NOTHING;
        """))

        # Insert credit packages seed data
        await conn.execute(text("""
            INSERT INTO credit_packages (package_name, display_name, hours, price_usd, discount_percent, sort_order, stripe_price_id, apple_product_id)
            VALUES
            ('1hr', '1 Hour', 1, 5, 0, 1, 'price_1hr_prod', 'com.livetranslator.credits.1hr'),
            ('4hr', '4 Hours', 4, 19, 5, 2, 'price_4hr_prod', 'com.livetranslator.credits.4hr'),
            ('8hr', '8 Hours (Best Value!)', 8, 35, 12.5, 3, 'price_8hr_prod', 'com.livetranslator.credits.8hr'),
            ('20hr', '20 Hours (Enterprise)', 20, 80, 20, 4, 'price_20hr_prod', 'com.livetranslator.credits.20hr')
            ON CONFLICT DO NOTHING;
        """))
    await engine.dispose()

    yield


# Database Fixtures
@pytest_asyncio.fixture(scope="function")
async def test_db_engine(verify_migrations):
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
    print("\n🔧 Creating test_db_session fixture...")
    AsyncTestSession = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with AsyncTestSession() as session:
        # Clean up all data BEFORE the test (preserve schema_migrations and seed data)
        try:
            # Get all table names dynamically (excluding schema_migrations and seed data tables)
            result = await session.execute(
                text("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename NOT IN ('schema_migrations', 'subscription_tiers', 'credit_packages')
                    ORDER BY tablename;
                """)
            )
            tables = [row[0] for row in result.fetchall()]

            if tables:
                await session.execute(
                    text(f"TRUNCATE {', '.join(tables)} CASCADE")
                )
                await session.commit()
        except Exception as e:
            print(f"Pre-test cleanup error: {e}")
            await session.rollback()

        # ALWAYS re-seed static data after cleanup (CASCADE can delete seed data via FK constraints)
        # Note: Re-seeding is required because TRUNCATE ... CASCADE can delete seed data
        try:
            from api.models import SubscriptionTier, CreditPackage
            # Use raw SQL with ON CONFLICT to ensure data exists
            await session.execute(text("""
                INSERT INTO subscription_tiers (tier_name, display_name, monthly_price_usd, monthly_quota_hours, features, provider_tier, stripe_price_id, apple_product_id)
                VALUES
                ('free', 'Free', 0, 0.17, '["10 minutes per month"]'::jsonb, 'free', NULL, NULL),
                ('plus', 'Plus', 29, 2.00, '["2 hours per month"]'::jsonb, 'standard', 'price_plus_monthly_prod', 'com.livetranslator.plus.monthly'),
                ('pro', 'Pro', 199, 10.00, '["10 hours per month"]'::jsonb, 'premium', 'price_pro_monthly_prod', 'com.livetranslator.pro.monthly')
                ON CONFLICT (tier_name) DO UPDATE SET
                    monthly_quota_hours = EXCLUDED.monthly_quota_hours,
                    display_name = EXCLUDED.display_name;
            """))
            await session.execute(text("""
                INSERT INTO credit_packages (package_name, display_name, hours, price_usd, discount_percent, sort_order, stripe_price_id, apple_product_id)
                VALUES
                ('1hr', '1 Hour', 1, 5, 0, 1, 'price_1hr_prod', 'com.livetranslator.credits.1hr'),
                ('4hr', '4 Hours', 4, 19, 5, 2, 'price_4hr_prod', 'com.livetranslator.credits.4hr'),
                ('8hr', '8 Hours (Best Value!)', 8, 35, 12.5, 3, 'price_8hr_prod', 'com.livetranslator.credits.8hr'),
                ('20hr', '20 Hours (Enterprise)', 20, 80, 20, 4, 'price_20hr_prod', 'com.livetranslator.credits.20hr')
                ON CONFLICT (package_name) DO UPDATE SET
                    hours = EXCLUDED.hours,
                    price_usd = EXCLUDED.price_usd;
            """))
            await session.commit()
            # Force expire to ensure fresh read
            session.expire_all()
        except Exception as e:
            import sys
            print(f"❌ Test fixture re-seed failed: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc()
            await session.rollback()
            raise

        yield session

        # Clean up all data after the test (preserve schema_migrations and seed data)
        try:
            # Get all table names dynamically (excluding schema_migrations and seed data tables)
            result = await session.execute(
                text("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename NOT IN ('schema_migrations', 'subscription_tiers', 'credit_packages')
                    ORDER BY tablename;
                """)
            )
            tables = [row[0] for row in result.fetchall()]

            if tables:
                await session.execute(
                    text(f"TRUNCATE {', '.join(tables)} CASCADE")
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


# Seed data fixture (ensures subscription_tiers and credit_packages exist)
@pytest_asyncio.fixture(scope="function")
async def seed_data(test_db_session):
    """Ensure seed data exists for tests that need subscription tiers or credit packages."""
    from api.models import SubscriptionTier, CreditPackage
    try:
        # Check if subscription tiers exist
        result = await test_db_session.execute(select(SubscriptionTier))
        tiers = result.scalars().all()

        if not tiers:
            # Insert seed data using ORM models
            free_tier = SubscriptionTier(
                tier_name="free",
                display_name="Free",
                monthly_price_usd=Decimal("0"),
                monthly_quota_hours=Decimal("0.167"),
                features=["10 minutes per month"],
                provider_tier="free"
            )
            plus_tier = SubscriptionTier(
                tier_name="plus",
                display_name="Plus",
                monthly_price_usd=Decimal("29"),
                monthly_quota_hours=Decimal("2"),
                features=["2 hours per month"],
                provider_tier="standard",
                stripe_price_id="price_plus_monthly_prod",
                apple_product_id="com.livetranslator.plus.monthly"
            )
            pro_tier = SubscriptionTier(
                tier_name="pro",
                display_name="Pro",
                monthly_price_usd=Decimal("199"),
                monthly_quota_hours=Decimal("10"),
                features=["10 hours per month"],
                provider_tier="premium",
                stripe_price_id="price_pro_monthly_prod",
                apple_product_id="com.livetranslator.pro.monthly"
            )
            test_db_session.add_all([free_tier, plus_tier, pro_tier])

            # Insert credit packages
            pkg_1hr = CreditPackage(
                package_name="1hr",
                display_name="1 Hour",
                hours=Decimal("1"),
                price_usd=Decimal("5"),
                discount_percent=Decimal("0"),
                sort_order=1,
                stripe_price_id="price_1hr_prod",
                apple_product_id="com.livetranslator.credits.1hr"
            )
            pkg_4hr = CreditPackage(
                package_name="4hr",
                display_name="4 Hours",
                hours=Decimal("4"),
                price_usd=Decimal("19"),
                discount_percent=Decimal("5"),
                sort_order=2,
                stripe_price_id="price_4hr_prod",
                apple_product_id="com.livetranslator.credits.4hr"
            )
            test_db_session.add_all([pkg_1hr, pkg_4hr])

            await test_db_session.commit()
    except Exception as e:
        print(f"Seed data fixture error: {e}")
        await test_db_session.rollback()

    return True


# User Fixtures
@pytest_asyncio.fixture(scope="function")
async def test_user(test_db_session):
    """Create a test user."""
    from api.models import User
    import uuid

    user = User(
        email=f"user-{uuid.uuid4().hex[:8]}@test.com",
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
    import uuid

    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
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


# FastAPI TestClient Fixtures
@pytest.fixture(scope="function")
def test_client():
    """Create a FastAPI TestClient for synchronous HTTP tests."""
    from fastapi.testclient import TestClient
    from api.main import app

    # Disable rate limiters for testing
    try:
        from api.routers.payments import limiter
        limiter._enabled = False
    except:
        pass

    client = TestClient(app)
    yield client

    # Re-enable rate limiters after test
    try:
        from api.routers.payments import limiter
        limiter._enabled = True
    except:
        pass


@pytest.fixture(scope="function")
def test_db():
    """Create sync database session for integration tests."""
    from api.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture(scope="function")
def test_user_token(test_db):
    """Create test user and return JWT token."""
    from api.models import User, UserSubscription, SubscriptionTier
    from api.auth import _issue
    from datetime import datetime, timedelta
    from sqlalchemy import select
    import uuid

    # Get existing free tier
    free_tier = test_db.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    ).scalar_one_or_none()

    if not free_tier:
        # Create free tier if it doesn't exist
        free_tier = SubscriptionTier(
            tier_name="free",
            stripe_price_id=None,
            price_usd=0.0,
            hours_included=1.0,
            recording_enabled=False
        )
        test_db.add(free_tier)
        test_db.commit()
        test_db.refresh(free_tier)

    # Create test user with unique email
    unique_email = f'test-{uuid.uuid4().hex[:8]}@example.com'
    user = User(
        email=unique_email,
        password_hash='hashed',
        display_name='Test User',
        preferred_lang='en'
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Create subscription
    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30),
        status='active'
    )
    test_db.add(subscription)
    test_db.commit()

    # Generate token
    token = _issue(user)
    return token.access_token


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


# Additional fixtures for integration tests
@pytest.fixture(scope="function")
def client():
    """Alias for test_client (for compatibility)"""
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


@pytest.fixture(scope="function")
def db_session(test_db):
    """Alias for test_db (for compatibility)"""
    return test_db


@pytest.fixture(scope="function")
def admin_token(test_db):
    """Create admin user and return JWT token"""
    from api.models import User
    from api.auth import _issue
    import uuid

    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed",
        is_admin=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    token = _issue(user)
    return token.access_token


@pytest.fixture(scope="function")
def user_token(test_db):
    """Create regular user and return JWT token"""
    from api.models import User
    from api.auth import _issue
    import uuid

    user = User(
        email=f"user-{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed",
        is_admin=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    token = _issue(user)
    return token.access_token

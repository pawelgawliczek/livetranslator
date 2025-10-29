"""
Integration tests for Event model persistence.

Tests cover the critical bug that was missed:
- Event model CRUD operations
- Segment transcription and translation persistence
- Database schema alignment with SQLAlchemy model
- Error handling for missing/incorrect fields

This test would have caught the bug where Event model was missing columns:
segment_id, revision, is_final, src_lang, text, translated_text, created_at
"""

import pytest
import pytest_asyncio
import asyncpg
import os
import uuid
from datetime import datetime


POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator")


@pytest_asyncio.fixture
async def db_pool():
    """Create a database connection pool for testing."""
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', POSTGRES_DSN)
    if not match:
        pytest.skip("Invalid POSTGRES_DSN")

    user, password, host, port, database = match.groups()

    pool = await asyncpg.create_pool(
        user=user,
        password=password,
        host=host,
        port=int(port),
        database=database,
        min_size=1,
        max_size=5
    )

    yield pool

    await pool.close()


@pytest_asyncio.fixture
async def test_room(db_pool):
    """Create a test room and clean up after test."""
    # Use UUID to ensure uniqueness across parallel test runs
    unique_id = str(uuid.uuid4())[:8]
    room_code = f"t{unique_id}"  # Keep under 12 chars (t + 8 chars = 9 chars)
    test_email = f"test-{unique_id}@example.com"

    # Create test user (owner)
    owner_id = await db_pool.fetchval(
        "INSERT INTO users (email, password_hash, preferred_lang, is_admin) VALUES ($1, $2, $3, $4) RETURNING id",
        test_email, "hash", "en", False
    )

    # Create test room
    room_id = await db_pool.fetchval(
        "INSERT INTO rooms (code, owner_id, recording) VALUES ($1, $2, $3) RETURNING id",
        room_code, owner_id, False
    )

    yield {"code": room_code, "id": room_id, "owner_id": owner_id}

    # Cleanup
    await db_pool.execute("DELETE FROM events WHERE room_id = $1", room_id)
    await db_pool.execute("DELETE FROM rooms WHERE id = $1", room_id)
    await db_pool.execute("DELETE FROM users WHERE id = $1", owner_id)


class TestEventModelPersistence:
    """Test Event model persistence - would have caught the missing columns bug."""

    @pytest.mark.asyncio
    async def test_event_table_has_required_columns(self, db_pool):
        """Verify Event table has all required columns (regression test)."""
        # Query table schema
        columns = await db_pool.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'events'
            ORDER BY ordinal_position
        """)

        column_names = {col['column_name'] for col in columns}

        # These are the columns that were missing from the SQLAlchemy model
        required_columns = {
            'id', 'room_id', 'segment_id', 'revision', 'is_final',
            'src_lang', 'text', 'translated_text', 'created_at'
        }

        missing_columns = required_columns - column_names
        assert not missing_columns, f"Missing required columns: {missing_columns}"

    @pytest.mark.asyncio
    async def test_save_stt_event(self, db_pool, test_room):
        """Test saving STT event with all required fields."""
        # Insert event using raw SQL (simulating what persistence.py does)
        event_id = await db_pool.fetchval("""
            INSERT INTO events (
                room_id, segment_id, revision, is_final,
                src_lang, text, translated_text, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, test_room['id'], 1, 5, False, "pl", "Witaj świecie", "", datetime.utcnow())

        assert event_id is not None, "Failed to insert event"

        # Verify event was saved correctly
        event = await db_pool.fetchrow(
            "SELECT * FROM events WHERE id = $1", event_id
        )

        assert event['room_id'] == test_room['id']
        assert event['segment_id'] == 1
        assert event['revision'] == 5
        assert event['is_final'] is False
        assert event['src_lang'] == "pl"
        assert event['text'] == "Witaj świecie"
        assert event['translated_text'] == ""

    @pytest.mark.asyncio
    async def test_save_final_event_with_translation(self, db_pool, test_room):
        """Test saving final event with translation."""
        event_id = await db_pool.fetchval("""
            INSERT INTO events (
                room_id, segment_id, revision, is_final,
                src_lang, text, translated_text, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, test_room['id'], 2, 12, True, "pl", "Dziękuję bardzo", "Thank you very much", datetime.utcnow())

        assert event_id is not None

        event = await db_pool.fetchrow(
            "SELECT * FROM events WHERE id = $1", event_id
        )

        assert event['is_final'] is True
        assert event['src_lang'] == "pl"
        assert event['text'] == "Dziękuję bardzo"
        assert event['translated_text'] == "Thank you very much"

    @pytest.mark.asyncio
    async def test_query_events_by_segment(self, db_pool, test_room):
        """Test querying events by segment_id."""
        # Insert multiple revisions for same segment
        for revision in range(1, 4):
            await db_pool.execute("""
                INSERT INTO events (
                    room_id, segment_id, revision, is_final,
                    src_lang, text, translated_text, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """, test_room['id'], 5, revision, False, "en", f"Text revision {revision}", "", datetime.utcnow())

        # Query all events for segment 5
        events = await db_pool.fetch("""
            SELECT * FROM events
            WHERE room_id = $1 AND segment_id = $2
            ORDER BY revision
        """, test_room['id'], 5)

        assert len(events) == 3
        assert events[0]['revision'] == 1
        assert events[1]['revision'] == 2
        assert events[2]['revision'] == 3

    @pytest.mark.asyncio
    async def test_final_event_flag(self, db_pool, test_room):
        """Test is_final flag filtering."""
        # Insert mix of partial and final events
        await db_pool.execute("""
            INSERT INTO events (room_id, segment_id, revision, is_final, src_lang, text, translated_text, created_at)
            VALUES
                ($1, 10, 1, false, 'en', 'Hello', '', NOW()),
                ($1, 10, 5, false, 'en', 'Hello world', '', NOW()),
                ($1, 10, 10, true, 'en', 'Hello world!', 'Bonjour le monde!', NOW())
        """, test_room['id'])

        # Query only final events
        final_events = await db_pool.fetch("""
            SELECT * FROM events
            WHERE room_id = $1 AND is_final = true
        """, test_room['id'])

        assert len(final_events) == 1
        assert final_events[0]['revision'] == 10
        assert final_events[0]['text'] == 'Hello world!'

    @pytest.mark.asyncio
    async def test_empty_text_handling(self, db_pool, test_room):
        """Test that empty text is saved correctly (regression for Speechmatics bug)."""
        # This simulates what happened when Speechmatics returned empty transcriptions
        event_id = await db_pool.fetchval("""
            INSERT INTO events (
                room_id, segment_id, revision, is_final,
                src_lang, text, translated_text, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, test_room['id'], 12, 15, True, "auto", "", "", datetime.utcnow())

        assert event_id is not None

        event = await db_pool.fetchrow(
            "SELECT * FROM events WHERE id = $1", event_id
        )

        # Should save empty strings, not NULL
        assert event['text'] == ""
        assert event['translated_text'] == ""
        assert event['src_lang'] == "auto"


class TestPersistenceModule:
    """Test persistence.py functions using SQLAlchemy models."""

    @pytest.mark.asyncio
    async def test_save_stt_event_via_persistence(self, db_pool, test_room):
        """Test save_stt_event function from persistence.py."""
        # Import after DB is ready
        from api.persistence import save_stt_event

        # This call would have failed with the bug: 'segment_id' is an invalid keyword
        save_stt_event(
            room_code=test_room['code'],
            segment_id=3,
            revision=7,
            is_final=False,
            src_lang="pl",
            text="Testowy tekst",
            translated_text=""
        )

        # Verify it was saved
        event = await db_pool.fetchrow("""
            SELECT * FROM events
            WHERE room_id = $1 AND segment_id = 3
        """, test_room['id'])

        assert event is not None
        assert event['text'] == "Testowy tekst"
        assert event['src_lang'] == "pl"

    @pytest.mark.asyncio
    async def test_upsert_final_translation_via_persistence(self, db_pool, test_room):
        """Test upsert_final_translation function from persistence.py."""
        from api.persistence import upsert_final_translation

        # Save initial final event
        await db_pool.execute("""
            INSERT INTO events (room_id, segment_id, revision, is_final, src_lang, text, translated_text, created_at)
            VALUES ($1, 4, 10, true, 'pl', 'Pierwotny tekst', '', NOW())
        """, test_room['id'])

        # Upsert translation
        upsert_final_translation(
            room_code=test_room['code'],
            segment_id=4,
            src_lang="pl",
            text="Pierwotny tekst",
            translated_text="Original text"
        )

        # Verify translation was added
        event = await db_pool.fetchrow("""
            SELECT * FROM events
            WHERE room_id = $1 AND segment_id = 4 AND is_final = true
        """, test_room['id'])

        assert event['translated_text'] == "Original text"

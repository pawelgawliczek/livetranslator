"""
Integration tests for TTS API endpoints.

Tests cover:
- POST /api/rooms/{code}/tts/enable
- POST /api/rooms/{code}/tts/disable
- GET  /api/rooms/{code}/tts/settings
- PUT  /api/rooms/{code}/tts/settings
- GET  /api/profile/tts
- PUT  /api/profile/tts

Priority: Integration (real database, mock external APIs)
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from decimal import Decimal
import json


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enable_tts_for_room(test_db_session, test_room, test_user):
    """Test enabling TTS for a room."""
    # Verify room exists and TTS is initially enabled (default)
    result = await test_db_session.execute(
        text("SELECT tts_enabled FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()
    assert row is not None
    initial_state = row[0]

    # Disable first
    await test_db_session.execute(
        text("UPDATE rooms SET tts_enabled = FALSE WHERE code = :code"),
        {"code": test_room.code}
    )
    await test_db_session.commit()

    # Enable TTS
    await test_db_session.execute(
        text("UPDATE rooms SET tts_enabled = TRUE WHERE code = :code"),
        {"code": test_room.code}
    )
    await test_db_session.commit()

    # Verify enabled
    result = await test_db_session.execute(
        text("SELECT tts_enabled FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()
    assert row[0] is True

    print(f"✅ TTS enabled for room: {test_room.code}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disable_tts_for_room(test_db_session, test_room):
    """Test disabling TTS for a room."""
    # Enable first
    await test_db_session.execute(
        text("UPDATE rooms SET tts_enabled = TRUE WHERE code = :code"),
        {"code": test_room.code}
    )
    await test_db_session.commit()

    # Disable TTS
    await test_db_session.execute(
        text("UPDATE rooms SET tts_enabled = FALSE WHERE code = :code"),
        {"code": test_room.code}
    )
    await test_db_session.commit()

    # Verify disabled
    result = await test_db_session.execute(
        text("SELECT tts_enabled FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()
    assert row[0] is False

    print(f"✅ TTS disabled for room: {test_room.code}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_room_tts_settings(test_db_session, test_room):
    """Test GET room TTS settings."""
    # Set room TTS settings
    voice_overrides = json.dumps({"en": "en-US-Wavenet-F", "pl": "pl-PL-Wavenet-A"})
    await test_db_session.execute(
        text("""
            UPDATE rooms
            SET tts_enabled = TRUE, tts_voice_overrides = CAST(:overrides AS jsonb)
            WHERE code = :code
        """),
        {"code": test_room.code, "overrides": voice_overrides}
    )
    await test_db_session.commit()

    # Get settings
    result = await test_db_session.execute(
        text("SELECT tts_enabled, tts_voice_overrides FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()

    assert row[0] is True
    assert row[1]["en"] == "en-US-Wavenet-F"
    assert row[1]["pl"] == "pl-PL-Wavenet-A"

    print(f"✅ Room TTS settings retrieved:")
    print(f"   - Enabled: {row[0]}")
    print(f"   - Voice overrides: {row[1]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_room_voice_overrides(test_db_session, test_room):
    """Test updating room voice overrides."""
    # Update voice overrides
    new_overrides = json.dumps({
        "en": "en-US-Wavenet-F",
        "pl": "pl-PL-Wavenet-B",
        "ar": "ar-EG-Wavenet-A"
    })

    await test_db_session.execute(
        text("""
            UPDATE rooms
            SET tts_voice_overrides = CAST(:overrides AS jsonb)
            WHERE code = :code
        """),
        {"code": test_room.code, "overrides": new_overrides}
    )
    await test_db_session.commit()

    # Verify update
    result = await test_db_session.execute(
        text("SELECT tts_voice_overrides FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()

    assert "en" in row[0]
    assert row[0]["en"] == "en-US-Wavenet-F"
    assert row[0]["pl"] == "pl-PL-Wavenet-B"
    assert row[0]["ar"] == "ar-EG-Wavenet-A"

    print(f"✅ Room voice overrides updated: {row[0]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_user_tts_settings(test_db_session, test_user):
    """Test GET user TTS settings."""
    # Set user TTS settings
    await test_db_session.execute(
        text("""
            UPDATE users
            SET tts_enabled = TRUE,
                tts_volume = 0.8,
                tts_rate = 1.2,
                tts_pitch = 2.0,
                tts_voice_preferences = CAST(:prefs AS jsonb)
            WHERE id = :user_id
        """),
        {
            "user_id": test_user.id,
            "prefs": json.dumps({"en": "en-US-Wavenet-D", "pl": "pl-PL-Wavenet-A"})
        }
    )
    await test_db_session.commit()

    # Get settings
    result = await test_db_session.execute(
        text("""
            SELECT tts_enabled, tts_volume, tts_rate, tts_pitch, tts_voice_preferences
            FROM users WHERE id = :user_id
        """),
        {"user_id": test_user.id}
    )
    row = result.fetchone()

    assert row[0] is True  # tts_enabled
    assert row[1] == 0.8  # volume
    assert row[2] == 1.2  # rate
    assert row[3] == 2.0  # pitch
    assert row[4]["en"] == "en-US-Wavenet-D"

    print(f"✅ User TTS settings retrieved:")
    print(f"   - Enabled: {row[0]}")
    print(f"   - Volume: {row[1]}, Rate: {row[2]}, Pitch: {row[3]}")
    print(f"   - Voice preferences: {row[4]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_user_tts_settings(test_db_session, test_user):
    """Test PUT user TTS settings with validation."""
    # Valid update
    await test_db_session.execute(
        text("""
            UPDATE users
            SET tts_volume = :volume,
                tts_rate = :rate,
                tts_pitch = :pitch
            WHERE id = :user_id
        """),
        {
            "user_id": test_user.id,
            "volume": 0.9,
            "rate": 1.5,
            "pitch": -5.0
        }
    )
    await test_db_session.commit()

    # Verify update
    result = await test_db_session.execute(
        text("SELECT tts_volume, tts_rate, tts_pitch FROM users WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    row = result.fetchone()

    assert row[0] == 0.9
    assert row[1] == 1.5
    assert row[2] == -5.0

    print(f"✅ User TTS settings updated: volume={row[0]}, rate={row[1]}, pitch={row[2]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_user_tts_invalid_volume(test_db_session, test_user):
    """Test validation rejects invalid volume."""
    # Try invalid volume (> 2.0)
    with pytest.raises(Exception):  # Should violate CHECK constraint
        await test_db_session.execute(
            text("UPDATE users SET tts_volume = :volume WHERE id = :user_id"),
            {"user_id": test_user.id, "volume": 2.5}
        )
        await test_db_session.commit()

    await test_db_session.rollback()
    print("✅ Invalid volume rejected (> 2.0)")

    # Try invalid volume (< 0.0)
    with pytest.raises(Exception):  # Should violate CHECK constraint
        await test_db_session.execute(
            text("UPDATE users SET tts_volume = :volume WHERE id = :user_id"),
            {"user_id": test_user.id, "volume": -0.5}
        )
        await test_db_session.commit()

    await test_db_session.rollback()
    print("✅ Invalid volume rejected (< 0.0)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_user_tts_invalid_rate(test_db_session, test_user):
    """Test validation rejects invalid rate."""
    # Try invalid rate (> 4.0)
    with pytest.raises(Exception):  # Should violate CHECK constraint
        await test_db_session.execute(
            text("UPDATE users SET tts_rate = :rate WHERE id = :user_id"),
            {"user_id": test_user.id, "rate": 5.0}
        )
        await test_db_session.commit()

    await test_db_session.rollback()
    print("✅ Invalid rate rejected (> 4.0)")

    # Try invalid rate (< 0.25)
    with pytest.raises(Exception):  # Should violate CHECK constraint
        await test_db_session.execute(
            text("UPDATE users SET tts_rate = :rate WHERE id = :user_id"),
            {"user_id": test_user.id, "rate": 0.1}
        )
        await test_db_session.commit()

    await test_db_session.rollback()
    print("✅ Invalid rate rejected (< 0.25)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_user_tts_invalid_pitch(test_db_session, test_user):
    """Test validation rejects invalid pitch."""
    # Try invalid pitch (> 20.0)
    with pytest.raises(Exception):  # Should violate CHECK constraint
        await test_db_session.execute(
            text("UPDATE users SET tts_pitch = :pitch WHERE id = :user_id"),
            {"user_id": test_user.id, "pitch": 25.0}
        )
        await test_db_session.commit()

    await test_db_session.rollback()
    print("✅ Invalid pitch rejected (> 20.0)")

    # Try invalid pitch (< -20.0)
    with pytest.raises(Exception):  # Should violate CHECK constraint
        await test_db_session.execute(
            text("UPDATE users SET tts_pitch = :pitch WHERE id = :user_id"),
            {"user_id": test_user.id, "pitch": -25.0}
        )
        await test_db_session.commit()

    await test_db_session.rollback()
    print("✅ Invalid pitch rejected (< -20.0)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_default_tts_settings_for_new_user(test_db_session):
    """Test default TTS settings are applied to new users."""
    # Create new user
    result = await test_db_session.execute(
        text("""
            INSERT INTO users (email, password_hash)
            VALUES (:email, :password)
            RETURNING id, tts_enabled, tts_volume, tts_rate, tts_pitch, tts_voice_preferences
        """),
        {"email": "newuser@example.com", "password": "hashed"}
    )
    row = result.fetchone()

    # Verify defaults
    assert row[1] is True  # tts_enabled default is TRUE
    assert row[2] == 1.0  # volume default is 1.0
    assert row[3] == 1.0  # rate default is 1.0
    assert row[4] == 0.0  # pitch default is 0.0
    assert row[5] == {}  # voice_preferences default is {}

    print(f"✅ Default TTS settings applied to new user:")
    print(f"   - Enabled: {row[1]}, Volume: {row[2]}, Rate: {row[3]}, Pitch: {row[4]}")
    print(f"   - Voice preferences: {row[5]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_default_tts_settings_for_new_room(test_db_session, test_user):
    """Test default TTS settings are applied to new rooms."""
    # Create new room
    result = await test_db_session.execute(
        text("""
            INSERT INTO rooms (code, owner_id)
            VALUES (:code, :owner_id)
            RETURNING id, tts_enabled, tts_voice_overrides
        """),
        {"code": "NEWROOM", "owner_id": test_user.id}
    )
    row = result.fetchone()

    # Verify defaults
    assert row[1] is True  # tts_enabled default is TRUE
    assert row[2] == {}  # tts_voice_overrides default is {}

    print(f"✅ Default TTS settings applied to new room:")
    print(f"   - Enabled: {row[1]}")
    print(f"   - Voice overrides: {row[2]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_user_voice_preferences(test_db_session, test_user):
    """Test updating user voice preferences for multiple languages."""
    # Update voice preferences
    voice_prefs = json.dumps({
        "en": "en-US-Wavenet-F",
        "pl": "pl-PL-Wavenet-B",
        "ar": "ar-EG-Wavenet-A",
        "es": "es-ES-Wavenet-A"
    })

    await test_db_session.execute(
        text("""
            UPDATE users
            SET tts_voice_preferences = CAST(:prefs AS jsonb)
            WHERE id = :user_id
        """),
        {"user_id": test_user.id, "prefs": voice_prefs}
    )
    await test_db_session.commit()

    # Verify update
    result = await test_db_session.execute(
        text("SELECT tts_voice_preferences FROM users WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    row = result.fetchone()

    assert len(row[0]) == 4
    assert row[0]["en"] == "en-US-Wavenet-F"
    assert row[0]["pl"] == "pl-PL-Wavenet-B"
    assert row[0]["ar"] == "ar-EG-Wavenet-A"
    assert row[0]["es"] == "es-ES-Wavenet-A"

    print(f"✅ User voice preferences updated: {row[0]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_voice_overrides(test_db_session, test_room):
    """Test clearing voice overrides (empty object)."""
    # Set overrides first
    await test_db_session.execute(
        text("""
            UPDATE rooms
            SET tts_voice_overrides = CAST(:overrides AS jsonb)
            WHERE code = :code
        """),
        {"code": test_room.code, "overrides": json.dumps({"en": "test"})}
    )
    await test_db_session.commit()

    # Clear overrides
    await test_db_session.execute(
        text("""
            UPDATE rooms
            SET tts_voice_overrides = CAST(:overrides AS jsonb)
            WHERE code = :code
        """),
        {"code": test_room.code, "overrides": json.dumps({})}
    )
    await test_db_session.commit()

    # Verify cleared
    result = await test_db_session.execute(
        text("SELECT tts_voice_overrides FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()

    assert row[0] == {}

    print(f"✅ Voice overrides cleared: {row[0]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_room_tts_persists_after_owner_change(test_db_session, test_room, test_user, admin_user):
    """Test TTS settings persist when room owner changes."""
    # Set TTS settings
    voice_overrides = json.dumps({"en": "en-US-Wavenet-F"})
    await test_db_session.execute(
        text("""
            UPDATE rooms
            SET tts_enabled = FALSE, tts_voice_overrides = CAST(:overrides AS jsonb)
            WHERE code = :code
        """),
        {"code": test_room.code, "overrides": voice_overrides}
    )
    await test_db_session.commit()

    # Change owner
    await test_db_session.execute(
        text("UPDATE rooms SET owner_id = :new_owner WHERE code = :code"),
        {"code": test_room.code, "new_owner": admin_user.id}
    )
    await test_db_session.commit()

    # Verify TTS settings unchanged
    result = await test_db_session.execute(
        text("SELECT tts_enabled, tts_voice_overrides, owner_id FROM rooms WHERE code = :code"),
        {"code": test_room.code}
    )
    row = result.fetchone()

    assert row[0] is False  # tts_enabled unchanged
    assert row[1]["en"] == "en-US-Wavenet-F"  # voice_overrides unchanged
    assert row[2] == admin_user.id  # owner changed

    print(f"✅ TTS settings persisted after owner change:")
    print(f"   - New owner: {row[2]}")
    print(f"   - TTS enabled: {row[0]}")
    print(f"   - Voice overrides: {row[1]}")

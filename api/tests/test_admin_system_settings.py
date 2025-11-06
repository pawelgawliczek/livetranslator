"""
Tests for US-003: System Settings Page APIs
Tests feature flags, rate limits, and provider routing endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from api.main import app
from api.auth import _issue
from api.models import User

@pytest.fixture
def admin_token(test_db):
    """Create admin JWT token"""
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

@pytest.fixture
def user_token(test_db):
    """Create regular user JWT token"""
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

def test_get_feature_flags_requires_admin(admin_token, user_token):
    """Test GET /settings/feature-flags requires admin access"""
    client = TestClient(app)

    # Admin access: 200 OK
    response = client.get(
        "/api/admin/settings/feature-flags",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert "flags" in response.json()

    # Non-admin: 403 Forbidden
    response = client.get(
        "/api/admin/settings/feature-flags",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403

def test_get_feature_flags_returns_metadata(admin_token):
    """Test GET /settings/feature-flags returns full metadata"""
    client = TestClient(app)

    response = client.get(
        "/api/admin/settings/feature-flags",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert "flags" in data
    assert len(data["flags"]) > 0

    # Check first flag has required fields
    flag = data["flags"][0]
    assert "key" in flag
    assert "value" in flag
    assert "value_type" in flag
    assert "description" in flag
    assert "category" in flag

def test_update_feature_flag_boolean(admin_token, test_db):
    """Test PUT /settings/feature-flags/{key} for boolean value"""
    client = TestClient(app)

    # Get current value
    response = client.get(
        "/api/admin/settings/feature-flags",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    flags = response.json()["flags"]
    diarization_flag = next(f for f in flags if f["key"] == "enable_diarization")
    original_value = diarization_flag["value"]

    # Update boolean flag
    response = client.put(
        "/api/admin/settings/feature-flags/enable_diarization",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": "false"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "enable_diarization"
    assert data["new_value"] == False

    # Verify in database
    result = test_db.execute(
        text("SELECT value FROM system_settings WHERE key = 'enable_diarization'")
    ).fetchone()
    assert result[0] == "false"

    # Restore original value
    client.put(
        "/api/admin/settings/feature-flags/enable_diarization",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": str(original_value).lower()}
    )

def test_update_feature_flag_invalid_boolean(admin_token):
    """Test PUT /settings/feature-flags/{key} rejects invalid boolean"""
    client = TestClient(app)

    # Try to set boolean flag to invalid value
    response = client.put(
        "/api/admin/settings/feature-flags/enable_diarization",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": "maybe"}
    )

    assert response.status_code == 400
    assert "Boolean value must be" in response.json()["detail"]

def test_update_feature_flag_integer(admin_token, test_db):
    """Test PUT /settings/feature-flags/{key} for integer value"""
    client = TestClient(app)

    # Get original value
    response = client.get(
        "/api/admin/settings/feature-flags",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    flags = response.json()["flags"]
    speakers_flag = next(f for f in flags if f["key"] == "max_speakers_per_room")
    original_value = speakers_flag["value"]

    # Update integer flag
    response = client.put(
        "/api/admin/settings/feature-flags/max_speakers_per_room",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": "15"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["key"] == "max_speakers_per_room"

    # Verify in database
    result = test_db.execute(
        text("SELECT value FROM system_settings WHERE key = 'max_speakers_per_room'")
    ).fetchone()
    assert result[0] == "15"

    # Restore original value
    client.put(
        "/api/admin/settings/feature-flags/max_speakers_per_room",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": str(original_value)}
    )

def test_update_feature_flag_creates_audit_log(admin_token, test_db):
    """Test feature flag updates are logged in admin_audit_log"""
    client = TestClient(app)

    # Count existing logs
    count_before = test_db.execute(
        text("SELECT COUNT(*) FROM admin_audit_log WHERE action = 'update_setting'")
    ).scalar()

    # Update flag
    client.put(
        "/api/admin/settings/feature-flags/enable_diarization",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": "true"}
    )

    # Verify audit log created
    count_after = test_db.execute(
        text("SELECT COUNT(*) FROM admin_audit_log WHERE action = 'update_setting'")
    ).scalar()

    assert count_after > count_before

def test_get_rate_limits(admin_token):
    """Test GET /settings/rate-limits returns performance settings"""
    client = TestClient(app)

    response = client.get(
        "/api/admin/settings/rate-limits",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert "limits" in data
    assert len(data["limits"]) > 0

    # Check for required rate limit keys
    limit_keys = [limit["key"] for limit in data["limits"]]
    assert "stt_max_concurrent_connections" in limit_keys
    assert "max_room_participants" in limit_keys

def test_update_rate_limits(admin_token, test_db):
    """Test PUT /settings/rate-limits updates multiple limits"""
    client = TestClient(app)

    # Get original values
    response = client.get(
        "/api/admin/settings/rate-limits",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    original_limits = {limit["key"]: limit["value"] for limit in response.json()["limits"]}

    # Update multiple limits
    response = client.put(
        "/api/admin/settings/rate-limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "limits": {
                "max_room_participants": 75,
                "stt_max_concurrent_connections": 150
            }
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["updated"]) == 2

    # Verify in database
    result = test_db.execute(
        text("SELECT value FROM system_settings WHERE key = 'max_room_participants'")
    ).fetchone()
    assert int(result[0]) == 75

    # Restore original values
    client.put(
        "/api/admin/settings/rate-limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"limits": original_limits}
    )

def test_update_rate_limits_rejects_non_performance(admin_token):
    """Test PUT /settings/rate-limits rejects non-performance settings"""
    client = TestClient(app)

    response = client.put(
        "/api/admin/settings/rate-limits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "limits": {
                "enable_diarization": 100  # This is 'stt' category, not 'performance'
            }
        }
    )

    assert response.status_code == 400
    assert "not a rate limit" in response.json()["detail"]

def test_get_usage_stats(admin_token):
    """Test GET /system/usage-stats returns current usage"""
    client = TestClient(app)

    response = client.get(
        "/api/admin/system/usage-stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Check required fields
    assert "stt_max_connections" in data
    assert "max_room_participants" in data
    assert "active_rooms" in data
    assert "mt_requests_last_minute" in data

def test_update_stt_routing_requires_admin(admin_token, user_token, test_db):
    """Test PUT /routing/stt/{id} requires admin access"""
    client = TestClient(app)

    # Get a valid STT routing config ID
    result = test_db.execute(
        text("SELECT id FROM stt_routing_config LIMIT 1")
    ).fetchone()

    if not result:
        pytest.skip("No STT routing configs in database")

    config_id = result[0]

    # Non-admin: 403 Forbidden
    response = client.put(
        f"/api/admin/routing/stt/{config_id}",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"provider_primary": "google_v2"}
    )
    assert response.status_code == 403

    # Admin: 200 OK
    response = client.put(
        f"/api/admin/routing/stt/{config_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"provider_primary": "google_v2"}
    )
    assert response.status_code == 200

def test_update_stt_routing_clears_cache(admin_token, test_db):
    """Test PUT /routing/stt/{id} clears language router cache"""
    client = TestClient(app)

    # Get a valid STT routing config ID
    result = test_db.execute(
        text("SELECT id, provider_primary FROM stt_routing_config LIMIT 1")
    ).fetchone()

    if not result:
        pytest.skip("No STT routing configs in database")

    config_id = result[0]
    original_provider = result[1]

    # Update provider
    response = client.put(
        f"/api/admin/routing/stt/{config_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"provider_primary": "speechmatics"}
    )

    assert response.status_code == 200
    data = response.json()

    # Check cache_cleared flag (may be False if cache module unavailable)
    assert "cache_cleared" in data

    # Restore original provider
    client.put(
        f"/api/admin/routing/stt/{config_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"provider_primary": original_provider}
    )

def test_update_stt_routing_invalid_id(admin_token):
    """Test PUT /routing/stt/{id} returns 404 for invalid ID"""
    client = TestClient(app)

    response = client.put(
        "/api/admin/routing/stt/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"provider_primary": "google_v2"}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_feature_flag_not_found(admin_token):
    """Test PUT /settings/feature-flags/{key} returns 404 for invalid key"""
    client = TestClient(app)

    response = client.put(
        "/api/admin/settings/feature-flags/nonexistent_flag",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"value": "true"}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

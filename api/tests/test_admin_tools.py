"""
US-007: Support Tools Page - Backend API Tests

Tests for admin tools endpoints:
- Room lookup (by code and ID)
- Room messages (paginated)
- Redis inspector (list keys, get values)
- Cache management (clear, stats)
"""
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from api.main import app
from api.jwt_tools import JWT_SECRET, ALGO

client = TestClient(app)

@pytest.fixture
def admin_token():
    """Generate admin JWT token"""
    return jwt.encode(
        {"email": "admin@test.com", "sub": "1", "is_admin": True},
        JWT_SECRET,
        algorithm=ALGO
    )

@pytest.fixture
def user_token():
    """Generate non-admin JWT token"""
    return jwt.encode(
        {"email": "user@test.com", "sub": "2", "is_admin": False},
        JWT_SECRET,
        algorithm=ALGO
    )

# ============================================================================
# Room Lookup Tests
# ============================================================================

def test_room_lookup_by_code_success(admin_token):
    """Test room lookup by code - should return room details"""
    response = client.get(
        "/api/admin/rooms/lookup?q=test-room",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "room_code" in data
    assert "room_id" in data
    assert "owner_email" in data
    assert "cost_summary" in data
    assert "stt_cost_usd" in data["cost_summary"]
    assert "mt_cost_usd" in data["cost_summary"]
    assert "total_cost_usd" in data["cost_summary"]

def test_room_lookup_by_id_success(admin_token):
    """Test room lookup by ID - should return room details"""
    response = client.get(
        "/api/admin/rooms/lookup?q=1060",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["room_id"] == 1060
    assert "room_code" in data

def test_room_lookup_not_found(admin_token):
    """Test room lookup with invalid code - should return 404"""
    response = client.get(
        "/api/admin/rooms/lookup?q=INVALID999",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 404
    assert "detail" in response.json()

def test_room_lookup_requires_admin(user_token):
    """Test room lookup requires admin access - should return 403"""
    response = client.get(
        "/api/admin/rooms/lookup?q=test-room",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403

# ============================================================================
# Room Messages Tests
# ============================================================================

def test_room_messages_success(admin_token):
    """Test getting room messages - should return paginated list"""
    response = client.get(
        "/api/admin/rooms/test-room/messages?limit=20&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert "total" in data
    assert "has_more" in data
    assert isinstance(data["messages"], list)

def test_room_messages_pagination(admin_token):
    """Test room messages pagination - should respect limit/offset"""
    response = client.get(
        "/api/admin/rooms/test-room/messages?limit=5&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["messages"]) <= 5

def test_room_messages_requires_admin(user_token):
    """Test room messages requires admin - should return 403"""
    response = client.get(
        "/api/admin/rooms/test-room/messages",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403

# ============================================================================
# Redis Inspector Tests
# ============================================================================

def test_redis_keys_list_success(admin_token):
    """Test listing Redis keys - should return keys matching pattern"""
    response = client.get(
        "/api/admin/debug/redis/keys?pattern=room:*&limit=50",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert "total" in data
    assert "truncated" in data
    assert isinstance(data["keys"], list)

def test_redis_keys_invalid_pattern(admin_token):
    """Test Redis keys with invalid pattern - should return 400"""
    response = client.get(
        "/api/admin/debug/redis/keys?pattern=invalid:*",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 400
    assert "Invalid pattern" in response.json()["detail"]

def test_redis_keys_requires_admin(user_token):
    """Test Redis keys requires admin - should return 403"""
    response = client.get(
        "/api/admin/debug/redis/keys?pattern=room:*",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403

def test_redis_get_value_success(admin_token):
    """Test getting Redis key value - should return key details"""
    # First, list keys to get a valid key
    list_response = client.get(
        "/api/admin/debug/redis/keys?pattern=debug:*&limit=1",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    if list_response.status_code == 200 and list_response.json()["keys"]:
        key = list_response.json()["keys"][0]["key"]

        response = client.get(
            f"/api/admin/debug/redis/get?key={key}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "key" in data
        assert "type" in data
        assert "value" in data
        assert "ttl" in data

# ============================================================================
# Cache Management Tests
# ============================================================================

def test_cache_stats_success(admin_token):
    """Test getting cache stats - should return Redis info"""
    response = client.get(
        "/api/admin/cache/stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "redis_info" in data
    assert "cache_breakdown" in data
    assert "used_memory_human" in data["redis_info"]
    assert "total_keys" in data["redis_info"]

def test_cache_clear_room_success(admin_token):
    """Test clearing room cache - should return keys deleted"""
    response = client.post(
        "/api/admin/cache/clear",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cache_type": "room_translations", "room_code": "TEST9999"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "keys_deleted" in data
    assert "cache_type" in data

def test_cache_clear_missing_room_code(admin_token):
    """Test clearing room cache without room_code - should return 400"""
    response = client.post(
        "/api/admin/cache/clear",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cache_type": "room_translations"}
    )

    assert response.status_code == 400
    assert "room_code required" in response.json()["detail"]

def test_cache_clear_invalid_type(admin_token):
    """Test clearing cache with invalid type - should return 400"""
    response = client.post(
        "/api/admin/cache/clear",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"cache_type": "invalid_type"}
    )

    assert response.status_code == 400
    assert "Invalid cache_type" in response.json()["detail"]

def test_cache_clear_requires_admin(user_token):
    """Test cache clear requires admin - should return 403"""
    response = client.post(
        "/api/admin/cache/clear",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"cache_type": "stt_cache"}
    )

    assert response.status_code == 403

# ============================================================================
# Security Tests
# ============================================================================

def test_all_endpoints_require_authentication():
    """Test all endpoints require authentication - should return 401"""
    endpoints = [
        ("/api/admin/rooms/lookup?q=test", "GET"),
        ("/api/admin/rooms/test/messages", "GET"),
        ("/api/admin/debug/redis/keys?pattern=room:*", "GET"),
        ("/api/admin/debug/redis/get?key=test", "GET"),
        ("/api/admin/cache/clear", "POST"),
        ("/api/admin/cache/stats", "GET"),
    ]

    for endpoint, method in endpoints:
        if method == "GET":
            response = client.get(endpoint)
        else:
            response = client.post(endpoint, json={})

        assert response.status_code == 401, f"Endpoint {endpoint} should require auth"

# ============================================================================
# Performance Tests
# ============================================================================

def test_room_lookup_performance(admin_token):
    """Test room lookup performance - should complete in <500ms"""
    import time

    start = time.time()
    response = client.get(
        "/api/admin/rooms/lookup?q=test-room",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    duration = (time.time() - start) * 1000  # Convert to ms

    assert response.status_code == 200
    assert duration < 500, f"Room lookup took {duration}ms (>500ms threshold)"

def test_cache_stats_performance(admin_token):
    """Test cache stats performance - should complete in <500ms"""
    import time

    start = time.time()
    response = client.get(
        "/api/admin/cache/stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    duration = (time.time() - start) * 1000

    assert response.status_code == 200
    assert duration < 500, f"Cache stats took {duration}ms (>500ms threshold)"

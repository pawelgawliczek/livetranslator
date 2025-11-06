"""
Integration tests for Phase 2A Metrics API - Component & Layer endpoints.

Tests:
- GET /api/admin/metrics/layers - Layer aggregations
- GET /api/admin/metrics/components - Component list with filters
- GET /api/admin/metrics/components/{name} - Component detail
- Component mapping validation
- Priority calculation for components
- Health status calculation
- Glob pattern expansion
"""
import pytest
from datetime import date, datetime


@pytest.fixture
def admin_user_token(test_db):
    """Create admin user and return JWT token."""
    from api.models import User
    from api.auth import _issue
    from sqlalchemy import select

    # Create or get admin user
    admin = test_db.execute(select(User).where(User.email == "admin@test.com")).scalar_one_or_none()
    if not admin:
        admin = User(
            email="admin@test.com",
            password_hash="hashed",
            is_admin=True,
            preferred_lang="en"
        )
        test_db.add(admin)
        test_db.commit()
        test_db.refresh(admin)

    # Generate JWT token
    token = _issue(admin)
    return token.access_token


@pytest.fixture
def regular_user_token(test_user_token):
    """Alias for test_user_token (regular non-admin user)."""
    return test_user_token


@pytest.fixture
def seed_component_metrics_data(test_db):
    """Seed comprehensive test metrics data for components"""
    from sqlalchemy import text

    # Insert metrics snapshot
    test_db.execute(text("""
        INSERT INTO metrics_snapshots (
            date, health_score, total_loc, api_loc, web_loc, test_loc,
            test_pass_rate, test_count, avg_complexity, created_at
        )
        VALUES (:date, :health_score, :total_loc, :api_loc, :web_loc, :test_loc,
                :test_pass_rate, :test_count, :avg_complexity, :created_at)
        ON CONFLICT (date) DO UPDATE SET
            health_score = EXCLUDED.health_score,
            total_loc = EXCLUDED.total_loc
    """), {
        'date': date.today(),
        'health_score': 82,
        'total_loc': 179000,
        'api_loc': 89500,
        'web_loc': 67200,
        'test_loc': 22300,
        'test_pass_rate': 98.5,
        'test_count': 689,
        'avg_complexity': 12.3,
        'created_at': datetime.utcnow()
    })

    # Insert complexity data for billing component
    billing_files = [
        ('api/billing_api.py', 14.1, 28, 720, 22, False),
        ('api/subscription_api.py', 13.5, 25, 680, 19, False),
        ('api/routers/payments.py', 18.5, 42, 850, 18, True),
        ('api/routers/quota.py', 12.3, 22, 450, 15, True),
        ('api/routers/admin_credits.py', 11.8, 20, 380, 12, False),
    ]

    # Insert complexity data for authentication component
    auth_files = [
        ('api/auth.py', 12.8, 24, 520, 16, True),
        ('api/auth_deps.py', 10.5, 18, 280, 8, True),
        ('api/oauth_api.py', 14.2, 26, 420, 11, True),
    ]

    # Insert complexity data for websocket component
    ws_files = [
        ('api/ws_manager.py', 11.5, 21, 380, 10, True),
        ('api/presence_manager.py', 9.8, 16, 240, 7, True),
    ]

    # Insert complexity data for STT component (subset)
    stt_files = [
        ('api/routers/stt/router.py', 12.1, 23, 520, 14, True),
        ('api/routers/stt/language_router.py', 11.2, 19, 380, 11, True),
        ('api/routers/stt/streaming_manager.py', 13.5, 25, 480, 13, True),
    ]

    # Insert complexity data for admin component
    admin_files = [
        ('api/routers/admin_costs.py', 13.8, 24, 520, 15, False),
        ('api/routers/admin_api.py', 10.5, 18, 340, 10, False),
        ('api/routers/metrics.py', 9.2, 15, 280, 8, False),
    ]

    # Insert complexity data for web layer
    web_files = [
        ('web/src/pages/RoomPage.jsx', 8.5, 15, 480, 12, False),
        ('web/src/pages/LoginPage.jsx', 7.2, 12, 220, 6, False),
        ('web/src/pages/AdminMetricsPage.jsx', 9.8, 17, 380, 10, False),
    ]

    all_files = billing_files + auth_files + ws_files + stt_files + admin_files + web_files

    for file_path, avg_ccn, max_ccn, total_loc, function_count, is_critical_path in all_files:
        test_db.execute(text("""
            INSERT INTO complexity_snapshots (
                date, file_path, avg_ccn, max_ccn, total_loc, function_count, is_critical_path, created_at
            )
            VALUES (:date, :file_path, :avg_ccn, :max_ccn, :total_loc, :function_count, :is_critical_path, :created_at)
            ON CONFLICT (date, file_path) DO UPDATE SET
                avg_ccn = EXCLUDED.avg_ccn,
                max_ccn = EXCLUDED.max_ccn,
                total_loc = EXCLUDED.total_loc
        """), {
            'date': date.today(),
            'file_path': file_path,
            'avg_ccn': avg_ccn,
            'max_ccn': max_ccn,
            'total_loc': total_loc,
            'function_count': function_count,
            'is_critical_path': is_critical_path,
            'created_at': datetime.utcnow()
        })

    # Insert function complexity data for top file
    test_db.execute(text("""
        INSERT INTO function_complexity (
            snapshot_id, function_name, ccn, loc, created_at
        )
        SELECT
            cs.id,
            'create_checkout_session',
            42,
            95,
            :created_at
        FROM complexity_snapshots cs
        WHERE cs.date = :date AND cs.file_path = 'api/routers/payments.py'
        ON CONFLICT DO NOTHING
    """), {
        'date': date.today(),
        'created_at': datetime.utcnow()
    })

    test_db.commit()
    yield


# ============================================================================
# Layer Endpoint Tests
# ============================================================================

def test_get_layers_success(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /layers returns all layers with correct structure"""
    response = test_client.get(
        "/api/admin/metrics/layers",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Validate structure
    assert "layers" in data
    assert "generated_at" in data
    assert isinstance(data["layers"], list)
    assert len(data["layers"]) >= 2  # At least api and web

    # Find API layer
    api_layer = next((l for l in data["layers"] if l["name"] == "api"), None)
    assert api_layer is not None
    assert api_layer["display_name"] == "Backend API"
    assert api_layer["total_loc"] > 0
    assert api_layer["avg_ccn"] > 0
    assert api_layer["file_count"] > 0
    assert api_layer["component_count"] > 0
    assert api_layer["health_status"] in ["healthy", "warning", "critical"]
    assert isinstance(api_layer["critical_components"], list)


def test_get_layers_health_status_calculation(test_client, admin_user_token, seed_component_metrics_data):
    """Test layer health status is calculated correctly"""
    response = test_client.get(
        "/api/admin/metrics/layers",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # API layer should have avg_ccn around 12-13 (warning or healthy)
    api_layer = next((l for l in data["layers"] if l["name"] == "api"), None)
    assert api_layer is not None

    if api_layer["avg_ccn"] < 12:
        assert api_layer["health_status"] == "healthy"
    elif api_layer["avg_ccn"] < 18:
        assert api_layer["health_status"] == "warning"
    else:
        assert api_layer["health_status"] == "critical"


def test_get_layers_requires_admin(test_client, regular_user_token):
    """Test GET /layers requires admin role"""
    response = test_client.get(
        "/api/admin/metrics/layers",
        headers={"Authorization": f"Bearer {regular_user_token}"}
    )

    assert response.status_code == 403


def test_get_layers_requires_authentication(test_client):
    """Test GET /layers requires authentication"""
    response = test_client.get("/api/admin/metrics/layers")
    assert response.status_code == 401


# ============================================================================
# Components Endpoint Tests
# ============================================================================

def test_get_components_success(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components returns all components with correct structure"""
    response = test_client.get(
        "/api/admin/metrics/components",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Validate structure
    assert "components" in data
    assert "total_components" in data
    assert "threshold" in data
    assert "generated_at" in data
    assert isinstance(data["components"], list)

    # Validate component structure
    if len(data["components"]) > 0:
        component = data["components"][0]
        assert "name" in component
        assert "display_name" in component
        assert "layer" in component
        assert "total_loc" in component
        assert "avg_ccn" in component
        assert "max_ccn" in component
        assert "file_count" in component
        assert "function_count" in component
        assert "is_critical" in component
        assert "priority" in component
        assert "health_status" in component
        assert component["priority"] in ["high", "medium", "low"]
        assert component["health_status"] in ["healthy", "warning", "critical"]


def test_get_components_critical_only_filter(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components with critical_only filter"""
    response = test_client.get(
        "/api/admin/metrics/components?critical_only=true",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # All returned components should be critical
    for component in data["components"]:
        assert component["is_critical"] is True


def test_get_components_layer_filter(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components with layer filter"""
    response = test_client.get(
        "/api/admin/metrics/components?layer=api",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # All returned components should be in API layer
    for component in data["components"]:
        assert component["layer"] == "api"


def test_get_components_threshold_filter(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components with threshold filter"""
    response = test_client.get(
        "/api/admin/metrics/components?threshold=15.0",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # All returned components should have avg_ccn >= 15
    for component in data["components"]:
        assert component["avg_ccn"] >= 15.0


def test_get_components_sort_by_priority(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components sorts by priority correctly"""
    response = test_client.get(
        "/api/admin/metrics/components?sort_by=priority",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    if len(data["components"]) > 1:
        # Verify priority order: high -> medium -> low
        priority_order = {"high": 0, "medium": 1, "low": 2}
        priorities = [priority_order[c["priority"]] for c in data["components"]]

        # Check if sorted (allowing equal priorities)
        for i in range(len(priorities) - 1):
            assert priorities[i] <= priorities[i + 1]


def test_get_components_sort_by_complexity(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components sorts by complexity correctly"""
    response = test_client.get(
        "/api/admin/metrics/components?sort_by=complexity",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    if len(data["components"]) > 1:
        # Verify descending order by avg_ccn
        avg_ccns = [c["avg_ccn"] for c in data["components"]]
        assert avg_ccns == sorted(avg_ccns, reverse=True)


def test_get_components_sort_by_loc(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components sorts by LOC correctly"""
    response = test_client.get(
        "/api/admin/metrics/components?sort_by=loc",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    if len(data["components"]) > 1:
        # Verify descending order by total_loc
        total_locs = [c["total_loc"] for c in data["components"]]
        assert total_locs == sorted(total_locs, reverse=True)


def test_get_components_priority_calculation(test_client, admin_user_token, seed_component_metrics_data):
    """Test component priority calculation logic"""
    response = test_client.get(
        "/api/admin/metrics/components",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Find billing component (critical, avg_ccn ~14.2)
    billing = next((c for c in data["components"] if c["name"] == "billing"), None)
    if billing:
        assert billing["is_critical"] is True
        if billing["avg_ccn"] > 13:
            assert billing["priority"] == "high"
        elif billing["avg_ccn"] > 10:
            assert billing["priority"] == "medium"


def test_get_components_requires_admin(test_client, regular_user_token):
    """Test GET /components requires admin role"""
    response = test_client.get(
        "/api/admin/metrics/components",
        headers={"Authorization": f"Bearer {regular_user_token}"}
    )

    assert response.status_code == 403


# ============================================================================
# Component Detail Endpoint Tests
# ============================================================================

def test_get_component_detail_success(test_client, admin_user_token, seed_component_metrics_data):
    """Test GET /components/{name} returns component detail"""
    response = test_client.get(
        "/api/admin/metrics/components/billing",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Validate structure
    assert "component" in data
    assert "files" in data
    assert "generated_at" in data

    # Validate component section
    component = data["component"]
    assert component["name"] == "billing"
    assert component["display_name"] == "Billing & Subscriptions"
    assert "description" in component
    assert component["layer"] == "api"
    assert component["is_critical"] is True
    assert "metrics" in component
    assert component["health_status"] in ["healthy", "warning", "critical"]
    assert component["priority"] in ["high", "medium", "low"]

    # Validate metrics section
    metrics = component["metrics"]
    assert metrics["total_loc"] > 0
    assert metrics["avg_ccn"] > 0
    assert metrics["max_ccn"] > 0
    assert metrics["file_count"] > 0
    assert metrics["function_count"] > 0

    # Validate files section
    assert isinstance(data["files"], list)
    assert len(data["files"]) > 0

    # Validate first file structure
    file_data = data["files"][0]
    assert "path" in file_data
    assert "avg_ccn" in file_data
    assert "max_ccn" in file_data
    assert "total_loc" in file_data
    assert "function_count" in file_data
    assert "priority" in file_data
    assert file_data["priority"] in ["critical", "high", "medium", "low"]


def test_get_component_detail_with_top_function(test_client, admin_user_token, seed_component_metrics_data):
    """Test component detail includes top function for files"""
    response = test_client.get(
        "/api/admin/metrics/components/billing",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Find payments.py in files (should have function data)
    payments_file = next((f for f in data["files"] if "payments.py" in f["path"]), None)

    if payments_file and payments_file.get("top_function"):
        top_func = payments_file["top_function"]
        assert "name" in top_func
        assert "ccn" in top_func
        assert "loc" in top_func
        assert top_func["name"] == "create_checkout_session"
        assert top_func["ccn"] == 42
        assert top_func["loc"] == 95


def test_get_component_detail_files_sorted_by_complexity(test_client, admin_user_token, seed_component_metrics_data):
    """Test component detail files are sorted by complexity"""
    response = test_client.get(
        "/api/admin/metrics/components/billing",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify files are sorted by avg_ccn DESC
    if len(data["files"]) > 1:
        avg_ccns = [f["avg_ccn"] for f in data["files"]]
        assert avg_ccns == sorted(avg_ccns, reverse=True)


def test_get_component_detail_not_found(test_client, admin_user_token):
    """Test GET /components/{name} returns 404 for invalid component"""
    response = test_client.get(
        "/api/admin/metrics/components/nonexistent",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_component_detail_requires_admin(test_client, regular_user_token):
    """Test GET /components/{name} requires admin role"""
    response = test_client.get(
        "/api/admin/metrics/components/billing",
        headers={"Authorization": f"Bearer {regular_user_token}"}
    )

    assert response.status_code == 403


# ============================================================================
# Caching Tests
# ============================================================================

def test_layers_caching(test_client, admin_user_token, seed_component_metrics_data):
    """Test layers endpoint uses Redis caching"""
    # First request (cache miss)
    response1 = test_client.get(
        "/api/admin/metrics/layers",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Second request (cache hit)
    response2 = test_client.get(
        "/api/admin/metrics/layers",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Data should be identical (from cache)
    assert data1["generated_at"] == data2["generated_at"]


def test_components_caching(test_client, admin_user_token, seed_component_metrics_data):
    """Test components endpoint uses Redis caching"""
    # First request (cache miss)
    response1 = test_client.get(
        "/api/admin/metrics/components",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )
    assert response1.status_code == 200
    data1 = response1.json()

    # Second request (cache hit)
    response2 = test_client.get(
        "/api/admin/metrics/components",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )
    assert response2.status_code == 200
    data2 = response2.json()

    # Data should be identical (from cache)
    assert data1["generated_at"] == data2["generated_at"]


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_components_with_no_matching_files(test_client, admin_user_token, test_db):
    """Test component aggregation handles missing files gracefully"""
    # Query for component that might not have all files
    response = test_client.get(
        "/api/admin/metrics/components?layer=tests",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Should return successfully even if no test layer components found
    assert "components" in data
    assert isinstance(data["components"], list)


def test_health_status_edge_cases(test_client, admin_user_token, seed_component_metrics_data):
    """Test health status calculation at boundary values"""
    response = test_client.get(
        "/api/admin/metrics/components",
        headers={"Authorization": f"Bearer {admin_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify health status matches thresholds
    for component in data["components"]:
        avg_ccn = component["avg_ccn"]
        health = component["health_status"]

        if avg_ccn < 12:
            assert health == "healthy"
        elif avg_ccn < 18:
            assert health == "warning"
        else:
            assert health == "critical"

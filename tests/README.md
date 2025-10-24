# LiveTranslator Test Suite

Comprehensive automated testing infrastructure for LiveTranslator with complete isolation from production.

## 📋 Overview

This test suite provides multi-layer testing with:
- **Unit Tests**: Fast, isolated tests (no I/O) - <30 seconds
- **Integration Tests**: Service integration with test database/Redis - 2-5 minutes
- **E2E Tests**: Full browser automation with Playwright - 10-20 minutes
- **Contract Tests**: API schema validation - Coming soon
- **Performance Tests**: Load and stress testing - Coming soon

## 🏗️ Test Infrastructure

### Isolated Test Environment
All tests run in **completely isolated Docker environment** separate from production:

| Service | Production | Test Environment |
|---------|-----------|------------------|
| PostgreSQL | `localhost:5432` | `localhost:5433` |
| Redis | `localhost:6379` | `localhost:6380` |
| API | `localhost:9003` | `localhost:9004` |
| Network | `stack_appnet` | `test_network` |
| Volumes | `pg_data`, `redis_data` | `test_pg_data`, `test_redis_data` |

**Zero impact on production services!**

## 🚀 Quick Start

### 1. Initial Setup
```bash
# Install test dependencies
make test-setup

# Install Git hooks (optional but recommended)
make test-hooks
```

### 2. Run Tests
```bash
# Run all tests
make test

# Run specific test types
make test-unit          # Fast unit tests (<30s)
make test-integration   # Integration tests (2-5min)
make test-e2e          # E2E tests (10-20min)
make test-quick        # Pre-commit subset

# Run with coverage
make test-coverage
```

### 3. Test Services Management
```bash
# Start test environment
make test-start

# Stop test environment
make test-stop

# Clean test data (remove volumes)
make test-clean

# View logs
make test-logs
```

## 📂 Test Organization

```
tests/
├── unit/                      # Pure unit tests (no I/O)
│   ├── test_auth_utils.py
│   ├── test_jwt_tools.py
│   └── test_language_utils.py
├── integration/               # Service integration tests
│   ├── api/                   # API endpoint tests
│   ├── websocket/             # WebSocket flow tests
│   ├── providers/             # Provider integration
│   └── database/              # Database tests
├── e2e/                       # End-to-end browser tests
│   ├── auth/                  # Authentication flows
│   ├── rooms/                 # Room management
│   ├── translation/           # Real-time translation
│   └── mobile/                # PWA/mobile tests
├── contract/                  # API contract tests
├── performance/               # Load/stress tests
├── fixtures/                  # Shared test data
│   ├── factories.py           # Data factories
│   ├── mock_providers.py      # Mock STT/MT responses
│   └── websocket_messages.py  # WS message builders
├── mocks/                     # Mock services
│   ├── stt_provider/          # Mock STT service
│   └── mt_provider/           # Mock MT service
├── conftest.py                # Global fixtures
├── pytest.ini                 # Pytest config
└── README.md                  # This file
```

## 🧪 Writing Tests

### Unit Tests
Fast, isolated tests with no I/O:

```python
# tests/unit/test_jwt_tools.py
import pytest
from api.jwt_tools import create_token, verify_token

def test_create_token():
    """Test JWT token creation."""
    token = create_token(user_id=123, email="test@example.com")
    assert token is not None
    assert isinstance(token, str)

def test_verify_token():
    """Test JWT token verification."""
    token = create_token(user_id=123, email="test@example.com")
    payload = verify_token(token)
    assert payload["user_id"] == 123
    assert payload["email"] == "test@example.com"
```

**Run:** `pytest tests/unit/test_jwt_tools.py -v`

### Integration Tests
Tests with test database/Redis:

```python
# tests/integration/api/test_rooms_api.py
import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.mark.integration
async def test_create_room(test_db_session, test_redis):
    """Test room creation with database."""
    client = TestClient(app)

    response = client.post(
        "/api/rooms",
        json={"code": "test-room"},
        headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert response.json()["code"] == "test-room"

    # Verify database
    room = test_db_session.query(Room).filter_by(code="test-room").first()
    assert room is not None
```

**Run:** `make test-integration`

### E2E Tests
Full browser automation with Playwright:

```javascript
// tests/e2e/rooms/create_join_room.spec.js
import { test, expect } from '@playwright/test';

test('user can create and join room', async ({ page }) => {
  // Login
  await page.goto('http://localhost:9004');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'password');
  await page.click('button[type="submit"]');

  // Create room
  await page.click('text=Create Room');
  await page.fill('[name="roomCode"]', 'my-test-room');
  await page.click('button:has-text("Create")');

  // Verify room page
  await expect(page).toHaveURL(/.*my-test-room/);
  await expect(page.locator('h1')).toContainText('my-test-room');
});
```

**Run:** `make test-e2e`

## 🎯 Test Markers

Use pytest markers to run specific test categories:

```bash
# Run WebSocket tests
pytest -m websocket

# Run database tests
pytest -m database

# Run slow tests
pytest -m slow

# Exclude slow tests
pytest -m "not slow"
```

Available markers:
- `unit` - Unit tests
- `integration` - Integration tests
- `e2e` - End-to-end tests
- `slow` - Slow tests
- `websocket` - WebSocket tests
- `provider` - Provider tests
- `database` - Database tests
- `redis` - Redis tests
- `auth` - Authentication tests
- `api` - API tests

## 🔧 Configuration

### Test Environment Variables
Edit `.env.test` to configure test environment:

```bash
# Test Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=livetranslator_test

# Test Redis
REDIS_URL=redis://localhost:6380/5

# Mock API keys (no real calls)
OPENAI_API_KEY=test-key-mock
```

### Pytest Configuration
Edit `tests/pytest.ini` for pytest settings:

```ini
[pytest]
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
```

## 🪝 Git Hooks

Automatically enforce testing on commits and pushes:

### Install Hooks
```bash
make test-hooks
```

### Pre-Commit Hook
Runs **unit tests only** (<30 seconds):
- Executes on: `git commit`
- Tests: Unit tests
- Skip: `git commit --no-verify`

### Pre-Push Hook
Runs **full test suite** (5-10 minutes):
- Executes on: `git push`
- Tests: Unit + Integration
- Skip: `git push --no-verify`

### Commit Message Hook
Validates commit message format (Conventional Commits):
- Format: `<type>(<scope>): <description>`
- Example: `feat(auth): add Google OAuth support`
- Types: feat, fix, docs, test, refactor, chore, etc.

## 📊 Coverage

Generate coverage reports:

```bash
# Run tests with coverage
make test-coverage

# View HTML report
open tests/htmlcov/index.html
```

Coverage targets:
- **Unit Tests**: 90%+
- **Integration Tests**: 80%+
- **Overall**: 85%+

## 🐛 Troubleshooting

### Tests Fail with "Connection Refused"
Test services not running:
```bash
make test-start
```

### Database Tables Don't Exist
Run migrations on test database:
```bash
# TODO: Add migration command
```

### Port Already in Use
Stop production services or change test ports in `docker-compose.test.yml`.

### Redis Keys Persist Between Tests
Tests should auto-cleanup, but you can manually flush:
```bash
docker exec redis_test redis-cli flushdb
```

### Test Containers Won't Start
Clean everything and start fresh:
```bash
make test-clean
docker system prune -f
make test-start
```

## 🤝 Contributing

### Adding New Tests

1. **Choose test type**: unit, integration, or E2E
2. **Create test file**: Follow naming convention `test_*.py`
3. **Write tests**: Use appropriate fixtures
4. **Add markers**: Use `@pytest.mark.integration`, etc.
5. **Run tests**: `pytest path/to/test_file.py -v`
6. **Check coverage**: `make test-coverage`

### Test Naming Convention
- Files: `test_*.py` or `*_test.py`
- Functions: `test_*`
- Classes: `Test*`

### Test Documentation
Add docstrings to all tests:

```python
def test_feature_name():
    """
    Test that feature works correctly.

    Scenario:
    1. Setup initial state
    2. Execute action
    3. Verify result

    Expected: Result should match expectations
    """
    # Test implementation
```

## 📚 Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Playwright Documentation](https://playwright.dev/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Docker Compose](https://docs.docker.com/compose/)

## 🎓 Best Practices

1. **Test Isolation**: Each test should be independent
2. **Fast Tests**: Keep unit tests under 30 seconds total
3. **Clean State**: Use fixtures for setup/teardown
4. **Descriptive Names**: Test names should describe behavior
5. **Arrange-Act-Assert**: Follow AAA pattern
6. **No Production**: Never test against production services
7. **Mock External**: Mock all external API calls
8. **Coverage**: Aim for 85%+ overall coverage
9. **CI/CD**: All tests must pass before merge
10. **Documentation**: Document complex test scenarios

## 📝 Current Status

### ✅ Phase 1 Complete (Test Infrastructure)
- ✅ Isolated test environment
- ✅ Test directory structure
- ✅ Docker compose for test services
- ✅ Pytest configuration
- ✅ Test runner scripts
- ✅ Git hooks
- ✅ Makefile commands
- ✅ Documentation

### 🚧 Phase 2 In Progress (Backend Tests)
- 🔄 Unit tests migration
- 🔄 Integration tests
- ⏳ Contract tests
- ⏳ Provider tests

### ⏳ Phase 3 Planned (Frontend & E2E)
- ⏳ Frontend unit tests (Vitest)
- ⏳ E2E tests (Playwright)
- ⏳ Visual regression tests

### ⏳ Phase 4 Planned (CI/CD)
- ⏳ GitHub Actions workflow
- ⏳ Coverage reporting
- ⏳ PR status checks

---

**Last Updated**: 2025-10-24
**Version**: 1.0.0 - Phase 1 Complete

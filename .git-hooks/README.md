# Git Hooks for LiveTranslator

Automated testing and commit validation to ensure code quality and proper metrics tracking.

## Quick Setup

```bash
./setup-git-hooks.sh
```

That's it! Both hooks are now installed.

---

## Commit-Msg Hook (NEW!)

**Validates that all commits include a Feature ID** for metrics tracking.

### Required Format

```bash
git commit -m "feat: Add authentication [Feature-ID-10]"
git commit -m "fix: Resolve login bug [Feature-10]"
git commit -m "refactor: Improve API [FID-10]"
git commit -m "docs: Update README [#10]"
```

### Valid Feature ID Formats

- `[Feature-ID-10]` - Full format (recommended)
- `[Feature-10]` - Short format
- `[FID-10]` - Abbreviated
- `[#10]` - GitHub-style

### Special Cases (No Feature ID Required)

- **Merge commits** - Automatically detected, no Feature ID needed
- **Revert commits** - Automatically detected, no Feature ID needed
- **Emergency fixes** - Add `[no-feature-id]` tag (use sparingly!)

### Examples

**✅ Valid commits:**
```bash
git commit -m "feat: Add Essential Mode API [Feature-ID-10]"
git commit -m "fix: Fix quota deduction race condition [FID-10]"
git commit -m "test: Add sponsorship tests [#10]"
git commit -m "Merge branch 'feature/auth'" # Auto-allowed
```

**❌ Invalid commits (will be blocked):**
```bash
git commit -m "feat: Add Essential Mode API"  # Missing Feature ID
git commit -m "fix stuff"  # Missing Feature ID
```

**Emergency override (use rarely!):**
```bash
git commit -m "hotfix: Critical production bug [no-feature-id]"
```

### Finding Active Feature IDs

```bash
# Show recent features
PGPASSWORD=${POSTGRES_PASSWORD} docker compose exec -T postgres psql -U lt_user -d livetranslator -c \
  "SELECT id, feature_name, phase FROM ai_development_metrics WHERE completed_at > NOW() - INTERVAL '7 days' ORDER BY id;"
```

---

## Pre-Commit Hook

Automatically runs tests before each commit. If tests fail, the commit is blocked.

### Test Levels

#### 1. Fast Mode (Unit Tests Only)
**Duration**: ~10 seconds
**Use case**: Quick iterations during active development

```bash
TEST_LEVEL=fast git commit -m "feat: add new feature"
```

**What runs**:
- ✅ Unit tests (`tests/unit/`)

---

#### 2. Standard Mode (Default)
**Duration**: ~30 seconds
**Use case**: Most commits

```bash
git commit -m "feat: add new feature"
# Or explicitly:
TEST_LEVEL=standard git commit -m "feat: add new feature"
```

**What runs**:
- ✅ Unit tests (`tests/unit/`)
- ✅ Integration tests (`tests/integration/`)

---

#### 3. Full Mode (All Tests)
**Duration**: ~2-3 minutes
**Use case**: Before pushing, important commits

```bash
TEST_LEVEL=full git commit -m "feat: major feature complete"
```

**What runs**:
- ✅ Unit tests (`tests/unit/`)
- ✅ Integration tests (`tests/integration/`)
- ✅ E2E tests (Playwright headless)

---

#### 4. Skip Tests (Emergency Only)
**Use case**: Hotfix, emergency deployment

```bash
# Option 1: Git's native flag
git commit --no-verify -m "hotfix: critical bug"

# Option 2: Environment variable
TEST_LEVEL=skip git commit -m "hotfix: critical bug"
```

**⚠️ Warning**: Only use when absolutely necessary. Always run tests manually later.

---

## Common Workflows

### Active Development
```bash
# Quick iterations with unit tests
TEST_LEVEL=fast git commit -m "wip: working on feature"
```

### Feature Complete
```bash
# Standard commit with integration tests
git commit -m "feat: complete user authentication"
```

### Before Push
```bash
# Full test suite
TEST_LEVEL=full git commit -m "feat: ready for review"
git push
```

### Emergency Hotfix
```bash
# Skip tests (run manually afterward!)
git commit --no-verify -m "hotfix: fix production bug"
# Then manually run:
docker compose exec api pytest
```

---

## Setting Default Test Level

### Per-Session
```bash
export TEST_LEVEL=fast
git commit -m "message 1"  # Uses fast
git commit -m "message 2"  # Uses fast
```

### Permanently (in shell config)

**Bash** (`~/.bashrc`):
```bash
export TEST_LEVEL=fast
```

**Zsh** (`~/.zshrc`):
```bash
export TEST_LEVEL=fast
```

**Fish** (`~/.config/fish/config.fish`):
```fish
set -x TEST_LEVEL fast
```

After editing, reload:
```bash
source ~/.bashrc  # or ~/.zshrc
```

---

## Understanding Test Output

### Success
```
🔍 Running pre-commit tests (level: standard)

📋 Running unit tests...
✅ Unit tests passed

🔗 Running integration tests...
✅ Integration tests passed

╔═══════════════════════════════════════════════════════╗
║  ✅ All tests passed! Proceeding with commit...       ║
╚═══════════════════════════════════════════════════════╝
```

### Failure
```
🔍 Running pre-commit tests (level: standard)

📋 Running unit tests...
❌ Unit tests failed

╔═══════════════════════════════════════════════════════╗
║  ❌ COMMIT BLOCKED: Tests failed                     ║
╚═══════════════════════════════════════════════════════╝

Fix the failing tests and try again.
To skip tests (not recommended): git commit --no-verify
```

---

## Troubleshooting

### Hook Not Running?
```bash
# Reinstall hooks
./setup-git-hooks.sh

# Verify hook is executable
ls -la .git/hooks/pre-commit

# Should show: -rwxr-xr-x (executable)
```

### Tests Failing?
```bash
# Run tests manually to debug
docker compose exec api pytest tests/unit/ -v
docker compose exec api pytest tests/integration/ -v
./run-e2e-tests.sh
```

### Hook Too Slow?
```bash
# Use fast mode by default
echo 'export TEST_LEVEL=fast' >> ~/.bashrc
source ~/.bashrc

# Then explicitly use full mode when needed
TEST_LEVEL=full git commit -m "important change"
```

### Need to Bypass Hook?
```bash
# Use --no-verify (rarely needed)
git commit --no-verify -m "message"

# IMPORTANT: Run tests manually afterward!
docker compose exec api pytest
```

---

## Test Coverage by Level

| Test Level | Unit | Integration | E2E | Time | Use Case |
|-----------|------|-------------|-----|------|----------|
| Fast      | ✅   | ❌          | ❌  | ~10s | Active development |
| Standard  | ✅   | ✅          | ❌  | ~30s | Most commits |
| Full      | ✅   | ✅          | ✅  | ~2-3m | Before push |

---

## Hook Files

```
.git-hooks/
├── pre-commit          # Test validation hook
├── commit-msg          # Feature ID validation hook
└── README.md           # This file

setup-git-hooks.sh      # Installation script
```

---

## Uninstalling Hooks

```bash
# Remove hooks
rm .git/hooks/pre-commit .git/hooks/commit-msg

# Verify removal
ls .git/hooks/
```

To reinstall later: `./setup-git-hooks.sh`

---

## Advanced Usage

### Run Specific Test Types
```bash
# Only unit tests, but manually
docker compose exec api pytest tests/unit/ -v

# Only integration tests
docker compose exec api pytest tests/integration/ -v

# Only E2E tests
./run-e2e-tests.sh

# Specific test file
docker compose exec api pytest tests/unit/test_auth_deps.py -v

# Specific test
docker compose exec api pytest tests/unit/test_auth_deps.py::test_validate_token -v
```

### Debugging Failed Tests
```bash
# Verbose output with full traceback
docker compose exec api pytest tests/unit/ -vv --tb=long

# Stop on first failure
docker compose exec api pytest tests/unit/ -x

# Run last failed tests only
docker compose exec api pytest --lf

# Show print statements
docker compose exec api pytest tests/unit/ -s
```

---

## Best Practices

### ✅ DO
- Use `fast` mode during active development
- Use `standard` mode for feature commits
- Use `full` mode before pushing or creating PRs
- Fix failing tests immediately
- Keep tests fast and reliable

### ❌ DON'T
- Don't habitually use `--no-verify`
- Don't commit broken tests
- Don't disable hooks permanently
- Don't skip tests before pushing

---

## CI/CD Integration

While these git hooks run locally, CI/CD should run the full test suite:

```yaml
# Example GitHub Actions (future)
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: docker compose exec api pytest
      - run: ./run-e2e-tests.sh
```

**Note**: Local hooks are a safety net, not a replacement for CI/CD.

---

## Related Documentation

- [Test Strategy](../.claude/test-strategy.md) - Overall testing strategy and coverage
- [Complete System Documentation](../.claude/DOCUMENTATION.md) - Architecture, API, services, deployment

---

**Last Updated**: 2025-11-07
**Maintainer**: Development Team
**Version**: 2.0.0 (Added commit-msg hook for Feature ID tracking)

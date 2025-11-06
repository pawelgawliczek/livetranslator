# Playwright E2E Authentication Setup

## Overview

This directory contains Playwright E2E tests with **global authentication** configured.
All tests now run with authentication automatically - no manual login or test.skip() needed.

## How It Works

1. **auth.setup.js**: Creates test user and logs in once before all tests
2. **.auth/user.json**: Stores authenticated session (cookies + localStorage)
3. **playwright.config.js**: Configures all tests to use saved auth state

## Test User

- **Email**: e2e-test@example.com
- **Password**: E2ETestPassword123!
- **Creation**: Automatic (created on first run if doesn't exist)

## Running Tests

```bash
# Run all tests (auth setup runs automatically first)
docker compose run --rm playwright npx playwright test

# Run specific test suite
docker compose run --rm playwright npx playwright test subscription-management

# Run with UI (for debugging)
docker compose run --rm playwright npx playwright test --ui

# Re-generate auth (if token expires)
rm tests/e2e/.auth/user.json
docker compose run --rm playwright npx playwright test --project=setup
```

## Test Results

**Before authentication setup**:
- 29 billing tests: 25 skipped, 4 passed (14% pass rate)

**After authentication setup**:
- 29 billing tests: 0 skipped, 29 passed (100% pass rate)

### Test Breakdown

**Payment Flows** (15 tests):
- Stripe checkout navigation
- Credit package purchases
- Payment success/failure handling
- Customer portal access
- Checkout session validation

**Subscription Management** (14 tests):
- Page display and tier comparison
- Quota status display
- Upgrade button functionality
- Billing history page

## Files Created/Modified

### New Files
- `tests/e2e/auth.setup.js` - Authentication setup script
- `tests/e2e/.auth/.gitignore` - Ignore auth state files
- `tests/e2e/.auth/user.json` - Saved authentication state (auto-generated)

### Modified Files
- `tests/e2e/playwright.config.js` - Added setup project + storageState
- `tests/e2e/tests/subscription-management.spec.js` - Removed skip logic
- `tests/e2e/tests/payment-flows.spec.js` - Removed skip logic

## Authentication Flow

```
Setup Project (runs once):
1. POST /auth/signup (creates user if doesn't exist)
2. POST /auth/login (gets JWT token)
3. Save cookies + localStorage to .auth/user.json

Test Project (runs after setup):
1. Load .auth/user.json
2. Tests automatically have auth cookies/tokens
3. Can access protected routes (/subscription, /billing-history, etc.)
```

## Token Expiry

JWT tokens expire after 12 hours (43200 seconds). If tests start failing with auth errors:

```bash
# Re-authenticate
rm tests/e2e/.auth/user.json
docker compose run --rm playwright npx playwright test --project=setup
```

## CI/CD Integration

The authentication setup is compatible with CI/CD:

1. Setup project runs first (creates/logs in test user)
2. All other tests depend on setup project
3. Auth state persists for entire test run
4. No manual intervention needed

## Security Notes

- Test user credentials are in code (not sensitive - test environment only)
- `.auth/user.json` contains JWT tokens - **DO NOT commit to git** (.gitignore added)
- Tokens are domain-specific (livetranslator.pawelgawliczek.cloud)
- Test user has no admin privileges

## Troubleshooting

**Tests still skip**: Verify auth.setup.js ran successfully
```bash
docker compose run --rm playwright npx playwright test --project=setup
```

**Login fails**: Check API is running
```bash
docker compose ps
docker compose logs api | tail -50
```

**Domain mismatch**: Verify BASE_URL matches auth state
```bash
docker compose run --rm playwright env | grep BASE_URL
```

**Stale token**: Remove and regenerate auth state
```bash
rm tests/e2e/.auth/user.json
docker compose run --rm playwright npx playwright test --project=setup
```

## Future Enhancements

- [ ] Multiple test users (admin, free tier, pro tier)
- [ ] API-based auth (faster than browser login)
- [ ] Parallel test execution with isolated auth states
- [ ] Auto-refresh tokens before expiry

# Playwright E2E authentication

Tests use global authentication. A test user is created and logged in once before all tests run.

## Test user

- Email: `e2e-test@example.com`
- Password: `E2ETestPassword123!`
- Created automatically on first run

## How it works

1. `auth.setup.js` creates the user and logs in (runs once)
2. Session saved to `.auth/user.json` (gitignored)
3. All tests load this session automatically

## Running tests

```bash
# All tests (auth setup runs first)
docker compose run --rm playwright npx playwright test

# Specific suite
docker compose run --rm playwright npx playwright test homepage

# Re-authenticate if token expires
rm tests/e2e/.auth/user.json
docker compose run --rm playwright npx playwright test --project=setup
```

## Token expiry

JWT tokens expire after 12 hours. If tests fail with auth errors, delete `.auth/user.json` and re-run.

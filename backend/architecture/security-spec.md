# Security specification

## Authentication

### JWT tokens

- Web: HttpOnly cookies (not localStorage)
- iOS: Keychain (secure enclave when available)
- Access token: 15 minutes
- Refresh token: 7 days
- Token blacklisting via Redis on logout

### Authorization

Admin endpoints require `is_admin=True` on the user record. Checked via `require_admin` dependency in FastAPI.

### Brute force protection

Login attempts tracked in Redis per email. After 5 failures, locked for 15 minutes.

## SQL injection prevention

All queries use parameterized statements (SQLAlchemy ORM or `$1` placeholders). Never string concatenation.

## Rate limiting

Redis-based sliding window. Configured per endpoint:
- Auth endpoints: 100/min
- Admin endpoints: 1000/min
- Global fallback: 100/min

## CORS

Restricted to the configured domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.LT_DOMAIN}", f"http://{settings.LT_DOMAIN}"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## WebSocket security

- Authentication via JWT token in query parameter
- Invalid/expired tokens get `4401` close code
- Message type validation (only known types processed)
- Per-user rate limiting on WebSocket messages

## Encryption

- HTTPS via Caddy (auto-renewing TLS 1.3)
- WebSocket over WSS
- Passwords hashed with bcrypt (passlib)
- Secrets stored in `/opt/stack/secrets/` (not in repo)

## Data retention

- Transcripts: kept until room is deleted (30min after last participant leaves)
- Cost records: indefinite (for admin analytics)
- User accounts: until manually deleted

## Secrets management

Secrets are read from files at startup, not environment variables:

```
/opt/stack/secrets/
├── jwt_secret
├── google_oauth_client_id.txt
└── google_oauth_client_secret.txt
```

API keys for STT/MT providers are passed via environment variables in `docker-compose.yml`, sourced from `.env` (gitignored).

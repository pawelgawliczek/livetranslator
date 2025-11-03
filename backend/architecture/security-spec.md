# LiveTranslator Security Specification

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Architecture - Development Ready

---

## Table of Contents
1. [Authentication & Authorization](#authentication--authorization)
2. [Apple Receipt Validation](#apple-receipt-validation)
3. [Stripe Webhook Verification](#stripe-webhook-verification)
4. [SQL Injection Prevention](#sql-injection-prevention)
5. [Rate Limiting](#rate-limiting)
6. [Data Encryption](#data-encryption)
7. [API Security](#api-security)
8. [WebSocket Security](#websocket-security)
9. [GDPR & Privacy](#gdpr--privacy)
10. [Incident Response](#incident-response)

---

## Authentication & Authorization

### JWT Token Security

**Token Storage:**
- **Web:** HttpOnly cookies (not localStorage to prevent XSS)
- **iOS:** Keychain (secure enclave when available)

**Token Lifetimes:**
- Access token: 15 minutes
- Refresh token: 7 days
- Remember-me: 30 days (optional)

**Implementation (FastAPI):**
```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("JWT_SECRET")  # Read from /opt/stack/secrets/jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise JWTError("Invalid token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Token Rotation:**
```python
@app.post("/api/auth/refresh")
async def refresh_token(refresh_token: str = Cookie(None)):
    # Verify refresh token
    payload = verify_token(refresh_token, expected_type="refresh")
    user_id = payload.get("sub")

    # Check if token blacklisted (logout)
    if await redis.get(f"blacklist:refresh:{refresh_token}"):
        raise HTTPException(status_code=401, detail="Token revoked")

    # Generate new tokens
    new_access_token = create_access_token({"sub": user_id, "email": payload["email"]})
    new_refresh_token = create_refresh_token({"sub": user_id, "email": payload["email"]})

    # Blacklist old refresh token (prevent reuse)
    await redis.setex(f"blacklist:refresh:{refresh_token}", REFRESH_TOKEN_EXPIRE_DAYS * 86400, "1")

    # Return new tokens
    response = JSONResponse({"access_token": new_access_token})
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,  # HTTPS only
        samesite="strict",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400
    )
    return response
```

**Token Revocation (Logout):**
```python
@app.post("/api/auth/logout")
async def logout(
    access_token: str = Depends(oauth2_scheme),
    refresh_token: str = Cookie(None)
):
    # Blacklist both tokens in Redis
    payload = verify_token(access_token)
    ttl_access = payload["exp"] - datetime.utcnow().timestamp()
    ttl_refresh = REFRESH_TOKEN_EXPIRE_DAYS * 86400

    await redis.setex(f"blacklist:access:{access_token}", int(ttl_access), "1")
    await redis.setex(f"blacklist:refresh:{refresh_token}", ttl_refresh, "1")

    return {"message": "Logged out successfully"}
```

**Authorization Middleware:**
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)) -> dict:
    # Verify token
    payload = verify_token(token.credentials)

    # Check blacklist
    if await redis.get(f"blacklist:access:{token.credentials}"):
        raise HTTPException(status_code=401, detail="Token revoked")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Fetch user from database
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

---

## Apple Receipt Validation

### Security Implementation

**Critical:** Prevent duplicate processing + receipt replay attacks

```python
from typing import Optional
import httpx
import base64

APPLE_PRODUCTION_URL = "https://buy.itunes.apple.com/verifyReceipt"
APPLE_SANDBOX_URL = "https://sandbox.itunes.apple.com/verifyReceipt"
APPLE_SHARED_SECRET = os.getenv("APPLE_SHARED_SECRET")
EXPECTED_BUNDLE_ID = "com.livetranslator.ios"

class AppleReceiptError(Exception):
    pass

async def verify_apple_receipt(
    receipt_data: str,
    transaction_id: str,
    original_transaction_id: str
) -> dict:
    """
    Verify Apple IAP receipt with security validations.

    Security checks:
    1. Duplicate transaction prevention
    2. Bundle ID verification
    3. Receipt authenticity (Apple API)
    4. Expiration validation
    """

    # 1. CHECK DUPLICATE TRANSACTION
    existing = await db.fetch_one(
        "SELECT 1 FROM payment_transactions WHERE apple_transaction_id = $1",
        transaction_id
    )
    if existing:
        raise AppleReceiptError(f"Duplicate transaction: {transaction_id} already processed")

    # 2. VERIFY WITH APPLE (production first, fallback to sandbox)
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {
            "receipt-data": receipt_data,
            "password": APPLE_SHARED_SECRET,
            "exclude-old-transactions": True  # Only return latest
        }

        # Try production first
        response = await client.post(APPLE_PRODUCTION_URL, json=payload)
        data = response.json()

        # If sandbox receipt sent to production, retry with sandbox
        if data.get("status") == 21007:
            response = await client.post(APPLE_SANDBOX_URL, json=payload)
            data = response.json()

    # Check status code
    if data.get("status") != 0:
        status_messages = {
            21000: "App Store could not read receipt",
            21002: "Receipt data malformed",
            21003: "Receipt authentication failed",
            21004: "Shared secret mismatch",
            21005: "Receipt server unavailable",
            21006: "Receipt valid but subscription expired",
            21007: "Sandbox receipt sent to production",
            21008: "Production receipt sent to sandbox"
        }
        error_msg = status_messages.get(data["status"], f"Unknown status: {data['status']}")
        raise AppleReceiptError(f"Apple verification failed: {error_msg}")

    # 3. VERIFY BUNDLE ID
    receipt_bundle_id = data.get("receipt", {}).get("bundle_id")
    if receipt_bundle_id != EXPECTED_BUNDLE_ID:
        raise AppleReceiptError(
            f"Bundle ID mismatch: expected {EXPECTED_BUNDLE_ID}, got {receipt_bundle_id}"
        )

    # 4. EXTRACT LATEST TRANSACTION INFO
    latest_info = data.get("latest_receipt_info", [])
    if not latest_info:
        raise AppleReceiptError("No transaction info in receipt")

    transaction = latest_info[0]  # Most recent transaction

    # 5. VALIDATE EXPIRATION (for subscriptions)
    expires_date_ms = transaction.get("expires_date_ms")
    if expires_date_ms:
        expires_date = datetime.fromtimestamp(int(expires_date_ms) / 1000, tz=timezone.utc)
        if expires_date < datetime.now(timezone.utc):
            raise AppleReceiptError(f"Subscription expired at {expires_date}")

    # 6. RETURN VERIFIED DATA
    return {
        "verified": True,
        "product_id": transaction["product_id"],
        "original_transaction_id": transaction["original_transaction_id"],
        "transaction_id": transaction["transaction_id"],
        "purchase_date": datetime.fromtimestamp(int(transaction["purchase_date_ms"]) / 1000),
        "expires_date": expires_date if expires_date_ms else None,
        "is_trial_period": transaction.get("is_trial_period") == "true",
        "is_in_intro_offer_period": transaction.get("is_in_intro_offer_period") == "true"
    }

# Endpoint implementation
@app.post("/api/payments/apple-verify")
async def verify_apple_iap(
    request: VerifyAppleReceiptRequest,
    user: dict = Depends(get_current_user)
):
    try:
        verified_data = await verify_apple_receipt(
            receipt_data=request.receipt_data,
            transaction_id=request.transaction_id,
            original_transaction_id=request.original_transaction_id
        )

        # Map product_id to tier or credit package
        if "plus" in verified_data["product_id"]:
            tier_name = "plus"
        elif "pro" in verified_data["product_id"]:
            tier_name = "pro"
        elif "credits" in verified_data["product_id"]:
            # Handle credit purchase
            hours = extract_hours_from_product_id(verified_data["product_id"])
            await grant_bonus_credits(user["id"], hours * 3600)
            return {"success": True, "credits_granted": hours}

        # Update subscription
        await update_user_subscription(
            user_id=user["id"],
            tier_name=tier_name,
            apple_transaction_id=verified_data["transaction_id"],
            apple_original_transaction_id=verified_data["original_transaction_id"],
            expires_date=verified_data["expires_date"]
        )

        # Create payment transaction record
        await db.execute(
            """
            INSERT INTO payment_transactions (
                user_id, platform, transaction_type, amount_usd, status,
                apple_transaction_id, apple_original_transaction_id, apple_product_id,
                created_at, completed_at
            ) VALUES ($1, 'apple', 'subscription', $2, 'succeeded', $3, $4, $5, NOW(), NOW())
            """,
            user["id"],
            29.00 if tier_name == "plus" else 199.00,
            verified_data["transaction_id"],
            verified_data["original_transaction_id"],
            verified_data["product_id"]
        )

        return {"verified": True, "tier": tier_name}

    except AppleReceiptError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

---

## Stripe Webhook Verification

### Signature Validation

**Critical:** Prevent webhook spoofing attacks

```python
import stripe
from fastapi import Request, HTTPException

STRIPE_WEBHOOK_SECRET = open("/opt/stack/secrets/stripe_webhook_secret").read().strip()

@app.post("/api/payments/stripe-webhook")
async def stripe_webhook(request: Request):
    # Get raw body (required for signature verification)
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        # Verify signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Process event
    event_type = event["type"]
    event_data = event["data"]["object"]

    # Idempotency: Check if already processed
    event_id = event["id"]
    if await redis.get(f"stripe:event:{event_id}"):
        print(f"Event {event_id} already processed, skipping")
        return {"status": "duplicate"}

    # Mark as processed (TTL 7 days)
    await redis.setex(f"stripe:event:{event_id}", 7 * 86400, "1")

    # Handle events
    if event_type == "checkout.session.completed":
        await handle_checkout_completed(event_data)
    elif event_type == "invoice.payment_succeeded":
        await handle_payment_succeeded(event_data)
    elif event_type == "invoice.payment_failed":
        await handle_payment_failed(event_data)
    elif event_type == "customer.subscription.deleted":
        await handle_subscription_deleted(event_data)

    return {"status": "success"}

async def handle_checkout_completed(session: dict):
    user_id = session["metadata"]["user_id"]
    subscription_id = session["subscription"]

    # Update user subscription
    await db.execute(
        """
        UPDATE user_subscriptions
        SET stripe_subscription_id = $1,
            stripe_customer_id = $2,
            status = 'active',
            billing_period_start = NOW(),
            billing_period_end = NOW() + INTERVAL '1 month'
        WHERE user_id = $3
        """,
        subscription_id,
        session["customer"],
        user_id
    )

    # Send confirmation email
    await send_email(
        to=session["customer_email"],
        subject="Subscription Activated",
        template="subscription_confirmed",
        context={"tier": "Plus"}
    )
```

---

## SQL Injection Prevention

### Parameterized Queries

**CRITICAL:** Never use string concatenation for SQL queries

**❌ DANGEROUS (Vulnerable to SQL Injection):**
```python
# NEVER DO THIS
user_id = request.query_params.get("user_id")
query = f"SELECT * FROM users WHERE id = {user_id}"  # ❌ VULNERABLE
result = await db.fetch_one(query)
```

**✅ SAFE (Parameterized Query):**
```python
# ALWAYS DO THIS
user_id = request.query_params.get("user_id")
query = "SELECT * FROM users WHERE id = $1"  # ✅ SAFE
result = await db.fetch_one(query, user_id)
```

### ORM Usage (SQLAlchemy)

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def get_user_by_email(db: AsyncSession, email: str):
    # SQLAlchemy automatically parameterizes
    stmt = select(User).where(User.email == email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

### Input Validation

```python
from pydantic import BaseModel, EmailStr, constr, validator

class CreateUserRequest(BaseModel):
    email: EmailStr  # Validates email format
    display_name: constr(min_length=1, max_length=120)  # Length constraints
    password: constr(min_length=8, max_length=128)

    @validator("password")
    def validate_password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v
```

### Escaping User Input (for display)

```python
from markupsafe import escape

def sanitize_display_name(name: str) -> str:
    # Remove HTML tags, escape special characters
    return escape(name).striptags()
```

---

## Rate Limiting

### Implementation (FastAPI + Redis)

```python
from fastapi import HTTPException, Request
from redis.asyncio import Redis

redis = Redis.from_url("redis://redis:6379/5")

async def rate_limit(
    request: Request,
    key_prefix: str,
    max_requests: int,
    window_seconds: int
):
    """
    Rate limit requests using sliding window algorithm.

    Args:
        key_prefix: Redis key prefix (e.g., "api:quota:status")
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
    """
    # Get user identifier (IP or user_id)
    user_id = request.state.user.get("id") if hasattr(request.state, "user") else None
    identifier = user_id or request.client.host

    # Redis key
    key = f"rate_limit:{key_prefix}:{identifier}"

    # Get current count
    current = await redis.get(key)

    if current is None:
        # First request in window
        await redis.setex(key, window_seconds, 1)
        return

    current = int(current)

    if current >= max_requests:
        # Rate limit exceeded
        ttl = await redis.ttl(key)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {ttl} seconds.",
            headers={"Retry-After": str(ttl)}
        )

    # Increment counter
    await redis.incr(key)

# Middleware
from fastapi import FastAPI

app = FastAPI()

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Apply rate limits based on endpoint
    path = request.url.path

    if path == "/api/quota/status":
        await rate_limit(request, "quota_status", max_requests=100, window_seconds=60)
    elif path == "/api/transcript-direct":
        await rate_limit(request, "transcript_direct", max_requests=100, window_seconds=60)
    elif path.startswith("/api/admin/"):
        await rate_limit(request, "admin", max_requests=1000, window_seconds=60)
    else:
        # Global rate limit
        await rate_limit(request, "global", max_requests=100, window_seconds=60)

    response = await call_next(request)
    return response
```

### Brute Force Protection (Login)

```python
@app.post("/api/auth/login")
async def login(credentials: LoginRequest, request: Request):
    # Check login attempts
    email = credentials.email
    attempts_key = f"login_attempts:{email}"

    attempts = await redis.get(attempts_key)
    if attempts and int(attempts) >= 5:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Try again in 15 minutes."
        )

    # Verify credentials
    user = await authenticate_user(credentials.email, credentials.password)

    if not user:
        # Increment failed attempts
        await redis.incr(attempts_key)
        await redis.expire(attempts_key, 15 * 60)  # 15 minutes

        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Clear failed attempts on success
    await redis.delete(attempts_key)

    # Generate tokens
    access_token = create_access_token({"sub": user["id"], "email": user["email"]})
    return {"access_token": access_token}
```

---

## Data Encryption

### Encryption at Rest

**Database:** PostgreSQL with full disk encryption (LUKS)
**Backups:** Encrypted with AES-256 (GPG)
**Secrets:** `/opt/stack/secrets/` directory (encrypted filesystem)

### Encryption in Transit

**HTTPS:** All API endpoints use TLS 1.3
**WebSocket:** WSS (WebSocket over TLS)

**Caddy Configuration (auto HTTPS):**
```caddyfile
livetranslator.pawelgawliczek.cloud {
    reverse_proxy api:8000
    tls {
        protocols tls1.3
    }
}
```

### Sensitive Data Hashing

**Passwords:** bcrypt (12 rounds)
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

**API Keys:** SHA-256 + random salt
```python
import hashlib
import secrets

def hash_api_key(api_key: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((api_key + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_api_key(api_key: str, stored_hash: str) -> bool:
    salt, hashed = stored_hash.split(":")
    computed = hashlib.sha256((api_key + salt).encode()).hexdigest()
    return secrets.compare_digest(computed, hashed)
```

---

## API Security

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://livetranslator.pawelgawliczek.cloud",
        "http://localhost:5173"  # Development only
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"]
)
```

### CSRF Protection

**Web:** SameSite cookies + CSRF tokens
**iOS:** Not applicable (native app, no cookies)

```python
from fastapi_csrf_protect import CsrfProtect

@app.post("/api/sensitive-action")
async def sensitive_action(
    request: Request,
    csrf_protect: CsrfProtect = Depends()
):
    await csrf_protect.validate_csrf(request)
    # Process action
```

### Content Security Policy

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss://livetranslator.pawelgawliczek.cloud"
    )

    return response
```

---

## WebSocket Security

### Authentication

```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str):
    # Authenticate via query parameter (JWT token)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    try:
        user = await verify_token_and_get_user(token)
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return

    # Accept connection
    await websocket.accept()

    # Join room
    await join_room(user, room_code, websocket)
```

### Message Validation

```python
async def handle_websocket_message(websocket: WebSocket, user: dict, data: dict):
    # Validate message structure
    if "type" not in data:
        await websocket.send_json({"error": "Missing message type"})
        return

    # Validate message type
    allowed_types = ["transcript_direct", "audio_chunk", "room_leave"]
    if data["type"] not in allowed_types:
        await websocket.send_json({"error": f"Invalid message type: {data['type']}"})
        return

    # Rate limit (100 messages/min per user)
    if not await check_websocket_rate_limit(user["id"]):
        await websocket.send_json({"error": "Rate limit exceeded"})
        return

    # Process message
    if data["type"] == "transcript_direct":
        await process_transcript(user, data)
```

---

## GDPR & Privacy

### User Data Rights

**1. Right to Access (GDPR Article 15):**
```python
@app.get("/api/users/{user_id}/data-export")
async def export_user_data(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Export all user data
    data = {
        "profile": await get_user_profile(user_id),
        "subscriptions": await get_user_subscriptions(user_id),
        "payments": await get_user_payments(user_id),
        "rooms": await get_user_rooms(user_id),
        "transcripts": await get_user_transcripts(user_id)
    }

    return data
```

**2. Right to Erasure (GDPR Article 17):**
```python
@app.delete("/api/users/{user_id}")
async def delete_user_account(user_id: int, current_user: dict = Depends(get_current_user)):
    if current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Cancel active subscriptions
    await cancel_stripe_subscription(user_id)
    # Note: Cannot cancel Apple subscriptions (user must do it in iOS Settings)

    # Anonymize data (GDPR allows retention for accounting)
    await db.execute(
        """
        UPDATE users
        SET email = $1,
            display_name = 'Deleted User',
            google_id = NULL,
            deleted_at = NOW()
        WHERE id = $2
        """,
        f"deleted_{user_id}@livetranslator.local",
        user_id
    )

    # Delete transcripts (if user requests, 30-day retention)
    await db.execute(
        "DELETE FROM segments WHERE room_id IN (SELECT id FROM rooms WHERE owner_id = $1)",
        user_id
    )

    return {"message": "Account deleted successfully"}
```

### Data Retention

**Transcripts:** 30 days (configurable per room)
**Payment Records:** 7 years (legal requirement)
**Audit Logs:** 1 year
**Session Logs:** 90 days

---

## Incident Response

### Security Incident Playbook

**1. Detection:**
- Monitoring: Prometheus + Grafana alerts
- Log aggregation: Centralized logging (ELK/Loki)
- Anomaly detection: Unusual API traffic patterns

**2. Response:**
- Isolate affected systems (firewall rules)
- Revoke compromised credentials (blacklist tokens)
- Notify affected users (within 72 hours per GDPR)

**3. Recovery:**
- Restore from encrypted backups
- Apply security patches
- Rotate secrets (JWT secret, database passwords)

**4. Post-Incident:**
- Root cause analysis
- Update security procedures
- Implement additional monitoring

### Contact

**Security Issues:** security@livetranslator.com
**Bug Bounty:** (Future) Responsible disclosure program

---

**End of Security Specification - Version 1.0**
**All security gaps addressed per Business Analyst review 2025-11-03**

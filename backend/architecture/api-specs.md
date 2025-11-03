# LiveTranslator Tier System API Specifications

**Version:** 1.1
**Created:** 2025-11-03
**Updated:** 2025-11-03 (Added missing endpoints per Business Analyst review)
**Status:** Phase 1 Architecture - Development Ready

## Table of Contents
1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Tier Management](#tier-management)
4. [Quota Tracking](#quota-tracking)
5. [Payments (Stripe)](#payments-stripe)
6. [Payments (Apple)](#payments-apple)
7. [Admin Dashboard](#admin-dashboard)
8. [WebSocket Protocol Extensions](#websocket-protocol-extensions)

---

## Overview

All endpoints follow REST conventions:
- **Base URL**: `https://livetranslator.pawelgawliczek.cloud/api`
- **Authentication**: JWT Bearer token in `Authorization` header
- **Content-Type**: `application/json`
- **Error Format**: `{"detail": "Error message"}`
- **Timestamps**: ISO 8601 format (`2025-11-03T12:00:00Z`)

### HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `500` - Internal Server Error

---

## Authentication

All endpoints require JWT token unless marked as **Public**.

**Header:**
```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

**JWT Claims:**
```json
{
  "sub": "123",
  "email": "user@example.com",
  "preferred_lang": "en",
  "exp": 1730635200
}
```

---

## Tier Management

### GET `/api/tiers`
**Public** - List all available subscription tiers

**Response:** `200 OK`
```json
{
  "tiers": [
    {
      "id": 1,
      "tier_name": "free",
      "display_name": "Free",
      "monthly_price_usd": 0.00,
      "monthly_quota_hours": 0.167,
      "features": [
        "10 minutes per month",
        "Apple STT/MT/TTS (iOS)",
        "Speechmatics STT (Web)",
        "Basic support"
      ],
      "provider_tier": "free"
    },
    {
      "id": 2,
      "tier_name": "plus",
      "display_name": "Plus",
      "monthly_price_usd": 29.00,
      "monthly_quota_hours": 2.00,
      "features": [
        "2 hours per month",
        "Premium STT providers",
        "Premium MT providers",
        "Email support"
      ],
      "provider_tier": "standard"
    },
    {
      "id": 3,
      "tier_name": "pro",
      "display_name": "Pro",
      "monthly_price_usd": 199.00,
      "monthly_quota_hours": 10.00,
      "features": [
        "10 hours per month",
        "All premium providers",
        "Server-side TTS",
        "Priority support",
        "API access"
      ],
      "provider_tier": "premium"
    }
  ]
}
```

---

### GET `/api/users/{user_id}/subscription`
Get user's current subscription details

**Response:** `200 OK`
```json
{
  "subscription": {
    "id": 456,
    "user_id": 123,
    "tier": {
      "id": 1,
      "tier_name": "free",
      "display_name": "Free",
      "monthly_price_usd": 0.00,
      "monthly_quota_hours": 0.167
    },
    "status": "active",
    "billing_period_start": "2025-11-01T00:00:00Z",
    "billing_period_end": "2025-12-01T00:00:00Z",
    "bonus_credits_seconds": 0,
    "auto_renew": true,
    "stripe_customer_id": null,
    "apple_customer_id": null,
    "created_at": "2025-10-15T10:30:00Z",
    "updated_at": "2025-11-01T00:00:00Z"
  }
}
```

---

### POST `/api/users/{user_id}/subscription`
Create or update user subscription

**Request Body:**
```json
{
  "tier_name": "plus",
  "payment_method": "stripe",
  "payment_intent_id": "pi_1A2B3C4D5E6F7G8H"
}
```

**Response:** `200 OK` (same as GET)

**Business Logic:**
1. Validate tier_name exists
2. Calculate pro-rated amount if mid-cycle upgrade
3. Create payment_transaction record (status: pending)
4. Update user_subscriptions.tier_id
5. Reset billing_period_start to now
6. Webhook will confirm payment success

---

### PATCH `/api/users/{user_id}/subscription`
Modify existing subscription (upgrade/downgrade)

**Request Body:**
```json
{
  "tier_name": "pro",
  "immediate": true
}
```

**Response:** `200 OK`
```json
{
  "subscription": { /* updated subscription */ },
  "pro_rated_charge": 141.67,
  "message": "Upgraded to Pro tier. You've been charged $141.67 for remaining 25 days."
}
```

**Business Logic (Upgrade):**
1. Calculate days remaining: `(billing_period_end - now) / 30`
2. Pro-rated charge: `(new_price - old_price) * (days_remaining / 30)`
3. Create payment transaction for pro-rated amount
4. Update tier immediately
5. Keep existing billing_period_end

**Business Logic (Downgrade):**
1. Schedule tier change for end of billing period
2. No immediate charge/refund
3. User keeps current tier until period ends

---

### DELETE `/api/users/{user_id}/subscription`
Cancel subscription (auto-renew off)

**Response:** `200 OK`
```json
{
  "message": "Subscription cancelled. Your Plus tier will remain active until 2025-12-01.",
  "active_until": "2025-12-01T00:00:00Z"
}
```

**Business Logic:**
1. Set `auto_renew = false`
2. Cancel Stripe subscription (if exists)
3. User keeps tier until billing_period_end
4. After end date, tier downgrades to 'free' via cron job

---

## Quota Tracking

### GET `/api/users/{user_id}/quota`
Get user's current quota status

**Response:** `200 OK`
```json
{
  "quota": {
    "tier": "plus",
    "monthly_quota_seconds": 7200,
    "bonus_credits_seconds": 3600,
    "total_available_seconds": 5400,
    "used_seconds": 5400,
    "remaining_seconds": 5400,
    "usage_breakdown": {
      "stt": 3600,
      "mt": 1200,
      "tts": 600
    },
    "billing_period_start": "2025-11-01T00:00:00Z",
    "billing_period_end": "2025-12-01T00:00:00Z",
    "reset_in_days": 28
  }
}
```

**Calculation Logic:**
```python
# Bonus credits used first (purchased credits)
total_available = bonus_credits + monthly_quota
remaining = total_available - used_seconds
```

---

### GET `/api/quota/status`
**NEW** - Real-time quota for authenticated user (optimized for frequent polling)

**Authentication:** Required (JWT)
**Rate Limit:** 100/min per user
**Caching:** Redis 30s TTL

**Response:** `200 OK`
```json
{
  "tier": "plus",
  "quota_seconds_total": 10800,
  "quota_seconds_used": 5400,
  "quota_seconds_remaining": 5400,
  "quota_reset_date": "2025-12-01T00:00:00Z",
  "grace_quota_seconds": 0,
  "alerts": [
    {
      "type": "warning",
      "threshold": "80_percent",
      "message": "You've used 50% of your quota"
    }
  ]
}
```

**Implementation Notes:**
- Cached in Redis with key: `quota:status:{user_id}` (30s TTL)
- Invalidated immediately on quota deduction
- Used by frontend for real-time quota display
- Lightweight response (no detailed breakdown)

---

### GET `/api/rooms/{code}/quota-pool`
**NEW** - Admin sees all participants' quota usage in room

**Authorization:** Room admin only (checks `room_participants.is_admin`)
**Response:** `200 OK`

```json
{
  "room_code": "room-abc123",
  "admin": {
    "user_id": 123,
    "email": "admin@example.com",
    "tier": "plus",
    "remaining_seconds": 3600,
    "provided_to_others_seconds": 900
  },
  "participants": [
    {
      "user_id": 456,
      "email": "guest@example.com",
      "tier": "free",
      "remaining_seconds": 0,
      "quota_used_in_room": 600,
      "is_using_admin_quota": false,
      "quota_source": "own"
    },
    {
      "user_id": null,
      "email": "guest:john:1730635200",
      "display_name": "John",
      "tier": null,
      "is_guest": true,
      "quota_used_in_room": 300,
      "is_using_admin_quota": true,
      "quota_source": "admin"
    }
  ],
  "total_pool_seconds": 3600,
  "total_used_seconds": 900,
  "pooling_active": true,
  "last_updated": "2025-11-03T12:00:00Z"
}
```

**Business Logic:**
- Query `room_participants` table joined with `user_subscriptions`
- Calculate `provided_to_others_seconds` from `quota_transactions` where `quota_source='admin'`
- Real-time data (no caching)
- Admin receives WebSocket `quota_pool_update` when values change

---

### POST `/api/quota/deduct`
**Internal API** - Deduct quota for a user (called by STT/MT/TTS routers)

**Request Body:**
```json
{
  "user_id": 123,
  "room_code": "room-abc123",
  "amount_seconds": 30,
  "service_type": "stt",
  "provider_used": "speechmatics",
  "quota_source": "own"
}
```

**Response:** `200 OK`
```json
{
  "transaction_id": 789,
  "remaining_seconds": 3570,
  "quota_exhausted": false
}
```

**Business Logic:**
1. Check participant's quota: `get_user_quota_available(user_id)`
2. If available: Deduct from own quota (`quota_source='own'`)
3. If exhausted: Check room admin's quota
4. If admin has quota: Deduct from admin (`quota_source='admin'`)
5. If admin exhausted: Return `quota_exhausted=true` (trigger free provider fallback)
6. Insert `quota_transactions` record
7. Update `room_participants.quota_used_seconds`

---

### POST `/api/transcript-direct`
**NEW** - iOS sends pre-transcribed text from Apple STT (no audio upload)

**Authentication:** Required (JWT)
**Rate Limit:** 100/min per user

**Request Body:**
```json
{
  "room_code": "room-abc123",
  "text": "Hello, this is a test transcription from Apple Speech Recognition.",
  "speaker_email": "user@example.com",
  "is_final": true,
  "segment_id": "seg_1730635200_1",
  "estimated_seconds": 3,
  "source_lang": "en",
  "timestamp": "2025-11-03T12:00:00.123Z"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "segment_id": "seg_1730635200_1",
  "translations": [
    {
      "target_lang": "pl",
      "text": "Cześć, to jest test transkrypcji z Apple Speech Recognition.",
      "provider": "deepl"
    },
    {
      "target_lang": "es",
      "text": "Hola, esta es una prueba de transcripción de Apple Speech Recognition.",
      "provider": "google_translate"
    }
  ],
  "quota_remaining_seconds": 7197,
  "quota_deducted_seconds": 3
}
```

**Business Logic:**
1. Validate user is participant in room (check `room_participants`)
2. Deduct estimated quota (default: 3 seconds per sentence)
3. Skip STT router (already transcribed client-side)
4. Publish directly to `stt_events` Redis channel
5. Trigger MT router for translations
6. Return translations synchronously (for fast feedback)
7. If `is_final=false`, treat as partial (display only, no translation)

**Error Responses:**
- `402 Payment Required` - Quota exhausted
- `403 Forbidden` - User not in room
- `429 Too Many Requests` - Rate limit exceeded

**Implementation Notes:**
- Used exclusively by iOS app (Apple Speech Framework)
- Audio never leaves device (privacy + cost savings)
- Quota estimation based on sentence count (configurable: 2-5s/sentence)
- Alternative: Use word count (avg 2.5 words/sec for English)

---

## Payments (Stripe)

### POST `/api/payments/stripe-checkout`
Create Stripe Checkout session for subscription or credit purchase

**Request Body (Subscription):**
```json
{
  "type": "subscription",
  "tier_name": "plus",
  "success_url": "https://livetranslator.../profile?tab=subscription",
  "cancel_url": "https://livetranslator.../profile?tab=subscription"
}
```

**Request Body (Credit Purchase):**
```json
{
  "type": "credit_purchase",
  "package_id": 2,
  "success_url": "https://livetranslator.../profile?tab=subscription",
  "cancel_url": "https://livetranslator.../profile?tab=subscription"
}
```

**Response:** `200 OK`
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

**Business Logic:**
1. Create Stripe Checkout Session
2. Set mode: 'subscription' or 'payment'
3. Set line items (tier price or credit package)
4. Store user_id in metadata
5. Return checkout_url (frontend redirects)

---

### POST `/api/payments/stripe-webhook`
**Public** - Stripe webhook handler (validates signature)

**Handled Events:**
- `checkout.session.completed` - Payment succeeded
- `customer.subscription.updated` - Subscription renewed
- `customer.subscription.deleted` - Subscription cancelled
- `invoice.payment_failed` - Payment failed

**Business Logic (checkout.session.completed):**
1. Verify Stripe signature
2. Extract user_id from metadata
3. If subscription: Update `user_subscriptions.tier_id`, `stripe_subscription_id`
4. If credit purchase: Add to `bonus_credits_seconds`
5. Create `payment_transactions` record (status: succeeded)
6. Send confirmation email

**Business Logic (invoice.payment_failed):**
1. Mark subscription as `status='past_due'`
2. Send payment failure email
3. After 3 failures: Downgrade to free tier

---

### GET `/api/payments/history`
Get user's payment history

**Response:** `200 OK`
```json
{
  "payments": [
    {
      "id": 123,
      "platform": "stripe",
      "transaction_type": "subscription",
      "amount_usd": 29.00,
      "currency": "USD",
      "status": "succeeded",
      "stripe_invoice_id": "in_1A2B3C4D5E6F7G8H",
      "created_at": "2025-11-01T10:00:00Z",
      "completed_at": "2025-11-01T10:00:05Z"
    },
    {
      "id": 124,
      "platform": "stripe",
      "transaction_type": "credit_purchase",
      "amount_usd": 19.00,
      "currency": "USD",
      "status": "succeeded",
      "metadata": {
        "package_id": 2,
        "hours": 4
      },
      "created_at": "2025-11-15T14:30:00Z",
      "completed_at": "2025-11-15T14:30:03Z"
    }
  ],
  "total_spent_usd": 48.00
}
```

---

## Payments (Apple)

### POST `/api/payments/apple-verify`
**UPDATED** - Verify Apple In-App Purchase receipt (enhanced security)

**Request Body:**
```json
{
  "transaction_id": "1000000123456789",
  "original_transaction_id": "1000000123456789",
  "product_id": "com.livetranslator.plus.monthly",
  "receipt_data": "MIITtgYJKoZIhvcNAQcCoIITpzCCE..."
}
```

**Response:** `200 OK`
```json
{
  "verified": true,
  "subscription": {
    "product_id": "com.livetranslator.plus.monthly",
    "tier_name": "plus",
    "expires_date": "2025-12-01T10:00:00Z",
    "original_transaction_id": "1000000123456789",
    "auto_renew_status": true
  },
  "message": "Subscription activated successfully"
}
```

**Business Logic:**
1. **Check duplicate transaction_id** in `payment_transactions` table (prevent fraud)
2. Validate receipt with Apple's verifyReceipt API (production, fallback to sandbox)
3. **Verify bundle_id** matches `com.livetranslator.ios` (prevent receipt replay attacks)
4. Check receipt authenticity and expiration
5. Map product_id to tier_name:
   - `com.livetranslator.plus.monthly` → plus
   - `com.livetranslator.pro.monthly` → pro
   - `com.livetranslator.credits.4hr` → credit package (4 hours)
6. If subscription: Update `user_subscriptions.tier_id`, `apple_original_transaction_id`
7. If credit: Add to `bonus_credits_seconds`
8. Create `payment_transactions` record (status: succeeded)
9. Store `original_transaction_id` for subscription linking

**Security Validations:**
```python
# Pseudo-code
async def verify_apple_receipt(receipt_data: str, transaction_id: str):
    # 1. Check for duplicate transaction_id
    if await db.fetch_one(
        "SELECT 1 FROM payment_transactions WHERE apple_transaction_id = $1",
        transaction_id
    ):
        raise DuplicateTransactionError("Transaction already processed")

    # 2. Validate with Apple (production first, then sandbox)
    response = await http_client.post(
        "https://buy.itunes.apple.com/verifyReceipt",
        json={"receipt-data": receipt_data, "password": APPLE_SHARED_SECRET}
    )

    if response["status"] == 21007:  # Sandbox receipt sent to production
        response = await http_client.post(
            "https://sandbox.itunes.apple.com/verifyReceipt",
            json={"receipt-data": receipt_data, "password": APPLE_SHARED_SECRET}
        )

    # 3. Verify bundle_id
    if response["receipt"]["bundle_id"] != "com.livetranslator.ios":
        raise BundleIdMismatchError("Invalid bundle_id")

    # 4. Extract and return verified data
    return {
        "verified": True,
        "product_id": response["latest_receipt_info"][0]["product_id"],
        "expires_date": response["latest_receipt_info"][0]["expires_date_ms"],
        "original_transaction_id": response["latest_receipt_info"][0]["original_transaction_id"]
    }
```

**Apple Product IDs (configured in App Store Connect):**
```
Subscriptions:
- com.livetranslator.plus.monthly ($29/month)
- com.livetranslator.pro.monthly ($199/month)

Consumable In-App Purchases (Credits):
- com.livetranslator.credits.1hr ($5)
- com.livetranslator.credits.4hr ($19)
- com.livetranslator.credits.8hr ($35)
- com.livetranslator.credits.20hr ($80)
```

**Error Responses:**
- `400 Bad Request` - Invalid receipt format
- `409 Conflict` - Duplicate transaction_id (already processed)
- `422 Unprocessable Entity` - Bundle ID mismatch or receipt verification failed

---

### POST `/api/payments/apple-status`
**UPDATED** - Apple Server-to-Server Notification (webhook)

**Public** - No auth header, validated by shared secret in payload

**Handled Notification Types:**
- `DID_RENEW` - Subscription renewed successfully
- `DID_FAIL_TO_RENEW` - Payment failed (retry)
- `DID_CHANGE_RENEWAL_STATUS` - User toggled auto-renew
- `REFUND` - User received refund (downgrade immediately)
- `EXPIRED` - Subscription expired (grace period ended)

**Request Body (Apple unified_receipt format):**
```json
{
  "notification_type": "DID_FAIL_TO_RENEW",
  "password": "shared_secret_from_app_store_connect",
  "unified_receipt": {
    "latest_receipt_info": [
      {
        "product_id": "com.livetranslator.plus.monthly",
        "original_transaction_id": "1000000123456789",
        "expires_date_ms": "1730635200000"
      }
    ]
  }
}
```

**Response:** `200 OK`
```json
{
  "status": "success"
}
```

**Business Logic (DID_FAIL_TO_RENEW):**
1. Validate shared secret matches stored value
2. Find user by `apple_original_transaction_id`
3. Mark subscription `status='past_due'`
4. Send notification to user (email + push)
5. Set grace period (7 days before downgrade)

**Business Logic (REFUND):**
1. Validate shared secret
2. Find user and payment transaction
3. **Immediately downgrade** to free tier (no grace period)
4. Update `payment_transactions.status='refunded'`
5. Send notification to user
6. **Preserve bonus credits** (only refund affects subscription, not purchased credits)

**Business Logic (DID_RENEW):**
1. Update `billing_period_end` to new expiration date
2. Reset quota usage (`used_seconds = 0`)
3. Send renewal confirmation email

**Implementation Notes:**
- Endpoint URL configured in App Store Connect: `https://livetranslator.../api/payments/apple-status`
- Shared secret stored in environment variable: `APPLE_SHARED_SECRET`
- Apple retries failed webhooks for 72 hours

---

## Admin Dashboard

### GET `/api/admin/financial/summary`
**Admin only** - Financial overview

**Query Parameters:**
- `start_date` (optional, default: 30 days ago)
- `end_date` (optional, default: today)

**Response:** `200 OK`
```json
{
  "summary": {
    "period": {
      "start": "2025-10-04T00:00:00Z",
      "end": "2025-11-03T23:59:59Z"
    },
    "revenue": {
      "total_usd": 12000.00,
      "subscriptions_usd": 9800.00,
      "credit_purchases_usd": 2200.00,
      "stripe_usd": 7000.00,
      "apple_usd": 5000.00
    },
    "costs": {
      "total_usd": 9000.00,
      "stt_usd": 3500.00,
      "mt_usd": 4000.00,
      "tts_usd": 1500.00,
      "infrastructure_usd": 0.00
    },
    "profit": {
      "gross_profit_usd": 3000.00,
      "gross_margin_percent": 25.00
    },
    "users": {
      "total_paying": 85,
      "plus": 60,
      "pro": 25
    }
  }
}
```

**Data Source:** `admin_financial_summary` materialized view + real-time aggregation

---

### GET `/api/admin/financial/revenue-vs-cost`
**Admin only** - Daily revenue vs cost chart data

**Response:** `200 OK`
```json
{
  "chart_data": [
    {
      "date": "2025-11-01",
      "revenue_usd": 450.00,
      "costs_usd": 320.00,
      "profit_usd": 130.00,
      "margin_percent": 28.89
    },
    {
      "date": "2025-11-02",
      "revenue_usd": 380.00,
      "costs_usd": 290.00,
      "profit_usd": 90.00,
      "margin_percent": 23.68
    }
  ]
}
```

---

### GET `/api/admin/financial/tier-analysis`
**Admin only** - Profitability by tier

**Response:** `200 OK`
```json
{
  "tiers": [
    {
      "tier_name": "free",
      "active_users": 200,
      "monthly_revenue_usd": 0.00,
      "monthly_costs_usd": 500.00,
      "profit_usd": -500.00,
      "margin_percent": -100.00,
      "notes": "Expected loss (acquisition funnel)"
    },
    {
      "tier_name": "plus",
      "active_users": 60,
      "monthly_revenue_usd": 1740.00,
      "monthly_costs_usd": 1200.00,
      "profit_usd": 540.00,
      "margin_percent": 31.03
    },
    {
      "tier_name": "pro",
      "active_users": 25,
      "monthly_revenue_usd": 4975.00,
      "monthly_costs_usd": 3800.00,
      "profit_usd": 1175.00,
      "margin_percent": 23.62
    }
  ],
  "total": {
    "total_revenue_usd": 6715.00,
    "total_costs_usd": 5500.00,
    "total_profit_usd": 1215.00,
    "overall_margin_percent": 18.09
  }
}
```

**Data Source:** `admin_tier_analysis` materialized view

---

### GET `/api/admin/financial/provider-costs`
**Admin only** - Cost breakdown by provider

**Response:** `200 OK`
```json
{
  "providers": [
    {
      "provider": "speechmatics",
      "service_type": "stt",
      "event_count": 1250,
      "total_cost_usd": 3000.00,
      "avg_cost_per_event": 2.40,
      "total_units": 37500,
      "unit_type": "seconds"
    },
    {
      "provider": "deepl",
      "service_type": "mt",
      "event_count": 8500,
      "total_cost_usd": 2500.00,
      "avg_cost_per_event": 0.29,
      "total_units": 250000,
      "unit_type": "characters"
    },
    {
      "provider": "openai",
      "service_type": "mt",
      "event_count": 2100,
      "total_cost_usd": 1500.00,
      "avg_cost_per_event": 0.71,
      "total_units": 4000000,
      "unit_type": "tokens"
    }
  ]
}
```

**Data Source:** `admin_provider_costs` materialized view

---

### GET `/api/admin/users/acquisition`
**Admin only** - User acquisition metrics

**Response:** `200 OK`
```json
{
  "metrics": {
    "period": "last_30_days",
    "new_signups": 150,
    "signup_conversion_rate": 18.5,
    "cost_per_acquisition": 12.50,
    "time_to_first_room_avg_minutes": 4.2,
    "activation_rate": 42.0
  },
  "daily_breakdown": [
    {
      "date": "2025-11-01",
      "signups": 8,
      "activated": 3,
      "activation_rate": 37.5
    }
  ]
}
```

**Data Source:** `admin_user_metrics` materialized view + real-time aggregation

---

### GET `/api/admin/users/{user_id}`
**Admin only** - Detailed user profile

**Response:** `200 OK`
```json
{
  "user": {
    "id": 123,
    "email": "user@example.com",
    "display_name": "John Doe",
    "created_at": "2025-10-15T10:30:00Z",
    "subscription": {
      "tier": "plus",
      "status": "active",
      "billing_period_start": "2025-11-01T00:00:00Z",
      "billing_period_end": "2025-12-01T00:00:00Z",
      "auto_renew": true
    },
    "quota": {
      "monthly_quota_seconds": 7200,
      "bonus_credits_seconds": 3600,
      "used_seconds": 5400,
      "remaining_seconds": 5400
    },
    "usage_stats": {
      "rooms_created": 12,
      "total_sessions": 45,
      "total_minutes_used": 90,
      "avg_session_duration_minutes": 15
    },
    "payments": {
      "total_spent_usd": 87.00,
      "lifetime_value_usd": 87.00,
      "last_payment_date": "2025-11-01T10:00:00Z"
    }
  }
}
```

---

### POST `/api/admin/users/{user_id}/grant-credits`
**UPDATED** - Admin manually grants bonus credits (refund, support, compensation)

**Authorization:** Admin only
**Audit:** All grants logged in `quota_transactions` with admin ID + reason

**Request Body:**
```json
{
  "seconds": 1800,
  "reason": "Refund for issue #1234 - poor translation quality during room session",
  "expires_date": null
}
```

**Alternative (hours notation):**
```json
{
  "hours": 0.5,
  "reason": "Compensation for service downtime on 2025-11-02",
  "expires_date": "2025-12-31T23:59:59Z"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Granted 1800 seconds (0.5 hours) to user",
  "transaction_id": 456,
  "new_bonus_credits_seconds": 10800,
  "granted_by": {
    "admin_id": 1,
    "admin_email": "admin@livetranslator.com"
  },
  "audit_logged": true
}
```

**Business Logic:**
1. Validate admin permissions (check `users.is_admin` or role)
2. Convert hours to seconds if provided
3. Add to `user_subscriptions.bonus_credits_seconds`
4. Create `quota_transactions` record:
   - `type='manual_grant'`
   - `quota_type='bonus'`
   - `amount_seconds=1800` (positive value)
   - `description=reason`
   - `metadata={'granted_by': admin_id, 'expires_date': ...}`
5. Create audit log entry in `admin_audit_log` table
6. Send email notification to user
7. Send push notification to iOS user (if registered)
8. Invalidate Redis quota cache

**Audit Log Entry:**
```sql
INSERT INTO admin_audit_log (
  admin_id,
  action,
  target_user_id,
  details,
  ip_address,
  created_at
) VALUES (
  1,
  'grant_credits',
  123,
  '{"seconds": 1800, "reason": "Refund for issue #1234"}',
  '192.168.1.1',
  NOW()
);
```

**Error Responses:**
- `403 Forbidden` - User not admin
- `400 Bad Request` - Invalid seconds/hours value (must be positive)
- `404 Not Found` - User not found

**Implementation Notes:**
- Credits never expire by default (`expires_date=null`)
- Expiring credits: Admin can set `expires_date` for promotional grants
- No maximum limit (admin discretion)
- Used primarily for: Refunds, compensation, customer support resolutions

---

## WebSocket Protocol Extensions

### New Message Types (Client → Server)

#### `transcript_direct`
Sent by iOS app when using Apple STT (client-side transcription)

```json
{
  "type": "transcript_direct",
  "roomId": "room-abc123",
  "text": "Hello world",
  "source_lang": "en",
  "is_final": true,
  "timestamp": "2025-11-03T12:00:00.123456Z"
}
```

**Backend Actions:**
1. Skip STT router (audio already transcribed)
2. Publish directly to `stt_events` Redis channel
3. Trigger MT router for translation
4. Track quota: Deduct 3 seconds per sentence (estimated)

---

### New Message Types (Server → Client)

#### `quota_alert`
Sent when user's quota drops below threshold

```json
{
  "type": "quota_alert",
  "threshold": "80_percent",
  "remaining_seconds": 1440,
  "message": "You have 24 minutes remaining this month",
  "action": "consider_upgrade"
}
```

**Thresholds:**
- 80% used → Warning notification
- 95% used → Critical notification
- 100% used → `quota_exhausted` event

---

#### `quota_exhausted`
Sent when user exhausts quota (triggers upgrade prompt)

```json
{
  "type": "quota_exhausted",
  "quota_type": "monthly",
  "message": "Your monthly quota is exhausted. Upgrade to Plus for 2 hours/month or buy credits.",
  "fallback_mode": "admin",
  "upgrade_options": [
    {
      "tier": "plus",
      "price_usd": 29.00,
      "quota_hours": 2
    }
  ],
  "credit_options": [
    {
      "package_id": 2,
      "hours": 4,
      "price_usd": 19.00
    }
  ]
}
```

**Frontend Actions:**
1. Show modal with upgrade options
2. "Upgrade to Plus" → Stripe Checkout
3. "Buy 4 Hours" → Stripe payment
4. iOS: Show StoreKit 2 subscription sheet

---

#### `quota_pool_update`
**NEW** - Sent to admin when quota pool changes (real-time)

```json
{
  "type": "quota_pool_update",
  "room_code": "room-abc123",
  "admin_remaining_seconds": 3600,
  "admin_provided_seconds": 900,
  "participants": [
    {
      "email": "guest@example.com",
      "quota_used_in_room": 600,
      "is_using_admin_quota": false
    },
    {
      "email": "guest:john",
      "quota_used_in_room": 300,
      "is_using_admin_quota": true
    }
  ],
  "last_updated": "2025-11-03T12:00:00Z"
}
```

**Frontend Actions:**
- Update participants sidebar with quota usage per user
- Highlight participants using admin quota (visual indicator)

---

#### `tier_limit_reached`
Sent when provider routing is limited by tier

```json
{
  "type": "tier_limit_reached",
  "current_tier": "free",
  "limitation": "Server-side TTS not available on Free tier",
  "available_providers": ["Apple TTS (iOS)", "Browser Web Speech (Web)"],
  "upgrade_message": "Upgrade to Pro for server-side TTS (Google/AWS/Azure)"
}
```

---

#### `quota_fallback`
Sent to admin when participant uses admin's quota

```json
{
  "type": "quota_fallback",
  "participant_email": "guest@example.com",
  "participant_name": "John",
  "amount_seconds": 120,
  "your_remaining_seconds": 5280,
  "message": "John is using your quota (2 minutes)"
}
```

**Admin UI:**
- Show notification in room header
- Display quota usage per participant in sidebar

---

## Error Responses

### Validation Error (400)
```json
{
  "detail": [
    {
      "loc": ["body", "tier_name"],
      "msg": "value is not a valid enumeration member; permitted: 'free', 'plus', 'pro'",
      "type": "type_error.enum"
    }
  ]
}
```

### Authentication Error (401)
```json
{
  "detail": "Invalid authentication credentials"
}
```

### Authorization Error (403)
```json
{
  "detail": "Admin access required"
}
```

### Quota Exhausted Error (402 Payment Required)
```json
{
  "detail": "Quota exhausted",
  "quota_exhausted": true,
  "remaining_seconds": 0,
  "upgrade_required": true
}
```

---

## Rate Limiting

**Global:** 100 requests/minute per user
**Admin endpoints:** 1000 requests/minute
**Webhook endpoints:** No limit (validated by signature)
**Special:**
- `/api/transcript-direct`: 100/min per user
- `/api/quota/status`: 100/min per user (cached 30s)

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1730635200
```

---

## Pagination

List endpoints support pagination:

**Query Parameters:**
- `page` (default: 1)
- `per_page` (default: 50, max: 100)

**Response Envelope:**
```json
{
  "data": [ /* array of items */ ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total_items": 123,
    "total_pages": 3
  }
}
```

---

## Idempotency

POST/PATCH endpoints support idempotency via header:

**Request:**
```
Idempotency-Key: uuid-v4-here
```

**Backend:** Store key + response for 24 hours, return cached response if duplicate

---

## Webhooks

### Stripe Webhook
**URL:** `https://livetranslator.../api/payments/stripe-webhook`
**Secret:** Stored in `/opt/stack/secrets/stripe_webhook_secret`

### Apple Server Notifications
**URL:** `https://livetranslator.../api/payments/apple-status`
**Authentication:** Shared secret validation

---

## Testing Endpoints

### POST `/api/test/quota-deduct`
**Dev/Staging only** - Simulate quota deduction

**Request Body:**
```json
{
  "user_id": 123,
  "amount_seconds": 600
}
```

### POST `/api/test/trigger-webhook`
**Dev/Staging only** - Trigger Stripe webhook event

---

**End of API Specifications - Version 1.1**
**All architecture gaps addressed per Business Analyst review 2025-11-03**

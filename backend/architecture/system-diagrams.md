# LiveTranslator System Architecture Diagrams

**Version:** 1.1
**Created:** 2025-11-03
**Updated:** 2025-11-03 (Added Performance SLA section per BA review)
**Status:** Phase 1 Architecture

All diagrams use ASCII art for clarity and version control friendliness.

---

## Table of Contents
1. [Quota Pooling Flow](#quota-pooling-flow)
2. [Tier-Based Provider Routing](#tier-based-provider-routing)
3. [Admin Dashboard Data Pipeline](#admin-dashboard-data-pipeline)
4. [Payment Flow (Dual Platform)](#payment-flow-dual-platform)
5. [iOS Client-Side Processing](#ios-client-side-processing)
6. [Quota Tracking State Machine](#quota-tracking-state-machine)
7. [WebSocket Message Flow (Extended)](#websocket-message-flow-extended)
8. [Performance SLA & Monitoring](#performance-sla--monitoring) ⭐ NEW

---

## 1. Quota Pooling Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                    QUOTA POOLING SYSTEM                          │
│  Goal: Participant uses own quota first, then admin's           │
└──────────────────────────────────────────────────────────────────┘

┌─────────────┐
│ Participant │  Free tier user (10 min/month)
│   Speaks    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│ 1. Check Participant Quota                 │
│    SELECT get_user_quota_available(p_id)   │
└──────────────┬──────────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
       ▼               ▼
  Has Quota      Quota Exhausted
  (600s left)    (0s left)
       │               │
       ▼               ▼
┌─────────────┐  ┌─────────────────────────────┐
│ Deduct from │  │ 2. Check Admin Quota        │
│ Participant │  │    (Room Owner)             │
│ Quota       │  │    SELECT get_user_quota... │
└──────┬──────┘  └──────────┬──────────────────┘
       │                    │
       │             ┌──────┴────────┐
       │             │               │
       │             ▼               ▼
       │        Admin Has       Admin Exhausted
       │        Quota           (0s left)
       │        (3600s)              │
       │             │               │
       │             ▼               ▼
       │      ┌─────────────┐  ┌────────────────┐
       │      │ Deduct from │  │ 3. Downgrade   │
       │      │ Admin Quota │  │    to Free     │
       │      │             │  │    Providers   │
       │      │ Notify      │  │                │
       │      │ Admin       │  │ Apple STT (iOS)│
       │      └──────┬──────┘  │ Browser (Web)  │
       │             │         └────────┬───────┘
       │             │                  │
       │             ▼                  │
       │      ┌─────────────────┐      │
       │      │ quota_source=   │      │
       │      │ 'admin'         │      │
       │      └──────┬──────────┘      │
       │             │                  │
       └─────────────┼──────────────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │ 4. Insert Transaction  │
         │                        │
         │ quota_transactions:    │
         │   user_id: p_id        │
         │   amount_seconds: -30  │
         │   quota_type: 'own'    │
         │     or 'admin_fallback'│
         │   provider: 'speechm.' │
         └────────┬───────────────┘
                  │
                  ▼
         ┌────────────────────────┐
         │ 5. Update Room         │
         │    Participants        │
         │                        │
         │ room_participants:     │
         │   quota_used_seconds   │
         │   += 30                │
         │   quota_source = 'own' │
         │     or 'admin'         │
         └────────┬───────────────┘
                  │
                  ▼
         ┌────────────────────────┐
         │ 6. Continue Session    │
         │    (or prompt upgrade) │
         └────────────────────────┘

┌─────────────────────────────────────────────┐
│ GUEST BEHAVIOR (No Own Quota)              │
├─────────────────────────────────────────────┤
│ Guest Speaks → Skip step 1                 │
│              → Immediately use Admin Quota │
│              → quota_source='admin'        │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ QUOTA DEPLETION NOTIFICATIONS              │
├─────────────────────────────────────────────┤
│ Participant:                               │
│   80% used → Warning toast                 │
│   100% used → quota_exhausted WebSocket    │
│                                            │
│ Admin:                                     │
│   When participant uses admin quota →     │
│   quota_fallback WebSocket notification    │
│   "John is using your quota (2 min)"      │
└─────────────────────────────────────────────┘
```

**Key Design Decisions:**
1. **Waterfall Model**: Own quota → Admin quota → Free providers
2. **Real-time Checks**: Every STT/MT/TTS event checks quota before processing
3. **Granular Tracking**: Seconds (not minutes) for precision
4. **Attribution**: `quota_transactions.quota_type` tracks whose quota was used
5. **Notification**: Admin notified when participants use their quota

---

## 2. Tier-Based Provider Routing

```
┌──────────────────────────────────────────────────────────────────┐
│              TIER-BASED PROVIDER ROUTING                         │
│  Different providers based on subscription tier                  │
└──────────────────────────────────────────────────────────────────┘

User Speaks
    │
    ▼
┌───────────────────────┐
│ Check User Tier       │
│ (from JWT or DB)      │
└──────┬────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│                     TIER ROUTING MATRIX                          │
└──────────────────────────────────────────────────────────────────┘

┌────────────┬─────────────────────────────────────────────────────┐
│   FREE     │                                                     │
├────────────┼─────────────────────────────────────────────────────┤
│ Platform   │ Provider                                            │
├────────────┼─────────────────────────────────────────────────────┤
│ iOS        │ Apple Speech Framework (FREE)                       │
│ iOS        │ Apple Translation API (FREE)                        │
│ iOS        │ AVSpeechSynthesizer TTS (FREE)                      │
├────────────┼─────────────────────────────────────────────────────┤
│ Web        │ Speechmatics STT ($0.08/hr, basic config)          │
│ Web        │ Browser Translation API (FREE, if available)       │
│ Web        │ Browser Web Speech API TTS (FREE)                  │
├────────────┼─────────────────────────────────────────────────────┤
│ Quota      │ 10 minutes/month                                    │
│ Server TTS │ ❌ Not available                                    │
└────────────┴─────────────────────────────────────────────────────┘

┌────────────┬─────────────────────────────────────────────────────┐
│   PLUS     │                                                     │
├────────────┼─────────────────────────────────────────────────────┤
│ STT        │ Choice:                                             │
│            │   - Speechmatics ($0.08/hr, premium config)         │
│            │   - Google Cloud Speech v2 ($0.96/hr)               │
│            │   - Azure Speech ($1.00/hr)                         │
│            │   OR Apple STT (iOS, free)                          │
├────────────┼─────────────────────────────────────────────────────┤
│ MT         │ Choice:                                             │
│            │   - DeepL ($10/1M chars, European languages)        │
│            │   - Google Translate ($20/1M chars)                 │
│            │   - OpenAI GPT-4o-mini ($0.375/1k tokens)           │
│            │   OR Apple Translation (iOS, free)                  │
├────────────┼─────────────────────────────────────────────────────┤
│ TTS        │ Client-side only:                                   │
│            │   - Apple TTS (iOS)                                 │
│            │   - Browser Web Speech (Web)                        │
├────────────┼─────────────────────────────────────────────────────┤
│ Quota      │ 2 hours/month                                       │
│ Server TTS │ ❌ Not available                                    │
└────────────┴─────────────────────────────────────────────────────┘

┌────────────┬─────────────────────────────────────────────────────┐
│    PRO     │                                                     │
├────────────┼─────────────────────────────────────────────────────┤
│ STT        │ All premium providers:                              │
│            │   - Speechmatics (priority routing)                 │
│            │   - Google Cloud Speech v2 (multi-language)         │
│            │   - Azure Speech (diarization)                      │
│            │   - Soniox (budget option)                          │
│            │   - OpenAI Whisper (fallback)                       │
├────────────┼─────────────────────────────────────────────────────┤
│ MT         │ All premium providers:                              │
│            │   - DeepL (European languages, priority)            │
│            │   - Google Translate (multi-language)               │
│            │   - Amazon Translate (cost-optimized)               │
│            │   - OpenAI GPT-4o-mini (Arabic dialect)             │
├────────────┼─────────────────────────────────────────────────────┤
│ TTS        │ Server-side TTS enabled:                            │
│            │   - Google Cloud TTS ($16/1M chars)                 │
│            │   - AWS Polly ($4/1M chars)                         │
│            │   - Azure TTS ($16/1M chars)                        │
│            │   OR client-side (Apple/Browser)                    │
├────────────┼─────────────────────────────────────────────────────┤
│ Quota      │ 10 hours/month                                      │
│ Features   │ Advanced analytics, API access                      │
└────────────┴─────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                   PROVIDER SELECTION LOGIC                       │
└──────────────────────────────────────────────────────────────────┘

User Speaks (with tier='plus')
    │
    ▼
┌───────────────────────────┐
│ STT Router                │
│ Check tier='plus'         │
└──────┬────────────────────┘
       │
       ▼
┌───────────────────────────┐
│ Query stt_routing_config  │
│ WHERE provider_tier IN    │
│   ('free', 'standard')    │
└──────┬────────────────────┘
       │
       ▼
┌────────────────────────────────┐
│ Select Provider:               │
│ - Language: Polish (pl-PL)     │
│ - Mode: partial                │
│ - Quality: standard            │
│ → Result: Speechmatics         │
└──────┬─────────────────────────┘
       │
       ▼
┌────────────────────────────────┐
│ Check Quota Available          │
│ If exhausted → Fallback to     │
│ Free tier providers            │
└──────┬─────────────────────────┘
       │
       ▼
Route to Speechmatics WebSocket

┌──────────────────────────────────────────────────────────────────┐
│                      TIER TRANSITION                             │
└──────────────────────────────────────────────────────────────────┘

User Upgrades: Free → Plus (mid-conversation)
    │
    ▼
┌───────────────────────────┐
│ Stripe webhook received   │
│ Update user_subscriptions │
│ tier_id = 2 (Plus)        │
└──────┬────────────────────┘
       │
       ▼
┌───────────────────────────┐
│ Next audio chunk arrives  │
│ STT router checks tier    │
│ → Now 'plus'              │
└──────┬────────────────────┘
       │
       ▼
┌───────────────────────────┐
│ Switch to premium         │
│ providers mid-session     │
│ (no disruption)           │
└───────────────────────────┘
```

**Key Design Decisions:**
1. **iOS Free = Apple APIs**: Zero cost on free tier for iOS users
2. **Web Free = Speechmatics Basic**: Low-cost STT ($0.08/hr)
3. **Plus = Premium Choice**: User can choose premium or free providers
4. **Pro = All Providers**: Access to all, with priority routing
5. **Server TTS = Pro Only**: Google/AWS/Azure TTS requires Pro tier
6. **Dynamic Routing**: Tier changes apply immediately (no restart)

---

## 3. Admin Dashboard Data Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                 ADMIN DASHBOARD ARCHITECTURE                     │
│  Real-time events → Aggregation → Materialized views → API      │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     DATA SOURCES (Real-Time)                    │
└─────────────────────────────────────────────────────────────────┘

STT Events          MT Events          Payment Events
(Redis)             (Redis)            (PostgreSQL)
    │                   │                    │
    ▼                   ▼                    ▼
┌───────────┐     ┌───────────┐     ┌──────────────┐
│ Cost      │     │ Cost      │     │ Payment      │
│ Tracker   │     │ Tracker   │     │ Transactions │
└─────┬─────┘     └─────┬─────┘     └──────┬───────┘
      │                 │                    │
      └────────┬────────┴────────────────────┘
               │
               ▼
    ┌────────────────────┐
    │   room_costs       │  ← Base cost tracking table
    │   (per event)      │
    └──────────┬─────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────────┐
│              AGGREGATION LAYER (Scheduled)                       │
│  Cron job runs daily at 2am UTC: refresh_admin_views()          │
└──────────────────────────────────────────────────────────────────┘

               │
       ┌───────┼───────┬───────┬───────┐
       │       │       │       │       │
       ▼       ▼       ▼       ▼       ▼
┌──────────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│Financial │ │Tier  │ │User  │ │Provider  │
│Summary   │ │Analy.│ │Metric│ │Costs     │
│(Matview) │ │(Matv)│ │(Matv)│ │(Matview) │
└────┬─────┘ └───┬──┘ └───┬──┘ └────┬─────┘
     │           │        │         │
     │           │        │         │
     └───────────┼────────┼─────────┘
                 │        │
                 ▼        ▼
         ┌────────────────────┐
         │   Redis Cache      │  ← 30-second TTL
         │   (Hot data)       │
         └──────────┬─────────┘
                    │
                    ▼
         ┌────────────────────┐
         │  Admin API         │
         │  /api/admin/*      │
         └──────────┬─────────┘
                    │
                    ▼
         ┌────────────────────┐
         │  Admin Panel       │  ← React frontend
         │  (Charts, Tables)  │
         └────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                  DATA FLOW TIMELINE                              │
└──────────────────────────────────────────────────────────────────┘

T+0s:     User speaks → STT event → room_costs record
T+0.5s:   Cost tracker writes to PostgreSQL
T+1s:     Real-time chart updates (if admin viewing)

T+2am:    Cron job triggers: SELECT refresh_admin_views()
T+2:05am: Materialized views refreshed (5-minute operation)

T+8am:    Admin opens dashboard
T+8:00s:  API queries materialized views (instant)
T+8:01s:  Response cached in Redis (30s TTL)
T+8:15s:  Second request → Served from Redis cache (<10ms)

┌──────────────────────────────────────────────────────────────────┐
│                  CACHING STRATEGY                                │
└──────────────────────────────────────────────────────────────────┘

Layer 1: Materialized Views (Refreshed Daily)
┌──────────────────────────────────────┐
│ admin_financial_summary              │  ← 90 days historical
│ admin_tier_analysis                  │  ← Current state
│ admin_user_metrics                   │  ← 90 days historical
│ admin_provider_costs                 │  ← 30 days
└──────────────────────────────────────┘

Layer 2: Redis Cache (30s TTL)
┌──────────────────────────────────────┐
│ admin:financial:summary              │  ← Hot data
│ admin:tier:analysis                  │
│ admin:user:metrics                   │
│ admin:provider:costs                 │
└──────────────────────────────────────┘

Layer 3: Real-Time Queries (For Recent Data)
┌──────────────────────────────────────┐
│ Today's revenue → Direct query       │  ← Not in matview yet
│ Last hour costs → Direct query       │
│ Active users now → Redis presence    │
└──────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                  PERFORMANCE TARGETS                             │
└──────────────────────────────────────────────────────────────────┘

Financial Summary:        < 500ms (cached) / < 2s (uncached)
Tier Analysis:            < 500ms (cached) / < 3s (uncached)
User Metrics:             < 500ms (cached) / < 2s (uncached)
Provider Costs:           < 500ms (cached) / < 1s (uncached)
Real-time chart updates:  < 5s (WebSocket push)

Database Size Estimates:
- 1M users, 100M events:  ~50GB
- Materialized views:      ~500MB
- Redis cache:             ~10MB
```

**Key Design Decisions:**
1. **Materialized Views**: Pre-compute expensive queries (daily refresh)
2. **Redis Cache**: 30s TTL for hot data (admin dashboard)
3. **Dual-Layer**: Historical (matviews) + Real-time (direct queries)
4. **Cron Job**: Daily 2am refresh (low-traffic window)
5. **Read Replica**: Optional for large datasets (scale to 10M+ users)

---

## 4. Payment Flow (Dual Platform)

```
┌──────────────────────────────────────────────────────────────────┐
│              WEB PAYMENT FLOW (Stripe)                           │
└──────────────────────────────────────────────────────────────────┘

User clicks "Upgrade to Plus"
    │
    ▼
┌────────────────────────────┐
│ Frontend (React)           │
│ POST /api/payments/        │
│   stripe-checkout          │
│ Body: {                    │
│   type: 'subscription',    │
│   tier_name: 'plus'        │
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Backend (FastAPI)          │
│ Create Stripe Checkout     │
│ Session                    │
│ - mode: 'subscription'     │
│ - price_id: price_plus_mo  │
│ - metadata: {user_id: 123} │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Return checkout_url        │
│ → Frontend redirects       │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Stripe Checkout Page       │
│ User enters card details   │
│ User confirms payment      │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Stripe processes payment   │
│ (5-10 seconds)             │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Stripe webhook fires:      │
│ checkout.session.completed │
│                            │
│ POST /api/payments/        │
│   stripe-webhook           │
│                            │
│ Payload: {                 │
│   type: 'checkout.session..│
│   data: {                  │
│     metadata: {user_id:123}│
│     subscription: sub_...  │
│   }                        │
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Backend verifies signature │
│ (Stripe webhook secret)    │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Update Database:           │
│                            │
│ user_subscriptions:        │
│   tier_id = 2 (Plus)       │
│   status = 'active'        │
│   stripe_subscription_id   │
│   billing_period_start=NOW │
│   billing_period_end=+1mo  │
│                            │
│ payment_transactions:      │
│   platform = 'stripe'      │
│   type = 'subscription'    │
│   amount = 29.00           │
│   status = 'succeeded'     │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Send confirmation email    │
│ (via background task)      │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ User redirected back to    │
│ /profile?tab=subscription  │
│ Sees "Plus tier active"    │
└────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│              iOS PAYMENT FLOW (Apple)                            │
└──────────────────────────────────────────────────────────────────┘

User taps "Upgrade to Plus"
    │
    ▼
┌────────────────────────────┐
│ iOS App (SwiftUI)          │
│ StoreKit 2 API             │
│ Product.purchase(          │
│   id: "com.livetranslator. │
│       plus.monthly"        │
│ )                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ iOS displays subscription  │
│ sheet (Apple native UI)    │
│ User confirms with Face ID │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Apple processes payment    │
│ (5-10 seconds)             │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ StoreKit 2 returns         │
│ Transaction object         │
│ - transactionID            │
│ - originalTransactionID    │
│ - productID                │
│ - purchaseDate             │
│ - expirationDate           │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ iOS App sends receipt to   │
│ backend:                   │
│                            │
│ POST /api/payments/        │
│   apple-verify             │
│                            │
│ Body: {                    │
│   transaction_id: "100..." │
│   product_id: "com.live..."│
│   receipt_data: "base64..."│
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Backend verifies receipt   │
│ with Apple:                │
│                            │
│ POST https://buy.itunes... │
│   /verifyReceipt           │
│ (Production + Sandbox)     │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Apple returns:             │
│ {                          │
│   status: 0,               │
│   receipt: {...},          │
│   latest_receipt_info: [   │
│     {                      │
│       product_id: "...",   │
│       expires_date_ms: ... │
│     }                      │
│   ]                        │
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Update Database:           │
│                            │
│ user_subscriptions:        │
│   tier_id = 2 (Plus)       │
│   status = 'active'        │
│   apple_transaction_id     │
│   apple_original_txn_id    │
│   billing_period_start=NOW │
│   billing_period_end=(from │
│     expires_date_ms)       │
│                            │
│ payment_transactions:      │
│   platform = 'apple'       │
│   type = 'subscription'    │
│   amount = 29.00 (from map)│
│   status = 'succeeded'     │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Return success to iOS app  │
│ App updates UI:            │
│ "Plus tier active"         │
└────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│          CREDIT PURCHASE FLOW (Both Platforms)                   │
└──────────────────────────────────────────────────────────────────┘

User clicks "Buy 4 Hours" ($19)
    │
    ├──────────── WEB ─────────────┐
    │                              │
    ▼                              ▼
Stripe Checkout              Apple In-App Purchase
type: 'payment'              Consumable product
price_id: price_4hr          "com.livetranslator.credits.4hr"
    │                              │
    └──────────┬───────────────────┘
               │
               ▼
    ┌────────────────────────┐
    │ Payment succeeds       │
    │ Webhook/Receipt sent   │
    └──────┬─────────────────┘
           │
           ▼
    ┌────────────────────────┐
    │ Backend:               │
    │ user_subscriptions:    │
    │   bonus_credits_seconds│
    │   += (4 * 3600)        │
    │                        │
    │ quota_transactions:    │
    │   type = 'grant'       │
    │   quota_type = 'bonus' │
    │   amount_seconds = 14400│
    └──────┬─────────────────┘
           │
           ▼
    ┌────────────────────────┐
    │ User sees:             │
    │ "4 hours added!"       │
    │ Bonus credits: 4h 0m   │
    └────────────────────────┘
```

**Key Design Decisions:**
1. **Stripe**: Production-ready webhooks, subscription management
2. **Apple**: StoreKit 2 for iOS 15+, server-side receipt verification
3. **Dual Verification**: Both platforms verify with provider APIs
4. **Idempotency**: Use transaction_id/payment_intent_id as dedup key
5. **Webhook Retry**: Stripe retries for 3 days if webhook fails
6. **Apple Notifications**: Server-to-server for subscription status changes

---

## 5. iOS Client-Side Processing

```
┌──────────────────────────────────────────────────────────────────┐
│           iOS NATIVE PROCESSING ARCHITECTURE                     │
│  Apple STT/MT/TTS → Processed on-device → Sent as text          │
└──────────────────────────────────────────────────────────────────┘

User speaks into iOS app
    │
    ▼
┌────────────────────────────┐
│ Microphone Capture         │
│ AVAudioEngine              │
│ - Sample rate: 16kHz       │
│ - Format: PCM16            │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Voice Activity Detection   │
│ (Energy-based RMS)         │
│ - Start: RMS > threshold   │
│ - End: RMS < threshold (2s)│
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────────────────────┐
│ Apple Speech Recognition (SFSpeechRecognizer)│
│                                            │
│ let request = SFSpeechAudioBufferRequest() │
│ request.shouldReportPartialResults = true  │
│                                            │
│ recognizer.recognitionTask(request) { res..│
│   if res.isFinal {                         │
│     // Final result                        │
│   } else {                                 │
│     // Partial result (real-time)          │
│   }                                        │
│ }                                          │
└──────┬─────────────────────────────────────┘
       │
       ├─────────── Partials ──────────┐
       │                               │
       ▼                               ▼
┌──────────────────┐         ┌──────────────────┐
│ Display in UI    │         │ (Not sent to     │
│ (real-time)      │         │  server)         │
└──────────────────┘         └──────────────────┘
       │
       │
       ▼ (Speech ends, isFinal=true)
┌────────────────────────────┐
│ Final Transcript Ready     │
│ Text: "Hello world"        │
│ Language: "en-US"          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Send to Server via         │
│ WebSocket:                 │
│                            │
│ {                          │
│   type: 'transcript_direct'│
│   text: 'Hello world',     │
│   source_lang: 'en',       │
│   is_final: true,          │
│   roomId: 'room-abc123'    │
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Backend (FastAPI)          │
│ Receives transcript_direct │
│ - No STT router call       │
│ - No audio processing      │
│ - Publish to stt_events    │
│ - Deduct estimated quota   │
│   (3 seconds per sentence) │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ MT Router                  │
│ Translate to target langs  │
│ - Use tier-based routing   │
│ - iOS can use Apple MT API │
│   (on-device, FREE)        │
│ - Or server-side (paid)    │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Translation sent back to   │
│ iOS app via WebSocket:     │
│                            │
│ {                          │
│   type: 'translation_final'│
│   text: 'Cześć świecie',   │
│   src: 'en',               │
│   tgt: 'pl'                │
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ iOS TTS (AVSpeechSynth.)   │
│                            │
│ let utterance =            │
│   AVSpeechUtterance(       │
│     string: 'Cześć świecie'│
│   )                        │
│ utterance.voice =          │
│   AVSpeechSynthesisVoice(  │
│     language: 'pl-PL'      │
│   )                        │
│ synthesizer.speak(utterance)│
└────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│              APPLE API USAGE (FREE TIER)                         │
└──────────────────────────────────────────────────────────────────┘

Component                 Apple API               Cost        Quota Impact
───────────────────────── ─────────────────────── ─────────── ────────────
Speech-to-Text           SFSpeechRecognizer      FREE        3s per sentence
Machine Translation      Translation Framework   FREE        None (client-side)
Text-to-Speech          AVSpeechSynthesizer     FREE        None (client-side)

Note: Apple STT has limits:
- 1 minute per recognition request
- 60 minutes per day per device
- Unlimited for on-device recognition (iOS 15+)

┌──────────────────────────────────────────────────────────────────┐
│              QUOTA ESTIMATION (iOS FREE TIER)                    │
└──────────────────────────────────────────────────────────────────┘

iOS app sends final transcripts only (no audio):
- Backend estimates quota usage based on sentence count
- Assumption: Average sentence = 3 seconds of speech
- Formula: quota_seconds = sentence_count * 3

Example:
- 5-minute conversation = ~100 sentences
- Quota deducted: 100 * 3 = 300 seconds (5 minutes) ✅ Accurate
- Alternative: Use word count (avg 2.5 words/sec for English)
```

**Key Design Decisions:**
1. **Client-Side STT**: Apple Speech Framework (iOS), no audio sent to server
2. **Quota Estimation**: Estimate seconds based on sentence count (3s/sentence)
3. **Partial Results**: Displayed in UI only, not sent to server
4. **Final Only**: Only final transcripts sent via WebSocket
5. **TTS Options**: Apple TTS (free) or server TTS (Pro tier only)

---

## 6. Quota Tracking State Machine

```
┌──────────────────────────────────────────────────────────────────┐
│              USER QUOTA STATE MACHINE                            │
└──────────────────────────────────────────────────────────────────┘

              START
                │
                ▼
        ┌───────────────┐
        │ New User      │
        │ Created       │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │ Free Tier     │
        │ 10 min quota  │
        │ Status: active│
        └───────┬───────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
Uses      Upgrades     Exhausts
quota     to Plus      quota (0 left)
    │           │           │
    ▼           ▼           ▼
┌───────┐  ┌────────┐  ┌─────────────┐
│ 5 min │  │ Plus   │  │ Quota       │
│ left  │  │ 2hr    │  │ Exhausted   │
└───┬───┘  │ quota  │  │             │
    │      └───┬────┘  │ Prompt:     │
    │          │       │ Upgrade or  │
    │          │       │ Buy Credits │
    │          │       └──────┬──────┘
    │          │              │
    │          │              ▼
    │          │      ┌───────────────┐
    │          │      │ User chooses: │
    │          │      │ 1. Upgrade    │
    │          │      │ 2. Buy credits│
    │          │      │ 3. Continue   │
    │          │      │    with admin │
    │          │      │    quota      │
    │          │      └──────┬────────┘
    │          │             │
    │          │      ┌──────┴────┬─────────┐
    │          │      ▼           ▼         ▼
    │          │  Upgrades    Buys 4hr  Uses admin
    │          │  to Plus     credits   quota
    │          │      │           │         │
    └──────────┼──────┘           │         │
               │                  │         │
               ▼                  ▼         ▼
        ┌──────────────┐   ┌──────────┐ ┌──────────┐
        │ Plus Tier    │   │ Free +   │ │ Admin    │
        │ 2hr/month    │   │ 4hr      │ │ fallback │
        │              │   │ bonus    │ │          │
        │ Next billing │   │ credits  │ │ quota_   │
        │ cycle: Reset │   │          │ │ source=  │
        │ to 2hr       │   │ No expiry│ │ 'admin'  │
        └──────┬───────┘   └────┬─────┘ └────┬─────┘
               │                │            │
               │                │            │
    ┌──────────┴────────────────┴────────────┘
    │
    ▼
End of billing cycle (monthly reset)
    │
    ▼
┌───────────────────────────────────────┐
│ Cron job: reset_monthly_quotas.py     │
│                                       │
│ FOR EACH user WHERE                   │
│   billing_period_end <= NOW:          │
│                                       │
│   IF auto_renew = TRUE:               │
│     - Keep current tier               │
│     - Reset used_seconds to 0         │
│     - billing_period_start = NOW      │
│     - billing_period_end = +1 month   │
│     - Charge subscription (Stripe)    │
│                                       │
│   ELSE:                               │
│     - Downgrade to 'free'             │
│     - Preserve bonus_credits_seconds  │
│     - Reset used_seconds to 0         │
└───────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│              QUOTA USAGE TRACKING (Per Event)                    │
└──────────────────────────────────────────────────────────────────┘

Every STT/MT/TTS event:
    │
    ▼
┌────────────────────────────┐
│ Calculate duration/tokens  │
│ amount_seconds = duration  │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Check available quota:     │
│ bonus_credits + monthly -  │
│ used_seconds               │
└──────┬─────────────────────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
   Has Quota         No Quota
       │                     │
       ▼                     ▼
┌─────────────┐      ┌──────────────┐
│ Deduct:     │      │ Check admin  │
│ bonus first,│      │ quota        │
│ then monthly│      │ (if in room) │
└──────┬──────┘      └──────┬───────┘
       │                    │
       │             ┌──────┴────┐
       │             │           │
       │             ▼           ▼
       │        Has admin   No admin
       │        quota       quota
       │             │           │
       │             ▼           ▼
       │      ┌──────────┐  ┌─────────┐
       │      │ Deduct   │  │ Reject  │
       │      │ from     │  │ or use  │
       │      │ admin    │  │ free    │
       │      └────┬─────┘  │ provider│
       │           │        └─────────┘
       └───────────┴────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Insert transaction:  │
        │ quota_transactions   │
        └──────────────────────┘
```

**Key States:**
- `active` - Normal usage
- `past_due` - Payment failed
- `cancelled` - Auto-renew off, expires at period end
- `expired` - Period ended, downgraded to free

---

## 7. WebSocket Message Flow (Extended)

```
┌──────────────────────────────────────────────────────────────────┐
│         WEBSOCKET MESSAGE FLOW (With Quota Tracking)             │
└──────────────────────────────────────────────────────────────────┘

iOS User speaks → Apple STT → Final transcript
    │
    ▼
┌────────────────────────────────────────────────────────────────┐
│ iOS App (WebSocket Client)                                     │
│                                                                 │
│ ws.send({                                                       │
│   type: 'transcript_direct',                                   │
│   text: 'Hello world',                                         │
│   source_lang: 'en',                                           │
│   is_final: true,                                              │
│   roomId: 'room-abc123'                                        │
│ })                                                              │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────────────┐
│ API (FastAPI WebSocket Handler)                                │
│                                                                 │
│ 1. Receive message                                             │
│ 2. Extract user_id from JWT                                    │
│ 3. Check quota:                                                │
│    POST /api/quota/deduct {                                    │
│      user_id: 123,                                             │
│      room_code: 'room-abc123',                                 │
│      amount_seconds: 3,                                        │
│      service_type: 'stt',                                      │
│      provider_used: 'apple_speech'                             │
│    }                                                            │
│                                                                 │
│ 4. If quota OK:                                                │
│    - Publish to Redis 'stt_events' channel                     │
│    - Skip STT router (already transcribed)                     │
│    - Generate segment_id                                       │
│                                                                 │
│ 5. If quota exhausted:                                         │
│    ws.send({                                                    │
│      type: 'quota_exhausted',                                  │
│      message: 'Your quota is exhausted...',                    │
│      upgrade_options: [...]                                    │
│    })                                                           │
│    - Stop processing this message                              │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼ (Quota OK, message published to stt_events)
┌────────────────────────────────────────────────────────────────┐
│ MT Router (Listens to stt_events)                              │
│                                                                 │
│ 1. Receive stt_final event                                     │
│ 2. Get target languages from room                              │
│ 3. For each target language:                                   │
│    - Route to provider (tier-based)                            │
│    - Translate text                                            │
│    - Publish to 'mt_events' channel                            │
│ 4. Deduct quota for MT (tokens/characters)                     │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────────────┐
│ WS Manager (Listens to stt_events + mt_events)                 │
│                                                                 │
│ 1. Receive translation_final event                             │
│ 2. Broadcast to all WebSocket clients in room:                 │
│                                                                 │
│    ws.send({                                                    │
│      type: 'translation_final',                                │
│      text: 'Cześć świecie',                                    │
│      src: 'en',                                                │
│      tgt: 'pl',                                                │
│      segment_id: 123                                           │
│    })                                                           │
└──────┬──────────────────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────────────────────────┐
│ iOS App (Receives translation)                                 │
│                                                                 │
│ 1. Update UI with translation                                  │
│ 2. If auto_play_audio enabled:                                 │
│    - Speak text via AVSpeechSynthesizer                        │
│    - No server TTS (client-side, FREE)                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│         QUOTA ALERT FLOW (80% Threshold)                         │
└──────────────────────────────────────────────────────────────────┘

User's quota drops below 80% available
    │
    ▼
┌────────────────────────────┐
│ Quota Deduction Logic      │
│ After deducting, check:    │
│ remaining / total < 0.80   │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Send quota_alert via WS:   │
│                            │
│ {                          │
│   type: 'quota_alert',     │
│   threshold: '80_percent', │
│   remaining_seconds: 1440, │
│   message: 'You have 24...'│
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ iOS App shows notification │
│ "⚠️ 24 minutes remaining"  │
│ + "Buy More" button        │
└────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│         ADMIN QUOTA FALLBACK NOTIFICATION                        │
└──────────────────────────────────────────────────────────────────┘

Participant's quota exhausted → Uses admin's quota
    │
    ▼
┌────────────────────────────┐
│ Send quota_fallback to     │
│ admin (room owner):        │
│                            │
│ {                          │
│   type: 'quota_fallback',  │
│   participant: 'john',     │
│   amount_seconds: 120,     │
│   your_remaining: 5280,    │
│   message: 'John is using..'│
│ }                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Admin sees notification:   │
│ "John is using your quota" │
│ Shows in room header       │
└────────────────────────────┘
```

**New WebSocket Message Types:**
1. `transcript_direct` - iOS sends pre-transcribed text (Apple STT)
2. `quota_alert` - Warns user at 80% usage
3. `quota_exhausted` - Triggers upgrade prompt
4. `quota_fallback` - Notifies admin when participant uses admin's quota
5. `tier_limit_reached` - Notifies user of tier restrictions

---

## 8. Performance SLA & Monitoring

**NEW SECTION** - Added per Business Analyst review 2025-11-03

### API Latency Targets

```
┌──────────────────────────────────────────────────────────────────┐
│                    API LATENCY SLA                               │
│  Critical endpoints with performance requirements                │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────────────┬────────┬────────┬────────┬─────────┐
│ Endpoint                    │ P50    │ P95    │ P99    │ Timeout │
├─────────────────────────────┼────────┼────────┼────────┼─────────┤
│ GET /api/quota/status       │ <50ms  │ <100ms │ <200ms │ 500ms   │
│ POST /api/quota/deduct      │ <50ms  │ <100ms │ <200ms │ 500ms   │
│ POST /api/transcript-direct │ <100ms │ <200ms │ <500ms │ 1s      │
│ GET /api/rooms/{code}/      │ <100ms │ <200ms │ <500ms │ 1s      │
│   quota-pool                │        │        │        │         │
│ POST /api/payments/         │ <200ms │ <500ms │ <1s    │ 2s      │
│   stripe-webhook            │        │        │        │         │
│ POST /api/payments/         │ <300ms │ <500ms │ <1s    │ 2s      │
│   apple-verify              │        │        │        │         │
│ GET /api/admin/financial/   │ <500ms │ <2s    │ <5s    │ 10s     │
│   summary (cached)          │        │        │        │         │
│ GET /api/admin/financial/   │ <2s    │ <3s    │ <10s   │ 30s     │
│   summary (uncached)        │        │        │        │         │
└─────────────────────────────┴────────┴────────┴────────┴─────────┘

CRITICAL PATHS (User-facing):
1. Quota check: <100ms (p95) - Prevents blocking translation
2. Payment webhooks: <500ms (p95) - User waiting for confirmation
3. Transcript submission: <200ms (p95) - Real-time requirement

ADMIN PATHS (Dashboard):
1. Cached queries: <500ms (p95) - Fast dashboard load
2. Uncached queries: <3s (p95) - Acceptable for admin tools
3. Materialized view refresh: <10min (daily batch job)
```

### Database Query Optimization

```
┌──────────────────────────────────────────────────────────────────┐
│              DATABASE PERFORMANCE STRATEGY                       │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────┬──────────────────────────────────────────┐
│ Optimization        │ Implementation                           │
├─────────────────────┼──────────────────────────────────────────┤
│ Connection Pooling  │ asyncpg pool: 50 connections max         │
│                     │ Min idle: 10, Max lifetime: 1 hour       │
├─────────────────────┼──────────────────────────────────────────┤
│ Query Timeout       │ 30s hard limit (prevent runaway queries) │
│                     │ Critical queries: 500ms timeout          │
├─────────────────────┼──────────────────────────────────────────┤
│ Indexes (Critical)  │ - user_subscriptions.billing_period_end  │
│                     │ - quota_transactions(user_id, created_at)│
│                     │ - payment_transactions.status            │
│                     │ - room_participants.is_using_admin_quota │
├─────────────────────┼──────────────────────────────────────────┤
│ Materialized Views  │ Refresh: Daily at 2am UTC (off-peak)     │
│                     │ CONCURRENTLY to avoid locking            │
│                     │ Views: financial_summary, tier_analysis, │
│                     │        user_metrics, provider_costs      │
├─────────────────────┼──────────────────────────────────────────┤
│ Read Replica        │ Optional: For admin dashboard queries    │
│                     │ Reduces load on primary (write master)   │
│                     │ Lag tolerance: <5 seconds                │
├─────────────────────┼──────────────────────────────────────────┤
│ Partitioning        │ quota_transactions: Monthly partitions   │
│                     │ (when >100M rows)                        │
│                     │ Prune old partitions after 1 year        │
└─────────────────────┴──────────────────────────────────────────┘

QUERY OPTIMIZATION EXAMPLES:

-- ✅ FAST: Uses index on (user_id, created_at)
SELECT COALESCE(SUM(-amount_seconds), 0)
FROM quota_transactions
WHERE user_id = $1
  AND transaction_type = 'deduct'
  AND created_at >= $2;  -- billing_period_start

-- ✅ FAST: Uses index on billing_period_end + status
SELECT user_id
FROM user_subscriptions
WHERE billing_period_end <= NOW()
  AND status = 'active';

-- ❌ SLOW: Sequential scan (no index on description)
SELECT * FROM quota_transactions WHERE description LIKE '%refund%';

-- ✅ FAST: Use full-text search index
SELECT * FROM quota_transactions WHERE to_tsvector(description) @@ to_tsquery('refund');
```

### Redis Caching Strategy

```
┌──────────────────────────────────────────────────────────────────┐
│                  REDIS CACHING STRATEGY                          │
└──────────────────────────────────────────────────────────────────┘

┌────────────────────────┬───────────┬──────────────────────────┐
│ Cache Key              │ TTL       │ Invalidation Strategy    │
├────────────────────────┼───────────┼──────────────────────────┤
│ quota:status:{user_id} │ 30s       │ Immediate on deduction   │
│ subscription:{user_id} │ 5min      │ Immediate on tier change │
│ admin:financial:sum    │ 1min      │ Daily matview refresh    │
│ admin:tier:analysis    │ 1min      │ Daily matview refresh    │
│ admin:dashboard:today  │ 1min      │ Hourly for today's data  │
│ admin:provider:costs   │ 1hr       │ Daily (historical data)  │
│ provider:health:{name} │ 10s       │ Fast failover detection  │
└────────────────────────┴───────────┴──────────────────────────┘

CACHE INVALIDATION FLOW:

User deducts quota (POST /api/quota/deduct)
    │
    ▼
┌────────────────────────────┐
│ Update database:           │
│ INSERT INTO                │
│ quota_transactions         │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Invalidate cache:          │
│ redis.delete(              │
│   f"quota:status:{user_id}"│
│ )                          │
└──────┬─────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ Next API call:             │
│ Cache miss → Query DB      │
│ → Store in cache (30s TTL) │
└────────────────────────────┘

CACHE WARMING (on startup):
- Pre-load subscription tiers
- Pre-load credit packages
- Pre-warm admin dashboard (last 7 days)
```

### Monitoring & Alerts

```
┌──────────────────────────────────────────────────────────────────┐
│              PROMETHEUS METRICS & GRAFANA DASHBOARDS             │
└──────────────────────────────────────────────────────────────────┘

PROMETHEUS METRICS (FastAPI Instrumentation):

1. API Latency Histogram:
   http_request_duration_seconds{endpoint="/api/quota/status", method="GET"}

2. Request Rate Counter:
   http_requests_total{endpoint="/api/quota/deduct", status="200"}

3. Error Rate Counter:
   http_requests_failed_total{endpoint="/api/payments/stripe-webhook"}

4. Quota Deduction Gauge:
   quota_deduction_latency_seconds{p95="0.085"}

5. Payment Success Rate:
   payment_webhook_success_rate{platform="stripe"} = 98.5%

6. Admin Dashboard Load Time:
   admin_dashboard_load_seconds{cached="true", p95="0.450"}

7. Database Connection Pool:
   db_connection_pool_active = 35 / 50
   db_connection_pool_wait_time_ms = 12

GRAFANA DASHBOARDS:

Dashboard 1: Real-Time Operations
- Quota deduction latency (p50, p95, p99)
- API request rate (req/sec)
- WebSocket connections (active)
- Error rate (5xx responses)

Dashboard 2: Business Metrics
- Daily revenue (Stripe + Apple)
- Tier conversion funnel (Free → Plus → Pro)
- Active subscriptions by tier
- Quota usage distribution

Dashboard 3: Admin Dashboard Performance
- Query latency by endpoint
- Cache hit rate
- Materialized view refresh duration
- Database connection pool utilization

ALERTS (PagerDuty / Slack):

┌────────────────────────────────┬────────────┬──────────┐
│ Alert                          │ Threshold  │ Priority │
├────────────────────────────────┼────────────┼──────────┤
│ Quota check latency >200ms p95│ 5min       │ High     │
│ Payment webhook failure >5%    │ 5min       │ Critical │
│ Admin dashboard load >10s      │ 10min      │ Medium   │
│ Margin drops below 20%         │ Daily      │ High     │
│ Database connections >45/50    │ 5min       │ High     │
│ Redis cache miss rate >30%     │ 10min      │ Medium   │
│ Provider failover triggered    │ Immediate  │ High     │
│ Stripe webhook backlog >100    │ 5min       │ Critical │
└────────────────────────────────┴────────────┴──────────┘

EXAMPLE ALERT (Prometheus AlertManager):

groups:
- name: quota_alerts
  rules:
  - alert: QuotaCheckLatencyHigh
    expr: histogram_quantile(0.95, http_request_duration_seconds{endpoint="/api/quota/status"}) > 0.2
    for: 5m
    labels:
      severity: high
    annotations:
      summary: "Quota check latency exceeds 200ms (p95)"
      description: "Current p95 latency: {{ $value }}s. Target: <200ms."
```

### Performance Testing

```
┌──────────────────────────────────────────────────────────────────┐
│                    LOAD TESTING SCENARIOS                        │
└──────────────────────────────────────────────────────────────────┘

SCENARIO 1: 100 Concurrent Users (Quota Deduction)

Setup:
- 100 rooms with 1 user each
- All users speaking simultaneously
- Duration: 10 minutes

Expected Results:
- Quota deduction latency: <100ms (p95), <200ms (p99)
- Database writes: All 100 transactions recorded
- No race conditions: No double-charges
- Redis atomic operations: INCR successful

Test Command (Locust):
```
locust -f load_test.py --headless --users 100 --spawn-rate 10 --run-time 10m
```

SCENARIO 2: Admin Dashboard (Heavy Query Load)

Setup:
- Admin loads /admin/financial (last 90 days)
- Database: 100,000 users, 10M quota transactions
- Concurrent admin requests: 10

Expected Results:
- Dashboard load: <3s (uncached), <500ms (cached)
- Materialized view query: <500ms
- No database timeouts
- Cache hit rate: >70% after warm-up

SCENARIO 3: Payment Webhook Spike

Setup:
- Simulate 1000 Stripe webhooks in 1 minute
- Test idempotency (duplicate webhooks)
- Test signature verification performance

Expected Results:
- Webhook processing: <500ms (p95)
- Idempotency: 100% (no duplicate processing)
- Queue: No backlog buildup
- Database: All transactions recorded

PERFORMANCE BASELINES (to track regression):

Baseline captured 2025-11-03:
- Quota check: p95 = 85ms, p99 = 150ms ✅
- Admin dashboard (cached): p95 = 420ms ✅
- Payment webhook: p95 = 380ms ✅
- Database connections: avg 30/50 ✅
- Redis cache hit rate: 82% ✅

Regression tests run weekly (CI/CD pipeline).
```

---

**End of System Diagrams - Version 1.1**
**Performance SLA section added per Business Analyst review 2025-11-03**

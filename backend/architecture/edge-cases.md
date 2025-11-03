# LiveTranslator Tier System - Edge Cases & Error Scenarios

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Requirements

---

## Overview

45+ edge cases covering quota system, payment integration, provider routing, iOS/Web synchronization, admin dashboard, and security.

**Edge Case Categories:**
1. Quota System (10 cases)
2. Payment System (9 cases)
3. Provider Routing (8 cases)
4. iOS/Web Synchronization (8 cases)
5. Admin Dashboard (6 cases)
6. Security & Abuse (4 cases)

---

## 1. Quota System Edge Cases

### EC-Q01: User Exhausts Quota Mid-Sentence

**Scenario:** User speaking when quota hits 0 during sentence

**Expected Behavior:**
1. Current sentence completes normally (already in flight)
2. After sentence completes, send `quota_exhausted` message
3. Next sentence blocked until quota added
4. Show upgrade modal

**Alternative:** Immediately cut off (bad UX)

**Implementation:**
- STT router checks quota before processing new audio chunk
- In-flight transcriptions always complete
- WebSocket message sent after current segment finalized

**Test Case:**
```python
def test_quota_exhaustion_mid_sentence():
    user.quota_remaining = 5  # 5 seconds
    user.speak_for(10)  # 10 second sentence
    # First 5 seconds transcribed
    # Sentence completes
    # quota_exhausted sent
    # Next sentence blocked
```

---

### EC-Q02: Admin Quota Also Exhausted (Room Blocked)

**Scenario:** Participant exhausted, falls back to admin, admin also at 0

**Expected Behavior:**
1. Participant quota exhausted → Try admin quota
2. Admin quota also exhausted → Send `quota_exhausted` to participant
3. Show modal: "Room owner quota exhausted. Ask them to upgrade."
4. Microphone button disabled
5. Participant can still see translations from others
6. Admin receives notification: "Your quota is exhausted. Room paused."

**Recovery:**
- Admin buys credits → Participants auto-resume
- Admin upgrades tier → Monthly quota restored → Auto-resume

**Implementation:**
- Quota waterfall: `participant → admin → exhausted`
- Redis check: `get_user_quota_available(admin_id)`
- WebSocket broadcast: `room_quota_exhausted` to all participants

---

### EC-Q03: Multiple Participants Exhaust Simultaneously

**Scenario:** 3 participants hit quota=0 within 1 second

**Expected Behavior:**
1. All 3 participants fall back to admin quota simultaneously
2. Admin receives 3 separate notifications (debounced to 1 summary)
3. Admin sees: "3 participants now using your quota"
4. All quota transactions recorded with `quota_source='admin'`
5. Redis INCR ensures no race conditions

**Implementation:**
- Use Redis atomic operations for quota deduction
- Debounce notifications (5-second window)
- Summary notification: "X participants using your quota"

---

### EC-Q04: Quota Reset During Active Session

**Scenario:** User in active room at midnight (monthly reset time)

**Expected Behavior:**
1. Cron job runs: Reset user quota to monthly amount
2. WebSocket sends `quota_reset` message to connected clients
3. Frontend updates quota indicator (no page reload)
4. User sees: "Your quota has been reset to 2 hours"
5. Conversation continues without interruption

**Edge Case:** User speaking exactly at midnight
- Current segment completes with old quota
- Next segment uses new quota

**Implementation:**
- Cron job: `UPDATE user_subscriptions SET total_seconds_used=0 WHERE billing_period_end <= NOW()`
- WebSocket: Publish `quota_reset` event to active sessions
- Frontend: Listen for event, update state

---

### EC-Q05: iOS App Offline Quota Tracking

**Scenario:** iOS user speaks in room, loses internet, regains internet

**Expected Behavior:**
1. User speaks while offline
2. iOS app uses Apple STT (on-device, works offline)
3. iOS app queues quota transactions locally (SQLite)
4. iOS app reconnects to internet
5. iOS app syncs queued transactions to backend
6. Backend deducts quota (may be delayed 5-10 min)
7. iOS app shows updated quota

**Data Loss Prevention:**
- iOS app stores: `transaction_id`, `amount_seconds`, `timestamp`
- Backend deduplicates via `transaction_id` (UUID)
- If quota exhausted during sync → User notified, can buy credits

**Implementation:**
- iOS: Local SQLite table: `pending_quota_transactions`
- iOS: Background sync task runs every 5 minutes (if online)
- Backend: Idempotency check via `transaction_id`

---

### EC-Q06: User Downgrade (Pro → Plus) Mid-Billing Cycle

**Scenario:** Pro user downgrades to Plus on day 15 of 30-day cycle

**Expected Behavior:**
1. User clicks "Downgrade to Plus"
2. System shows: "Downgrade scheduled for Dec 1 (end of billing period)"
3. User keeps Pro tier until Dec 1
4. No refund issued (user consumed Pro features)
5. On Dec 1:
   - Tier changes to Plus
   - Monthly quota changes to 2 hours
   - Bonus credits preserved
   - Stripe subscription updated

**Alternative (Immediate Downgrade):**
- Pro-rated refund calculated
- Tier downgraded immediately
- Quota reduced immediately (may cause mid-conversation interruption)

**Recommendation:** Schedule downgrade for end of period (better UX)

---

### EC-Q07: Bonus Credits Expire or Don't Expire?

**Decision Point:** Should purchased credits expire?

**Option A: Credits Expire After 1 Year**
- Pros: Prevents hoarding, encourages usage
- Cons: Bad UX, user loses money

**Option B: Credits Never Expire**
- Pros: Better UX, user keeps value
- Cons: Accounting complexity (long-term liability)

**Recommendation:** Credits never expire (better user trust)

**Implementation:**
- `bonus_credits_seconds` persists indefinitely
- User can accumulate multiple credit purchases
- User sees: "Bonus credits: 8 hours 30 minutes"

---

### EC-Q08: Quota Deduction Double-Charge (Race Condition)

**Scenario:** Two audio chunks arrive simultaneously, both deduct quota

**Expected Behavior:**
1. Both chunks enter STT router concurrently
2. Both call `deduct_quota(user_id, 3)` simultaneously
3. Redis INCR ensures atomic increment
4. User charged exactly 6 seconds (not 3 or 9)

**Implementation:**
```python
# Use Redis INCR (atomic)
redis.incr(f"quota:{user_id}:used", amount=3)
```

**Avoidance:**
- Never read-modify-write quota (race condition)
- Always use atomic operations (INCR, DECR)

---

### EC-Q09: User Charges Back Payment, Keeps Quota

**Scenario:** User buys 4 hours credits, then disputes charge with bank

**Expected Behavior:**
1. Stripe webhook: `charge.dispute.created`
2. Backend receives webhook
3. Backend checks: User still has bonus credits
4. Backend actions:
   - Deduct `bonus_credits_seconds` (revoke credits)
   - Mark user account: `chargebacks = 1`
   - If `chargebacks >= 2`: Suspend account
5. User receives email: "Chargeback detected. Credits revoked."
6. If user already used credits: Create negative balance
7. Block future purchases until balance cleared

**Implementation:**
- Stripe webhook handler: `charge.dispute.created`
- Database: Add `chargebacks` column to users table
- Enforce: `WHERE chargebacks < 2` for purchases

---

### EC-Q10: Cron Job Fails (Quota Not Reset)

**Scenario:** Monthly quota reset cron job crashes

**Expected Behavior:**
1. Cron job attempts reset, crashes (e.g., database timeout)
2. Alert sent to admin: "Quota reset failed at 2025-12-01 00:00"
3. Backup cron job runs 1 hour later (01:00)
4. If still failing: Manual intervention required
5. Once fixed: Run catch-up reset for all missed users

**Monitoring:**
- Cron job logs success/failure
- Alert if no success log within 2 hours of scheduled time
- Dashboard shows: "Last quota reset: 2025-12-01 00:05" (green if recent)

**Recovery:**
```sql
-- Manual reset script
UPDATE user_subscriptions
SET total_seconds_used = 0,
    billing_period_start = billing_period_end,
    billing_period_end = billing_period_end + INTERVAL '30 days'
WHERE billing_period_end <= NOW()
  AND total_seconds_used > 0;
```

---

## 2. Payment System Edge Cases

### EC-P01: Stripe Webhook Delayed (>5 Minutes)

**Scenario:** User completes payment, webhook takes 10 minutes to arrive

**Expected Behavior:**
1. User completes Stripe Checkout
2. User redirected back to app with `session_id` in URL
3. Frontend shows: "Payment processing..."
4. Frontend polls: `GET /api/payments/status?session_id=...` every 5 seconds
5. After 3 minutes: Frontend shows: "Payment taking longer than usual. We'll email you."
6. Webhook arrives 10 minutes later
7. Backend processes payment, updates tier
8. User receives email: "Payment confirmed! Plus tier activated."
9. Next time user opens app: Tier updated

**Fallback:**
- After 5 minutes: Backend polls Stripe API directly
- Query: `stripe.PaymentIntent.retrieve(payment_intent_id)`
- If status='succeeded': Process payment manually

---

### EC-P02: Duplicate Payment (User Clicks Twice)

**Scenario:** User clicks "Subscribe" button twice rapidly

**Expected Behavior:**
1. First click: Creates Stripe Checkout session
2. Second click: Returns same session (idempotency)
3. User redirected to Stripe once
4. Payment processed once
5. Webhook received once
6. User charged once

**Implementation:**
- Stripe Checkout session: Include `client_reference_id={user_id}`
- Backend: Check if active session exists for user
- If exists and not expired: Return existing session

```python
# Check for existing session (last 10 minutes)
existing_session = stripe.checkout.Session.list(
    customer=customer_id,
    limit=1,
    created={'gte': int(time.time()) - 600}
)
if existing_session:
    return existing_session.url
```

---

### EC-P03: User Downgrade (Pro → Plus) Pro-Rated Credit

**Scenario:** User pays $199 for Pro on Nov 1, downgrades on Nov 15

**Expected Behavior (Stripe Standard):**
1. User clicks "Downgrade to Plus"
2. System schedules downgrade for Dec 1
3. No immediate refund
4. On Dec 1:
   - Stripe charges $29 for Plus (next cycle)
   - User effectively paid $199 for 1 month Pro

**Expected Behavior (Pro-Rated Refund):**
1. User clicks "Downgrade to Plus"
2. System calculates:
   - Days used: 15 days Pro
   - Days remaining: 15 days
   - Pro cost: $199/30 = $6.63/day
   - Plus cost: $29/30 = $0.97/day
   - Refund: ($6.63 - $0.97) × 15 = $84.90
3. System issues Stripe refund: $84.90
4. User tier downgraded immediately to Plus
5. User receives email with refund details

**Recommendation:** Schedule downgrade (no refund) - simpler, industry standard

---

### EC-P04: Payment Fails During Renewal (Card Expired)

**Scenario:** User's card expires, renewal payment fails

**Expected Behavior:** (See UC-009 for full flow)
1. **Day 1:** Payment fails, status='past_due'
2. **Day 2:** Stripe auto-retry #1 fails
3. **Day 4:** Stripe auto-retry #2 fails
4. **Day 7:** Stripe auto-retry #3 fails (final attempt)
5. **Day 7:** Subscription canceled, tier downgraded to Free
6. Bonus credits preserved

**Grace Period:**
- User keeps tier for 7 days (Stripe retry period)
- User can update card anytime during grace period
- If updated: Immediate retry, tier restored

---

### EC-P05: Apple Receipt Fraud (Jailbroken Device)

**Scenario:** Malicious user sends forged Apple receipt

**Expected Behavior:**
1. iOS app calls backend: `POST /api/payments/apple-verify`
2. Backend receives receipt data
3. Backend calls Apple's verifyReceipt API
4. Apple returns: `status=21002` (invalid receipt)
5. Backend rejects: `{"verified": false, "error": "Invalid receipt"}`
6. iOS app shows: "Purchase verification failed. Contact support."
7. No credits granted, no tier updated
8. Backend logs suspicious activity (potential fraud)

**Additional Checks:**
- Verify `bundle_id` matches app
- Verify `product_id` matches configured products
- Check `original_transaction_id` for duplicates
- Rate limit: Max 5 verifications per user per hour

---

### EC-P06: User Buys Credits on iOS and Web Simultaneously

**Scenario:** User has both iOS and Web open, clicks "Buy 4 Hours" on both

**Expected Behavior:**
1. iOS purchase completes first (Apple IAP)
2. Backend verifies receipt, grants 4 hours
3. Web purchase completes 2 seconds later (Stripe)
4. Backend verifies payment, grants another 4 hours
5. User has 8 hours bonus credits total
6. Both purchases recorded in `payment_transactions`
7. No duplicate detection (user intentionally bought twice)

**Alternative (Prevent Duplicate):**
- Check last purchase timestamp
- If same package purchased within 60 seconds: Show confirmation: "You just purchased this. Buy again?"
- User confirms: Allow duplicate
- User cancels: Refund Stripe, reject purchase

**Recommendation:** Allow duplicates (user intent unclear, better to allow)

---

### EC-P07: Stripe Webhook Signature Invalid

**Scenario:** Attacker sends fake webhook to `/api/payments/stripe-webhook`

**Expected Behavior:**
1. Backend receives webhook POST request
2. Backend extracts `Stripe-Signature` header
3. Backend verifies signature using webhook secret
4. Signature invalid → Return `400 Bad Request`
5. Log security event: "Invalid Stripe webhook signature from IP X.X.X.X"
6. No database changes
7. Attacker cannot forge payments

**Implementation:**
```python
try:
    event = stripe.Webhook.construct_event(
        payload, sig_header, webhook_secret
    )
except ValueError:
    return {"error": "Invalid payload"}, 400
except stripe.error.SignatureVerificationError:
    return {"error": "Invalid signature"}, 400
```

---

### EC-P08: User Cancels Stripe Subscription, Then Immediately Resubscribes

**Scenario:** User cancels Plus on Nov 15, changes mind, resubscribes on Nov 16

**Expected Behavior:**
1. Nov 15: User cancels subscription
   - Stripe subscription status = 'canceled'
   - User tier remains Plus until Dec 1
   - `auto_renew = false`
2. Nov 16: User clicks "Subscribe to Plus"
   - New Stripe subscription created
   - User charged $29 immediately
   - New billing period: Nov 16 - Dec 16
   - Old subscription ignored (already canceled)
3. User has overlapping Plus access:
   - Old: Until Dec 1
   - New: Nov 16 - Dec 16
4. Effective billing period: Nov 16 - Dec 16 (use new)

**Alternative (Credit for Overlap):**
- Detect overlap: Nov 16 - Dec 1 (15 days)
- Pro-rate new charge: $29 × (15/30) = $14.50 credit
- Apply credit to first renewal

**Recommendation:** No overlap credit (simpler, rare case)

---

### EC-P09: iOS App Rejected Due to IAP Violations

**Scenario:** Apple rejects app for violating In-App Purchase guidelines

**Common Violations:**
1. Web link in iOS app (can't link to Stripe checkout)
2. Mentioning "cheaper on web" in iOS app
3. Using non-Apple payment in iOS (Stripe)

**Expected Behavior (Compliant):**
1. iOS app: Only shows Apple IAP for subscriptions
2. iOS app: No mention of Web pricing
3. iOS app: No external payment links
4. Web app: Can use Stripe freely
5. Cross-platform: User can subscribe on either platform

**Implementation:**
- `#if iOS` compiler directives for payment code
- Separate UI flows: iOS = StoreKit, Web = Stripe
- No price comparison in iOS app

---

## 3. Provider Routing Edge Cases

### EC-PR01: All Plus Providers Down

**Scenario:** Speechmatics, Google v2, and Azure all report errors

**Expected Behavior:**
1. Plus user creates room
2. Backend checks provider health:
   - Speechmatics: status='down'
   - Google v2: status='down'
   - Azure: status='down'
3. Backend falls back to Free tier providers:
   - Web: Speechmatics Basic (budget tier)
   - iOS: Apple STT (always available)
4. User notified: "Premium providers unavailable. Using fallback."
5. Translation quality may be reduced
6. User still charged Plus tier price (service partially delivered)

**Recovery:**
- Health check runs every 60 seconds
- When provider recovers: Automatic switch to premium

---

### EC-PR02: User Tier Changes Mid-Conversation

**Scenario:** User upgrades from Free → Plus during active room

**Expected Behavior:**
1. User in room, using Free tier providers
2. User completes Plus tier purchase (Stripe webhook)
3. Backend updates `user_subscriptions.tier_id = 2`
4. Backend sends WebSocket: `tier_updated`
5. Frontend shows notification: "Upgraded to Plus! Better providers now available."
6. **Current segment:** Completes with Free tier provider
7. **Next segment:** Uses Plus tier provider (Speechmatics)
8. Smooth transition, no disconnection

**Implementation:**
- STT router checks user tier before routing each new audio chunk
- Cache tier for 30 seconds (balance: freshness vs performance)
- WebSocket message triggers immediate cache invalidation

---

### EC-PR03: iOS Free User Tries Premium Provider

**Scenario:** iOS Free user tries to manually select Speechmatics

**Expected Behavior:**
1. User opens provider settings
2. User sees premium providers (grayed out)
3. User taps "Speechmatics"
4. System shows modal:
   - "Premium providers require Plus tier"
   - "Upgrade to Plus ($29/mo) to unlock"
   - [Upgrade Button] [Cancel]
5. User clicks Cancel → Remains on Apple STT
6. User clicks Upgrade → Redirects to StoreKit subscription

**Implementation:**
- Frontend: Disable premium provider dropdowns for Free tier
- Backend: Double-check tier before routing (security)
- Backend: Return `403 Forbidden` if Free user tries premium

---

### EC-PR04: Provider Quota Exhausted (API Limit)

**Scenario:** OpenAI GPT-4o-mini hits rate limit (10k requests/day)

**Expected Behavior:**
1. User speaks, triggers MT translation
2. MT router calls OpenAI API
3. OpenAI returns: `429 Too Many Requests`
4. MT router catches error
5. MT router falls back to secondary provider (DeepL)
6. Translation succeeds with fallback
7. User sees: "Translation provider switched due to limits"
8. Backend logs: "OpenAI quota exhausted, using DeepL"

**Prevention:**
- Monitor provider usage daily
- Alert if approaching 80% of daily limit
- Increase API limits proactively

---

### EC-PR05: iOS Offline → Online (STT Provider Sync)

**Scenario:** iOS user loses internet, speaks offline, reconnects

**Expected Behavior:**
1. User speaks while offline
2. iOS uses Apple STT (on-device, works offline)
3. iOS queues transcriptions locally
4. User reconnects to internet
5. iOS syncs queued transcriptions to backend:
   - Sends `transcript_direct` messages with historical timestamps
6. Backend accepts historical messages (up to 10 minutes old)
7. Backend publishes to `stt_events` channel
8. Other participants see messages appear (may be delayed)

**Rejection:**
- Messages older than 10 minutes: Rejected (too stale)
- User notified: "Some offline messages too old, not synced"

---

### EC-PR06: Provider Returns Gibberish (Bad Transcription)

**Scenario:** Speechmatics returns: "ajsdlkfjas dfkljasdf kjasdf"

**Expected Behavior:**
1. STT router receives transcription
2. STT router validates:
   - Check confidence score (if available)
   - Check character set (ASCII/UTF-8)
   - Check language detection
3. If confidence < 30%: Reject, retry with fallback provider
4. If gibberish detected: Log error, notify user
5. User sees: "Transcription quality poor. Please repeat."

**Implementation:**
- Confidence threshold: 0.3 (30%)
- Fallback chain: Primary → Fallback → Local

---

### EC-PR07: Diarization Fails (Multiple Speakers, 1 Detected)

**Scenario:** 3 people speaking, provider detects only 1 speaker

**Expected Behavior:**
1. Room has 3 participants
2. Speechmatics returns: `speaker_id=1` for all transcriptions
3. Backend fallback: Use email-based speaker detection
   - Map WebSocket connection → User email
   - Use email as speaker_id
4. Frontend shows correct speaker labels
5. Diarization accuracy degrades, but functional

---

### EC-PR08: Provider Latency Spike (10s Delay)

**Scenario:** Google Cloud Speech API takes 10 seconds to respond

**Expected Behavior:**
1. User speaks
2. Audio sent to Google v2
3. No response after 5 seconds (timeout)
4. STT router cancels request
5. STT router falls back to Azure (secondary)
6. Azure responds in 2 seconds
7. User sees transcription (7s total delay)
8. Backend logs: "Google v2 timeout, used Azure fallback"
9. Health monitor marks Google v2 as 'degraded'

**Timeout Configuration:**
- Streaming providers: 5s timeout
- Batch providers: 10s timeout

---

## 4. iOS/Web Synchronization Edge Cases

### EC-IW01: Quota Deduction Mismatch (iOS Offline)

**Scenario:** iOS tracks 10 min offline, backend only sees 8 min

**Expected Behavior:**
1. iOS app tracks quota locally while offline
2. iOS app reconnects, syncs transactions
3. Backend receives transactions, calculates: 8 min total
4. Mismatch detected: iOS=10 min, Backend=8 min
5. Backend truth wins (server authority)
6. iOS app updates local quota to match backend
7. User sees updated quota (may be higher or lower than expected)

**Logging:**
- Log discrepancy for analysis
- If consistent discrepancy: Fix iOS quota calculation

---

### EC-IW02: iOS Purchased Credits Don't Show on Web

**Scenario:** User buys 4 hours on iOS, Web still shows 0

**Expected Behavior:**
1. iOS purchase completes
2. iOS sends receipt to backend
3. Backend verifies, grants credits
4. Web user opens app
5. Web fetches quota: `GET /api/users/{id}/quota`
6. Backend returns updated quota (includes iOS purchase)
7. Web shows: "4 hours 0 minutes remaining"

**If Web doesn't update:**
- Check WebSocket connection (may need manual refresh)
- Check backend sync (Apple receipt verification may have failed)
- Retry: Click "Refresh Quota" button

---

### EC-IW03: User Subscribes on iOS, Tries to Subscribe on Web

**Scenario:** User has Apple subscription, clicks "Subscribe" on Web

**Expected Behavior:**
1. User clicks "Upgrade to Plus" on Web
2. Backend checks: User already has Plus tier
3. Backend returns: `{"error": "Already subscribed", "platform": "ios"}`
4. Frontend shows: "You're already subscribed via iOS. Manage subscription in iOS Settings."
5. No duplicate subscription created
6. No duplicate charge

**Implementation:**
- Check `user_subscriptions.tier_id` before creating Stripe session
- Check `apple_customer_id` field (indicates iOS subscription)

---

### EC-IW04: Apple vs Stripe Price Discrepancy

**Scenario:** Apple charges $29, Stripe charges $28 (currency conversion)

**Expected Behavior:**
1. User subscribes on iOS: Apple charges $29 USD
2. User subscribes on Web: Stripe charges $28.99 USD (promotional)
3. Both users get same Plus tier features
4. No price matching required (platform-specific pricing)

**Communication:**
- Pricing page shows: "Prices may vary by platform"
- No mention of Web pricing in iOS app (Apple policy)

---

### EC-IW05: StoreKit Receipt Validation Timeout

**Scenario:** Apple verifyReceipt API takes 30 seconds to respond

**Expected Behavior:**
1. iOS app completes purchase
2. iOS app sends receipt to backend
3. Backend calls Apple verifyReceipt API
4. API times out after 30 seconds
5. Backend returns: `{"verified": false, "error": "Timeout"}`
6. iOS app shows: "Verification taking longer than usual. Please wait."
7. iOS app retries after 10 seconds
8. Retry succeeds, credits granted

**Implementation:**
- Timeout: 30 seconds
- Retry: 3 attempts with exponential backoff
- If all retries fail: Store receipt locally, background sync

---

### EC-IW06: User Changes Email (Cross-Platform Sync)

**Scenario:** User changes email on Web, logs into iOS with old email

**Expected Behavior:**
1. User changes email on Web: old@example.com → new@example.com
2. User tries to login on iOS with old@example.com
3. Backend returns: `401 Unauthorized`
4. iOS app shows: "Email or password incorrect"
5. User enters new@example.com
6. Login succeeds
7. iOS app syncs user profile

**Alternative (Email Redirect):**
- Backend stores: `old_email → new_email` mapping
- Login with old_email → Automatically redirected to new_email
- User notified: "Your email has been updated to new@example.com"

**Recommendation:** Require new email (more secure)

---

### EC-IW07: iOS App Version Outdated (Backend Breaking Change)

**Scenario:** Backend API changes, iOS app v1.0 incompatible

**Expected Behavior:**
1. iOS app sends API request with old format
2. Backend detects old API version (header: `X-App-Version: 1.0.0`)
3. Backend returns: `426 Upgrade Required`
4. iOS app shows: "App update required. Please update from App Store."
5. iOS app opens App Store (auto-redirect)
6. User updates app to v1.1.0
7. New app compatible with backend

**Implementation:**
- Backend: Check `X-App-Version` header
- Backend: Minimum required version: 1.1.0
- iOS: Send version header in all requests

---

### EC-IW08: Web User Exports History, iOS User Can't See

**Scenario:** Web user exports history as PDF, wants to view on iOS

**Expected Behavior:**
1. Web user exports history: Downloads PDF to computer
2. iOS user opens iOS app
3. iOS app shows same history (not PDF export)
4. iOS user can export again (native Share Sheet)
5. PDF formats may differ slightly (platform UI differences)

**Alternative (Cloud Export):**
- Store export in cloud: `exports/{user_id}/{timestamp}.pdf`
- Both Web and iOS can download same PDF
- Requires: Cloud storage (S3), URL expiration

**Recommendation:** Platform-specific export (simpler)

---

## 5. Admin Dashboard Edge Cases

### EC-AD01: Financial Data Staleness (Materialized View)

**Scenario:** Admin views dashboard, data is 2 hours old

**Expected Behavior:**
1. Admin opens /admin/financial
2. Backend queries materialized view (last refresh: 2 hours ago)
3. Frontend shows staleness indicator: "Last updated: 2 hours ago"
4. Admin clicks "Refresh Now" button
5. Backend triggers manual refresh: `REFRESH MATERIALIZED VIEW admin_financial_summary`
6. Refresh completes in 10 seconds
7. Dashboard updates with fresh data

**Automatic Refresh:**
- Cron job: Refresh materialized views daily at 2am
- On-demand: Allow admin manual refresh (max once per hour)

---

### EC-AD02: Export Timeout (1M+ Rows)

**Scenario:** Admin exports financial data, dataset too large

**Expected Behavior:**
1. Admin clicks "Export CSV"
2. Backend starts export job
3. Export times out after 60 seconds
4. Backend returns: `{"error": "Export too large, will be emailed"}`
5. Backend queues background job
6. Job exports data in batches (100k rows/batch)
7. Job completes in 10 minutes
8. Admin receives email with download link
9. Link expires after 7 days

**Implementation:**
- Celery/RQ background job queue
- S3 presigned URL for download
- Email notification with link

---

### EC-AD03: Concurrent Admin Changes (Race Condition)

**Scenario:** Two admins edit Pro tier quota simultaneously

**Expected Behavior:**
1. Admin A: Opens /admin/tiers, sees Pro quota = 10hr
2. Admin B: Opens /admin/tiers, sees Pro quota = 10hr
3. Admin A: Changes to 8hr, clicks Save (11:00:00)
4. Admin B: Changes to 9hr, clicks Save (11:00:05)
5. Backend: Last write wins (Admin B's 9hr)
6. Admin A sees: "Your changes were overwritten by Admin B"
7. Audit log shows both changes

**Alternative (Optimistic Locking):**
- Track `updated_at` timestamp
- Admin A saves with `updated_at=10:59:00`
- Backend checks: Current `updated_at=11:00:00` (conflict!)
- Return error: "Data changed by another admin. Refresh and try again."

**Recommendation:** Optimistic locking (prevents data loss)

---

### EC-AD04: Admin Dashboard Shows Wrong Margin

**Scenario:** Dashboard shows 25% margin, actual is 28%

**Root Cause:**
- Materialized view stale (data from yesterday)
- Recent payments not included
- Cost tracking delayed

**Expected Behavior:**
1. Admin notices discrepancy
2. Admin checks: "Last updated: 18 hours ago"
3. Admin clicks "Refresh Now"
4. Materialized view refreshed with latest data
5. Margin updates to 28%
6. Admin validates against Stripe dashboard (matches)

**Prevention:**
- Refresh materialized views more frequently (every 6 hours)
- Show staleness indicator prominently
- Add "Real-time" toggle (slower, but accurate)

---

### EC-AD05: Provider Cost Missing (New Provider Added)

**Scenario:** Admin adds new MT provider, costs not tracked

**Expected Behavior:**
1. Admin adds Azure Translator to mt_routing_config
2. Users start using Azure Translator
3. Cost tracker doesn't recognize provider (not in provider_pricing table)
4. Costs not tracked → Margin calculation wrong
5. Admin views provider costs: Azure Translator not listed
6. Admin realizes: Missing pricing config
7. Admin adds Azure Translator to provider_pricing table
8. Historical costs backfilled (if usage data available)

**Prevention:**
- Validation: Require provider_pricing entry before enabling provider
- Alert: Daily check for providers with missing pricing

---

### EC-AD06: Admin Accidentally Sets Quota to 0

**Scenario:** Admin typo: Pro quota = 0 hours

**Expected Behavior:**
1. Admin edits Pro tier quota
2. Admin types "0" (meant to type "10")
3. Admin clicks Save
4. Backend validation: `quota_hours > 0`
5. Backend returns: `400 Bad Request: Quota must be greater than 0`
6. Frontend shows error: "Invalid quota. Must be at least 1 hour."
7. Admin corrects to 10 hours, saves successfully

**Additional Validation:**
- Warn if quota reduced by >50%: "Reducing quota from 10hr to 4hr. Are you sure?"
- Require reason field for large changes

---

## 6. Security & Abuse Edge Cases

### EC-SEC01: JWT Token Theft (XSS Attack)

**Scenario:** Malicious user steals JWT token via XSS

**Expected Behavior:**
1. Attacker injects script: `<script>alert(localStorage.getItem('token'))</script>`
2. Script executes, steals token
3. Attacker uses token to impersonate user
4. Backend receives request with stolen token
5. Token is valid (not expired)
6. Request succeeds (no way to detect theft)

**Mitigation:**
- HttpOnly cookies (token not accessible to JavaScript)
- Short token expiration (15 minutes)
- Refresh token rotation
- Suspicious activity detection (IP change, user-agent change)

**Implementation:**
- Store token in HttpOnly cookie (not localStorage)
- Refresh token every 15 minutes
- Log suspicious activity: "Token used from new IP"

---

### EC-SEC02: Rate Limiting (API Abuse)

**Scenario:** Malicious user sends 10,000 requests/second

**Expected Behavior:**
1. User sends 10,000 requests
2. Rate limiter detects: 100 requests/minute exceeded
3. Rate limiter blocks requests: `429 Too Many Requests`
4. User sees: "Rate limit exceeded. Try again in 60 seconds."
5. After 60 seconds: User can resume
6. If abuse continues: IP blocked for 24 hours

**Rate Limits:**
- Global: 100 requests/minute per IP
- Authentication: 5 failed logins/15 minutes per IP
- Payments: 10 requests/hour per user
- Admin endpoints: 1000 requests/minute (higher limit)

---

### EC-SEC03: Apple Receipt Validation (Bundle ID Spoofing)

**Scenario:** Attacker sends receipt from different app

**Expected Behavior:**
1. Attacker purchases subscription in App A
2. Attacker sends App A receipt to LiveTranslator backend
3. Backend calls Apple verifyReceipt API
4. Apple returns: Receipt valid, but `bundle_id=com.other.app`
5. Backend checks: `bundle_id != com.livetranslator.ios`
6. Backend rejects: `{"verified": false, "error": "Invalid bundle ID"}`
7. No credits granted

**Additional Checks:**
- Verify `product_id` matches configured products
- Verify `original_transaction_id` unique (prevent replay attacks)

---

### EC-SEC04: SQL Injection (User Input)

**Scenario:** Attacker tries SQL injection in room name

**Expected Behavior:**
1. User creates room with name: `"; DROP TABLE users; --`
2. Backend receives room name
3. Backend uses parameterized query:
   ```python
   cursor.execute(
       "INSERT INTO rooms (code, name) VALUES (%s, %s)",
       (code, room_name)
   )
   ```
4. SQL injection prevented (parameterized query)
5. Room created with literal name: `"; DROP TABLE users; --`
6. No database damage

**Prevention:**
- Never concatenate user input into SQL queries
- Always use parameterized queries (SQLAlchemy, psycopg2)
- Input validation (length limits, character whitelist)

---

## Summary

| Category | Edge Cases | Critical | High | Medium |
|----------|-----------|----------|------|--------|
| Quota System | 10 | 3 | 5 | 2 |
| Payment System | 9 | 4 | 3 | 2 |
| Provider Routing | 8 | 2 | 4 | 2 |
| iOS/Web Sync | 8 | 2 | 4 | 2 |
| Admin Dashboard | 6 | 1 | 3 | 2 |
| Security | 4 | 4 | 0 | 0 |
| **Total** | **45** | **16** | **19** | **10** |

**Critical Edge Cases (Must Handle):**
1. Quota exhaustion mid-sentence
2. Admin quota also exhausted
3. Stripe webhook delayed
4. Duplicate payment prevention
5. Apple receipt fraud
6. All providers down
7. JWT token theft
8. Rate limiting
9. SQL injection
10. Bundle ID spoofing

**Testing Priority:**
1. P0: All critical edge cases (16)
2. P1: High priority edge cases (19)
3. P2: Medium priority edge cases (10)

---

**Last Updated:** 2025-11-03
**Related Documents:** `user-stories.md`, `use-cases.md`, `acceptance-tests.md`

# LiveTranslator Tier System - Acceptance Test Scenarios

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Requirements

---

## Overview

38 acceptance test scenarios covering quota system, payment integration, admin dashboard, iOS features, cross-platform functionality, and performance.

**Test Priority:**
- **P0 (Critical):** Must pass for MVP launch (15 tests)
- **P1 (High):** Important for user experience (16 tests)
- **P2 (Medium):** Nice-to-have validation (7 tests)

**Test Coverage:**
- Quota System: 8 scenarios
- Payment Integration: 7 scenarios
- Admin Dashboard: 6 scenarios
- iOS Features: 7 scenarios
- Cross-Platform: 5 scenarios
- Performance: 5 scenarios

---

## 1. Quota System Tests (8 scenarios)

### AT-Q01: Quota Waterfall (Participant → Admin)

**Priority:** P0
**Related:** US-013, UC-008

**Test Data:**
- User A (Plus): 30 minutes remaining
- User B (Free): 0 minutes remaining
- User C (Pro, Admin): 5 hours remaining

**Test Steps:**
1. User C creates room "Test Waterfall"
2. User A and User B join room
3. User A speaks for 40 minutes
4. Verify quota deductions:
   - User A: 30 min (own quota) + 10 min (admin quota)
   - User B: Always uses admin quota
   - User C (admin): Provided 10 min to User A, all of User B's usage
5. Check `quota_transactions` table:
   - User A: 2 rows (30 min `quota_source='own'`, 10 min `quota_source='admin'`)
   - User B: All rows have `quota_source='admin'`
6. Verify admin notification: "User A using your quota (10 min)"

**Expected Result:**
- ✅ User A used own quota first, then admin's
- ✅ User B always used admin quota
- ✅ Admin notified correctly
- ✅ All quota transactions recorded accurately
- ✅ Total admin quota deducted correctly

**Failure Conditions:**
- User A skips own quota, uses admin immediately
- User B charged own quota (should be admin)
- Admin not notified
- Quota transactions missing or incorrect

---

### AT-Q02: Real-Time Quota Updates Across Devices

**Priority:** P0
**Related:** US-008, US-009, EC-IW01

**Test Data:**
- User has Plus tier (2 hours quota)
- User has iOS app and Web browser open simultaneously

**Test Steps:**
1. User opens room on iOS
2. User opens same room on Web (same account)
3. iOS quota indicator shows: "2 hours 0 minutes"
4. Web quota indicator shows: "2 hours 0 minutes"
5. User speaks on iOS for 15 minutes
6. Verify both devices update in real-time:
   - iOS shows: "1 hour 45 minutes"
   - Web shows: "1 hour 45 minutes"
7. User speaks on Web for 30 minutes
8. Verify both devices update:
   - iOS shows: "1 hour 15 minutes"
   - Web shows: "1 hour 15 minutes"
9. User buys 4 hours on iOS (Apple Pay)
10. Verify both devices update:
    - iOS shows: "5 hours 15 minutes"
    - Web shows: "5 hours 15 minutes"

**Expected Result:**
- ✅ Quota synced across iOS and Web
- ✅ Updates happen in real-time (< 2 seconds)
- ✅ WebSocket broadcasts quota_updated message
- ✅ No quota discrepancies

**Failure Conditions:**
- iOS and Web show different quota values
- Updates delayed >5 seconds
- Manual refresh required to sync

---

### AT-Q03: Monthly Quota Reset at Billing Cycle

**Priority:** P0
**Related:** US-015, EC-Q04

**Test Data:**
- User has Plus tier
- `billing_period_end = 2025-12-01 00:00:00`
- User has used 1.5 hours of 2 hours
- User has 2 hours bonus credits (purchased)

**Test Steps:**
1. Set system time to 2025-11-30 23:59:00
2. User quota: 30 min monthly + 2 hours bonus = 2 hr 30 min remaining
3. Cron job runs at 2025-12-01 00:00:00
4. Verify database updates:
   - `user_quota_usage.total_seconds_used = 0` (reset)
   - `billing_period_start = 2025-12-01`
   - `billing_period_end = 2025-12-31`
   - `bonus_credits_seconds = 7200` (preserved)
5. User opens app
6. User sees: "4 hours 0 minutes remaining" (2 hr monthly + 2 hr bonus)
7. User receives email: "Your Plus quota has been reset"
8. iOS user receives push notification

**Expected Result:**
- ✅ Monthly quota reset to 2 hours
- ✅ Bonus credits preserved (not reset)
- ✅ Billing period advanced 30 days
- ✅ User notified via email + push
- ✅ No quota loss or double-reset

**Failure Conditions:**
- Bonus credits also reset (incorrect)
- Quota not reset (cron job failed)
- Billing period not advanced
- User not notified

---

### AT-Q04: Quota Exhaustion Triggers Upgrade Modal

**Priority:** P0
**Related:** US-012, UC-002

**Test Data:**
- User has Free tier (10 minutes quota)
- User has used 9 minutes 50 seconds

**Test Steps:**
1. User creates room, speaks
2. At 10 minutes used: Backend sends `quota_exhausted` WebSocket message
3. Frontend shows modal:
   - Title: "Quota Exhausted"
   - Message: "You've used your 10 free minutes this month."
   - Button 1: "Upgrade to Plus ($29/mo)"
   - Button 2: "Buy 4 Hours ($19)"
4. Microphone button disabled (user cannot speak)
5. User can still see translations from others
6. User clicks "Upgrade to Plus"
7. Redirected to Stripe Checkout

**Expected Result:**
- ✅ Modal appears exactly at quota=0
- ✅ Microphone disabled
- ✅ User can still view translations
- ✅ Upgrade options clearly presented
- ✅ Modal cannot be dismissed (user must take action or close room)

**Failure Conditions:**
- Modal doesn't appear
- User can continue speaking after exhaustion
- Modal dismissable without action

---

### AT-Q05: Quota Warning at 80% Usage

**Priority:** P1
**Related:** US-012, EC-Q01

**Test Data:**
- User has Plus tier (2 hours = 7200 seconds)
- User has used 5760 seconds (80%)

**Test Steps:**
1. User in active room
2. User speaks, reaches 5760 seconds used
3. Backend sends `quota_alert` WebSocket message
4. Frontend shows banner: "You've used 80% of your quota. 24 minutes remaining."
5. Banner has buttons:
   - "Buy Credits" (primary)
   - "Dismiss" (secondary)
6. User continues speaking
7. At 6840 seconds (95%): Second alert: "Critical: Only 6 minutes remaining"
8. Alert shown only once per threshold

**Expected Result:**
- ✅ Alert at exactly 80% (5760s)
- ✅ Second alert at 95% (6840s)
- ✅ Each alert shown only once
- ✅ Redis flag prevents duplicate alerts
- ✅ User can dismiss and continue

**Failure Conditions:**
- Alert not shown
- Alert shown multiple times (spam)
- Alert shown too early/late

---

### AT-Q06: Pro-Rated Quota After Mid-Cycle Upgrade

**Priority:** P1
**Related:** US-003, EC-Q06

**Test Data:**
- User has Plus tier ($29/mo, 2 hours)
- Billing period: Nov 1 - Dec 1 (30 days)
- User upgrades to Pro on Nov 16 (day 15)

**Test Steps:**
1. User has Plus tier, 1 hour quota remaining
2. User clicks "Upgrade to Pro"
3. System calculates:
   - Days remaining: 15
   - Pro monthly quota: 10 hours
   - Pro-rated quota: 10 × (15/30) = 5 hours
4. User pays $170 (pro-rated)
5. Quota updated:
   - Existing: 1 hour (Plus unused)
   - New: 5 hours (Pro pro-rated)
   - Total: 6 hours
6. Billing period unchanged: Nov 1 - Dec 1
7. On Dec 1: Full 10 hours granted

**Expected Result:**
- ✅ Pro-rated quota calculated correctly
- ✅ Existing quota preserved
- ✅ Total quota = existing + pro-rated
- ✅ Billing period unchanged
- ✅ Full quota granted at next renewal

**Failure Conditions:**
- Pro-rated quota incorrect
- Existing quota lost
- Billing period reset (user loses days)

---

### AT-Q07: Admin Grants Bonus Credits (Manual)

**Priority:** P1
**Related:** US-028, UC-012

**Test Data:**
- User email: user@example.com
- User has 0 quota remaining
- Admin wants to grant 30 minutes refund

**Test Steps:**
1. Admin logs into /admin/tools/grant-credits
2. Admin enters:
   - Email: user@example.com
   - Amount: 0.5 hours (30 minutes)
   - Reason: "Refund for issue #1234"
3. Admin clicks "Grant Credits"
4. Backend:
   - Adds 1800 seconds to `bonus_credits_seconds`
   - Creates `quota_transactions` record: `type='grant'`
   - Creates audit log entry
5. User receives email notification
6. iOS user receives push notification
7. User opens app, sees: "30 minutes remaining (bonus credits)"
8. User creates room, uses bonus credits

**Expected Result:**
- ✅ Credits granted instantly
- ✅ User notified via email + push
- ✅ Audit log recorded with admin ID + reason
- ✅ Credits usable immediately
- ✅ Credits never expire

**Failure Conditions:**
- Credits not granted
- User not notified
- Audit log missing
- Credits expire

---

### AT-Q08: Guest Always Uses Admin Quota (Never Own)

**Priority:** P0
**Related:** US-020, EC-Q02

**Test Data:**
- Admin (Plus tier, 2 hours quota)
- Guest (no account)

**Test Steps:**
1. Admin creates room
2. Guest joins via invite link (no signup)
3. Guest enters name "John"
4. Guest speaks for 15 minutes
5. Verify `quota_transactions` table:
   - All rows have `quota_source='admin'`
   - No rows for guest's own quota
6. Admin sees in participants panel:
   - John (Guest) - Using your quota (15 min)
7. Admin quota reduced by 15 minutes
8. Guest sees no quota indicator (guests don't have quota)

**Expected Result:**
- ✅ Guest never uses own quota (doesn't have any)
- ✅ All guest usage charged to admin
- ✅ Admin has full visibility
- ✅ Guest experience smooth (no quota warnings)

**Failure Conditions:**
- Guest charged own quota (error)
- Admin not charged
- Admin not notified

---

## 2. Payment Integration Tests (7 scenarios)

### AT-P01: Stripe Subscription Flow (Web)

**Priority:** P0
**Related:** US-002, UC-002

**Test Data:**
- User email: test@example.com
- Stripe test card: 4242 4242 4242 4242

**Test Steps:**
1. User clicks "Upgrade to Plus"
2. Redirected to Stripe Checkout
3. Checkout shows:
   - Product: Plus Monthly Subscription
   - Price: $29.00/month
   - Recurring: Every 30 days
4. User enters test card details
5. User clicks "Subscribe"
6. Stripe processes payment (test mode)
7. Stripe sends webhook: `checkout.session.completed`
8. Backend receives webhook, verifies signature
9. Backend updates:
   - `user_subscriptions.tier_id = 2`
   - `stripe_customer_id = cus_xxxxx`
   - `stripe_subscription_id = sub_xxxxx`
   - `billing_period_start = now`
   - `billing_period_end = now + 30 days`
10. User redirected back to app
11. User sees: "Upgraded to Plus! 2 hours quota activated."
12. User receives confirmation email

**Expected Result:**
- ✅ Payment succeeds
- ✅ Tier updated to Plus
- ✅ Quota granted (2 hours)
- ✅ Subscription IDs stored
- ✅ Email confirmation sent
- ✅ User can immediately use premium features

**Failure Conditions:**
- Payment fails
- Webhook not received
- Tier not updated
- User charged but tier stays Free

---

### AT-P02: Apple IAP Subscription Flow (iOS)

**Priority:** P0
**Related:** US-004, UC-005

**Test Data:**
- iOS app (TestFlight or sandbox)
- Apple test account
- Product ID: com.livetranslator.plus.monthly

**Test Steps:**
1. User clicks "Upgrade to Plus" in iOS app
2. StoreKit 2 subscription sheet appears
3. Sheet shows:
   - Product: Plus Monthly
   - Price: $29.00
   - Free trial: None
4. User authenticates with Face ID (test mode)
5. Apple processes payment (sandbox)
6. iOS app receives transaction
7. iOS app sends receipt to backend: `POST /api/payments/apple-verify`
8. Backend calls Apple verifyReceipt API (sandbox)
9. Apple returns: Receipt valid
10. Backend verifies:
    - `bundle_id = com.livetranslator.ios`
    - `product_id = com.livetranslator.plus.monthly`
    - `original_transaction_id` unique
11. Backend updates:
    - `tier_id = 2`
    - `apple_transaction_id = xxxxx`
    - `apple_customer_id = xxxxx`
12. iOS app shows: "Plus tier activated!"
13. User can use premium providers

**Expected Result:**
- ✅ Apple payment succeeds
- ✅ Receipt verified successfully
- ✅ Tier updated to Plus
- ✅ Transaction IDs stored
- ✅ Cross-platform: Web also shows Plus tier

**Failure Conditions:**
- Apple receipt invalid
- Backend can't verify receipt
- Tier not updated
- Web still shows Free tier

---

### AT-P03: Cross-Platform Purchase Recognition

**Priority:** P0
**Related:** US-005, UC-005, EC-IW03

**Test Data:**
- User subscribed to Plus on Web (Stripe)
- User logs into iOS app with same account

**Test Steps:**
1. User has Plus tier on Web (Stripe subscription active)
2. User logs into iOS app
3. iOS app fetches user profile: `GET /api/users/{id}/subscription`
4. Backend returns:
   - `tier = 'plus'`
   - `stripe_customer_id = cus_xxxxx` (not null)
   - `apple_customer_id = null`
5. iOS app shows "Plus" badge in profile
6. iOS app unlocks Plus features (premium providers)
7. User tries to subscribe again on iOS
8. iOS app checks: User already has Plus tier
9. iOS app shows: "You're already subscribed via Web. Manage in Stripe portal."
10. No duplicate purchase created

**Expected Result:**
- ✅ iOS recognizes Web subscription
- ✅ Plus features unlocked on iOS
- ✅ Duplicate purchase prevented
- ✅ Clear messaging about subscription platform

**Failure Conditions:**
- iOS doesn't recognize Web subscription
- User can purchase duplicate subscription
- Features locked despite subscription

---

### AT-P04: Stripe Webhook Failure Recovery

**Priority:** P1
**Related:** EC-P01

**Test Data:**
- User completes Stripe payment
- Webhook endpoint temporarily down

**Test Steps:**
1. User completes Stripe Checkout
2. Stripe attempts to send webhook
3. Webhook endpoint returns 500 error (simulated)
4. Stripe retries after 5 minutes (automatic)
5. Webhook endpoint back online
6. Stripe retry succeeds
7. Backend processes webhook:
   - Checks if already processed (idempotency via `payment_intent_id`)
   - If not processed: Update tier
8. User tier updated (delayed by 5 minutes)
9. User receives email: "Payment confirmed! Plus tier activated."

**Alternative (Manual Sync):**
- After 10 minutes: Backend polls Stripe API
- Query: `stripe.PaymentIntent.retrieve(payment_intent_id)`
- If status='succeeded': Process manually

**Expected Result:**
- ✅ Payment eventually processed
- ✅ No duplicate processing
- ✅ User tier updated (may be delayed)
- ✅ User notified when complete

**Failure Conditions:**
- Payment never processed
- User charged but tier not updated
- Duplicate tier updates

---

### AT-P05: Payment Failure Retry Flow

**Priority:** P1
**Related:** US-007, UC-009, EC-P04

**Test Data:**
- User has Plus tier subscription
- User's credit card expired
- Renewal date: Dec 1

**Test Steps:**
1. Dec 1: Stripe attempts renewal charge
2. Payment fails: "Card expired"
3. Stripe sends webhook: `invoice.payment_failed`
4. Backend updates: `status = 'past_due'`
5. User receives email: "Payment failed. Update your card."
6. User tier remains Plus (grace period)
7. Dec 2: Stripe auto-retry #1 fails
8. Dec 4: Stripe auto-retry #2 fails
9. Dec 7: Stripe auto-retry #3 fails (final)
10. Stripe sends webhook: `customer.subscription.deleted`
11. Backend updates:
    - `status = 'canceled'`
    - `tier_id = 1` (Free)
    - Bonus credits preserved
12. User receives email: "Subscription canceled. Downgraded to Free tier."

**Alternative (User Fixes Card):**
- Dec 3: User updates card in Stripe portal
- Stripe immediately retries payment
- Payment succeeds
- Subscription remains active, no downgrade

**Expected Result:**
- ✅ 7-day grace period
- ✅ 3 automatic retries
- ✅ User notified at each step
- ✅ Bonus credits preserved
- ✅ Clear recovery path

**Failure Conditions:**
- Immediate downgrade (no grace period)
- Bonus credits lost
- User not notified

---

### AT-P06: Duplicate Payment Prevention

**Priority:** P0
**Related:** EC-P02

**Test Data:**
- User clicks "Subscribe" button twice rapidly

**Test Steps:**
1. User clicks "Subscribe to Plus"
2. Frontend sends: `POST /api/billing/subscribe`
3. Backend creates Stripe Checkout session: `session_1`
4. User clicks "Subscribe" again (rapid double-click)
5. Frontend sends: `POST /api/billing/subscribe` (duplicate)
6. Backend checks:
   - Last session created: 2 seconds ago
   - Session still valid (not expired)
7. Backend returns existing `session_1` (not new session)
8. User redirected to Stripe once
9. User completes payment
10. Webhook received once
11. User charged once

**Expected Result:**
- ✅ Only one Stripe session created
- ✅ User charged once
- ✅ No duplicate webhook processing
- ✅ Idempotency enforced

**Failure Conditions:**
- Two Stripe sessions created
- User charged twice
- Duplicate tier updates

---

### AT-P07: Credit Purchase on iOS (Apple Pay)

**Priority:** P0
**Related:** US-011, UC-003

**Test Data:**
- User has Plus tier (0 quota remaining)
- iOS app (TestFlight sandbox)
- Product ID: com.livetranslator.credits.4hr

**Test Steps:**
1. User exhausts quota mid-conversation
2. iOS app shows modal: "Quota exhausted. Buy more credits?"
3. User selects "4 Hours - $19"
4. StoreKit 2 shows consumable IAP sheet
5. User authenticates with Face ID (sandbox)
6. Apple processes payment
7. iOS app receives transaction
8. iOS app sends receipt to backend
9. Backend verifies with Apple verifyReceipt API
10. Backend grants:
    - `bonus_credits_seconds += 14400` (4 hours)
    - Creates `payment_transactions` record
11. Backend sends WebSocket: `quota_updated`
12. iOS app shows: "4 hours 0 minutes remaining"
13. Room continues immediately (no interruption)
14. User receives in-app receipt

**Expected Result:**
- ✅ Payment succeeds
- ✅ Credits granted instantly
- ✅ Room continues without interruption
- ✅ Quota updated in real-time
- ✅ Cross-platform: Web also shows credits

**Failure Conditions:**
- Payment succeeds but credits not granted
- Room interrupted during payment
- Credits not synced to Web

---

## 3. Admin Dashboard Tests (6 scenarios)

### AT-AD01: Financial Summary Accuracy

**Priority:** P0
**Related:** US-022, UC-004

**Test Data:**
- 10 rooms created yesterday with known costs
- Total STT cost: $45.00
- Total MT cost: $32.50
- Total revenue: $150.00 (5 Plus subscriptions)

**Test Steps:**
1. Admin logs into /admin/financial
2. Admin sets date range: Yesterday
3. Admin views financial summary:
   - Revenue: $150.00
   - Costs: $77.50 (STT + MT)
   - Profit: $72.50
   - Margin: 48.33%
4. Admin clicks "Provider Costs" tab
5. Verify breakdown matches:
   - Speechmatics: $30.00
   - DeepL: $25.00
   - OpenAI GPT-4o-mini: $22.50
6. Admin exports CSV
7. Verify CSV data matches database:
   ```sql
   SELECT SUM(amount_usd) FROM room_costs WHERE DATE(ts) = YESTERDAY
   ```
8. Verify margin calculation:
   - Margin = (Revenue - Costs) / Revenue × 100
   - Margin = (150 - 77.50) / 150 × 100 = 48.33% ✓

**Expected Result:**
- ✅ Revenue matches payment_transactions sum
- ✅ Costs match room_costs sum
- ✅ Provider breakdown accurate
- ✅ Margin calculation correct (2 decimals)
- ✅ CSV export matches dashboard

**Failure Conditions:**
- Revenue/costs mismatch (>1% error)
- Margin calculation wrong
- CSV data different from dashboard

---

### AT-AD02: Tier Profitability Breakdown

**Priority:** P0
**Related:** US-024, UC-004

**Test Data:**
- Free tier: 200 users, $0 revenue, $500 costs
- Plus tier: 60 users, $1,740 revenue, $1,200 costs
- Pro tier: 25 users, $4,975 revenue, $3,800 costs

**Test Steps:**
1. Admin navigates to /admin/financial/tier-analysis
2. Verify tier table shows:
   | Tier | Users | Revenue | Costs | Profit | Margin |
   |------|-------|---------|-------|--------|--------|
   | Free | 200 | $0 | $500 | -$500 | -100% |
   | Plus | 60 | $1,740 | $1,200 | $540 | 31.03% |
   | Pro | 25 | $4,975 | $3,800 | $1,175 | 23.62% |
3. Verify color coding:
   - Free: Red (-100% margin)
   - Plus: Green (31% > 30% target)
   - Pro: Yellow (23.62% < 30% target)
4. Verify alert: "Pro tier margin below target"
5. Admin clicks "Adjust Quota" for Pro tier
6. Admin reduces quota: 10hr → 8hr
7. Admin saves, system logs change

**Expected Result:**
- ✅ Tier breakdown accurate
- ✅ Color coding correct (red/yellow/green)
- ✅ Alert triggered for Pro tier
- ✅ Quota adjustment logged
- ✅ No manual calculation errors

**Failure Conditions:**
- Tier data incorrect
- Color coding wrong
- Alert not triggered
- Margin calculation wrong

---

### AT-AD03: KPI Dashboard Accuracy

**Priority:** P1
**Related:** US-023

**Test Data:**
- Last 30 days: 150 signups, 60 conversions to Plus

**Test Steps:**
1. Admin navigates to /admin/users/acquisition
2. Verify KPI cards:
   - New Signups: 150
   - Free → Plus Conversion: 40% (60/150)
   - Free → Pro Conversion: 5% (7.5/150)
   - DAU: 500
   - MAU: 3,000
   - Stickiness: 16.67% (500/3000)
3. Verify trend indicators:
   - Signups: +15% (green ↑) vs last 30 days
   - Conversion: +2% (green ↑)
4. Click "Daily Breakdown" chart
5. Verify daily signups sum to 150
6. Export CSV, verify calculations

**Expected Result:**
- ✅ All KPIs calculated correctly
- ✅ Trend indicators accurate
- ✅ Charts render correctly
- ✅ CSV export matches dashboard

**Failure Conditions:**
- KPI calculation errors
- Trend indicators wrong
- Chart data mismatch

---

### AT-AD04: Admin Query Performance (<3s)

**Priority:** P1
**Related:** EC-AD01

**Test Data:**
- 100,000 users
- 10,000,000 quota transactions

**Test Steps:**
1. Seed database with large dataset
2. Admin loads /admin/financial (last 30 days)
3. Measure query time:
   - Materialized view query: <500ms
   - Real-time aggregation: <2s
   - Total page load: <3s
4. Admin changes date range: Last 90 days
5. Measure query time:
   - Materialized view query: <800ms
   - Real-time aggregation: <2.5s
   - Total page load: <3.5s
6. Admin clicks "Refresh Now"
7. Materialized view refresh completes: <10s

**Expected Result:**
- ✅ Dashboard loads in <3s (cached)
- ✅ Date range change: <3.5s
- ✅ Manual refresh: <10s
- ✅ No timeout errors
- ✅ No browser freeze

**Failure Conditions:**
- Query timeout (>10s)
- Browser freeze
- Dashboard unusable with large dataset

---

### AT-AD05: Export CSV/PDF Functionality

**Priority:** P1
**Related:** US-026

**Test Data:**
- Last 30 days financial data

**Test Steps:**
1. Admin loads /admin/financial
2. Admin clicks "Export CSV"
3. Browser downloads: `financials_2025-11-01_2025-12-01.csv`
4. Verify CSV contents:
   - Header row: Date, Revenue, Costs, Profit, Margin
   - Data rows: 30 rows (one per day)
   - Values match dashboard
5. Admin clicks "Export PDF"
6. Browser downloads: `financials_2025-11-01_2025-12-01.pdf`
7. Verify PDF contents:
   - Title: "Financial Report: Nov 1 - Dec 1, 2025"
   - Charts: Revenue vs Cost line chart
   - Tables: Tier profitability, Provider costs
   - Footer: Total revenue, costs, margin
8. Admin clicks "Email Report"
9. Admin enters email, clicks Send
10. Admin receives email with PDF attachment

**Expected Result:**
- ✅ CSV downloads immediately (<2s)
- ✅ CSV data accurate
- ✅ PDF downloads within 10s
- ✅ PDF formatted correctly
- ✅ Email sent with attachment

**Failure Conditions:**
- Export fails or times out
- CSV/PDF data incorrect
- Email not sent

---

### AT-AD06: Admin Grants Credits (Manual Refund)

**Priority:** P1
**Related:** US-028, UC-012

**Test Data:**
- User: user@example.com
- Current quota: 0 minutes
- Refund reason: "Poor translation quality, issue #1234"

**Test Steps:**
1. Admin logs into /admin/tools/grant-credits
2. Admin enters:
   - Email: user@example.com (autocomplete works)
   - Amount: 0.5 hours
   - Reason: "Refund for poor translation quality, issue #1234"
3. Admin clicks "Grant Credits"
4. System confirms: "Grant 30 minutes to user@example.com?"
5. Admin clicks "Confirm"
6. Backend:
   - Updates `bonus_credits_seconds += 1800`
   - Creates `quota_transactions` record:
     - `type = 'grant'`
     - `granted_by_admin_id = 1`
     - `reason = "Refund for..."`
   - Creates audit log entry
7. User receives email: "We've added 30 minutes to your account"
8. iOS user receives push notification
9. User opens app, sees: "30 minutes remaining (bonus credits)"
10. Admin views audit log: Shows grant with reason and timestamp

**Expected Result:**
- ✅ Credits granted instantly
- ✅ User notified (email + push)
- ✅ Audit log entry created
- ✅ Reason stored for compliance
- ✅ User can use credits immediately

**Failure Conditions:**
- Credits not granted
- User not notified
- Audit log missing
- Admin ID not recorded

---

## 4. iOS Features Tests (7 scenarios)

### AT-iOS01: Apple STT On-Device Transcription

**Priority:** P0
**Related:** US-021, UC-010

**Test Data:**
- iOS app (iPhone 12+, iOS 15+)
- Free tier user
- Language: English

**Test Steps:**
1. User creates room on iOS
2. User enables microphone permission
3. iOS app initializes SFSpeechRecognizer (on-device)
4. User speaks: "Hello, testing Apple Speech Recognition"
5. iOS app transcribes on-device (no audio sent to server)
6. iOS app sends WebSocket message:
   ```json
   {
     "type": "transcript_direct",
     "text": "Hello, testing Apple Speech Recognition",
     "source_lang": "en",
     "is_final": true,
     "timestamp": "2025-11-03T12:00:00Z"
   }
   ```
7. Backend receives message
8. Backend publishes to `stt_events` channel (skips STT router)
9. MT router translates text
10. Other participants see translation
11. Verify quota deduction: ~3 seconds (estimated for sentence length)

**Expected Result:**
- ✅ Audio never sent to server (privacy + zero cost)
- ✅ Transcription accurate (Apple STT quality)
- ✅ Backend receives text-only message
- ✅ Translation works normally
- ✅ Quota deducted (estimated, not exact)

**Failure Conditions:**
- Audio sent to server (incorrect)
- Transcription fails or gibberish
- Backend doesn't receive message
- Translation doesn't work

---

### AT-iOS02: iOS Offline Mode (Apple Translation)

**Priority:** P1
**Related:** EC-IW05

**Test Data:**
- iOS app
- User has Plus tier
- Language pair: English → Spanish

**Test Steps:**
1. User creates room on iOS
2. User speaks: "Hello, how are you?"
3. User turns on Airplane Mode (offline)
4. iOS app detects offline
5. iOS app shows banner: "Offline mode - Using on-device translation"
6. User continues speaking: "I'm testing offline mode"
7. iOS app:
   - Uses Apple STT (on-device, works offline)
   - Uses Apple Translation API (on-device, works offline)
   - Queues messages locally (SQLite)
8. User sees translated text: "Hola, ¿cómo estás?"
9. User turns off Airplane Mode (online)
10. iOS app reconnects to backend
11. iOS app syncs queued messages
12. Backend receives historical messages
13. Backend deducts quota (may be delayed)

**Expected Result:**
- ✅ Offline mode works seamlessly
- ✅ Transcription + translation work offline
- ✅ Messages queued locally
- ✅ Messages synced when online
- ✅ Quota deducted accurately (after sync)

**Failure Conditions:**
- Offline mode crashes
- Messages lost (not queued)
- Sync fails
- Quota not deducted

---

### AT-iOS03: StoreKit 2 Subscription Purchase

**Priority:** P0
**Related:** US-004, AT-P02

**Test Data:**
- iOS app (TestFlight sandbox)
- Apple test account
- Product: com.livetranslator.plus.monthly

**Test Steps:**
1. User taps "Upgrade to Plus" in iOS app
2. StoreKit 2 sheet appears with:
   - Product name: "Plus Monthly"
   - Price: $29.00
   - Billing: "Renews monthly"
   - Features: "2 hours per month, Premium providers"
3. User authenticates with Face ID (test mode)
4. Apple processes payment (sandbox)
5. iOS app receives StoreKit transaction
6. iOS app extracts: `transaction_id`, `product_id`, `receipt_data`
7. iOS app sends to backend: `POST /api/payments/apple-verify`
8. Backend verifies with Apple API
9. Backend updates tier to Plus
10. iOS app receives success response
11. iOS app shows: "Plus tier activated!"
12. User quota updated: 2 hours
13. Premium providers unlocked

**Expected Result:**
- ✅ StoreKit purchase flow works
- ✅ Receipt verified successfully
- ✅ Tier updated to Plus
- ✅ Quota granted
- ✅ Features unlocked

**Failure Conditions:**
- StoreKit sheet doesn't appear
- Payment fails or times out
- Receipt verification fails
- Tier not updated

---

### AT-iOS04: Push Notifications (Quota Alerts)

**Priority:** P1
**Related:** US-012, US-009

**Test Data:**
- iOS app (registered for push notifications)
- User has Plus tier (2 hours quota)
- User has used 5760 seconds (80%)

**Test Steps:**
1. User uses quota to 80%
2. Backend detects threshold
3. Backend sends push notification to iOS device:
   ```json
   {
     "title": "Quota Warning",
     "body": "You've used 80% of your quota. 24 minutes remaining.",
     "data": {
       "type": "quota_alert",
       "threshold": "80_percent",
       "remaining_seconds": 1440
     }
   }
   ```
4. iOS receives push notification
5. User taps notification
6. iOS app opens to quota dashboard
7. User sees: "1 hour 36 minutes remaining"
8. User can buy credits directly

**Expected Result:**
- ✅ Push notification delivered
- ✅ Notification tappable
- ✅ Deep link to quota dashboard works
- ✅ User can take action (buy credits)

**Failure Conditions:**
- Notification not delivered
- Notification tap doesn't open app
- Deep link broken

---

### AT-iOS05: Background Audio Continuity

**Priority:** P1
**Related:** EC-PR05

**Test Data:**
- iOS app in background
- Active room conversation

**Test Steps:**
1. User in active room conversation
2. User presses Home button (app backgrounded)
3. Other participant speaks
4. iOS receives translation via WebSocket
5. iOS plays TTS audio (Apple AVSpeechSynthesizer)
6. Audio plays in background (user hears translation)
7. User opens Control Center, pauses
8. Audio pauses correctly
9. User returns to app (foreground)
10. Conversation continues normally

**Expected Result:**
- ✅ Audio plays in background
- ✅ WebSocket stays connected in background (up to 30 minutes)
- ✅ Control Center pause/play works
- ✅ No audio interruption

**Failure Conditions:**
- Audio doesn't play in background
- WebSocket disconnects immediately
- Audio cuts out

---

### AT-iOS06: iOS → Web QR Code Invite

**Priority:** P0
**Related:** UC-005

**Test Data:**
- iOS app (admin)
- Web browser (guest)

**Test Steps:**
1. iOS user creates room "Test Cross-Platform"
2. iOS user taps "Invite" button
3. iOS app generates QR code full-screen
4. Web user scans QR code with phone camera
5. Camera detects QR, opens Safari
6. Safari navigates to: `https://livetranslator.com/join?code=ABC123`
7. Web shows join page with room name
8. Web user enters name "Tom", clicks "Join"
9. Web user joins room (guest mode, no signup)
10. iOS user sees toast: "Tom joined with English"
11. iOS user speaks (Apple STT)
12. Web user sees translation
13. Web user speaks (Speechmatics STT)
14. iOS user sees translation + hears Apple TTS

**Expected Result:**
- ✅ QR code generated correctly
- ✅ QR scannable from screen (brightness sufficient)
- ✅ Cross-platform join works (iOS → Web)
- ✅ Bi-directional translation works
- ✅ Quota pooling works (guest uses admin quota)

**Failure Conditions:**
- QR code not scannable
- Join link broken
- Translation doesn't work cross-platform

---

### AT-iOS07: iOS App Update (Version Check)

**Priority:** P2
**Related:** EC-IW07

**Test Data:**
- iOS app v1.0.0 (old)
- Backend requires v1.1.0 (new)

**Test Steps:**
1. User opens iOS app v1.0.0
2. iOS app sends API request with header: `X-App-Version: 1.0.0`
3. Backend checks: Minimum required version = 1.1.0
4. Backend returns: `426 Upgrade Required`
5. iOS app shows modal:
   - "App Update Required"
   - "Please update to the latest version to continue."
   - [Update Now] button
6. User taps "Update Now"
7. iOS app opens App Store to LiveTranslator page
8. User updates app to v1.1.0
9. User reopens app
10. API requests succeed

**Expected Result:**
- ✅ Version check enforced
- ✅ User prompted to update
- ✅ App Store deep link works
- ✅ New version compatible

**Failure Conditions:**
- Version check not enforced (old app still works)
- App Store link broken
- Update doesn't resolve issue

---

## 5. Cross-Platform Tests (5 scenarios)

### AT-XP01: Quota Sync (iOS Purchase → Web Display)

**Priority:** P0
**Related:** UC-005, EC-IW02

**Test Steps:**
1. User has 0 quota on both iOS and Web
2. User buys 4 hours on iOS (Apple Pay)
3. iOS app shows: "4 hours 0 minutes remaining"
4. User opens Web app (same account)
5. Web fetches quota: `GET /api/users/{id}/quota`
6. Web shows: "4 hours 0 minutes remaining"
7. User speaks on Web for 30 minutes
8. iOS app updates: "3 hours 30 minutes remaining"
9. Web app updates: "3 hours 30 minutes remaining"

**Expected Result:**
- ✅ Credits purchased on iOS visible on Web
- ✅ Usage on Web updates iOS quota
- ✅ Real-time sync (<2s)

**Failure Conditions:**
- Web doesn't show iOS credits
- Manual refresh required
- Quota mismatch

---

### AT-XP02: Web Subscription → iOS Feature Unlock

**Priority:** P0
**Related:** UC-005, AT-P03

**Test Steps:**
1. User subscribes to Plus on Web (Stripe)
2. User logs into iOS app
3. iOS fetches subscription: `GET /api/users/{id}/subscription`
4. iOS unlocks Plus features:
   - Premium STT providers available
   - "Plus" badge in profile
5. User creates room on iOS
6. User can select Speechmatics (premium)
7. Room uses premium provider

**Expected Result:**
- ✅ iOS recognizes Web subscription
- ✅ Features unlocked immediately
- ✅ No duplicate purchase required

**Failure Conditions:**
- iOS doesn't recognize subscription
- Features still locked
- Duplicate purchase prompt

---

### AT-XP03: History Export Cross-Platform

**Priority:** P1
**Related:** UC-011

**Test Steps:**
1. User creates room on iOS, speaks for 30 minutes
2. User opens Web app
3. User navigates to History tab
4. User clicks room created on iOS
5. Web shows conversation history with timestamps
6. User clicks "Export PDF"
7. PDF downloads with iOS conversation data
8. Verify PDF contents match iOS session

**Expected Result:**
- ✅ Web can export iOS room history
- ✅ All data synced correctly
- ✅ PDF accurate

**Failure Conditions:**
- Web can't see iOS rooms
- Export fails
- Data missing

---

### AT-XP04: Provider Switching (iOS ↔ Web)

**Priority:** P1
**Related:** US-019

**Test Steps:**
1. User creates room on iOS (Apple STT)
2. Web guest joins same room
3. iOS user switches to Speechmatics (premium)
4. Next message uses Speechmatics
5. Web guest sees message (Speechmatics quality)
6. Web guest speaks (Speechmatics STT)
7. iOS user sees translation
8. Verify both use same provider going forward

**Expected Result:**
- ✅ Provider switch affects both platforms
- ✅ Quality consistent across devices
- ✅ No disconnection

**Failure Conditions:**
- Provider switch doesn't sync
- Quality mismatch
- Connection drops

---

### AT-XP05: Account Deletion (Cross-Platform)

**Priority:** P2
**Related:** (Security)

**Test Steps:**
1. User deletes account on Web
2. User tries to login on iOS
3. iOS receives: `401 Unauthorized` (account deleted)
4. iOS shows: "Account not found"
5. User data purged from database
6. Active subscriptions canceled
7. Bonus credits forfeited

**Expected Result:**
- ✅ Account deletion synced
- ✅ iOS login fails
- ✅ Subscriptions canceled
- ✅ Data purged

**Failure Conditions:**
- iOS still works
- Subscriptions not canceled
- Data not purged

---

## 6. Performance Tests (5 scenarios)

### AT-PERF01: 100 Concurrent Users (Quota Tracking)

**Priority:** P1
**Related:** EC-Q08

**Test Setup:**
- 100 rooms with 1 user each
- All users speaking simultaneously

**Test Steps:**
1. Create 100 rooms
2. 100 users join (1 per room)
3. All users speak for 10 seconds simultaneously
4. Measure:
   - Quota deduction latency: <100ms per user
   - Database writes: All 100 transactions recorded
   - Race conditions: No double-charges
5. Verify `quota_transactions` table: Exactly 100 rows

**Expected Result:**
- ✅ All 100 users charged correctly
- ✅ No quota deduction delays >200ms
- ✅ No double-charges (Redis INCR atomic)
- ✅ No database deadlocks

**Failure Conditions:**
- Quota deduction fails or times out
- Double-charges detected
- Database deadlocks

---

### AT-PERF02: Admin Dashboard Query Performance

**Priority:** P1
**Related:** AT-AD04

**Test Setup:**
- 100,000 users
- 10,000,000 quota transactions
- 1,000,000 payment transactions

**Test Steps:**
1. Admin loads /admin/financial (last 30 days)
2. Measure page load time: <3 seconds
3. Admin changes to last 90 days
4. Measure query time: <3.5 seconds
5. Admin clicks "Refresh Now"
6. Materialized view refresh: <10 seconds

**Expected Result:**
- ✅ Dashboard loads in <3s
- ✅ Date range change: <3.5s
- ✅ Manual refresh: <10s
- ✅ No timeouts

**Failure Conditions:**
- Query timeout (>10s)
- Browser freeze
- Dashboard unusable

---

### AT-PERF03: WebSocket Latency (Translation)

**Priority:** P0
**Related:** (Core functionality)

**Test Setup:**
- User speaks, measures end-to-end latency

**Test Steps:**
1. User speaks: "Hello world"
2. Measure timestamps:
   - T0: User stops speaking (audio_end)
   - T1: STT final received (backend)
   - T2: MT translation complete (backend)
   - T3: Translation displayed (frontend)
3. Calculate latency:
   - STT latency: T1 - T0 = <3s
   - MT latency: T2 - T1 = <1s
   - WebSocket latency: T3 - T2 = <200ms
   - Total: T3 - T0 = <4s

**Expected Result:**
- ✅ Total latency <4s (P50)
- ✅ Total latency <6s (P99)
- ✅ WebSocket latency <200ms

**Failure Conditions:**
- Total latency >6s
- WebSocket laggy (>500ms)

---

### AT-PERF04: Provider Failover Time

**Priority:** P1
**Related:** EC-PR01, EC-PR08

**Test Setup:**
- Primary provider (Speechmatics) down

**Test Steps:**
1. User creates room (Plus tier)
2. Backend tries Speechmatics: Connection fails
3. Backend detects failure: <2s
4. Backend falls back to Google v2: <1s
5. Google v2 responds: <3s
6. Total time to first transcription: <6s
7. User notified: "Using fallback provider due to outage"

**Expected Result:**
- ✅ Failover completes in <6s
- ✅ User notified
- ✅ No transcription loss
- ✅ Quality acceptable

**Failure Conditions:**
- Failover timeout (>10s)
- Transcription lost
- User not notified

---

### AT-PERF05: Mobile Data Usage (iOS)

**Priority:** P2
**Related:** (Mobile optimization)

**Test Setup:**
- iOS app on 4G cellular
- 30-minute conversation

**Test Steps:**
1. User creates room on iOS
2. User speaks for 30 minutes (using Apple STT, no audio upload)
3. Measure data usage:
   - WebSocket messages: ~500 KB
   - API requests: ~100 KB
   - Total: ~600 KB
4. Compare to server-side STT (audio upload):
   - Audio upload (16kHz PCM): ~30 MB
   - Savings: 98% (using Apple STT)

**Expected Result:**
- ✅ Data usage <1 MB for 30 min (Apple STT)
- ✅ WebSocket efficient (minimal overhead)
- ✅ 98% data savings vs server STT

**Failure Conditions:**
- Data usage >5 MB (excessive)
- Audio uploaded unnecessarily

---

## Test Execution Summary

| Category | Total Tests | P0 | P1 | P2 |
|----------|-------------|----|----|-----|
| Quota System | 8 | 5 | 3 | 0 |
| Payment Integration | 7 | 4 | 3 | 0 |
| Admin Dashboard | 6 | 2 | 4 | 0 |
| iOS Features | 7 | 3 | 3 | 1 |
| Cross-Platform | 5 | 3 | 2 | 0 |
| Performance | 5 | 1 | 3 | 1 |
| **Total** | **38** | **18** | **18** | **2** |

**Testing Strategy:**
1. **Phase 1 (Week 17):** P0 tests (18 tests) - Block MVP launch
2. **Phase 2 (Week 18):** P1 tests (18 tests) - Important UX
3. **Phase 3 (Post-launch):** P2 tests (2 tests) - Nice-to-have

**Acceptance Criteria for Launch:**
- ✅ 100% P0 tests passing
- ✅ 95% P1 tests passing
- ✅ No critical bugs (P0/P1) in backlog
- ✅ Performance tests meet targets

---

**Last Updated:** 2025-11-03
**Related Documents:** `user-stories.md`, `use-cases.md`, `edge-cases.md`

# LiveTranslator Tier System - User Stories

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Requirements

---

## Overview

28 user stories covering subscription management, quota tracking, room/provider routing, and admin dashboard for LiveTranslator tier system + iOS app project.

**Priority Levels:**
- **P0 (Critical):** Must-have for MVP launch (10 stories)
- **P1 (High):** Important for user experience (12 stories)
- **P2 (Medium):** Nice-to-have enhancements (6 stories)

**Effort Estimates:**
- **XS:** 1-2 hours
- **S:** 4-8 hours (half day)
- **M:** 1-2 days
- **L:** 3-5 days
- **XL:** 1-2 weeks

---

## Subscription & Onboarding (7 stories)

### US-001: Free Tier Signup
**As a** new user,
**I want to** sign up with email/Google OAuth and get 10 minutes free quota,
**So that** I can try LiveTranslator without payment commitment.

**Acceptance Criteria:**
- [ ] Email/password signup creates user with `tier='free'`
- [ ] Google OAuth signup creates user with `tier='free'`
- [ ] User receives `monthly_quota_seconds=600` (10 minutes)
- [ ] User sees "10 minutes free" in quota dashboard
- [ ] Onboarding tutorial shows 3 screens: Create Room, Invite Friends, Speak & Translate
- [ ] User can create first room immediately after signup

**Priority:** P0
**Estimated effort:** M
**Dependencies:** None

---

### US-002: Plus Tier Upgrade (Web)
**As a** free user who exhausted quota,
**I want to** upgrade to Plus tier ($29/mo) via Stripe Checkout,
**So that** I get 2 hours per month with premium providers.

**Acceptance Criteria:**
- [ ] "Upgrade to Plus" button visible in quota exhausted modal
- [ ] Click redirects to Stripe Checkout session
- [ ] Checkout shows: Plus tier, $29/month, 2 hours included
- [ ] Payment success triggers Stripe webhook
- [ ] Webhook updates `user_subscriptions.tier_id=2` (Plus)
- [ ] User redirected back to room with updated quota (7200 seconds)
- [ ] Quota indicator shows "2 hours 0 minutes remaining"
- [ ] Next translation uses premium providers (Speechmatics/DeepL)

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-001

---

### US-003: Pro Tier Upgrade (Web)
**As a** Plus user,
**I want to** upgrade to Pro tier ($199/mo) via Stripe,
**So that** I get 10 hours per month + server-side TTS.

**Acceptance Criteria:**
- [ ] "Upgrade to Pro" button visible in subscription tab
- [ ] Pro-rated charge calculated: `(199 - 29) * (days_remaining / 30)`
- [ ] Stripe Checkout shows pro-rated amount (e.g., $141.67 for 25 days)
- [ ] Payment success updates tier to Pro immediately
- [ ] Quota updated to 10 hours (36,000 seconds)
- [ ] Server-side TTS enabled (Google TTS / AWS Polly / Azure TTS)
- [ ] API access enabled (Pro feature)
- [ ] Billing period remains unchanged

**Priority:** P1
**Estimated effort:** L
**Dependencies:** US-002

---

### US-004: Plus Tier Purchase (iOS - StoreKit)
**As an** iOS free user,
**I want to** subscribe to Plus tier ($29/mo) via Apple In-App Purchase,
**So that** I get 2 hours per month using native iOS payment.

**Acceptance Criteria:**
- [ ] "Upgrade to Plus" button opens StoreKit 2 subscription sheet
- [ ] Sheet shows: Plus Monthly ($29), features list, terms
- [ ] User authenticates with Face ID / Touch ID
- [ ] Payment success triggers receipt verification
- [ ] Backend calls Apple verifyReceipt API
- [ ] Tier updated to Plus in database
- [ ] Receipt stored: `apple_transaction_id`, `apple_customer_id`
- [ ] Quota updated to 2 hours
- [ ] iOS app shows "Plus" badge in profile
- [ ] Cross-platform: Web shows Plus tier also

**Priority:** P0
**Estimated effort:** XL
**Dependencies:** US-001

---

### US-005: Pro Tier Purchase (iOS - StoreKit)
**As an** iOS Plus user,
**I want to** upgrade to Pro tier ($199/mo) via Apple In-App Purchase,
**So that** I get 10 hours per month + server-side TTS.

**Acceptance Criteria:**
- [ ] "Upgrade to Pro" button opens StoreKit 2 subscription sheet
- [ ] Sheet shows: Pro Monthly ($199), features list, upgrade benefits
- [ ] User authenticates with Face ID / Touch ID
- [ ] Payment success triggers receipt verification
- [ ] Backend verifies upgrade from Plus → Pro
- [ ] Pro-rated charge handled by Apple (no backend calculation)
- [ ] Tier updated to Pro
- [ ] Quota updated to 10 hours
- [ ] Server-side TTS enabled
- [ ] Cross-platform: Web shows Pro tier also

**Priority:** P1
**Estimated effort:** XL
**Dependencies:** US-004

---

### US-006: View Current Subscription Status
**As a** logged-in user,
**I want to** view my current tier, quota, and billing information,
**So that** I understand what I'm paying for and when it renews.

**Acceptance Criteria:**
- [ ] Profile page shows current tier badge (Free/Plus/Pro)
- [ ] Subscription tab shows:
  - [ ] Monthly price ($0/$29/$199)
  - [ ] Monthly quota (10 min / 2 hr / 10 hr)
  - [ ] Bonus credits (purchased add-ons)
  - [ ] Billing period: Start and end dates
  - [ ] Next renewal date
  - [ ] Auto-renew status (On/Off toggle)
  - [ ] Payment method (last 4 digits)
  - [ ] Cancel subscription button
- [ ] iOS shows Apple subscription management link
- [ ] Web shows Stripe customer portal link

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-002, US-004

---

### US-007: Cancel Subscription
**As a** paying user (Plus/Pro),
**I want to** cancel my subscription,
**So that** I stop recurring charges but keep tier until period ends.

**Acceptance Criteria:**
- [ ] "Cancel Subscription" button in subscription tab
- [ ] Confirmation modal shows: "Your [Tier] will remain active until [Date]"
- [ ] Click "Confirm Cancel" sets `auto_renew=false`
- [ ] Stripe subscription canceled (if Web)
- [ ] Apple subscription canceled (if iOS)
- [ ] User keeps current tier until `billing_period_end`
- [ ] After period ends, tier downgrades to Free
- [ ] Bonus credits preserved (don't expire)
- [ ] Email confirmation sent

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-006

---

## Quota Management (8 stories)

### US-008: View Remaining Quota (Web)
**As a** logged-in user on Web,
**I want to** see my remaining quota in real-time,
**So that** I know when I'm running low.

**Acceptance Criteria:**
- [ ] Room header shows quota indicator: "X hours Y min remaining"
- [ ] Color codes:
  - [ ] Green: >50% remaining
  - [ ] Yellow: 20-50% remaining
  - [ ] Red: <20% remaining
- [ ] Profile page shows circular progress indicator
- [ ] Displays: Monthly quota + Bonus credits combined
- [ ] Updates in real-time during conversation
- [ ] Shows usage breakdown: STT, MT, TTS percentages
- [ ] Shows next reset date

**Priority:** P0
**Estimated effort:** M
**Dependencies:** US-001

---

### US-009: View Remaining Quota (iOS)
**As an** iOS user,
**I want to** see my remaining quota in the app,
**So that** I know when I'm running low.

**Acceptance Criteria:**
- [ ] Room header shows quota indicator (same as Web)
- [ ] Profile tab shows native circular progress indicator
- [ ] Color codes match Web (green/yellow/red)
- [ ] Displays: Monthly quota + Bonus credits
- [ ] Updates in real-time during conversation
- [ ] Shows usage breakdown (STT, MT, TTS)
- [ ] Shows next reset countdown timer
- [ ] Push notification at 80% usage

**Priority:** P0
**Estimated effort:** M
**Dependencies:** US-004

---

### US-010: Buy Credit Package (Web - Stripe)
**As a** user who exhausted monthly quota,
**I want to** buy credit packages (1hr/$5, 4hr/$19, 8hr/$35, 20hr/$80),
**So that** I can continue using LiveTranslator without upgrading tier.

**Acceptance Criteria:**
- [ ] "Buy More Credits" button in quota exhausted modal
- [ ] Credit packages page shows 4 options:
  - [ ] 1 hour - $5
  - [ ] 4 hours - $19 (Best Value badge)
  - [ ] 8 hours - $35
  - [ ] 20 hours - $80
- [ ] Click package redirects to Stripe Checkout
- [ ] Payment success triggers webhook
- [ ] Webhook adds `bonus_credits_seconds` to user
- [ ] Quota updated immediately (no page reload)
- [ ] User sees new quota: "X hours Y min remaining"
- [ ] Room continues immediately (no interruption)
- [ ] Receipt sent via email

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-002, US-008

---

### US-011: Buy Credit Package (iOS - Apple Pay)
**As an** iOS user who exhausted quota,
**I want to** buy credit packages via Apple Pay,
**So that** I can continue using LiveTranslator with native payment.

**Acceptance Criteria:**
- [ ] "Buy More Credits" button opens native credit sheet
- [ ] StoreKit 2 shows 4 consumable IAPs:
  - [ ] 1 hour - $5
  - [ ] 4 hours - $19
  - [ ] 8 hours - $35
  - [ ] 20 hours - $80
- [ ] User authenticates with Face ID / Apple Pay
- [ ] Payment success triggers receipt verification
- [ ] Backend verifies consumable IAP receipt
- [ ] `bonus_credits_seconds` added to user
- [ ] Quota updated immediately
- [ ] Room continues without interruption
- [ ] In-app receipt shown

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-004, US-009

---

### US-012: Receive Quota Warning (80% Used)
**As a** user approaching quota limit,
**I want to** receive warning when I reach 80% usage,
**So that** I can buy credits or upgrade before running out.

**Acceptance Criteria:**
- [ ] WebSocket sends `quota_alert` message at 80% usage
- [ ] Web: Modal overlay shows warning
- [ ] iOS: Push notification + in-app banner
- [ ] Message: "You've used 80% of your quota. X min remaining."
- [ ] "Buy Credits" button (primary)
- [ ] "Upgrade to [Next Tier]" button (secondary)
- [ ] "Continue" button (dismiss)
- [ ] Alert shown only once per billing period
- [ ] Redis flag prevents duplicate alerts

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-008, US-009

---

### US-013: Handle Quota Exhaustion (Fall Back to Admin)
**As a** participant who exhausted personal quota,
**I want to** automatically fall back to admin's quota,
**So that** conversation continues without interruption.

**Acceptance Criteria:**
- [ ] Participant quota depleted → Backend checks admin quota
- [ ] If admin has quota: Deduct from admin's pool
- [ ] WebSocket sends `quota_fallback` message to admin
- [ ] Admin sees notification: "[User] is using your quota (X min)"
- [ ] Participant sees: "Using room owner's quota"
- [ ] Quota transactions table records: `quota_source='admin'`
- [ ] If admin also exhausted: Send `quota_exhausted` to participant
- [ ] Participant sees upgrade modal

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-008, US-019

---

### US-014: Admin Sees Room Quota Pool Status
**As a** room admin,
**I want to** see quota usage for all participants in real-time,
**So that** I know who's using my quota as fallback.

**Acceptance Criteria:**
- [ ] Room participants panel shows quota usage per user
- [ ] Displays:
  - [ ] User name + email
  - [ ] User tier (Free/Plus/Pro)
  - [ ] Quota used in this room (minutes)
  - [ ] Quota source (Own / Admin fallback)
- [ ] Real-time updates during conversation
- [ ] Color codes:
  - [ ] Green: Using own quota
  - [ ] Yellow: Using admin quota
  - [ ] Red: Exhausted, blocking translation
- [ ] Shows total admin quota pool remaining
- [ ] "Force Close Room" button (if quota critical)

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-013

---

### US-015: Monthly Quota Reset
**As a** user with recurring subscription,
**I want to** automatic monthly quota reset on billing cycle,
**So that** I get fresh quota each month.

**Acceptance Criteria:**
- [ ] Cron job runs daily at midnight UTC
- [ ] Checks each user's `billing_period_end` date
- [ ] If `today >= billing_period_end`:
  - [ ] Reset `user_quota_usage.total_seconds_used = 0`
  - [ ] Set `billing_period_start = today`
  - [ ] Set `billing_period_end = today + 30 days`
  - [ ] Bonus credits preserved (don't reset)
- [ ] Email notification: "Your [Tier] quota has been reset"
- [ ] iOS push notification: "2 hours quota restored"
- [ ] Web notification banner on next login

**Priority:** P0
**Estimated effort:** M
**Dependencies:** US-002, US-004

---

## Room & Provider Routing (6 stories)

### US-016: Create Room with Tier-Based Providers (Free)
**As a** free tier user,
**I want to** create a room using free STT/MT providers,
**So that** I can use LiveTranslator without provider costs.

**Acceptance Criteria:**
- [ ] Room created with `tier='free'`
- [ ] **iOS:** Uses Apple STT (on-device, free)
- [ ] **iOS:** Sends `transcript_direct` messages (no audio to server)
- [ ] **Web:** Uses Speechmatics Basic ($0.08/hr, lowest cost)
- [ ] **MT:** Uses free tier providers (LibreTranslate when quota exhausted)
- [ ] **TTS:** Client-side only (Apple AVSpeechSynthesizer / Web Speech API)
- [ ] Quota deduction: ~3 seconds per sentence (iOS), actual seconds (Web)
- [ ] No server-side TTS costs

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-001

---

### US-017: Create Room with Tier-Based Providers (Plus)
**As a** Plus tier user,
**I want to** create a room using premium STT/MT providers,
**So that** I get better translation quality.

**Acceptance Criteria:**
- [ ] Room created with `tier='plus'`
- [ ] **STT:** Routes to Speechmatics/Google v2/Azure (user choice)
- [ ] **MT:** Routes to DeepL (European) or OpenAI (Arabic)
- [ ] **TTS:** Client-side only (Plus tier)
- [ ] Provider selection UI shows available providers
- [ ] Quota deduction: Actual usage (seconds for STT, characters for MT)
- [ ] Cost tracking: Per-provider costs recorded
- [ ] Translation quality: Better than Free tier

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-002, US-004

---

### US-018: Create Room with Tier-Based Providers (Pro)
**As a** Pro tier user,
**I want to** create a room with all premium features + server TTS,
**So that** I get the best translation experience.

**Acceptance Criteria:**
- [ ] Room created with `tier='pro'`
- [ ] **STT:** All providers available (Speechmatics/Google v2/Azure/Soniox)
- [ ] **MT:** All providers available (DeepL/Google/Amazon/OpenAI)
- [ ] **TTS:** Server-side TTS enabled (Google TTS/AWS Polly/Azure TTS)
- [ ] Provider selection UI shows all options
- [ ] Multi-speaker diarization enabled
- [ ] API access enabled
- [ ] Priority support available
- [ ] Cost tracking: All provider costs recorded

**Priority:** P1
**Estimated effort:** XL
**Dependencies:** US-003, US-005

---

### US-019: Switch Providers During Conversation (Plus/Pro)
**As a** Plus/Pro user,
**I want to** switch STT/MT providers mid-conversation,
**So that** I can optimize for quality or cost.

**Acceptance Criteria:**
- [ ] Settings menu shows provider dropdowns
- [ ] **STT:** Dropdown lists available providers based on tier
- [ ] **MT:** Dropdown lists available providers based on tier
- [ ] Change provider → Next message uses new provider
- [ ] WebSocket connection reused (no reconnection)
- [ ] Segment counter preserved across provider switch
- [ ] Cost tracking reflects new provider
- [ ] Free tier users: Dropdown disabled (no choice)

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-017, US-018

---

### US-020: Guest Joins Room (Uses Admin Quota)
**As a** guest without account,
**I want to** join a room via invite link,
**So that** I can participate without signing up.

**Acceptance Criteria:**
- [ ] Guest clicks QR code / invite link
- [ ] Guest enters display name (no signup required)
- [ ] Guest joins room with `is_guest=true`
- [ ] Guest always uses admin's quota (no own quota)
- [ ] Quota transactions: `quota_source='admin'`
- [ ] Admin sees guest in participants panel
- [ ] Admin sees quota usage by guest
- [ ] Guest can speak and receive translations
- [ ] Guest cannot create rooms or upgrade
- [ ] Guest session expires after 24 hours

**Priority:** P0
**Estimated effort:** M
**Dependencies:** US-014

---

### US-021: iOS Client-Side STT Processing
**As an** iOS user,
**I want to** use Apple Speech Recognition on-device,
**So that** transcription is fast and quota-efficient.

**Acceptance Criteria:**
- [ ] iOS uses SFSpeechRecognizer (on-device)
- [ ] Audio never sent to server (privacy + zero cost)
- [ ] Sends `transcript_direct` messages via WebSocket
- [ ] Message includes: `text`, `source_lang`, `is_final`
- [ ] Backend receives text → Skips STT router
- [ ] Backend publishes to `stt_events` channel
- [ ] MT router translates as normal
- [ ] Quota deduction: ~3 seconds per sentence (estimated)
- [ ] Works offline (Apple Translation API)
- [ ] Fallback to server STT if speech recognition fails

**Priority:** P0
**Estimated effort:** XL
**Dependencies:** US-004, US-016

---

## Admin Dashboard (7 stories)

### US-022: View Revenue vs Costs (Monthly/Weekly/Daily)
**As an** admin,
**I want to** view revenue vs costs over time,
**So that** I can track profitability trends.

**Acceptance Criteria:**
- [ ] Admin dashboard shows financial overview card:
  - [ ] Total revenue (Stripe + Apple)
  - [ ] Total costs (STT + MT + TTS)
  - [ ] Gross profit
  - [ ] Gross margin percentage
- [ ] Time series chart: Revenue (green) vs Costs (red) vs Profit (blue)
- [ ] Date range selector: Last 7/30/90 days or custom
- [ ] Breakdowns:
  - [ ] Revenue: Subscriptions vs Credit purchases
  - [ ] Revenue: Stripe vs Apple
  - [ ] Costs: STT vs MT vs TTS
- [ ] Export to CSV button
- [ ] Data refreshes every 30 seconds (live)

**Priority:** P0
**Estimated effort:** L
**Dependencies:** None

---

### US-023: View KPIs (Signups, DAU, MAU, Conversion Rates)
**As an** admin,
**I want to** view key performance indicators,
**So that** I can measure business health.

**Acceptance Criteria:**
- [ ] Admin dashboard shows KPI cards:
  - [ ] New signups (today/week/month)
  - [ ] DAU (Daily Active Users)
  - [ ] WAU (Weekly Active Users)
  - [ ] MAU (Monthly Active Users)
  - [ ] Stickiness (DAU/MAU ratio)
  - [ ] Free → Plus conversion rate
  - [ ] Free → Pro conversion rate
  - [ ] Plus → Pro upgrade rate
  - [ ] Churn rate
- [ ] Each card shows: Current value, change vs last period
- [ ] Trend indicators: ↑ green (good), ↓ red (bad)
- [ ] Click card → Drill-down page with detailed charts
- [ ] Date range selector

**Priority:** P0
**Estimated effort:** L
**Dependencies:** US-022

---

### US-024: View Per-Tier Profitability
**As an** admin,
**I want to** see profitability breakdown by tier,
**So that** I can identify which tiers are profitable.

**Acceptance Criteria:**
- [ ] Tier analysis table shows:
  - [ ] Tier name (Free/Plus/Pro)
  - [ ] Active users count
  - [ ] Monthly revenue (sum of subscriptions)
  - [ ] Monthly costs (sum of provider costs)
  - [ ] Profit (revenue - costs)
  - [ ] Margin percentage
- [ ] Color codes:
  - [ ] Green: Margin >30% (target met)
  - [ ] Yellow: Margin 10-30% (caution)
  - [ ] Red: Margin <10% or negative (unprofitable)
- [ ] Sort by: Users, Revenue, Profit, Margin
- [ ] Alert if Pro margin <20% (below target)
- [ ] "Adjust Quota" button per tier (admin action)

**Priority:** P0
**Estimated effort:** M
**Dependencies:** US-022

---

### US-025: View Per-Provider Cost Breakdown
**As an** admin,
**I want to** see cost breakdown by provider,
**So that** I can identify expensive providers.

**Acceptance Criteria:**
- [ ] Provider costs table shows:
  - [ ] Provider name (Speechmatics, Google v2, DeepL, etc.)
  - [ ] Service type (STT, MT, TTS)
  - [ ] Event count (API calls)
  - [ ] Total units (seconds, characters, tokens)
  - [ ] Total cost (USD)
  - [ ] Average cost per event
- [ ] Sort by: Cost (desc), Events, Provider
- [ ] Chart: Pie chart showing cost distribution
- [ ] Filter by: Service type (STT/MT/TTS)
- [ ] Date range selector
- [ ] Export to CSV

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-022

---

### US-026: Export Financial Reports
**As an** admin,
**I want to** export financial data to CSV/PDF,
**So that** I can share reports with stakeholders.

**Acceptance Criteria:**
- [ ] "Export" button on all dashboard pages
- [ ] Export formats: CSV, PDF
- [ ] CSV includes all table data (no truncation)
- [ ] PDF includes charts + tables (formatted)
- [ ] Filename includes date range: `financials_2025-10-01_2025-10-31.csv`
- [ ] Email option: Send report to email address
- [ ] Schedule option: Daily/Weekly/Monthly automated exports
- [ ] Export history: List of past exports

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-022, US-023, US-024, US-025

---

### US-027: Set Quota Alerts for Users
**As an** admin,
**I want to** configure quota alert thresholds,
**So that** users receive warnings at appropriate times.

**Acceptance Criteria:**
- [ ] Admin settings page shows quota alert config:
  - [ ] Warning threshold (default: 80%)
  - [ ] Critical threshold (default: 95%)
  - [ ] Alert cooldown (default: 24 hours, prevents spam)
- [ ] Save → Updates `system_settings` table
- [ ] Changes apply immediately (Redis pub/sub invalidation)
- [ ] Test button sends sample alert to admin
- [ ] Alert history: View all quota alerts sent (last 30 days)
- [ ] Filter by: User, Threshold, Date

**Priority:** P2
**Estimated effort:** S
**Dependencies:** US-012

---

### US-028: Admin Grants Bonus Credits (Refund/Support)
**As an** admin,
**I want to** manually grant bonus credits to users,
**So that** I can handle refunds and support cases.

**Acceptance Criteria:**
- [ ] Admin tools page shows "Grant Credits" form
- [ ] Input fields:
  - [ ] User email (autocomplete)
  - [ ] Amount (hours)
  - [ ] Reason (text field, required)
- [ ] Click "Grant" → API call to `/api/admin/users/{id}/grant-credits`
- [ ] Backend adds `bonus_credits_seconds`
- [ ] Backend creates `quota_transactions` record: `type='grant'`
- [ ] User receives email notification
- [ ] iOS user receives push notification
- [ ] Audit log records admin action
- [ ] User sees updated quota immediately

**Priority:** P1
**Estimated effort:** M
**Dependencies:** US-006

---

## Effort Summary

| Effort | Count | Stories |
|--------|-------|---------|
| XL | 3 | US-004, US-005, US-018, US-021 |
| L | 8 | US-002, US-003, US-010, US-011, US-013, US-016, US-017, US-022, US-023 |
| M | 10 | US-006, US-007, US-008, US-009, US-012, US-014, US-015, US-019, US-020, US-024, US-025, US-026, US-028 |
| S | 5 | US-027 |
| XS | 2 | None |

**Total Estimated Effort:** ~25-30 developer-weeks

---

## Dependency Graph

```
US-001 (Free Signup)
  ├─→ US-002 (Plus Upgrade Web)
  │     ├─→ US-003 (Pro Upgrade Web)
  │     ├─→ US-006 (View Subscription)
  │     │     └─→ US-007 (Cancel Subscription)
  │     ├─→ US-008 (View Quota Web)
  │     │     └─→ US-010 (Buy Credits Web)
  │     │           └─→ US-012 (Quota Warning)
  │     ├─→ US-015 (Monthly Reset)
  │     └─→ US-017 (Plus Room Providers)
  │           └─→ US-019 (Switch Providers)
  │
  ├─→ US-004 (Plus Upgrade iOS)
  │     ├─→ US-005 (Pro Upgrade iOS)
  │     ├─→ US-009 (View Quota iOS)
  │     │     └─→ US-011 (Buy Credits iOS)
  │     ├─→ US-016 (Free Room Providers)
  │     └─→ US-021 (iOS Client STT)
  │
  ├─→ US-016 (Free Room Providers)
  ├─→ US-020 (Guest Join)
  │     └─→ US-014 (Admin Quota Pool)
  │           └─→ US-013 (Quota Fallback)
  │
  └─→ US-022 (Admin Revenue vs Costs)
        ├─→ US-023 (Admin KPIs)
        ├─→ US-024 (Tier Profitability)
        ├─→ US-025 (Provider Costs)
        └─→ US-026 (Export Reports)
```

---

## Notes for Development

1. **Prioritize P0 stories first** - These are MVP blockers
2. **iOS stories are XL effort** - Budget 2 weeks each for StoreKit integration
3. **Admin dashboard can be parallelized** - US-022 through US-026 are independent
4. **Test cross-platform quota sync** - US-004 and US-002 must sync perfectly
5. **Quota waterfall is complex** - US-013 requires careful Redis atomicity

---

**Last Updated:** 2025-11-03
**Related Documents:** `use-cases.md`, `acceptance-tests.md`

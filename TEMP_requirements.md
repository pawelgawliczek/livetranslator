# US-002: User Subscription Page - Requirements

**Phase:** 4 (Billing & Payments)
**Estimated Time:** 4 hours
**Status:** Requirements Ready

---

## Executive Summary

Users need a dedicated subscription management page to view available tiers (Free, Plus, Pro), compare features, see current subscription status, monitor quota usage, and initiate Stripe checkout for plan upgrades/purchases.

**Key Finding:** Backend Stripe checkout API (`POST /api/payments/stripe/create-checkout`) exists and is tested. ProfilePage has basic tier display in subscription tab. Need new dedicated `/subscription` page with comprehensive tier comparison, quota visualization, and credit package purchasing.

---

## User Stories

### US-002.1: View Available Subscription Tiers (P0 - Critical)

**As a** registered user
**I want** to see all available subscription plans with features and pricing
**So that** I can compare tiers and decide which plan fits my needs

**Acceptance Criteria:**
- Given I navigate to `/subscription` (authenticated)
- When page loads
- Then I see three tier cards: Free, Plus ($29/mo), Pro ($199/mo)
- And each card displays: tier name, price, quota (10min/2hr/10hr), feature list, provider access level
- And my current tier is visually highlighted (border accent color, badge)
- And quota is displayed as "X hours per month" (not seconds)

**Out of Scope:**
- Annual pricing toggle (future phase)
- Trial periods (future phase)
- Promotional discounts (future phase)

**Dependencies:**
- `GET /api/subscription` (exists - returns current user subscription)
- `subscription_tiers` table data (already seeded in Migration 016)

---

### US-002.2: Monitor Current Quota Usage (P0 - Critical)

**As a** subscriber
**I want** to see my real-time quota usage prominently
**So that** I know how much quota I have remaining before being blocked

**Acceptance Criteria:**
- Given I am on `/subscription` page
- When page loads
- Then I see current quota status card at top: "X.XX hours used / Y hours total this month"
- And I see visual progress bar (green <50%, yellow 50-80%, red >80%)
- And I see "Next reset: Nov 30, 2025" (billing_period_end)
- And if I have bonus_credits_seconds, show "+ Z.ZZ bonus hours"
- And quota updates when I refresh page (cached 30s via `GET /api/quota/status`)

**Out of Scope:**
- Real-time WebSocket quota updates (future phase)
- Historical usage graphs (future phase)

**Dependencies:**
- `GET /api/quota/status` (exists - tier_helpers.py)
- Requires authenticated user with active subscription

---

### US-002.3: Subscribe to Paid Tier (P0 - Critical)

**As a** free tier user
**I want** to click "Subscribe" on Plus/Pro tier
**So that** I can upgrade and get more quota + premium features

**Acceptance Criteria:**
- Given I am on Free tier and viewing Plus/Pro card
- When I click "Subscribe to Plus" button
- Then `POST /api/payments/stripe/create-checkout` is called with `{product_type: 'subscription', tier_id: 2}`
- And I am redirected to Stripe hosted checkout page (session.url)
- And after successful payment, Stripe webhook processes and updates my tier
- And I return to `/billing/success` page showing "Subscription activated!"
- And if Stripe API fails, show error toast "Payment system unavailable. Try again later."

**Out of Scope:**
- Stripe Elements inline checkout (use hosted checkout for MVP)
- Free trial implementation (future phase)

**Dependencies:**
- `POST /api/payments/stripe/create-checkout` (exists - payments.py:72)
- `POST /api/payments/stripe/webhook` (exists - handles checkout.session.completed)
- `/billing/success` and `/billing/cancel` pages (need to create)
- STRIPE_SECRET_KEY env var configured

---

### US-002.4: Purchase Credit Packages (P1 - High)

**As a** any tier user
**I want** to buy additional credit hours (1hr/$5, 4hr/$19, 8hr/$35, 20hr/$80)
**So that** I can top-up when I exceed my monthly quota

**Acceptance Criteria:**
- Given I am on `/subscription` page
- When I scroll to "Buy Additional Credits" section
- Then I see 4 credit package cards (1hr, 4hr, 8hr, 20hr) with prices and discount %
- And each card has "Buy Now" button
- When I click "Buy 4hr Credits"
- Then `POST /api/payments/stripe/create-checkout` is called with `{product_type: 'credits', package_id: 2}`
- And I am redirected to Stripe checkout
- And after payment, bonus_credits_seconds is updated via webhook
- And I see updated quota: "X hours + Y bonus hours"

**Out of Scope:**
- Credit gifting to other users (future phase)
- Bulk enterprise packages >20hr (future phase)

**Dependencies:**
- `GET /api/payments/credit-packages` (exists - payments.py:340)
- `POST /api/payments/stripe/create-checkout` with product_type='credits' (exists)
- `credit_packages` table seeded (Migration 016)

---

### US-002.5: View Current Subscription Details (P1 - High)

**As a** paid subscriber
**I want** to see my subscription status, billing date, and payment method
**So that** I know when my next charge occurs and can manage my subscription

**Acceptance Criteria:**
- Given I am on Plus/Pro tier
- When I view subscription page
- Then I see "Current Subscription" section with:
  - Tier: "Plus" (badge with accent color)
  - Status: "Active" (green) / "Past Due" (yellow) / "Canceled" (red)
  - Next billing: "Dec 1, 2025" (billing_period_end)
  - Auto-renew: "Enabled" toggle (read-only for MVP)
- And I see "Manage Subscription" button → links to Stripe Customer Portal (future)

**Out of Scope:**
- Cancel subscription inline (use Stripe Customer Portal)
- Downgrade to Free (future - requires prorating logic)
- Change payment method (use Stripe Customer Portal)

**Dependencies:**
- `GET /api/subscription` (exists - subscription_api.py:48)
- UserSubscription model fields: status, billing_period_end, auto_renew

---

## Page Structure

### Route
`/subscription` (authenticated only, redirect to `/login` if not logged in)

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Header: [← Back to Rooms] [Profile] [Logout]               │
├─────────────────────────────────────────────────────────────┤
│ "Subscription & Credits"                                     │
├─────────────────────────────────────────────────────────────┤
│ [Quota Status Card]                                          │
│ ┌───────────────────────────────────────────────────────┐   │
│ │ 1.23 hrs used / 2 hrs this month  [████░░] 61%       │   │
│ │ + 0.50 bonus hours                                    │   │
│ │ Next reset: Nov 30, 2025                             │   │
│ └───────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ "Choose Your Plan"                                           │
│ ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│ │  FREE    │  │  PLUS ✓  │  │   PRO    │                  │
│ │  $0/mo   │  │ $29/mo   │  │ $199/mo  │                  │
│ │ 10 min   │  │ 2 hours  │  │ 10 hours │                  │
│ │ Features │  │ Features │  │ Features │                  │
│ │ [Current]│  │[Upgrade] │  │[Upgrade] │                  │
│ └──────────┘  └──────────┘  └──────────┘                  │
├─────────────────────────────────────────────────────────────┤
│ "Buy Additional Credits" (Bonus Hours)                       │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│ │ 1 hr   │ │ 4 hrs  │ │ 8 hrs  │ │ 20 hrs │              │
│ │ $5     │ │ $19    │ │ $35    │ │ $80    │              │
│ │ [Buy]  │ │ [Buy]  │ │ [Buy]  │ │ [Buy]  │              │
│ └────────┘ └────────┘ └────────┘ └────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## Tier Comparison Table

| Feature | Free | Plus | Pro |
|---------|------|------|-----|
| **Price** | $0/month | $29/month | $199/month |
| **Quota** | 10 minutes/month | 2 hours/month | 10 hours/month |
| **STT Providers** | Apple, Speechmatics (Web) | Speechmatics, Deepgram, AssemblyAI | All providers + Azure |
| **MT Providers** | Web Speech API, DeepL | DeepL, OpenAI | All providers + Azure |
| **TTS** | Client-side only | Client-side only | Server-side (Google/AWS/Azure) |
| **Support** | Community | Email | Priority (24/7) |
| **History Export** | ❌ | ✅ PDF/TXT | ✅ PDF/TXT + API |
| **Multi-speaker** | ✅ | ✅ | ✅ |
| **Room recording** | ✅ | ✅ | ✅ |

---

## Subscription Flow Diagram

```
┌─────────────────┐
│ User clicks     │
│ "Subscribe"     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ POST /api/payments/stripe/create    │
│ {product_type: 'subscription',      │
│  tier_id: 2}                        │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Frontend receives:                  │
│ {checkout_url: "stripe.com/...",   │
│  session_id: "cs_..."}              │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ window.location.href = checkout_url │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ User on Stripe hosted checkout page │
│ Enter card details, confirm         │
└────────┬────────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  SUCCESS   CANCEL
    │         │
    │         └─→ Redirect to /billing/cancel
    │
    ▼
┌─────────────────────────────────────┐
│ Stripe sends webhook to             │
│ POST /api/payments/stripe/webhook   │
│ event: checkout.session.completed   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Webhook handler updates:            │
│ - user_subscriptions.tier_id = 2    │
│ - status = 'active'                 │
│ - billing_period_start = now        │
│ - billing_period_end = now + 30d    │
│ - payment_transactions record       │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ User redirected to                  │
│ /billing/success?session_id=cs_...  │
│ "Subscription activated!"           │
└─────────────────────────────────────┘
```

---

## Edge Cases

### EC-1: User Already Subscribed to Same Tier
**Scenario:** Plus user clicks "Subscribe to Plus"
**Behavior:** Button disabled, text "Current Plan"
**Test:** Verify button has `disabled` class and cursor-not-allowed

### EC-2: Upgrade from Plus to Pro
**Scenario:** Plus user clicks "Subscribe to Pro"
**Behavior:** Full checkout flow, webhook updates tier_id=3
**Test:** Verify tier_id changes from 2→3, quota increases from 2hr→10hr
**Note:** No prorating in MVP - user charged full $199, loses Plus

### EC-3: Downgrade from Pro to Plus
**Scenario:** Pro user wants to downgrade
**Behavior:** "Downgrade" not available in MVP (button hidden for higher tiers)
**Test:** Verify no downgrade button visible on lower-tier cards
**Future:** Implement via Stripe Customer Portal with prorating

### EC-4: Stripe API Unavailable
**Scenario:** POST /api/payments/stripe/create-checkout returns 503
**Behavior:** Toast error "Payment system unavailable. Try again later."
**Test:** Mock Stripe error, verify toast appears, no navigation

### EC-5: User Cancels Stripe Checkout
**Scenario:** User clicks back button on Stripe page
**Behavior:** Redirected to `/billing/cancel` → "Payment canceled. You can try again anytime."
**Test:** Verify cancel URL in session.create, cancel page exists

### EC-6: Webhook Processing Fails
**Scenario:** Database down during webhook processing
**Behavior:** Webhook returns 500, Stripe retries (exponential backoff)
**Test:** Simulate DB error, verify Stripe retry mechanism
**Mitigation:** Redis idempotency check prevents duplicate processing (line 186 payments.py)

### EC-7: Free User with 0 Quota Remaining
**Scenario:** Free user exhausted 10 minutes, views subscription page
**Behavior:** Quota card shows "0.00 / 0.17 hours (100%)" in red, alert banner "Upgrade to continue"
**Test:** Set quota_used=600s, verify red progress bar and CTA

### EC-8: User Has Bonus Credits
**Scenario:** User purchased 4hr package, has bonus_credits_seconds=14400
**Behavior:** Quota card shows "+ 4.00 bonus hours" below main quota
**Test:** Verify bonus hours displayed, deducted first (per tier_helpers.py logic)

### EC-9: Multiple Tabs Open During Checkout
**Scenario:** User opens 2 tabs, clicks subscribe in both
**Behavior:** Two checkout sessions created (different session_id), only first payment succeeds
**Test:** Verify idempotency - second webhook ignored via Redis cache

### EC-10: Payment Succeeds But User Not Redirected
**Scenario:** User closes browser before success redirect
**Behavior:** Webhook still processes, tier updated. Next login shows new tier.
**Test:** Verify subscription active even without visiting /billing/success

---

## Test Scenarios

### P0: Critical Path Tests

#### T-001: Free User Upgrades to Plus
**Steps:**
1. Login as free user (tier_id=1)
2. Navigate to `/subscription`
3. Click "Subscribe to Plus" button
4. Complete Stripe checkout (test card: 4242 4242 4242 4242)
5. Verify redirect to `/billing/success`
6. Verify tier_id=2, monthly_quota_hours=2, status='active'

**Expected:** Subscription active, quota shows "0.00 / 2.00 hours"

---

#### T-002: Plus User Buys 8hr Credit Package
**Steps:**
1. Login as plus user (tier_id=2)
2. Navigate to `/subscription`
3. Scroll to "Buy Additional Credits"
4. Click "Buy" on 8hr package
5. Complete Stripe checkout ($35)
6. Verify bonus_credits_seconds=28800 (8*3600)
7. Verify quota shows "+ 8.00 bonus hours"

**Expected:** Bonus credits added, quota_available increased by 8hr

---

#### T-003: Display Current Tier Badge
**Steps:**
1. Login as pro user (tier_id=3)
2. Navigate to `/subscription`
3. Verify Pro card has accent border + "Current Plan" badge
4. Verify Free and Plus cards show "Downgrade" (disabled/hidden in MVP)

**Expected:** Visual highlight on current tier, no upgrade button on current tier

---

### P1: Edge Case Tests

#### T-004: Stripe API Returns 503
**Steps:**
1. Mock `POST /api/payments/stripe/create-checkout` to return 503
2. Click "Subscribe to Plus"
3. Verify error toast appears
4. Verify no navigation occurs
5. Verify user remains on `/subscription` page

**Expected:** Graceful error handling, user can retry

---

#### T-005: Quota Usage Color Coding
**Steps:**
1. Set user quota_used=3600 (1hr), monthly_quota=7200 (2hr) → 50%
2. Verify progress bar is yellow
3. Set quota_used=6480 (1.8hr) → 90%
4. Verify progress bar is red
5. Set quota_used=1800 (0.5hr) → 25%
6. Verify progress bar is green

**Expected:** Color changes at 50% (yellow) and 80% (red) thresholds

---

#### T-006: Cancel Stripe Checkout
**Steps:**
1. Click "Subscribe to Plus"
2. On Stripe page, click back button
3. Verify redirect to `/billing/cancel`
4. Verify message "Payment canceled"
5. Click "Try Again" button → returns to `/subscription`

**Expected:** User can cancel and retry, no partial state

---

#### T-007: Webhook Idempotency
**Steps:**
1. Send `checkout.session.completed` webhook event
2. Verify tier updated
3. Send same event again (duplicate event_id)
4. Verify Redis cache hit: "already processed"
5. Verify tier not updated twice
6. Verify no duplicate payment_transactions record

**Expected:** Duplicate webhooks ignored, no double-charging

---

### P2: Integration Tests

#### T-008: End-to-End Subscription Flow
**Steps:**
1. Create new user via `/signup`
2. User auto-assigned Free tier (tier_id=1)
3. Navigate to `/subscription`
4. Verify quota shows "0.00 / 0.17 hours" (10 minutes)
5. Click "Subscribe to Plus"
6. Complete Stripe checkout
7. Verify webhook processed (check logs)
8. Refresh page
9. Verify tier shows "Plus", quota shows "0.00 / 2.00 hours"
10. Create room, use 30 minutes
11. Refresh `/subscription`
12. Verify quota shows "0.50 / 2.00 hours"

**Expected:** Full user journey works, quota tracked correctly

---

#### T-009: Credit Package Purchase Flow
**Steps:**
1. Login as free user (0.17hr quota)
2. Use 10 minutes (quota exhausted)
3. Navigate to `/subscription`
4. Verify quota shows "0.17 / 0.17 hours (100%)" in red
5. Buy 1hr package ($5)
6. Complete checkout
7. Verify webhook processed
8. Refresh page
9. Verify quota shows "0.17 / 0.17 hours + 1.00 bonus hours"
10. Create room, use 30 minutes
11. Verify bonus_credits_seconds reduced by 1800

**Expected:** Bonus credits deducted first, main quota preserved

---

### P3: UI/UX Tests

#### T-010: Mobile Responsive Layout
**Steps:**
1. Open `/subscription` on mobile (375px width)
2. Verify tier cards stack vertically
3. Verify credit package cards stack 2x2 grid
4. Verify quota card full width
5. Verify buttons remain tappable (44px min)

**Expected:** Usable on mobile devices

---

#### T-011: Loading States
**Steps:**
1. Open `/subscription`
2. Throttle network to Slow 3G
3. Verify "Loading..." spinner while fetching quota/tiers
4. Click "Subscribe to Plus"
5. Verify button shows "Processing..." during API call
6. Verify button disabled during processing

**Expected:** Clear loading feedback, prevent double-clicks

---

## API Endpoints Required

### Existing (No Changes)
- `GET /api/subscription` → Current user subscription
- `GET /api/quota/status` → Real-time quota status
- `POST /api/payments/stripe/create-checkout` → Create Stripe session
- `GET /api/payments/credit-packages` → List available packages
- `POST /api/payments/stripe/webhook` → Handle Stripe events

### New (To Create)
- **None** - All backend APIs exist and tested

---

## Frontend Components to Create

### New Pages
1. **`/web/src/pages/SubscriptionPage.jsx`** (main deliverable)
   - Imports: React, useState, useEffect, useNavigate, useTranslation
   - Fetches: /api/subscription, /api/quota/status, /api/payments/credit-packages
   - Components: TierCard, QuotaStatusCard, CreditPackageCard
   - Functions: handleSubscribe(tierId), handleBuyCredits(packageId)

2. **`/web/src/pages/BillingSuccessPage.jsx`**
   - Query param: session_id (from Stripe)
   - Display: "Payment Successful!" + tier details + "Continue to Dashboard" button

3. **`/web/src/pages/BillingCancelPage.jsx`**
   - Display: "Payment Canceled" + "Try Again" button → back to /subscription

### New Components
1. **`/web/src/components/TierCard.jsx`**
   - Props: tier, isCurrent, onSubscribe
   - Displays: tier name, price, quota, features, button (Subscribe/Current/Upgrade)

2. **`/web/src/components/QuotaStatusCard.jsx`**
   - Props: quotaStatus (from /api/quota/status)
   - Displays: progress bar, used/total, bonus hours, next reset date
   - Color logic: green <50%, yellow 50-80%, red >80%

3. **`/web/src/components/CreditPackageCard.jsx`**
   - Props: package, onBuy
   - Displays: hours, price, discount badge, "Buy Now" button

### Routes to Add (main.jsx)
```jsx
<Route path="/subscription" element={<SubscriptionPage token={token} />} />
<Route path="/billing/success" element={<BillingSuccessPage token={token} />} />
<Route path="/billing/cancel" element={<BillingCancelPage token={token} />} />
```

---

## i18n Keys (web/public/locales/en/translation.json)

```json
{
  "subscription": {
    "title": "Subscription & Credits",
    "choosePlan": "Choose Your Plan",
    "buyCredits": "Buy Additional Credits",
    "currentPlan": "Current Plan",
    "subscribe": "Subscribe",
    "upgrade": "Upgrade to {{tier}}",
    "buyNow": "Buy Now",
    "quotaUsed": "{{used}} / {{total}} hours this month",
    "bonusHours": "+ {{hours}} bonus hours",
    "nextReset": "Next reset: {{date}}",
    "perMonth": "/month",
    "features": "Features",
    "processing": "Processing...",
    "upgradeSuccess": "Subscription activated!",
    "paymentCanceled": "Payment canceled. You can try again anytime.",
    "tryAgain": "Try Again",
    "continueToDashboard": "Continue to Dashboard",
    "stripeError": "Payment system unavailable. Try again later."
  }
}
```

---

## Out of Scope (Future Phases)

1. **Annual pricing** ($290/year Plus, $1990/year Pro) - 20% discount
2. **Free trial** (7 days Pro trial for new users)
3. **Downgrade flow** (requires prorating, Stripe Customer Portal)
4. **Gifting credits** to other users
5. **Enterprise plans** (>20hr packages, custom pricing)
6. **Subscription pause** (vacation hold)
7. **Team/organization accounts** (shared quota pool)
8. **Invoice history** (download past invoices)
9. **Auto-upgrade** (when quota exhausted, prompt immediate upgrade)
10. **Referral program** (earn bonus hours for referrals)

---

## Security Considerations

1. **Stripe Webhook Verification:** Already implemented (signature check at payments.py:168)
2. **Idempotent Webhooks:** Redis cache prevents duplicate processing (TTL 7 days)
3. **CORS:** Frontend must match FRONTEND_URL env var for checkout redirect
4. **API Auth:** All endpoints require valid JWT token (except webhook)
5. **Rate Limiting:** Prevent subscription spam (future - add rate limit middleware)

---

## Performance

1. **Quota Status Caching:** Redis 30s TTL (quota.py:86)
2. **Tier Data:** Static table, cached in frontend state
3. **Credit Packages:** Fetch once on page load
4. **Optimistic UI:** Show "Processing..." immediately on button click
5. **Lazy Load:** Credit section below fold, load after tier comparison visible

---

## Accessibility

1. **Semantic HTML:** Use `<article>` for tier cards, `<section>` for groups
2. **ARIA Labels:** `aria-label="Subscribe to Plus tier"`
3. **Keyboard Nav:** All buttons focusable, Enter key triggers click
4. **Color Contrast:** Ensure 4.5:1 ratio on all text (WCAG AA)
5. **Screen Reader:** Announce quota percentage changes

---

## Monitoring

1. **Analytics Events:**
   - `subscription_page_viewed`
   - `subscribe_button_clicked` (tier_id)
   - `checkout_completed` (tier_id, amount)
   - `credit_package_purchased` (package_id, amount)

2. **Error Tracking:**
   - Stripe API errors (rate, error codes)
   - Webhook processing failures
   - Checkout abandonment rate

3. **Metrics:**
   - Conversion rate: Free → Plus
   - Conversion rate: Plus → Pro
   - Average time on subscription page
   - Bounce rate from Stripe checkout

---

## Rollout Plan

1. **Stage 1:** Create `/billing/success` and `/billing/cancel` pages (stub)
2. **Stage 2:** Build TierCard, QuotaStatusCard, CreditPackageCard components
3. **Stage 3:** Build SubscriptionPage, integrate components
4. **Stage 4:** Add routes to main.jsx
5. **Stage 5:** Test with Stripe test mode (4242...)
6. **Stage 6:** Add link to subscription page from ProfilePage nav
7. **Stage 7:** Deploy to staging, QA full flow
8. **Stage 8:** Switch to Stripe live mode, production deploy

---

## Acceptance Checklist

- [ ] `/subscription` page displays 3 tier cards with correct data
- [ ] Current tier visually highlighted with badge
- [ ] Quota status card shows accurate usage from `/api/quota/status`
- [ ] Progress bar color changes at 50% (yellow) and 80% (red)
- [ ] Bonus hours displayed if `bonus_credits_seconds > 0`
- [ ] "Subscribe" button calls Stripe checkout API, redirects to Stripe
- [ ] "Buy Credits" button calls Stripe checkout with `product_type='credits'`
- [ ] `/billing/success` page displays after successful payment
- [ ] `/billing/cancel` page displays if user cancels
- [ ] Webhook processes `checkout.session.completed` and updates tier
- [ ] Duplicate webhooks ignored (Redis idempotency)
- [ ] Error toast shows if Stripe API fails
- [ ] Mobile responsive (tier cards stack vertically)
- [ ] All text translatable via i18n keys
- [ ] No console errors in browser
- [ ] Passes T-001 through T-009 (critical tests)

---

## Time Breakdown (4 hours)

- **Hour 1:** Create BillingSuccessPage, BillingCancelPage (30min), TierCard component (30min)
- **Hour 2:** Create QuotaStatusCard (30min), CreditPackageCard (30min)
- **Hour 3:** Build SubscriptionPage main layout, integrate components, API calls
- **Hour 4:** Add i18n keys, test Stripe checkout flow (test mode), fix bugs, polish UI

---

## Dependencies Summary

**Backend (All Exist):**
- `POST /api/payments/stripe/create-checkout` ✅
- `GET /api/subscription` ✅
- `GET /api/quota/status` ✅
- `GET /api/payments/credit-packages` ✅
- Stripe webhook handler ✅

**Database:**
- `subscription_tiers` table seeded ✅
- `credit_packages` table seeded ✅
- `user_subscriptions` model extended ✅

**Environment:**
- `STRIPE_SECRET_KEY` configured (check .env)
- `FRONTEND_URL` matches deployment domain
- Redis running (quota cache)

**Frontend (To Create):**
- SubscriptionPage.jsx
- BillingSuccessPage.jsx
- BillingCancelPage.jsx
- TierCard, QuotaStatusCard, CreditPackageCard components
- Routes in main.jsx
- i18n keys

---

## Questions for Stakeholders

1. **Pricing Confirmation:** Free (10min), Plus ($29/2hr), Pro ($199/10hr) correct?
2. **Downgrade Policy:** Should we hide/disable downgrade buttons in MVP?
3. **Cancel Flow:** Implement inline or redirect to Stripe Customer Portal?
4. **Navigation:** Where should "Subscription" link appear? (ProfilePage? RoomsPage header?)
5. **Post-Purchase:** Redirect to /subscription or /rooms after successful upgrade?

---

**End of Requirements Document**

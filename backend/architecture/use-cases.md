# LiveTranslator Tier System - Use Cases

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Requirements

---

## Overview

12 detailed use cases covering tier system, quota management, payments, iOS app, and admin dashboard.

**Priority Levels:**
- **Priority 0 (Critical):** Must-have for MVP launch
- **Priority 1 (High Impact):** Important for user experience and business goals

---

## Priority 0 (Critical) Use Cases

### UC-001: New User Onboarding (Free Tier)

**Actor:** New User (Web or iOS)

**Preconditions:**
- User has not registered before
- User has internet connection
- Browser supports WebSocket (Web) or iOS 15+ (iOS)

**Main Flow:**
1. User visits https://livetranslator.pawelgawliczek.cloud (Web) or downloads iOS app
2. User clicks "Sign Up"
3. System presents signup options: Email/Password, Google OAuth (Web), Sign in with Apple (iOS)
4. User completes signup
5. System creates user with `tier='free'`, `monthly_quota_seconds=600` (10 minutes)
6. System shows onboarding tutorial (3 screens):
   - Screen 1: "Create a room" - Visual guide to room creation
   - Screen 2: "Invite friends" - QR code invite flow
   - Screen 3: "Speak & Translate" - Push microphone button demo
7. User clicks "Get Started"
8. System redirects to rooms page
9. User creates first room with auto-generated code
10. User sees quota dashboard: "10 minutes free"
11. User invites friend via QR code
12. User speaks → Sees transcription → Sees translation → Success!

**Alternative Flows:**
- 3a. Google OAuth (Web): Redirects to Google consent → Returns with user info
- 3b. Sign in with Apple (iOS): Face ID → Apple ID consent → Returns with user token
- 4a. Email already exists: Show "Already have an account? Login"
- 12a. User exhausts 10 minutes: Show upgrade modal (UC-002)

**Postconditions:**
- User account created with Free tier
- User has 10 minutes (600 seconds) quota
- User can create rooms and invite guests
- User understands how to use LiveTranslator

**Error Scenarios:**
- Email validation fails → Show error: "Invalid email format"
- Password too weak → Show error: "Password must be 8+ characters"
- Google OAuth fails → Show error: "Google login failed. Try email signup."
- Network error → Show error: "Connection failed. Check internet."

**Related User Stories:** US-001, US-016, US-020

---

### UC-002: Free User Exhausts Quota → Upgrades to Plus

**Actor:** Free User (Web)

**Preconditions:**
- User has Free tier account
- User has exhausted 10-minute free quota (`remaining_seconds <= 0`)
- User is in active room conversation
- User has valid payment method

**Main Flow:**
1. User speaks in room
2. Backend detects `remaining_seconds = 0`
3. Backend sends WebSocket message: `quota_exhausted`
4. Frontend shows modal:
   - Title: "Quota Exhausted"
   - Message: "You've used your 10 free minutes this month."
   - Option 1: "Upgrade to Plus ($29/mo)" - Primary button
   - Option 2: "Buy 4 Hours ($19)" - Secondary button
   - Option 3: "Continue" - Disabled (no quota)
5. User clicks "Upgrade to Plus"
6. System creates Stripe Checkout session:
   - Product: Plus Monthly Subscription
   - Price: $29.00
   - Recurring: Monthly
   - Trial: None
   - Success URL: `/profile?tab=subscription`
   - Cancel URL: `/profile?tab=subscription`
7. System redirects to Stripe Checkout
8. User enters payment details (card number, expiry, CVV)
9. User clicks "Subscribe"
10. Stripe processes payment
11. Stripe sends webhook: `checkout.session.completed`
12. Backend receives webhook:
    - Verifies signature
    - Extracts `user_id` from metadata
    - Updates `user_subscriptions.tier_id = 2` (Plus)
    - Sets `billing_period_start = now`
    - Sets `billing_period_end = now + 30 days`
    - Resets `user_quota_usage.total_seconds_used = 0`
    - Sets `monthly_quota_seconds = 7200` (2 hours)
    - Creates `payment_transactions` record
13. Backend sends WebSocket message: `tier_updated`
14. Frontend shows success message: "Upgraded to Plus! 2 hours quota activated."
15. User redirected back to room
16. User speaks → Backend uses Speechmatics (premium STT)
17. Translation uses DeepL (premium MT)
18. Quota indicator shows: "2 hours 0 minutes remaining"

**Alternative Flows:**
- 5a. User clicks "Buy 4 Hours" → See UC-003
- 8a. User clicks "Cancel" → Redirected back to profile, quota still 0
- 10a. Payment declined → Stripe shows error, user can retry
- 11a. Webhook delayed (>5 min) → Backend polls Stripe API after 5 min
- 11b. Webhook fails → User sees "Payment processing..." for 30s, then manual sync

**Postconditions:**
- User tier = Plus
- User has 2 hours (7200 seconds) monthly quota
- User subscription active with auto-renew
- Payment recorded in Stripe + database
- User receives confirmation email
- User can continue conversation with premium providers

**Error Scenarios:**
- Stripe API error → Show "Payment failed. Please try again."
- Webhook signature invalid → Log error, trigger manual sync
- Database update fails → Rollback, show error
- User already has Plus tier → Redirect to profile with message "Already subscribed"

**Related User Stories:** US-002, US-008, US-010, US-017

---

### UC-003: Plus User Exhausts Quota → Buys Credits

**Actor:** Plus User (Web or iOS)

**Preconditions:**
- User has Plus tier subscription
- User has exhausted monthly quota (2 hours used)
- User is mid-billing cycle (not near renewal)
- User is in active room conversation

**Main Flow:**
1. User speaks in room
2. Backend detects Plus user quota exhausted
3. Backend sends WebSocket: `quota_exhausted`
4. Frontend shows modal:
   - Title: "Monthly Quota Exhausted"
   - Message: "You've used your 2 hours this month. Next reset: Nov 30"
   - Credit packages:
     - [ ] 1 hour - $5
     - [ ] 4 hours - $19 ⭐ Best Value
     - [ ] 8 hours - $35
     - [ ] 20 hours - $80
   - "Upgrade to Pro (10 hr/mo)" link
5. User selects "4 hours - $19"
6. **Web Flow:**
   - System creates Stripe payment intent
   - Redirects to Stripe Checkout
   - User enters payment details
   - Payment succeeds
7. **iOS Flow:**
   - StoreKit 2 shows consumable IAP sheet
   - User authenticates with Face ID / Apple Pay
   - Apple processes payment
   - iOS app receives transaction
   - iOS app sends receipt to backend
8. Backend verifies payment:
   - **Web:** Stripe webhook `payment_intent.succeeded`
   - **iOS:** Apple verifyReceipt API call
9. Backend grants credits:
   - `bonus_credits_seconds += 14400` (4 hours)
   - Creates `payment_transactions` record
   - Creates `quota_transactions` record: `type='purchase'`
10. Backend sends WebSocket: `quota_updated`
11. Frontend updates quota display: "4 hours 0 minutes remaining"
12. Room continues immediately (no interruption)
13. User speaks → Translation works (uses bonus credits)
14. User receives confirmation email (Web) or receipt (iOS)

**Alternative Flows:**
- 5a. User clicks "Upgrade to Pro" → Redirects to subscription upgrade flow
- 6a. Payment declined → Show error, allow retry
- 8a. Apple receipt invalid → Show error: "Purchase verification failed. Contact support."
- 9a. User already purchased same package in last 5 minutes → Detect duplicate, show error
- 11a. WebSocket disconnected → Quota updates on reconnect

**Postconditions:**
- User has 4 hours bonus credits (14,400 seconds)
- Bonus credits used before monthly quota
- Payment recorded in database
- User can continue conversation
- Bonus credits don't expire (persist across billing cycles)

**Error Scenarios:**
- Stripe webhook fails → Retry 3 times, then manual sync
- Apple receipt fraud detected → Block transaction, flag account
- Database write fails → Rollback, refund payment
- User closes browser during payment → Stripe redirect handles resumption

**Related User Stories:** US-010, US-011, US-012

---

### UC-004: Admin Monitors Costs → Adjusts Pricing

**Actor:** Admin (Business Owner)

**Preconditions:**
- Admin has admin account (`is_admin=true`)
- Admin is logged in via Web
- System has been running for at least 30 days (data available)

**Main Flow:**
1. Admin navigates to `/admin/financial`
2. System loads financial overview (last 30 days):
   - **Revenue:** $12,000
     - Subscriptions: $9,800
     - Credit purchases: $2,200
     - Stripe: $7,000
     - Apple: $5,000
   - **Costs:** $9,000
     - STT: $3,500
     - MT: $4,000
     - TTS: $1,500
   - **Gross Profit:** $3,000
   - **Gross Margin:** 25% ⚠️ (below 30% target)
3. Admin clicks "Tier Analysis" tab
4. System shows profitability by tier:
   - **Free:** 700 users, -$500/mo (expected loss)
   - **Plus:** 200 users, +$3,000/mo (25% margin) ⚠️
   - **Pro:** 100 users, +$2,000/mo (20% margin) ⚠️
5. Admin identifies issue: Pro tier margin too low
6. Admin clicks "Provider Costs" tab
7. System shows cost breakdown:
   - Speechmatics: $3,000/mo
   - DeepL: $2,500/mo
   - OpenAI GPT-4o-mini: $1,500/mo
   - Google TTS: $1,000/mo (Pro only)
8. Admin analyzes: Pro users using expensive server TTS
9. Admin decision: Reduce Pro quota from 10hr → 8hr
10. Admin navigates to `/admin/tiers`
11. Admin edits Pro tier:
    - Field: `monthly_quota_hours`
    - Old value: 10
    - New value: 8
    - Reason: "Improve margin to 30% target"
12. Admin clicks "Save Changes"
13. System confirms: "Pro tier quota reduced. Existing users affected next billing cycle."
14. System logs admin action in audit table
15. System sends notification to Pro users: "Starting Dec 1, Pro tier quota is 8 hr/mo"
16. Admin monitors for 1 week
17. Week later: Pro margin improves to 28% (closer to target)
18. Admin creates report: Export financial data to CSV
19. Admin shares with stakeholders

**Alternative Flows:**
- 9a. Admin decides to increase Pro price instead → Navigate to `/admin/pricing`, update price
- 9b. Admin decides to remove expensive TTS provider → Navigate to `/admin/providers`, disable Google TTS
- 13a. Immediate change needed → Checkbox: "Apply to existing users immediately"
- 16a. Margin drops further → Revert quota change, try different approach

**Postconditions:**
- Pro tier quota reduced to 8 hours
- Existing Pro users notified
- Change effective on next billing cycle (or immediate if forced)
- Admin has data to justify decision
- Margin tracking continues

**Error Scenarios:**
- Database query timeout (1M+ users) → Show cached data with staleness indicator
- Export fails (large dataset) → Retry with pagination, or email when ready
- Admin accidentally sets quota to 0 → Validation error: "Quota must be > 0"
- Concurrent admin changes → Last write wins, show conflict warning

**Related User Stories:** US-022, US-023, US-024, US-025, US-026

---

### UC-005: iOS/Web Cross-Platform Usage (Same Account)

**Actor:** User with iOS app and Web access

**Preconditions:**
- User has Plus tier subscription (purchased on Web via Stripe)
- User has iOS app installed
- User logs into iOS app with same email

**Main Flow:**
1. **Day 1 - Web Signup:**
   - User signs up on Web with email/password
   - User upgrades to Plus tier via Stripe ($29/mo)
   - User has 2 hours quota
2. **Day 2 - iOS Login:**
   - User downloads iOS app
   - User logs in with same email/password
   - iOS app fetches user profile: `GET /api/users/{id}/subscription`
   - Backend returns: `tier='plus'`, `monthly_quota_seconds=7200`
   - iOS app shows "Plus" badge in profile
   - iOS app unlocks Plus features (premium providers)
3. **Day 2 - iOS Usage:**
   - User creates room on iOS
   - User speaks (Apple STT, on-device)
   - Backend receives `transcript_direct` message
   - Backend deducts quota: ~3 seconds per sentence
   - Translation uses DeepL (Plus tier)
   - User speaks for 30 minutes (1800 seconds)
   - Quota remaining: 7200 - 1800 = 5400 seconds (90 minutes)
4. **Day 3 - Web Usage:**
   - User opens Web app
   - User creates room on Web
   - Quota indicator shows: "1 hour 30 minutes remaining"
   - User speaks for 60 minutes (3600 seconds)
   - Quota remaining: 5400 - 3600 = 1800 seconds (30 minutes)
5. **Day 4 - iOS Check:**
   - User opens iOS app
   - iOS app fetches quota: `GET /api/users/{id}/quota`
   - iOS app shows: "30 minutes remaining"
   - Quota synced correctly across platforms
6. **Day 10 - iOS Credit Purchase:**
   - User exhausts quota on iOS
   - User buys 4 hours via Apple Pay (StoreKit)
   - Backend verifies Apple receipt
   - Backend grants `bonus_credits_seconds = 14400`
7. **Day 10 - Web Check:**
   - User opens Web app
   - Web app fetches quota
   - Web app shows: "4 hours 0 minutes remaining (bonus credits)"
   - Credits synced across platforms
8. **Day 30 - Monthly Reset:**
   - Cron job runs: Reset monthly quota
   - User quota reset to 7200 seconds (2 hours)
   - Bonus credits preserved (4 hours)
   - Both iOS and Web show: "6 hours 0 minutes remaining"

**Alternative Flows:**
- 2a. User purchased Plus on iOS (Apple IAP) → Web shows Plus tier also
- 3a. User has no internet on iOS → Offline mode (Apple Translation works, quota tracked locally, synced when online)
- 6a. User buys credits on Web (Stripe) → iOS shows updated credits
- 8a. User canceled subscription → Auto-downgrade to Free, bonus credits preserved

**Postconditions:**
- Quota synced perfectly across iOS and Web
- Payment platform doesn't matter (Stripe or Apple)
- User has seamless cross-platform experience
- No duplicate charges or quota discrepancies

**Error Scenarios:**
- iOS quota fetch fails → Show last cached quota + warning banner
- Web quota update delayed → WebSocket pushes update when available
- User buys credits on both iOS and Web simultaneously → Both purchases succeed, both credits granted
- Apple receipt validation fails → Show error, allow manual retry or contact support

**Related User Stories:** US-002, US-004, US-006, US-009, US-011

---

## Priority 1 (High Impact) Use Cases

### UC-006: Pro User Creates Multi-Speaker Room

**Actor:** Pro User (Web or iOS)

**Preconditions:**
- User has Pro tier subscription
- User has 10 hours monthly quota
- User wants to host meeting with 5 participants

**Main Flow:**
1. User creates room: "Team Meeting"
2. System assigns tier='pro' to room
3. User enables settings:
   - [x] Multi-speaker diarization (Pro feature)
   - [x] Server-side TTS (Pro feature)
   - [x] Recording enabled
4. User invites 4 participants via QR code:
   - Participant A: Free tier (English)
   - Participant B: Plus tier (Polish)
   - Participant C: Free tier (Arabic)
   - Participant D: Guest (no account, Spanish)
5. All participants join room
6. System calculates quota pool:
   - Admin (Pro): 10 hours available
   - Participant A (Free): 0 minutes (exhausted)
   - Participant B (Plus): 1 hour available
   - Participant C (Free): 5 minutes available
   - Participant D (Guest): 0 (uses admin quota)
7. **Conversation starts:**
   - Admin speaks English → Backend:
     - STT: Speechmatics (diarization: speaker_1)
     - MT: DeepL → Polish, OpenAI → Arabic, DeepL → Spanish
     - TTS: Google TTS plays Polish/Arabic/Spanish audio (Pro feature)
     - Quota: Deduct 10 seconds from Admin
   - Participant A speaks English → Backend:
     - Tries own quota: 0 available
     - Falls back to Admin quota
     - Admin sees notification: "Participant A using your quota (10s)"
     - Quota: Deduct 10 seconds from Admin
   - Participant B speaks Polish → Backend:
     - Uses own quota (Plus tier)
     - Quota: Deduct 10 seconds from Participant B
   - Participant C speaks Arabic → Backend:
     - Uses own quota (5 min available)
     - After 5 minutes exhausted → Falls back to Admin
     - Admin notified
   - Participant D speaks Spanish → Backend:
     - Always uses Admin quota (guest)
8. **Meeting ends after 2 hours:**
   - Admin quota used: 90 minutes (1.5 hours)
   - Participant B quota used: 30 minutes
   - Participant C quota used: 5 minutes
   - Total cost: ~$8.50 (STT + MT + TTS for 5 speakers)
9. Admin views room history:
   - Export conversation to PDF
   - Speaker labels: Admin, Participant A, B, C, D
   - Timestamps and translations included
10. Admin views costs:
    - Room cost breakdown: $8.50
    - Quota usage per participant shown
11. Admin quota remaining: 8.5 hours

**Alternative Flows:**
- 7a. Admin quota exhausted → All participants see error: "Room owner quota exhausted. Upgrade or buy credits."
- 7b. Participant leaves and rejoins → 10-second grace period, no duplicate notification
- 9a. Export during meeting → Real-time export with "Conversation ongoing..." note

**Postconditions:**
- Multi-speaker conversation successful
- Quota pooling worked correctly
- Admin has full cost transparency
- History exportable with speaker labels
- All participants satisfied with experience

**Error Scenarios:**
- Diarization fails (1 speaker detected) → Fallback to email-based speaker ID
- Server TTS fails → Fallback to client-side TTS (no additional cost)
- Admin disconnects mid-meeting → Participants can continue if they have own quota
- Network interruption → Participants reconnect with 10-second grace period

**Related User Stories:** US-018, US-013, US-014, US-020

---

### UC-007: Guest Joins Room → Exhausts Admin Quota

**Actor:** Guest (no account) + Room Admin (Plus tier)

**Preconditions:**
- Admin has Plus tier (2 hours quota)
- Admin has created room with invite link
- Guest has no LiveTranslator account
- Admin has 30 minutes quota remaining

**Main Flow:**
1. Guest receives room invite link: `https://livetranslator.../join?code=ABC123`
2. Guest clicks link in browser
3. System shows join page:
   - Room name: "Quick Chat"
   - Input: "Enter your name"
   - Button: "Join Room"
4. Guest enters name: "John"
5. Guest clicks "Join Room"
6. System creates guest session:
   - `user_id = null`
   - `display_name = "John"`
   - `is_guest = true`
   - `quota_source = 'admin'` (always)
7. Guest joins room, sees welcome banner: "Connected with [Admin name]"
8. Admin sees notification: "John joined the room"
9. **Guest speaks for 15 minutes:**
   - Backend deducts quota from Admin (guest has no own quota)
   - Admin quota: 30 min → 15 min remaining
   - Admin sees in participants panel:
     - John (Guest) - Using your quota (15 min)
10. Admin receives warning: "You have 15 minutes remaining. John is using your quota."
11. **Guest continues speaking for 10 more minutes:**
    - Admin quota: 15 min → 5 min remaining
    - Admin sees critical warning (red indicator)
12. Admin decides to buy credits:
    - Admin clicks "Buy 4 Hours"
    - Admin completes Stripe payment
    - Admin quota updated: 5 min + 4 hours = 4 hr 5 min
13. **Guest continues speaking for another 20 minutes:**
    - Admin quota: 4 hr 5 min → 3 hr 45 min
    - Conversation continues smoothly
14. Guest leaves room
15. Admin sees final usage:
    - John (Guest): 45 minutes used
    - Total cost: $2.25 (STT + MT for 45 min)
16. Admin exports conversation history
17. Guest receives no bill (used admin's quota)

**Alternative Flows:**
- 9a. Admin quota exhausted before guest finishes → Guest sees: "Room owner quota exhausted. Ask them to upgrade."
- 9b. Admin closes room → Guest disconnected with message: "Room closed by owner"
- 12a. Admin doesn't buy credits → At quota=0, guest cannot speak
- 14a. Guest's browser crashes → 10-second grace period, silent reconnect if returns

**Postconditions:**
- Guest used 45 minutes of admin's quota
- Admin purchased additional credits to continue
- Conversation history saved with guest name "John"
- Guest received no bill
- Admin has full cost visibility

**Error Scenarios:**
- Guest invite link expired → Show error: "Invite link expired. Ask room owner for new link."
- Admin account suspended → Guest cannot join: "Room unavailable"
- Guest name contains profanity → Filter/reject: "Please choose appropriate name"
- Admin quota exhausted + guest trying to speak → Show modal: "Waiting for room owner to add credits"

**Related User Stories:** US-020, US-013, US-014, US-010

---

### UC-008: Quota Pooling with 3 Participants

**Actor:** 3 Users with different tiers

**Preconditions:**
- User A: Plus tier (30 minutes remaining)
- User B: Free tier (0 minutes remaining)
- User C: Pro tier (creates room, 5 hours remaining)
- All users in same room

**Main Flow:**
1. User C (Pro) creates room "Group Chat"
2. User C invites User A and User B via QR code
3. All users join room
4. System calculates quota pool:
   - User A (Plus): 30 minutes
   - User B (Free): 0 minutes
   - User C (Pro, Admin): 5 hours
   - **Total pool:** 5.5 hours
5. **User A speaks for 20 minutes:**
   - Backend deducts from User A's quota
   - User A quota: 30 min → 10 min
   - User C (admin) not affected yet
6. **User B speaks for 5 minutes:**
   - Backend checks User B quota: 0 available
   - Backend falls back to User C (admin) quota
   - User C quota: 5 hr → 4 hr 55 min
   - User C sees notification: "User B using your quota (5 min)"
7. **User A speaks for another 15 minutes:**
   - Backend checks User A quota: 10 min available
   - Backend deducts 10 min from User A
   - User A quota exhausted: 10 min → 0 min
   - Backend falls back to User C for remaining 5 min
   - User C quota: 4 hr 55 min → 4 hr 50 min
   - User C sees notification: "User A using your quota (5 min)"
8. **User C speaks for 10 minutes:**
   - Backend deducts from User C's own quota
   - User C quota: 4 hr 50 min → 4 hr 40 min
9. **Conversation ends:**
   - Final quota status:
     - User A: 0 min (used 30 min own)
     - User B: 0 min (used 5 min from admin)
     - User C: 4 hr 40 min (used 20 min own, provided 10 min to others)
10. User C views room quota pool status:
    - Table shows:
      - User A: 30 min used (Own quota)
      - User B: 5 min used (Admin fallback)
      - User C: 20 min used (Own quota)
    - Total admin quota provided: 10 minutes
    - Total cost: $4.50
11. All users see accurate quota indicators
12. Database records all quota transactions with `quota_source` field

**Alternative Flows:**
- 6a. User C also exhausted → All users see error: "Room quota exhausted"
- 7a. User A buys credits mid-conversation → Uses new credits before admin fallback
- 9a. User C leaves room → Room continues if other users have quota

**Postconditions:**
- Quota pooling worked correctly (user → admin waterfall)
- All quota transactions recorded accurately
- Admin has full visibility into quota usage
- Costs accurately attributed to correct users
- No quota discrepancies or double-deductions

**Error Scenarios:**
- Concurrent quota deduction (race condition) → Redis INCR atomic operation prevents
- WebSocket disconnection during quota deduction → Quota update retried on reconnect
- Database write fails → Rollback quota deduction, show error
- Admin quota displayed incorrectly → Real-time WebSocket update corrects

**Related User Stories:** US-013, US-014, US-008, US-009

---

### UC-009: Payment Failure Recovery (Retry Flow)

**Actor:** Plus User with expired credit card

**Preconditions:**
- User has Plus tier subscription ($29/mo)
- User's credit card expired last month
- Billing renewal date is today
- User has active room conversation

**Main Flow:**
1. **Day 1 (Renewal Date):**
   - Stripe attempts to charge $29 for renewal
   - Payment fails: "Card expired"
   - Stripe sends webhook: `invoice.payment_failed`
   - Backend receives webhook:
     - Updates `user_subscriptions.status = 'past_due'`
     - Sets `payment_retry_count = 1`
   - User receives email: "Payment failed. Update your card to keep Plus tier."
   - iOS user receives push notification
2. **Day 1 (User Action):**
   - User logs into Web app
   - Banner shows: "Payment failed. Update card to keep access."
   - User clicks "Update Payment Method"
   - Redirects to Stripe Customer Portal
   - User updates card details
   - Stripe automatically retries payment
3. **Day 1 (Retry Success):**
   - Payment succeeds on retry
   - Stripe sends webhook: `invoice.payment_succeeded`
   - Backend updates:
     - `status = 'active'`
     - `payment_retry_count = 0`
     - `billing_period_start = today`
     - `billing_period_end = today + 30 days`
   - User receives confirmation email
   - Banner disappears
   - User continues using Plus tier

**Alternative Flow (Retry Fails):**
1. **Day 1:** Payment fails (card expired)
2. **Day 2:** Stripe auto-retry #1 fails (card still expired)
3. **Day 4:** Stripe auto-retry #2 fails
4. **Day 7:** Stripe auto-retry #3 fails (final attempt)
5. **Day 7:** Stripe sends webhook: `customer.subscription.deleted`
6. Backend receives webhook:
   - Updates `status = 'canceled'`
   - Downgrades `tier_id = 1` (Free)
   - Preserves `bonus_credits_seconds` (purchased credits don't expire)
7. User receives email: "Subscription canceled due to payment failure. You're now on Free tier."
8. User logs in, sees downgrade notice
9. User can resubscribe anytime with valid payment

**Alternative Flow (User Fixes Card Before Auto-Downgrade):**
1. **Day 1:** Payment fails
2. **Day 5:** User updates card in Stripe portal
3. **Day 5:** Stripe immediately retries payment
4. **Day 5:** Payment succeeds
5. User tier remains Plus (no downgrade)

**Postconditions:**
- Payment recovered successfully, or
- User downgraded to Free tier after 7 days
- Bonus credits preserved in all cases
- User notified at each step
- Clear recovery path provided

**Error Scenarios:**
- Stripe webhook never arrives → Backend polls Stripe API daily for `past_due` subscriptions
- User closes browser during card update → Stripe portal handles session resumption
- Duplicate payment charged → Stripe idempotency prevents, backend detects via `payment_intent_id`
- User's subscription deleted while they have bonus credits → Credits preserved, tier downgraded

**Related User Stories:** US-006, US-007, US-015

---

### UC-010: iOS User Switches from Apple to Premium Providers

**Actor:** iOS Plus User

**Preconditions:**
- User has Plus tier subscription
- User currently using Apple STT (on-device, free)
- User wants better accuracy for technical terms

**Main Flow:**
1. User opens room settings in iOS app
2. User sees provider options:
   - **STT Provider:**
     - [ ] Apple Speech Recognition (Free, on-device) ✓ Currently selected
     - [ ] Speechmatics (Premium, $0.08/hr)
     - [ ] Google Cloud Speech v2 (Premium, $0.96/hr)
   - **MT Provider:**
     - [ ] DeepL (Premium, best for European languages) ✓ Currently selected
     - [ ] OpenAI GPT-4o-mini (Premium, best for Arabic)
3. User changes STT to "Speechmatics"
4. System shows confirmation:
   - "Switching to Speechmatics will:"
   - "✓ Improve accuracy for technical terms"
   - "✓ Enable real-time partials (word-by-word)"
   - "✗ Use quota (audio sent to server)"
   - "Cost: ~$0.08 per hour of speech"
5. User taps "Confirm"
6. System updates user preference:
   - Saves to database: `user_settings.stt_provider = 'speechmatics'`
7. User starts speaking
8. iOS app captures audio via microphone
9. iOS app sends audio chunks to backend via WebSocket:
   - Message type: `audio_chunk` (not `transcript_direct`)
   - Audio format: PCM16, 16kHz, base64-encoded
10. Backend receives audio
11. Backend routes to Speechmatics (via STT router)
12. Speechmatics returns real-time partials:
    - "Hello" → "Hello world" → "Hello world, testing"
13. Frontend displays partials (gray text, spinning icon)
14. Speechmatics returns final: "Hello world, testing Speechmatics STT."
15. Frontend displays final (white text, checkmark)
16. Quota deducted: ~5 seconds of speech
17. User sees improved accuracy for technical terms
18. User satisfied with premium provider

**Alternative Flows:**
- 4a. User on Free tier tries to switch → Blocked: "Upgrade to Plus to use premium providers"
- 11a. Speechmatics API down → Backend falls back to Google v2 (automatic)
- 11b. User quota exhausted mid-sentence → Backend falls back to Apple STT, sends notification
- 16a. User switches back to Apple STT → Next message uses Apple, no audio sent

**Postconditions:**
- User successfully using Speechmatics STT on iOS
- Audio sent to server (no longer on-device)
- Quota deducted based on actual usage
- Improved transcription accuracy
- User preference saved for future sessions

**Error Scenarios:**
- Network error during audio upload → iOS app buffers audio, retries when connected
- Speechmatics connection fails → Backend auto-fallback to Google v2 or Azure
- User switches provider mid-sentence → Current sentence completes with old provider, next sentence uses new provider
- Quota exhausted while using premium → Backend falls back to Apple STT (free), no service interruption

**Related User Stories:** US-019, US-021, US-017

---

### UC-011: Web User Exports History with Quota Usage

**Actor:** Plus User (Web)

**Preconditions:**
- User has Plus tier subscription
- User has completed 5 conversations in past month
- User wants to review costs and export data

**Main Flow:**
1. User navigates to Profile → History tab
2. System shows room list:
   - Room "Team Meeting" - Nov 1 - 45 min - $3.50
   - Room "Client Call" - Nov 5 - 30 min - $2.25
   - Room "Interview" - Nov 10 - 60 min - $4.80
   - Room "Quick Chat" - Nov 15 - 20 min - $1.50
   - Room "Presentation" - Nov 20 - 25 min - $2.00
3. User clicks "Team Meeting" room
4. System loads conversation history:
   - 120 segments (transcriptions)
   - 3 languages (English, Polish, Arabic)
   - 2 hours duration
   - Speakers: User + 2 guests
5. User selects target language: "English"
6. System displays conversation with English translations
7. User clicks "Export" button
8. System shows export options:
   - Format: [ ] PDF [x] TXT [ ] CSV
   - Include: [x] Timestamps [x] Speaker names [x] Translations
   - Include: [x] Quota usage [x] Cost breakdown
9. User selects PDF with all options
10. System generates PDF:
    - Header: Room name, date, duration
    - Conversation transcript with timestamps
    - Speaker labels and translations
    - Footer: Quota usage (45 min), Cost ($3.50)
11. System downloads PDF: `team-meeting-2025-11-01.pdf`
12. User opens PDF, reviews content
13. User sees quota usage summary:
    - Own quota used: 30 minutes
    - Admin quota used (guests): 15 minutes
    - STT cost: $2.00 (Speechmatics)
    - MT cost: $1.50 (DeepL + OpenAI)
    - Total: $3.50
14. User satisfied with transparency

**Alternative Flows:**
- 9a. User selects CSV format → Downloads spreadsheet with one row per segment
- 9b. User unchecks "Include cost" → PDF generated without financial data
- 10a. PDF generation fails (timeout) → System emails PDF when ready
- 13a. User wants to dispute costs → Click "Report Issue" button, opens support ticket

**Postconditions:**
- User has exported conversation history
- Export includes quota usage and cost breakdown
- User understands what they're paying for
- Export saved locally or emailed

**Error Scenarios:**
- Room history too large (10,000+ segments) → Show warning: "Export will be emailed"
- Translation not available for target language → Generate on-demand, then export
- Export fails due to timeout → Retry with pagination, or queue for background job
- PDF rendering fails → Fallback to TXT format

**Related User Stories:** US-008, US-026

---

### UC-012: Admin Grants Bonus Credits (Refund Scenario)

**Actor:** Admin + User (Support Case)

**Preconditions:**
- User reported issue: "Translation quality poor in my last room"
- User exhausted quota during problematic room
- Admin reviewed issue logs
- Admin decided to issue refund as bonus credits

**Main Flow:**
1. Admin logs into admin panel
2. Admin navigates to `/admin/tools/grant-credits`
3. Admin enters user email: "user@example.com"
4. System auto-completes, shows user profile:
   - Name: John Doe
   - Tier: Plus
   - Current quota: 0 minutes remaining
   - Last room: "Client Call" (30 min, Nov 15)
5. Admin enters refund details:
   - Amount: 30 minutes (0.5 hours)
   - Reason: "Refund for poor translation quality in room 'Client Call' on Nov 15. Issue #1234."
6. Admin clicks "Grant Credits"
7. System confirms: "Grant 30 minutes to John Doe?"
8. Admin clicks "Confirm"
9. Backend processes:
   - `bonus_credits_seconds += 1800` (30 minutes)
   - Creates `quota_transactions` record:
     - `type = 'grant'`
     - `quota_source = 'bonus'`
     - `amount_seconds = 1800`
     - `reason = "Refund for poor translation..."`
     - `granted_by_admin_id = 1`
   - Creates audit log entry
10. Backend sends notifications:
    - Email to user: "We've added 30 minutes to your account as a refund for issue #1234."
    - iOS push notification: "30 minutes bonus credits added"
11. User receives notification, opens app
12. User sees updated quota: "30 minutes remaining (bonus credits)"
13. User creates new room, uses bonus credits
14. User satisfied with resolution

**Alternative Flows:**
- 4a. Email not found → Show error: "User not found. Check email address."
- 6a. Admin enters invalid amount (negative) → Validation error: "Amount must be > 0"
- 9a. Database write fails → Rollback, show error: "Grant failed. Try again."
- 14a. User already resolved issue (bought credits) → Credits stack, user has more quota

**Postconditions:**
- User received 30 minutes bonus credits
- Transaction recorded with reason and admin ID
- User notified via email and push
- Audit log entry created for compliance
- User can continue using service

**Error Scenarios:**
- Admin grants credits to wrong user → Audit log allows reversal, admin can revoke credits
- User reports duplicate credit grant → Check `quota_transactions` table, no duplicates found
- System sends duplicate notifications → Notification deduplication (5-minute window)
- Admin accidentally grants 1000 hours → Validation limit: Max 100 hours per grant

**Related User Stories:** US-028, US-014

---

## Summary

| Use Case | Priority | Complexity | Effort | Dependencies |
|----------|----------|------------|--------|--------------|
| UC-001 | P0 | Medium | M | None |
| UC-002 | P0 | High | L | UC-001 |
| UC-003 | P0 | High | L | UC-002 |
| UC-004 | P0 | Medium | L | None |
| UC-005 | P0 | High | XL | UC-002, UC-004 |
| UC-006 | P1 | High | XL | UC-003, UC-005 |
| UC-007 | P1 | Medium | M | UC-002 |
| UC-008 | P1 | High | L | UC-002, UC-003 |
| UC-009 | P1 | Medium | M | UC-002 |
| UC-010 | P1 | Medium | M | UC-005 |
| UC-011 | P1 | Low | S | UC-002 |
| UC-012 | P1 | Low | S | None |

**Total Use Cases:** 12 (5 P0, 7 P1)

---

**Last Updated:** 2025-11-03
**Related Documents:** `user-stories.md`, `acceptance-tests.md`, `system-diagrams.md`

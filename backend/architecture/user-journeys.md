# LiveTranslator Tier System - User Journey Maps

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Requirements

---

## Overview

5 detailed user journey maps covering the complete user lifecycle from signup → upgrade → usage → administration.

**Journey Components:**
- **Steps:** User actions and system responses
- **Emotions:** User emotional state at each step
- **Pain Points:** Friction and obstacles
- **Opportunities:** UX improvements

---

## Journey 1: New Free User → First Translation

**Persona:** Sarah, 32, Marketing Manager
**Goal:** Try LiveTranslator for international client meeting
**Context:** First-time user, referred by colleague

### Journey Map

```
Step 1: Landing Page
Action: Visits livetranslator.com, reads "Real-time translation for conversations"
Emotion: 😊 Curious
Pain Point: None yet
System: Shows hero section, "Try Free" CTA

↓

Step 2: Signup
Action: Clicks "Try Free", sees signup form (Email + Password + Name)
Emotion: 😐 Hesitant (why so many fields?)
Pain Point: ⚠️ Too many input fields for "quick try"
Opportunity: Reduce to email only, collect name later
System: Validates email, creates account

↓

Step 3: Onboarding Tutorial
Action: Sees 3 slides: "Create Room", "Invite Friends", "Speak & Translate"
Emotion: 😊 Excited (looks easy!)
Pain Point: None
System: Shows interactive tutorial with animations

↓

Step 4: Create First Room
Action: Clicks "Create Room", auto-generated code appears
Emotion: 😊 Confident
Pain Point: None
System: Room created: "room-abc123"

↓

Step 5: Invite Client
Action: Shows QR code to client on laptop webcam
Emotion: 😰 Anxious (will it work?)
Pain Point: ⚠️ QR code doesn't scan well from laptop screen
Opportunity: Add "Send Link via Email" button
System: QR code displayed, client scans with phone

↓

Step 6: Client Joins
Action: Client enters name, joins room
Emotion: 😌 Relieved
Pain Point: None
System: Shows welcome banner: "Connected with [Client name]"

↓

Step 7: Audio Permission
Action: Browser asks: "Allow microphone access?"
Emotion: 😰 Anxious (is this safe?)
Pain Point: ⚠️ No explanation why microphone needed
Opportunity: Show tooltip: "We need mic to hear you speak"
System: Grants microphone permission

↓

Step 8: First Words
Action: Says "Hello, can you hear me?" (English)
Emotion: 😊 Excited
Pain Point: None
System: Transcribes, shows gray text with spinner

↓

Step 9: See Translation
Action: Client sees "Cześć, czy mnie słyszysz?" (Polish translation)
Emotion: 😍 Delighted!
Pain Point: ⚠️ 2-4 second delay feels slow
Opportunity: Show "Translating..." indicator
System: Publishes translation via WebSocket

↓

Step 10: Success!
Action: 15-minute meeting completes successfully
Emotion: 😊 Satisfied
Pain Point: None
System: Shows quota warning: "You have 5 minutes remaining"

↓

Step 11: Quota Warning (Post-Meeting)
Action: Sees modal: "You've used 50% of your free quota (5 min left)"
Emotion: 😰 Worried (need more?)
Pain Point: ⚠️ Interruption after success (bad timing)
Opportunity: Show warning earlier (80% during meeting)
System: Shows upgrade options

```

### Summary

**Total Time:** 25 minutes (signup → meeting end)
**Emotion Trend:** Curious → Hesitant → Excited → Anxious → Relieved → Delighted → Satisfied → Worried
**Critical Pain Points:**
1. Too many signup fields (friction)
2. QR code hard to scan from laptop (technical)
3. Audio permission unexplained (trust issue)
4. Translation delay feels slow (performance)
5. Quota warning after meeting (bad timing)

**Conversion Rate Impact:**
- 40% drop-off at signup (too many fields)
- 15% drop-off at QR scan (technical issues)
- 10% drop-off at audio permission (trust issues)
- **Net conversion:** 40% × 85% × 90% = 30.6%

**Opportunities:**
1. Reduce signup to email only (+10% conversion)
2. Add "Email Invite" alternative to QR (+8% conversion)
3. Add microphone permission tooltip (+5% conversion)
4. Show "Translating..." indicator (better UX)
5. Move quota warning to 80% threshold (less intrusive)

---

## Journey 2: Plus Upgrade Decision

**Persona:** Mark, 28, Freelance Translator
**Goal:** Decide if Plus tier ($29/mo) is worth it
**Context:** Used free 10 minutes, needs more for client work

### Journey Map

```
Step 1: Quota Warning (80%)
Action: Mid-conversation, sees banner: "You've used 8 of 10 minutes"
Emotion: 😰 Anxious (running out!)
Pain Point: ⚠️ Warning interrupts conversation flow
Opportunity: Show quota indicator in header (always visible)
System: WebSocket sends quota_alert message

↓

Step 2: See Pricing Page
Action: Clicks "View Plans" in warning banner
Emotion: 🤔 Curious (what do I get?)
Pain Point: None yet
System: Redirects to /pricing page

↓

Step 3: Compare Tiers
Action: Sees table: Free (10 min) vs Plus (2 hr) vs Pro (10 hr)
Emotion: 🧐 Calculating (is 2 hr enough?)
Pain Point: ⚠️ Unclear how much 2 hours is (# of meetings?)
Opportunity: Add examples: "~4 meetings per month"
System: Shows tier comparison table

↓

Step 4: Check Features
Action: Reads Plus features: "Premium providers, 2 hr/mo, email support"
Emotion: 🤔 Considering (what's "premium providers"?)
Pain Point: ⚠️ Technical jargon unclear
Opportunity: Add tooltips: "Better translation quality"
System: Shows feature list

↓

Step 5: Decision Point
Action: Decides to try Plus for 1 month
Emotion: 😐 Trusting (but cautious)
Pain Point: ⚠️ No free trial mentioned
Opportunity: Add "First month $9" promotional pricing
System: Waits for user action

↓

Step 6: Checkout
Action: Clicks "Upgrade to Plus", redirected to Stripe
Emotion: 😰 Hesitant (entering card details)
Pain Point: ⚠️ Card form has many fields (friction)
Opportunity: Enable Apple Pay / Google Pay (faster)
System: Stripe Checkout session created

↓

Step 7: Payment
Action: Enters card: number, expiry, CVV, ZIP
Emotion: 😐 Neutral (standard checkout)
Pain Point: ⚠️ Manual typing (slow)
Opportunity: Autofill support
System: Stripe validates card

↓

Step 8: Confirmation
Action: Payment succeeds, redirected back to app
Emotion: 😌 Relieved
Pain Point: ⚠️ Email confirmation delayed (5 min)
Opportunity: Instant in-app confirmation
System: Webhook processes, tier updated

↓

Step 9: Use Premium
Action: Creates new room, notices faster translations
Emotion: 😊 Satisfied (worth it!)
Pain Point: None
System: Routes to Speechmatics (premium STT)

```

### Summary

**Total Time:** 10 minutes (warning → first premium use)
**Emotion Trend:** Anxious → Curious → Calculating → Considering → Trusting → Hesitant → Neutral → Relieved → Satisfied
**Conversion Rate:** 15% (of users who see pricing page)

**Critical Pain Points:**
1. Warning interrupts conversation (bad UX)
2. Unclear value proposition (how much is 2 hours?)
3. Technical jargon (premium providers?)
4. No free trial (risk aversion)
5. Card form friction (many fields)
6. Email confirmation delayed (uncertainty)

**Opportunities:**
1. Always-visible quota indicator (+5% conversion)
2. Usage examples: "~4 meetings/month" (+10% conversion)
3. Tooltips for technical terms (+3% conversion)
4. Promotional pricing: "First month $9" (+20% conversion)
5. Apple Pay / Google Pay support (+8% conversion)
6. Instant in-app confirmation (+2% conversion)

**Potential Conversion Improvement:** 15% → 25% (+66% lift)

---

## Journey 3: Admin Monthly Review

**Persona:** Alex, 35, LiveTranslator Founder
**Goal:** Review monthly financials, adjust pricing if needed
**Context:** End of month, checking profitability

### Journey Map

```
Step 1: Login
Action: Logs into admin panel: /admin
Emotion: 😐 Routine (monthly check)
Pain Point: None
System: Shows admin dashboard

↓

Step 2: Financial Overview
Action: Sees cards: Revenue $12k, Costs $9k, Profit $3k, Margin 25%
Emotion: 😟 Analytical (margin below 30% target)
Pain Point: None
System: Loads data from materialized view (cached)

↓

Step 3: Filter Date Range
Action: Changes from "Last 30 days" to "Last 7 days"
Emotion: 🧐 Focused (check recent trend)
Pain Point: ⚠️ Chart takes 3 seconds to reload
Opportunity: Pre-cache common date ranges
System: Queries database, re-renders chart

↓

Step 4: View Chart
Action: Sees revenue vs cost line chart (last 7 days)
Emotion: 😊 Satisfied (costs stabilizing)
Pain Point: None
System: Displays interactive chart (Recharts)

↓

Step 5: Drill into Tiers
Action: Clicks "Tier Analysis" tab
Emotion: 🤔 Curious (which tier is losing?)
Pain Point: None
System: Shows tier profitability table

↓

Step 6: Identify Issue
Action: Sees Pro tier: 25 users, $5k revenue, $3.8k cost, 23.6% margin ⚠️
Emotion: 🧐 Analytical (Pro margin too low)
Pain Point: None
System: Highlights Pro row in yellow (< 30% margin)

↓

Step 7: Check Provider Costs
Action: Clicks "Provider Costs" tab
Emotion: 🕵️ Investigating (what's expensive?)
Pain Point: None
System: Shows cost breakdown by provider

↓

Step 8: Root Cause
Action: Sees Google TTS (Pro only): $1k/mo, 20% of total costs
Emotion: 💡 Insightful (found it!)
Pain Point: None
System: Sorts by cost (descending)

↓

Step 9: Decision
Action: Decides to reduce Pro quota from 10hr → 8hr
Emotion: 😐 Confident (data-driven decision)
Pain Point: ⚠️ No impact preview (will this reach 30% margin?)
Opportunity: Add "If quota reduced to 8hr, margin = 28.5%"
System: Waits for admin action

↓

Step 10: Make Change
Action: Navigates to /admin/tiers, edits Pro quota, saves
Emotion: 😊 Satisfied
Pain Point: None
System: Updates database, logs audit entry

↓

Step 11: Export Report
Action: Clicks "Export CSV", downloads financial data
Emotion: 😊 Productive
Pain Point: None
System: Generates CSV, downloads instantly

```

### Summary

**Total Time:** 15 minutes
**Emotion Trend:** Routine → Analytical → Focused → Satisfied → Curious → Analytical → Investigating → Insightful → Confident → Satisfied → Productive
**Decision Quality:** High (data-driven, clear root cause)

**Critical Needs:**
1. Clear KPIs (revenue, costs, margin) ✓
2. Date range filtering ✓
3. Drill-down capability ✓
4. Profitability visibility ✓
5. Provider cost breakdown ✓
6. Export functionality ✓

**Pain Points:**
1. Chart reload slow (3s) - Minor
2. No impact preview for quota changes - Moderate

**Opportunities:**
1. Pre-cache common date ranges (-2s load time)
2. Add impact simulator: "If quota = 8hr, margin = X%" (+confidence)
3. Add alerts: Email when margin <30% (proactive)
4. Add forecasting: "At current rate, reach $15k revenue by Dec"

---

## Journey 4: iOS User Creates Room → Web Guest Joins

**Persona:** Lisa (iOS) + Tom (Web Guest)
**Goal:** Quick translation test between iOS and Web
**Context:** Cross-platform validation

### Journey Map

```
Step 1: iOS Room Creation
Action: Lisa opens iOS app, taps "Create Room"
Emotion: 😊 Confident
Pain Point: None
System: Room created: "room-xyz789"

↓

Step 2: Select Language
Action: Lisa selects "Polish" from language picker
Emotion: 😊 Easy
Pain Point: None
System: Sets source_lang = "pl"

↓

Step 3: Show QR Code
Action: Lisa taps "Invite", QR code appears full-screen
Emotion: 😊 Satisfied
Pain Point: None
System: Generates QR code with room link

↓

Step 4: Tom Scans QR
Action: Tom opens iPhone camera, scans QR code from Lisa's screen
Emotion: 🤔 Curious (will this work?)
Pain Point: ⚠️ QR code scan sometimes fails (lighting)
Opportunity: Add brightness adjustment hint
System: Camera detects QR, opens Safari

↓

Step 5: Web Join Page
Action: Safari opens: livetranslator.com/join?code=xyz789
Emotion: 😊 Intrigued
Pain Point: None
System: Shows join page with room name

↓

Step 6: Enter Name
Action: Tom enters name "Tom", clicks "Join Room"
Emotion: 😊 Excited
Pain Point: None
System: Creates guest session

↓

Step 7: Tom Joins
Action: Tom sees "Connected with Lisa"
Emotion: 😊 Relieved
Pain Point: None
System: WebSocket connected, presence_snapshot sent

↓

Step 8: Lisa Sees Notification
Action: Lisa sees toast: "🇬🇧 Tom joined with English"
Emotion: 😊 Satisfied
Pain Point: None
System: user_joined event broadcast

↓

Step 9: Lisa Speaks (iOS)
Action: Lisa speaks in Polish: "Cześć, jak się masz?"
Emotion: 😊 Confident
Pain Point: None
System: Apple STT (on-device) → transcript_direct

↓

Step 10: Tom Sees Translation
Action: Tom sees English: "Hi, how are you?"
Emotion: 😍 Amazed!
Pain Point: ⚠️ 2s delay (expected 1s)
Opportunity: Optimize MT routing
System: DeepL translation → WebSocket broadcast

↓

Step 11: Tom Speaks (Web)
Action: Tom speaks in English: "I'm good, thanks!"
Emotion: 😊 Engaged
Pain Point: None
System: Speechmatics STT (streaming) → audio_events

↓

Step 12: Lisa Sees Translation
Action: Lisa sees Polish: "Mam się dobrze, dzięki!"
Emotion: 😊 Satisfied
Pain Point: None
System: DeepL translation → WebSocket broadcast

↓

Step 13: Lisa Hears TTS
Action: Lisa's iPhone speaks: "Mam się dobrze, dzięki!"
Emotion: 😊 Delighted
Pain Point: ⚠️ TTS voice robotic (Apple AVSpeechSynthesizer)
Opportunity: Offer premium voices (Pro tier)
System: Apple TTS plays audio

↓

Step 14: Success!
Action: 5-minute conversation completes
Emotion: 😊 Successful
Pain Point: None
System: Quota deducted correctly (Lisa: 5 min, Tom: uses Lisa's quota)

```

### Summary

**Total Time:** 8 minutes (creation → conversation end)
**Emotion Trend:** Confident → Easy → Satisfied → Curious → Intrigued → Excited → Relieved → Satisfied → Confident → Amazed → Engaged → Satisfied → Delighted → Successful
**Cross-Platform Success:** 95% (minor delay and TTS quality issues)

**Critical Validations:**
1. iOS room creation ✓
2. QR code invite ✓
3. Web guest join (no signup) ✓
4. iOS Apple STT → Web translation ✓
5. Web Speechmatics STT → iOS translation ✓
6. iOS TTS playback ✓
7. Quota pooling (guest uses admin) ✓

**Pain Points:**
1. QR scan fails in poor lighting (minor)
2. 2s translation delay (expected 1s) - Minor
3. TTS voice robotic (Apple limitation) - Minor

**Opportunities:**
1. QR scan hints: "Adjust screen brightness"
2. MT routing optimization (-0.5s latency)
3. Premium TTS voices (Pro feature)

---

## Journey 5: Pro User Multi-Speaker + Server TTS

**Persona:** Rachel, 40, Conference Organizer
**Goal:** Host 5-person international panel with premium features
**Context:** Pro tier user, needs best quality

### Journey Map

```
Step 1: Room Setup
Action: Rachel creates room "Panel Discussion"
Emotion: 😊 Confident (Pro tier = best features)
Pain Point: None
System: Room tier = 'pro'

↓

Step 2: Enable Pro Features
Action: Rachel enables:
  [x] Multi-speaker diarization
  [x] Server-side TTS (Google TTS)
  [x] Recording
Emotion: 😊 Excited (using premium features)
Pain Point: None
System: Saves room settings

↓

Step 3: Invite Panelists
Action: Rachel sends QR codes to 4 panelists via email
Emotion: 😊 Organized
Pain Point: None
System: Generates invite links

↓

Step 4: Panelists Join
Action: 4 panelists join from different countries:
  - John (USA, English, Free tier)
  - Maria (Spain, Spanish, Plus tier)
  - Ahmed (Egypt, Arabic, Pro tier)
  - Wei (China, Chinese, Free tier)
Emotion: 😊 Satisfied (everyone connected)
Pain Point: ⚠️ Chinese language not in list (unexpected)
Opportunity: Add more Asian languages
System: All participants connected

↓

Step 5: Rachel Speaks (English)
Action: "Welcome everyone to the panel discussion"
Emotion: 😊 Confident
Pain Point: None
System: Speechmatics STT (diarization: speaker_1)

↓

Step 6: Real-Time Translation
Action: All panelists see translations simultaneously:
  - Maria sees: "Bienvenidos a todos al panel de discusión"
  - Ahmed sees: "مرحبا بالجميع في النقاش"
  - Wei sees: "欢迎大家参加小组讨论"
Emotion: 😊 Impressed
Pain Point: None
System: MT routing: DeepL (Spanish), OpenAI (Arabic), Google (Chinese)

↓

Step 7: Server TTS Playback
Action: Maria, Ahmed, Wei hear translations in their language (Google TTS)
Emotion: 😍 Delighted (premium quality voice)
Pain Point: None
System: Google TTS generates audio, plays via WebSocket

↓

Step 8: Multi-Speaker Diarization
Action: John speaks: "Thank you for having me"
Emotion: 😊 Engaged
Pain Point: None
System: Speechmatics diarization detects speaker_2 (not speaker_1)

↓

Step 9: Speaker Labels
Action: Chat shows:
  - Rachel (speaker_1): "Welcome everyone..."
  - John (speaker_2): "Thank you for having me"
Emotion: 😊 Clear (easy to follow)
Pain Point: None
System: Speaker IDs mapped to display names

↓

Step 10: Quota Pooling
Action: John (Free tier, exhausted) continues speaking
Emotion: 😰 Concerned (will I be cut off?)
Pain Point: ⚠️ No visible quota indicator for guests
Opportunity: Show quota status in guest UI
System: Falls back to Rachel's Pro quota (5 hours available)

↓

Step 11: Rachel Notified
Action: Rachel sees: "John using your quota (2 min)"
Emotion: 😐 Informed (expected)
Pain Point: None
System: quota_fallback message sent

↓

Step 12: Panel Ends
Action: 90-minute panel discussion completes
Emotion: 😊 Successful
Pain Point: None
System: Quota usage recorded

↓

Step 13: Export & Review
Action: Rachel exports conversation as PDF with speaker labels
Emotion: 😊 Satisfied
Pain Point: None
System: Generates PDF with timestamps, speakers, translations

↓

Step 14: Cost Review
Action: Rachel views room costs:
  - STT (Speechmatics): $4.50
  - MT (DeepL + OpenAI + Google): $8.00
  - TTS (Google TTS): $3.50
  - Total: $16.00
Emotion: 😊 Acceptable (within budget)
Pain Point: None
System: Shows detailed cost breakdown

```

### Summary

**Total Time:** 100 minutes (setup + 90 min panel)
**Emotion Trend:** Confident → Excited → Organized → Satisfied → Confident → Impressed → Delighted → Engaged → Clear → Concerned → Informed → Successful → Satisfied → Acceptable
**Pro Feature Validation:** 100% (all features worked)

**Critical Validations:**
1. Multi-speaker diarization ✓
2. Server-side TTS (Google TTS) ✓
3. Quota pooling (Free/Plus → Pro fallback) ✓
4. 5-speaker room handling ✓
5. 4 language translations simultaneously ✓
6. Export with speaker labels ✓
7. Detailed cost tracking ✓

**Pain Points:**
1. Chinese language not in list (minor)
2. No quota indicator for guests (moderate)

**Opportunities:**
1. Add more Asian languages (Japanese, Korean, Vietnamese)
2. Guest quota visibility in UI
3. Real-time cost tracker (show running total during meeting)

---

## Summary Insights

### Conversion Funnel Analysis

| Journey Stage | Drop-off Rate | Main Friction | Fix Impact |
|---------------|---------------|---------------|------------|
| Landing → Signup | 40% | Too many fields | +10% conversion |
| Signup → First Room | 15% | QR scan issues | +8% conversion |
| First Room → Success | 10% | Audio permission | +5% conversion |
| Free → Paid | 85% | Unclear value | +20% conversion |

### Emotional Patterns

**Positive emotions:** Confident, Satisfied, Delighted, Impressed (70% of journey)
**Neutral emotions:** Curious, Analytical, Focused (20% of journey)
**Negative emotions:** Anxious, Worried, Hesitant (10% of journey)

**Emotional peaks:**
1. First successful translation (😍 Delighted)
2. Multi-language TTS playback (😍 Amazed)
3. Speaker diarization working (😊 Impressed)

**Emotional valleys:**
1. Too many signup fields (😐 Hesitant)
2. QR code scan fails (😰 Anxious)
3. Card form friction (😰 Hesitant)

### Priority Improvements

| Improvement | Impact | Effort | Priority |
|-------------|--------|--------|----------|
| Reduce signup fields | High | Low | P0 |
| Add usage examples to pricing | High | Low | P0 |
| QR scan hints | Medium | Low | P1 |
| Apple Pay / Google Pay | High | Medium | P1 |
| Impact simulator (admin) | Medium | Medium | P1 |
| Guest quota indicator | Low | Low | P2 |

---

**Last Updated:** 2025-11-03
**Related Documents:** `user-stories.md`, `use-cases.md`

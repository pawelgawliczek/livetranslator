# LiveTranslator - TODO Roadmap

**Last Updated:** 2025-10-21

---

## 🎯 Vision: Transform into Full SaaS Product

LiveTranslator will evolve from a proof-of-concept into a production-ready SaaS platform with:
- **Smart multi-language matrix** - No source/target pairs, just "what language do I speak?"
- **Easy room sharing** - QR codes, invite links, anonymous join
- **Tiered subscriptions** - Free, Plus ($9.99/mo), Pro ($29.99/mo)
- **Video chat with subtitles** - WebRTC peer-to-peer video (Pro)
- **AI-powered features** - Summaries, action items, sentiment analysis (Pro)

---

## 📊 Priority Levels

- 🔥 **HIGH** - Critical for MVP/SaaS launch
- 📊 **MEDIUM** - Important but can be deferred
- 🎨 **NICE-TO-HAVE** - Future enhancements

---

## 🚀 Phase 0: STT/MT Provider Testing & Admin Controls (TOP PRIORITY)

### 🔥 0.1 Admin User & Database Setup

**Status:** Not Started
**Priority:** CRITICAL
**Estimated Time:** 30 minutes

**📋 Current State Review:**
- ✅ `rooms` table already has `is_public`, `requires_login`, `max_participants` (from migration 001)
- ❌ `users` table does NOT have `is_admin` field yet
- ❌ `rooms` table does NOT have STT provider override fields yet
- ✅ `room_costs` table already has `pipeline`, `mode` fields for tracking different providers
- ✅ Current STT modes: LT_STT_PARTIAL_MODE supports "local" or "openai_chunked"

**Tasks:**
- [ ] Create migration `005_add_admin_and_stt_settings.sql` (combines admin + STT settings)
- [ ] Run migration on database
- [ ] Update `api/models.py` - Add `is_admin` to User, `stt_*_provider` to Room, create SystemSettings model
- [ ] Update `api/auth.py` - Add `require_admin()` dependency
- [ ] Test admin check works

**Migration SQL:**
```sql
-- File: migrations/005_add_admin_and_stt_settings.sql

-- Add is_admin to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE NOT NULL;

-- Add STT provider overrides to rooms table (NULL = use global default)
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS stt_partial_provider VARCHAR(50) DEFAULT NULL;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS stt_final_provider VARCHAR(50) DEFAULT NULL;

-- Create system_settings table for global configuration
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Insert default STT settings
INSERT INTO system_settings (key, value) VALUES
    ('stt_partial_provider_default', 'openai_chunked'),
    ('stt_final_provider_default', 'openai')
ON CONFLICT (key) DO NOTHING;

-- Grant admin to YOU@example.com
UPDATE users SET is_admin = TRUE WHERE email = 'YOU@example.com';
```

**Files to Create:**
- `migrations/005_add_admin_and_stt_settings.sql`

**Files to Modify:**
- `api/models.py` - Add fields to User/Room models, create SystemSettings model
- `api/auth.py` - Add `require_admin()` dependency

---

### 🔥 0.2 Admin Settings UI

**Status:** Not Started
**Priority:** CRITICAL
**Estimated Time:** 1-2 days

**📋 Current Frontend Structure:**
- Routes defined in `web/src/main.jsx`: /, /login, /signup, /join/:code, /rooms, /room/:id, /profile
- No shared navigation component yet (each page has its own header)
- Need to add `/admin` route and navigation link

**Tasks:**
- [ ] Add `/admin` route to `main.jsx`
- [ ] Create `AdminSettingsPage.jsx` with tabs:
  - **STT Settings** - Choose provider for partials/finals
  - **MT Settings** - List available translation providers
  - **Global Defaults** - Set default models for new rooms
- [ ] Add "Admin" navigation link (visible only if `user.is_admin`)
  - Add to RoomsPage header
  - Add to RoomPage header
  - Add to ProfilePage header
- [ ] Create backend API endpoints for admin settings
- [ ] Fetch user profile to check `is_admin` status

**API Endpoints:**
```
GET  /api/admin/settings/stt          - Get current STT configuration
POST /api/admin/settings/stt          - Update STT defaults
GET  /api/admin/settings/mt           - Get current MT configuration
POST /api/admin/settings/mt           - Update MT defaults
GET  /api/admin/providers             - List all available providers
```

**Files to Create/Modify:**
- `web/src/pages/AdminSettingsPage.jsx` (new)
- `web/src/components/AdminMenu.jsx` (new)
- `api/routers/admin_api.py` (new)
- `api/models.py` - Add SystemSettings model

---

### 🔥 0.3 Per-Room STT Override (Admin Only)

**Status:** Not Started
**Priority:** CRITICAL
**Estimated Time:** 1 day

**Tasks:**
- [ ] Add STT settings panel to RoomPage (visible only to room owner or admin)
- [ ] Allow admin to override STT provider for specific room:
  - Partials: OpenAI / Deepgram / Local
  - Finals: OpenAI / ElevenLabs / None
- [ ] Store room-specific settings in `rooms` table
- [ ] Update STT router to check room settings before processing

**Database Changes:**
```sql
ALTER TABLE rooms ADD COLUMN stt_partial_provider VARCHAR(50) DEFAULT NULL;
ALTER TABLE rooms ADD COLUMN stt_final_provider VARCHAR(50) DEFAULT NULL;
-- NULL means use global default
```

**Files to Create/Modify:**
- `web/src/components/RoomSTTSettings.jsx` (new)
- `web/src/pages/RoomPage.jsx` - Add settings panel
- `api/routers/stt/router.py` - Check room settings
- `api/rooms_api.py` - Add endpoints to update room STT config

---

### 🔥 0.4 Implement Deepgram Streaming for Partials

**Status:** Not Started
**Priority:** CRITICAL
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Install Deepgram SDK: `pip install deepgram-sdk`
- [ ] Create `api/routers/stt/deepgram_backend.py`
- [ ] Implement WebSocket streaming handler
- [ ] Add speaker diarization support (real-time)
- [ ] Update router to support Deepgram mode: `LT_STT_PARTIAL_MODE=deepgram`
- [ ] Add Deepgram API key to environment variables
- [ ] Keep OpenAI as fallback option

**Environment Variables:**
```bash
DEEPGRAM_API_KEY=your_key_here
LT_STT_PARTIAL_MODE=deepgram  # or openai_chunked or local
```

**Files to Create/Modify:**
- `api/routers/stt/deepgram_backend.py` (new)
- `api/routers/stt/router.py` - Add Deepgram integration
- `workers/stt/requirements.txt` - Add deepgram-sdk
- `docker-compose.yml` - Add DEEPGRAM_API_KEY

**Testing Checklist:**
- [ ] Test single speaker transcription
- [ ] Test real-time speaker diarization (2+ speakers)
- [ ] Test language auto-detection
- [ ] Compare latency: OpenAI vs Deepgram
- [ ] Compare accuracy: OpenAI vs Deepgram
- [ ] Test interim results (partials)
- [ ] Test final results with speaker labels
- [ ] **Update cost tracking system** - Add Deepgram pricing ($0.0065/min streaming)
- [ ] Verify cost events published correctly for Deepgram usage

---

### 🔥 0.5 Implement ElevenLabs Batch for Finals

**Status:** Not Started
**Priority:** CRITICAL
**Estimated Time:** 1-2 days

**Tasks:**
- [ ] Install httpx (already installed)
- [ ] Create `api/routers/stt/elevenlabs_backend.py`
- [ ] Implement batch transcription API call
- [ ] Add speaker diarization parsing (up to 32 speakers)
- [ ] Add audio event detection parsing (laughter, music, etc.)
- [ ] Update `audio_end` handler to support ElevenLabs
- [ ] Add ElevenLabs API key to environment variables
- [ ] Keep OpenAI as fallback option

**Environment Variables:**
```bash
ELEVENLABS_API_KEY=your_key_here
LT_STT_FINAL_MODE=elevenlabs  # or openai or none
```

**Files to Create/Modify:**
- `api/routers/stt/elevenlabs_backend.py` (new)
- `api/routers/stt/router.py` - Add ElevenLabs integration in audio_end handler
- `docker-compose.yml` - Add ELEVENLABS_API_KEY

**Testing Checklist:**
- [ ] Test batch transcription quality vs OpenAI
- [ ] Test speaker diarization (2-5 speakers)
- [ ] Test audio event detection (background noise, music, laughter)
- [ ] Test word-level timestamps
- [ ] Compare accuracy: OpenAI vs ElevenLabs
- [ ] **Update cost tracking system** - Add ElevenLabs pricing ($0.40/hour)
- [ ] Verify cost events published correctly for ElevenLabs usage
- [ ] Test cost calculation with diarization enabled (same price)

---

### 🔥 0.6 Multi-Speaker Single-Room Scenario

**Status:** Not Started
**Priority:** CRITICAL
**Estimated Time:** 2-3 days

**📋 Current State:**
- ✅ `segments` table already has `speaker_id VARCHAR(64)` field
- Currently `speaker_id` stores device/client identifier (e.g., "web", "mobile")
- Need to use STT provider's speaker labels instead (e.g., "1", "2", "3")

**💡 NEW FEATURE: "Quick Multi-User Room" with Speaker Calibration**

This feature allows users to:
1. Create a room and enter "Speaker Detection" mode
2. Everyone speaks for 10-30 seconds
3. System detects unique speakers via STT diarization
4. Admin assigns names + languages to each detected speaker
5. Start session with proper speaker identification

**User Flow:**
```
[Create Room] → [Detect Speakers] → [Configure Speakers] → [Start Session]
                 (10-30s audio)      (name + language)      (live chat)
```

**Tasks:**

**A. Speaker Detection/Calibration Phase:**
- [ ] Add "Quick Multi-User Room" option to room creation
- [ ] Create `SpeakerCalibrationPage.jsx`:
  - Recording UI with countdown timer (10-30 seconds)
  - "Everyone please speak now" instructions
  - Visual indicator of audio activity
- [ ] Send calibration audio to STT with diarization enabled
- [ ] Parse speaker count and sample text per speaker
- [ ] Create `SpeakerConfigurationPage.jsx`:
  - Show detected speakers with sample text
  - Input fields for name + language per speaker
  - Color preview for each speaker
  - "Start Room" button

**B. Active Session with Configured Speakers:**
- [ ] Update frontend to show speaker labels (with custom names)
- [ ] Add speaker color coding in chat UI (per configured colors)
- [ ] Display speaker language badges
- [ ] Test Deepgram real-time speaker diarization
- [ ] Test ElevenLabs batch speaker diarization
- [ ] Handle speaker switching mid-sentence

**Frontend Changes:**
- [ ] Create `SpeakerCalibrationPage.jsx` (new) - Detection phase
- [ ] Create `SpeakerConfigurationPage.jsx` (new) - Setup phase
- [ ] Update `MessageBubble.jsx` to show configured speaker names
- [ ] Add speaker color palette (8 distinct colors)
- [ ] Add speaker legend/list in room sidebar showing names + languages
- [ ] Add real-time translation per speaker's target language

**Backend Changes:**
- [ ] Update `speaker_id` field usage: change from device ID to STT provider's speaker ID
- [ ] Update WebSocket events to include speaker_id from STT provider
- [ ] Create speaker mapping table:
  ```sql
  CREATE TABLE room_speakers (
      id SERIAL PRIMARY KEY,
      room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE,
      speaker_id INTEGER NOT NULL,  -- From STT provider (1, 2, 3...)
      display_name VARCHAR(120) NOT NULL,  -- Custom name from calibration
      target_language VARCHAR(10) NOT NULL,  -- Language per speaker (en, pl, ar...)
      color VARCHAR(7) NOT NULL,  -- Hex color code (#FF5733)
      sample_text TEXT,  -- Sample from calibration phase
      created_at TIMESTAMP DEFAULT NOW() NOT NULL,
      UNIQUE(room_id, speaker_id)  -- One mapping per speaker per room
  );

  CREATE INDEX idx_room_speakers_room_id ON room_speakers(room_id);
  ```
- [ ] Add API endpoints:
  ```
  POST /api/rooms/{room_id}/speakers/detect   - Send calibration audio, get speaker list
  POST /api/rooms/{room_id}/speakers/configure - Save speaker mappings
  GET  /api/rooms/{room_id}/speakers           - Get configured speakers
  PUT  /api/rooms/{room_id}/speakers/{id}      - Update speaker name/language
  ```
- [ ] Update STT router to use speaker mappings for display
- [ ] Update MT router to translate per speaker's target language

**Testing Scenarios:**
- [ ] Calibration phase: 2 speakers speaking simultaneously
- [ ] Calibration phase: 3-5 speakers in group
- [ ] Calibration phase: Different languages (en, pl, ar)
- [ ] Active session: Speaker switching (turn-taking)
- [ ] Active session: Overlapping speech detection
- [ ] Active session: Background speaker vs foreground speaker
- [ ] Active session: Translation to each speaker's target language

**Files to Create/Modify:**
- `migrations/006_add_room_speakers.sql` (new) - Speaker mapping table
- `web/src/pages/SpeakerCalibrationPage.jsx` (new) - Detection phase
- `web/src/pages/SpeakerConfigurationPage.jsx` (new) - Configuration UI
- `web/src/components/MessageBubble.jsx` - Add speaker name + color
- `web/src/components/SpeakerLegend.jsx` (new) - Sidebar speaker list
- `web/src/pages/RoomPage.jsx` - Integrate speaker info
- `web/src/pages/RoomsPage.jsx` - Add "Quick Multi-User Room" option
- `api/models.py` - Add RoomSpeaker model
- `api/routers/speakers_api.py` (new) - Speaker detection/config endpoints
- `api/routers/stt/router.py` - Use speaker mappings
- `api/routers/mt/router.py` - Translate per speaker's language

---

### 🔥 0.7 Comprehensive Testing & Documentation

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 1-2 days

**Tasks:**
- [ ] Create testing matrix spreadsheet
- [ ] Test all provider combinations:
  - Partials: OpenAI + Finals: OpenAI (baseline)
  - Partials: Deepgram + Finals: OpenAI
  - Partials: Deepgram + Finals: ElevenLabs
  - Partials: OpenAI + Finals: ElevenLabs
- [ ] Document accuracy, latency, cost for each combination
- [ ] Test edge cases:
  - Very noisy environment
  - Multiple languages in same session
  - Silent periods (VAD behavior)
  - Very fast speech
  - Accented speech
- [ ] Create admin documentation for provider selection
- [ ] Update DOCUMENTATION.md with new architecture

**Testing Metrics to Track:**
| Provider Combo | Latency (ms) | WER (%) | Cost/hour | Speaker Accuracy | Notes |
|----------------|--------------|---------|-----------|------------------|-------|
| OpenAI + OpenAI | ? | ? | $0.40 | N/A | Baseline |
| Deepgram + OpenAI | ? | ? | $0.39 | ? | ? |
| Deepgram + ElevenLabs | ? | ? | $0.79 | ? | ? |
| OpenAI + ElevenLabs | ? | ? | $0.80 | ? | ? |

**Files to Create/Modify:**
- `TESTING_RESULTS.md` (new)
- `DOCUMENTATION.md` - Update STT architecture section
- `ADMIN_GUIDE.md` (new)
- `api/services/cost_tracker_service.py` - Add Deepgram/ElevenLabs pricing
- `api/cost_tracker.py` - Update cost calculation logic

**Cost Tracking Updates Needed:**
- [ ] Add Deepgram pricing model: $0.0065/min streaming, $0.0043/min batch
- [ ] Add ElevenLabs pricing model: $0.40/hour ($0.00667/min)
- [ ] Update cost_tracker to handle multiple STT providers
- [ ] Add provider field to cost_events: `{"pipeline": "stt", "mode": "deepgram", ...}`
- [ ] Update cost calculation queries to aggregate by provider
- [ ] Update frontend cost display to show breakdown by provider
- [ ] Test cost tracking accuracy with mixed provider usage

---

## Phase 1: Core Invitation & Multi-Language Matrix (2-3 weeks)

### 🔥 1.1 Database Schema Changes

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Add `invite_code` field to `rooms` table (unique, shareable)
- [ ] Add `is_public`, `requires_login`, `max_participants` to `rooms`
- [ ] Add `tier_required` field to `rooms` (free/plus/pro)
- [ ] Create `room_participants` table:
  ```sql
  CREATE TABLE room_participants (
      id SERIAL PRIMARY KEY,
      room_id INTEGER REFERENCES rooms(id),
      user_id INTEGER REFERENCES users(id) NULL,  -- NULL for anonymous
      session_id VARCHAR(64),                     -- For anonymous users
      display_name VARCHAR(120),
      spoken_language VARCHAR(10),                -- Just ONE language
      joined_at TIMESTAMP,
      left_at TIMESTAMP,
      is_active BOOLEAN DEFAULT TRUE
  );
  ```
- [ ] Add indexes for performance
- [ ] Write migration script
- [ ] Test migration on dev database

**Files to Create/Modify:**
- `api/models.py` - Add RoomParticipant model
- `migrations/001_add_invite_system.sql` - Migration script
- `api/db.py` - Update migration logic

---

### 🔥 1.2 QR Code Generation & Invite Links

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 1-2 days

**Tasks:**
- [ ] Install `qrcode` Python library
- [ ] Create `api/utils/qr.py` - QR code generation
- [ ] Add `/api/rooms/{room_id}/invite` endpoint - Generate QR code
- [ ] Add `/api/rooms/{room_id}/invite/regenerate` - Regenerate invite code
- [ ] Store QR code as base64 in response (or S3 for production)
- [ ] Update `RoomsPage.jsx` to show QR code after creating room
- [ ] Add "Copy invite link" button
- [ ] Add "Download QR code" button

**Files to Create/Modify:**
- `api/utils/qr.py` (new)
- `api/events.py` or create `api/invites.py` (new router)
- `web/src/pages/RoomsPage.jsx`
- `web/src/components/InviteModal.jsx` (new)

**API Endpoints:**
```
GET  /api/rooms/{room_id}/invite       - Get invite info + QR code
POST /api/rooms/{room_id}/invite       - Generate new invite code
```

---

### 🔥 1.3 Anonymous Join Flow

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Create `/join/{invite_code}` route
- [ ] Create `JoinPage.jsx` component:
  - Language selection dropdown
  - Display name input
  - "Join as guest" vs "Sign in" toggle
- [ ] Backend: `GET /api/join/{invite_code}` - Validate invite, return room info
- [ ] Backend: `POST /api/join/{invite_code}` - Join room (create session for anonymous)
- [ ] Generate session_id for anonymous users (UUID)
- [ ] Store session in room_participants table
- [ ] Update WebSocket to accept anonymous users (session_id in query param)
- [ ] Update RoomPage to handle anonymous users

**Files to Create/Modify:**
- `web/src/pages/JoinPage.jsx` (new)
- `web/src/main.jsx` - Add route
- `api/join_api.py` (new router)
- `api/main.py` - Include router
- `api/ws_manager.py` - Handle anonymous users

**API Endpoints:**
```
GET  /api/join/{invite_code}                  - Validate & get room info
POST /api/join/{invite_code}                  - Join room (anonymous or logged in)
  Body: { display_name, spoken_language, session_id? }
```

---

### 🔥 1.4 Multi-Language Translation Matrix

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 3-4 days

**Tasks:**
- [ ] Create `api/translation_matrix.py` - Matrix manager
  - `add_participant(user_id, language)`
  - `remove_participant(user_id)`
  - `get_target_languages(speaker_id)` - Languages to translate TO
  - `get_translation_pairs(speaker_id)` - (src, tgt) pairs
- [ ] Store matrix in Redis: `room:{room_id}:participants`
- [ ] Update `ws_manager.py`:
  - Track participant languages on join
  - Remove participant on disconnect
  - Broadcast matrix changes to all clients
- [ ] Update `mt_router.py`:
  - Fetch translation matrix from Redis
  - Generate N translations (one per target language)
  - Publish each translation separately
- [ ] Update `RoomPage.jsx`:
  - Show participant list with languages
  - Display only translations for user's language
  - Show original text + translation for each message
- [ ] Update message format:
  ```json
  {
    "type": "stt_final",
    "segment_id": 123,
    "speaker": "user@example.com",
    "speaker_lang": "en",
    "text": "Hello world"
  }
  ```

**Files to Create/Modify:**
- `api/translation_matrix.py` (new)
- `api/ws_manager.py`
- `api/routers/mt/router.py`
- `web/src/pages/RoomPage.jsx`
- `web/src/components/ParticipantList.jsx` (new)

---

### 🔥 1.5 UI Updates for Multi-User

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Show participant list in room (with flags/languages)
- [ ] Update message bubbles:
  - Show speaker name/avatar
  - Show original text + translation
  - Different colors for different speakers
- [ ] Add language selection per user (not per room)
- [ ] Remove source/target language pickers (only "My Language")
- [ ] Add "Invite" button in room header
- [ ] Show connection status for each participant

**Files to Create/Modify:**
- `web/src/pages/RoomPage.jsx`
- `web/src/components/MessageBubble.jsx` (new)
- `web/src/components/ParticipantList.jsx` (new)
- `web/src/styles/room.css` (new)

---

## Phase 2: Subscription System (2-3 weeks)

### 🔥 2.1 Database Schema for Subscriptions

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 1-2 days

**Tasks:**
- [ ] Add subscription fields to `users` table:
  ```sql
  ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free';
  ALTER TABLE users ADD COLUMN subscription_expires TIMESTAMP NULL;
  ALTER TABLE users ADD COLUMN stt_minutes_used INTEGER DEFAULT 0;
  ALTER TABLE users ADD COLUMN stt_minutes_limit INTEGER DEFAULT 30;
  ALTER TABLE users ADD COLUMN mt_tokens_used INTEGER DEFAULT 0;
  ALTER TABLE users ADD COLUMN mt_tokens_limit INTEGER DEFAULT 100000;
  ALTER TABLE users ADD COLUMN usage_reset_date TIMESTAMP;
  ```
- [ ] Create `subscriptions` table (optional, for Stripe tracking):
  ```sql
  CREATE TABLE subscriptions (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id),
      stripe_subscription_id VARCHAR(255) UNIQUE,
      stripe_customer_id VARCHAR(255),
      tier VARCHAR(20),
      status VARCHAR(20),
      current_period_start TIMESTAMP,
      current_period_end TIMESTAMP,
      created_at TIMESTAMP DEFAULT NOW()
  );
  ```
- [ ] Write migration script
- [ ] Define tier limits in code (`api/tiers.py`)

**Files to Create/Modify:**
- `api/models.py`
- `api/tiers.py` (new) - TIER definitions
- `migrations/002_add_subscriptions.sql`

---

### 🔥 2.2 Stripe Integration

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 4-5 days

**Tasks:**
- [ ] Install Stripe Python SDK
- [ ] Create Stripe account & get API keys
- [ ] Create products in Stripe:
  - Plus: $9.99/month
  - Pro: $29.99/month
- [ ] Backend: `POST /api/subscribe/checkout` - Create Stripe checkout session
- [ ] Backend: `POST /webhooks/stripe` - Handle Stripe webhooks
  - `customer.subscription.created` - Upgrade user
  - `customer.subscription.updated` - Update subscription
  - `customer.subscription.deleted` - Downgrade to free
  - `invoice.payment_failed` - Handle failed payment
- [ ] Frontend: Subscription management page
  - Show current plan
  - "Upgrade" / "Manage Subscription" buttons
  - Redirect to Stripe checkout
- [ ] Test webhooks with Stripe CLI

**Files to Create/Modify:**
- `api/stripe_api.py` (new router)
- `api/stripe_webhooks.py` (new)
- `web/src/pages/SubscriptionPage.jsx` (new)
- `web/src/pages/CheckoutPage.jsx` (new)

**API Endpoints:**
```
POST /api/subscribe/checkout          - Create checkout session
GET  /api/subscribe/portal            - Stripe customer portal link
POST /webhooks/stripe                 - Stripe webhook handler
```

---

### 🔥 2.3 Usage Tracking & Quota Enforcement

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Create middleware: `api/middleware/quota_checker.py`
  - Check user's quota before STT/MT operations
  - Raise `QuotaExceededError` if over limit
- [ ] Update `stt_router.py`:
  - Track STT minutes used
  - Publish usage to `quota_events` channel
- [ ] Update `mt_router.py`:
  - Track MT tokens used
  - Publish usage to `quota_events` channel
- [ ] Create `quota_tracker` service:
  - Subscribe to `quota_events`
  - Update user usage in database
- [ ] Add monthly reset logic (cron job or on-demand)
- [ ] Frontend: Show usage stats in user dashboard
- [ ] Frontend: Show warning when approaching quota limit

**Files to Create/Modify:**
- `api/middleware/quota_checker.py` (new)
- `api/routers/stt/router.py`
- `api/routers/mt/router.py`
- `api/services/quota_tracker_service.py` (new)
- `web/src/pages/DashboardPage.jsx` (new)

---

### 📊 2.4 Persistence Toggle (Plus/Pro Only)

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 1 day

**Tasks:**
- [ ] Add `persistence_enabled` field to `rooms` table
- [ ] Update `persistence_service.py`:
  - Check room owner's subscription tier
  - Only persist if tier is Plus/Pro
  - Skip persistence for Free tier
- [ ] Update room creation UI:
  - Show "Save history" checkbox (disabled for Free)
  - Show upgrade prompt if user is on Free tier

**Files to Create/Modify:**
- `api/models.py`
- `api/services/persistence_service.py`
- `web/src/pages/RoomsPage.jsx`

---

## Phase 3: AI Features (Pro) (2-3 weeks)

### 📊 3.1 Conversation Summaries

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Create `api/ai_features.py` - AI utilities
- [ ] Implement `generate_summary(room_id)`:
  - Fetch all segments from room
  - Format conversation with speaker names
  - Call GPT-4o with summarization prompt
  - Return structured summary
- [ ] Backend: `GET /api/rooms/{room_id}/summary`
- [ ] Frontend: Add "Generate Summary" button in room history
- [ ] Show summary in modal or export

**Files to Create/Modify:**
- `api/ai_features.py` (new)
- `api/rooms_api.py` (new router)
- `web/src/pages/RoomHistoryPage.jsx` (new)
- `web/src/components/SummaryModal.jsx` (new)

**API Endpoints:**
```
GET /api/rooms/{room_id}/summary             - Generate AI summary
GET /api/rooms/{room_id}/action-items        - Extract action items
GET /api/rooms/{room_id}/topics              - Extract topics
```

---

### 📊 3.2 Action Items Extraction

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 1-2 days

**Tasks:**
- [ ] Implement `extract_action_items(room_id)` in `ai_features.py`
- [ ] Use GPT-4o to identify tasks/decisions
- [ ] Return structured list of action items
- [ ] Frontend: Display action items in room history

**Files to Create/Modify:**
- `api/ai_features.py`
- `web/src/components/ActionItemsList.jsx` (new)

---

### 🎨 3.3 Sentiment Analysis

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 2 days

**Tasks:**
- [ ] Implement `sentiment_analysis(room_id)` in `ai_features.py`
- [ ] Analyze tone, emotions, engagement
- [ ] Visualize sentiment over time
- [ ] Display in room analytics dashboard

**Files to Create/Modify:**
- `api/ai_features.py`
- `web/src/pages/RoomAnalyticsPage.jsx` (new)

---

## Phase 4: Video Chat (Pro) (3-4 weeks)

### 📊 4.1 WebRTC Setup

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 3-4 days

**Tasks:**
- [ ] Set up STUN server (use Google's free server)
- [ ] Set up TURN server (coturn or Twilio)
  - Required for NAT traversal
  - Configure on separate server
- [ ] Test WebRTC connectivity

**Infrastructure:**
- Install coturn on server
- Configure firewall rules for TURN

---

### 📊 4.2 WebRTC Signaling Server

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 3-4 days

**Tasks:**
- [ ] Add WebRTC signaling to WebSocket protocol:
  ```json
  {
    "type": "webrtc_signal",
    "to": "user_id",
    "payload": {
      "type": "offer|answer|ice_candidate",
      "sdp": "...",
      "candidate": "..."
    }
  }
  ```
- [ ] Update `ws_manager.py` to route WebRTC signals
- [ ] Create `web/src/services/webrtc.js` - WebRTC manager
  - Peer connection management
  - Offer/answer exchange
  - ICE candidate handling
  - Stream management

**Files to Create/Modify:**
- `api/ws_manager.py`
- `web/src/services/webrtc.js` (new)

---

### 📊 4.3 Video UI

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 3-4 days

**Tasks:**
- [ ] Create `VideoGrid.jsx` component - Grid layout for participants
- [ ] Create `VideoTile.jsx` component - Individual video stream
- [ ] Add "Start Video" button in room
- [ ] Request camera/microphone permissions
- [ ] Display local video preview
- [ ] Display remote video streams
- [ ] Add video controls (mute, camera off, etc.)

**Files to Create/Modify:**
- `web/src/components/VideoGrid.jsx` (new)
- `web/src/components/VideoTile.jsx` (new)
- `web/src/pages/RoomPage.jsx`

---

### 📊 4.4 Subtitles Overlay on Video

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 2 days

**Tasks:**
- [ ] Create `SubtitlesOverlay.jsx` component
- [ ] Position subtitles over video streams
- [ ] Show real-time translations
- [ ] Auto-hide after N seconds
- [ ] Style for readability (background, font size)

**Files to Create/Modify:**
- `web/src/components/SubtitlesOverlay.jsx` (new)
- `web/src/components/VideoTile.jsx`

---

## Phase 5: Export & Room Management (1-2 weeks)

### 🔥 5.1 Conversation Export

**Status:** Not Started
**Priority:** HIGH
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Backend: `GET /api/rooms/{room_id}/export?format={pdf|txt|json}`
- [ ] Implement PDF export (use ReportLab or WeasyPrint)
- [ ] Implement TXT export (plain text with timestamps)
- [ ] Implement JSON export (structured data)
- [ ] Frontend: Add "Export" button in room history
- [ ] Download file to user's device

**Files to Create/Modify:**
- `api/export_api.py` (new router)
- `api/utils/pdf_export.py` (new)
- `web/src/pages/RoomHistoryPage.jsx`

**API Endpoints:**
```
GET /api/rooms/{room_id}/export?format=pdf   - Export as PDF
GET /api/rooms/{room_id}/export?format=txt   - Export as TXT
GET /api/rooms/{room_id}/export?format=json  - Export as JSON
```

---

### 📊 5.2 Room Management

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 2-3 days

**Tasks:**
- [ ] Backend: `DELETE /api/rooms/{room_id}` - Delete room
- [ ] Backend: `PUT /api/rooms/{room_id}/archive` - Archive room
- [ ] Backend: `PUT /api/rooms/{room_id}` - Update room settings
- [ ] Frontend: Room settings modal
  - Public/Private toggle
  - Persistence toggle
  - Delete/Archive buttons
- [ ] Add "Archived" tab in rooms list

**Files to Create/Modify:**
- `api/events.py` or `api/rooms_api.py`
- `web/src/pages/RoomsPage.jsx`
- `web/src/components/RoomSettingsModal.jsx` (new)

---

### 📊 5.3 Search Through History

**Status:** Not Started
**Priority:** MEDIUM
**Estimated Time:** 2 days

**Tasks:**
- [ ] Add full-text search to `segments` table:
  ```sql
  CREATE INDEX idx_segments_text_fts ON segments USING gin(to_tsvector('english', text));
  ```
- [ ] Backend: `GET /api/rooms/{room_id}/search?q={query}`
- [ ] Frontend: Search input in room history
- [ ] Highlight search results

**Files to Create/Modify:**
- `api/history_api.py`
- `web/src/pages/RoomHistoryPage.jsx`

---

## Phase 6: Additional Features

### 🎨 6.1 Dark/Light Theme Toggle

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 1-2 days

**Tasks:**
- [ ] Add theme toggle in user settings
- [ ] Save preference in localStorage
- [ ] Create dark mode CSS variables
- [ ] Update all components to use theme variables

**Files to Create/Modify:**
- `web/src/main.jsx`
- `web/src/styles/theme.css` (new)
- All component files

---

### 🎨 6.2 More Languages

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 1 day

**Tasks:**
- [ ] Add language options:
  - Spanish (es)
  - French (fr)
  - German (de)
  - Italian (it)
  - Portuguese (pt)
  - Russian (ru)
  - Chinese (zh)
  - Japanese (ja)
- [ ] Update language picker UI
- [ ] Test translation quality

**Files to Create/Modify:**
- `web/src/pages/RoomPage.jsx`
- `api/routers/mt/router.py`

---

### 🎨 6.3 Custom Vocabulary/Glossary

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 3-4 days

**Tasks:**
- [ ] Create `glossary` table:
  ```sql
  CREATE TABLE glossary (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id),
      term VARCHAR(255),
      translation VARCHAR(255),
      source_lang VARCHAR(10),
      target_lang VARCHAR(10)
  );
  ```
- [ ] Backend: CRUD endpoints for glossary
- [ ] MT router: Apply glossary substitutions
- [ ] Frontend: Glossary management page

**Files to Create/Modify:**
- `api/models.py`
- `api/glossary_api.py` (new)
- `api/routers/mt/router.py`
- `web/src/pages/GlossaryPage.jsx` (new)

---

### 🎨 6.4 Speaker Colors/Avatars

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 2-3 hours

**Tasks:**
- [ ] Generate consistent color per speaker (hash email → color)
- [ ] Add avatar support (gravatar or initials)
- [ ] Update message bubbles with colors/avatars
- [ ] Add legend showing speaker colors

**Files to Create/Modify:**
- `web/src/utils/colors.js` (new)
- `web/src/components/MessageBubble.jsx`
- `web/src/components/ParticipantList.jsx`

---

### 🎨 6.5 Connection Status Indicator

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 1-2 hours

**Tasks:**
- [ ] Add WebSocket connection status indicator
- [ ] Show "Connected", "Connecting", "Disconnected" states
- [ ] Auto-reconnect on disconnect
- [ ] Show warning when connection is lost

**Files to Create/Modify:**
- `web/src/pages/RoomPage.jsx`
- `web/src/components/ConnectionStatus.jsx` (new)

---

### 🎨 6.6 Audio Playback

**Status:** Not Started
**Priority:** NICE-TO-HAVE
**Estimated Time:** 3-4 days

**Tasks:**
- [ ] Store audio chunks in database or S3
- [ ] Backend: `GET /api/segments/{segment_id}/audio` - Get audio file
- [ ] Frontend: Add play button next to each message
- [ ] Audio player with waveform visualization

**Files to Create/Modify:**
- `api/audio_storage.py` (new)
- `api/segments_api.py` (new)
- `web/src/components/AudioPlayer.jsx` (new)

---

## 📋 Quick Wins (Can be done anytime)

### ✅ Documentation
- [x] Create DOCUMENTATION.md
- [x] Create TODO.md
- [ ] Add API documentation (OpenAPI/Swagger)
- [ ] Add contribution guidelines
- [ ] Create user guides

### ✅ Developer Experience
- [ ] Add Docker development mode (hot reload)
- [ ] Add pre-commit hooks (linting, formatting)
- [ ] Set up CI/CD pipeline (GitHub Actions)
- [ ] Add automated tests (pytest, Jest)

### ✅ Performance
- [ ] Add caching for frequently accessed data
- [ ] Optimize database queries (add indexes)
- [ ] Implement rate limiting
- [ ] Add CDN for static assets

---

## 🏗️ Architecture Optimization (Thin Client vs Distributed)

**Last Discussed:** 2025-10-21

### Current Architecture (11 containers):
1. **postgres** - Database (essential)
2. **redis** - Message queue (essential)
3. **api** - Main FastAPI server (essential)
4. **web** - Nginx frontend (essential)
5. **stt_router** - Routes STT requests (~17MB RAM)
6. **stt_worker** - Local Whisper (~871MB RAM, unused with OpenAI STT)
7. **mt_router** - Routes MT requests (~36MB RAM)
8. **mt_worker** - Local translation (~188MB RAM)
9. **cost_tracker** - Tracks API costs (~17MB RAM)
10. **persistence** - Saves to DB (~33MB RAM)
11. **room_cleanup** - Cleans inactive rooms (~61MB RAM)

### Optimization Options:

#### **Option A: Aggressive Consolidation (Thin Client)**
**Target:** 11 → 5 containers (~1.2GB RAM saved)
- ✅ Merge **stt_router + mt_router + cost_tracker + persistence + room_cleanup** into **API**
- ✅ Remove **stt_worker** entirely (unused with OpenAI STT)
- ✅ Keep **mt_worker** for local fallback
- ✅ Result: postgres, redis, api, web, mt_worker

**Pros:**
- 70% less container overhead
- ~1.2GB RAM saved
- Faster in-process communication
- Simpler monitoring/deployment

**Cons:**
- Cannot scale routers independently
- Services coupled to API lifecycle
- Harder to migrate to distributed setup

---

#### **Option B: Hybrid (Recommended)**
**Target:** Keep microservices code, flexible deployment

**Strategy:**
1. Keep current modular code structure (routers as separate modules)
2. Create two docker-compose configurations:
   - `docker-compose.yml` - **Thin client mode** (5 containers)
   - `docker-compose.distributed.yml` - **Full microservices** (11 containers)
3. Switch between them based on hosting environment

**Implementation:**
```bash
# Thin client mode (current server)
docker compose up -d

# Distributed mode (better hosting / K8s)
docker compose -f docker-compose.distributed.yml up -d
```

**Pros:**
- ✅ Best performance now (thin client optimized)
- ✅ Easy migration later (just switch compose files)
- ✅ No code refactoring needed
- ✅ Future-proof for horizontal scaling
- ✅ Independent scaling when needed

**Cons:**
- Need to maintain two compose configurations
- Slightly more complex CI/CD

---

### Decision: **Pending User Input**

**Questions to answer:**
1. Do you plan to move to better hosting within 6 months?
2. Do you need to scale individual services independently?
3. Priority: Resource optimization NOW vs Future flexibility?

**Next Steps:**
- [ ] Decide on Option A (consolidate now) or Option B (hybrid approach)
- [ ] Create optimized docker-compose configuration(s)
- [ ] Test deployment in both modes
- [ ] Document deployment strategy
- [ ] Update CI/CD if needed

### ✅ Security
- [ ] Add rate limiting on authentication endpoints
- [ ] Implement CSRF protection
- [ ] Add security headers (Helmet.js equivalent)
- [ ] Audit dependencies for vulnerabilities

---

## 🚀 MVP Launch Checklist

Before launching to production:

- [ ] Phase 1 complete (Invitation & Matrix)
- [ ] Phase 2 complete (Subscriptions)
- [ ] Phase 5.1 complete (Export)
- [ ] Security audit
- [ ] Performance testing
- [ ] User acceptance testing
- [ ] Documentation complete
- [ ] Privacy policy & Terms of Service
- [ ] GDPR compliance (for EU users)
- [ ] Set up monitoring & alerts
- [ ] Backup & disaster recovery plan
- [ ] Customer support system

---

## 📊 Metrics to Track

Post-launch metrics:

- **Usage:**
  - Active users (daily/monthly)
  - Rooms created per day
  - Average session duration
  - Messages/translations per room

- **Performance:**
  - API response times
  - WebSocket latency
  - STT/MT processing times
  - Error rates

- **Business:**
  - Free vs Plus vs Pro users
  - Conversion rate (Free → Paid)
  - Monthly recurring revenue (MRR)
  - Churn rate
  - Customer acquisition cost (CAC)

- **Costs:**
  - OpenAI API costs per user
  - Infrastructure costs
  - Cost per user (by tier)

---

## 🔄 Ongoing Maintenance

Regular tasks:

- **Weekly:**
  - Monitor error logs
  - Check API costs vs revenue
  - Review user feedback

- **Monthly:**
  - Database backup verification
  - Security updates
  - Performance optimization

- **Quarterly:**
  - User surveys
  - Feature prioritization
  - Competitor analysis

---

## ✅ Done (Current Features)

### Core Features
- [x] OpenAI STT integration (Whisper API)
- [x] OpenAI MT integration (GPT-4o-mini)
- [x] Cost tracking per room with detailed breakdowns
- [x] Persistence of segments and translations
- [x] Chat history API endpoint with on-demand translation
- [x] WebSocket real-time delivery with processing indicators
- [x] Router architecture for multi-backend support
- [x] Database schema for rooms, segments, translations, costs
- [x] Google OAuth authentication
- [x] Email/password authentication
- [x] PWA support (Add to home screen)
- [x] Mobile-optimized UI with dynamic viewport
- [x] Auto-finalize partials on session end
- [x] Smart translation caching with deduplication

### STT Optimizations (October 2025)
- [x] **Conversation Context (Option 4)** - Track last 5 sentences for 15-20% better accuracy
- [x] **Parallel Processing (Option 5)** - Instant results + background quality refinement
- [x] **Smart Deduplication** - Word-level overlap detection prevents context duplicates
- [x] **Processing Indicators** - Visual feedback with spinning icons in 28 languages
- [x] **Incremental Transcription** - Only transcribe NEW audio (10-20x faster)
- [x] **Hallucination Filter** - Remove known Whisper watermarks
- [x] **Improved VAD** - Energy-based with 30s safety limit and washing machine noise handling
- [x] **Language Passing** - Source language hints to OpenAI for better accuracy
- [x] **Comprehensive Testing** - 100 unit tests (16 new STT tests)

### UI/UX Enhancements
- [x] Spinning processing indicators (⚙️) with CSS animations
- [x] Localized "Refining quality..." text in 28 languages
- [x] Room lifecycle management (30-minute admin absence timeout)
- [x] User profile, subscription, billing, and history pages
- [x] Invite system with QR codes and guest access

---

**For questions or suggestions, contact the development team.**

**Documentation:** See [DOCUMENTATION.md](./DOCUMENTATION.md)

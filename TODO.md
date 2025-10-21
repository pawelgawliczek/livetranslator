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

# LiveTranslator - Complete Technical Documentation

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [API Endpoints](#api-endpoints)
5. [WebSocket Protocol](#websocket-protocol)
6. [Message Flow](#message-flow)
7. [Services](#services)
8. [Frontend Structure](#frontend-structure)
9. [Development Guide](#development-guide)
10. [Deployment](#deployment)

---

## 📍 Project Overview

**LiveTranslator** is a real-time multi-language translation platform that enables live conversations between people speaking different languages.

### Key Features
- Real-time speech-to-text (STT) transcription using OpenAI Whisper
- Machine translation (MT) using local models (pl↔en) or OpenAI GPT-4o-mini
- WebSocket-based live updates
- Google OAuth + email/password authentication
- Smart translation caching
- Cost tracking per room
- Progressive Web App (PWA) support
- History with on-demand translation

### Technology Stack
- **Frontend**: React 18 + Vite + React Router
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7
- **Reverse Proxy**: Caddy 2
- **STT**: OpenAI Whisper API
- **MT**: Local translation workers + OpenAI GPT-4o-mini
- **Deployment**: Docker Compose

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                            User Browser                          │
│  ┌────────────────┐         ┌──────────────┐                   │
│  │   React App    │◄───────►│ VAD (Voice   │                   │
│  │   (Vite)       │         │  Activity    │                   │
│  └────────┬───────┘         │  Detection)  │                   │
│           │                 └──────────────┘                   │
└───────────┼──────────────────────────────────────────────────────┘
            │ HTTPS (WebSocket + REST)
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Caddy Reverse Proxy                      │
│  Routes:                                                         │
│    /ws/*      → api:8000   (WebSocket)                          │
│    /api/*     → api:8000   (REST API)                           │
│    /auth/*    → api:8000   (Authentication)                     │
│    /*         → web:80     (Static frontend)                    │
└───────────────┬─────────────────────────────────────────────────┘
                │
    ┌───────────┴────────────────┐
    ▼                            ▼
┌──────────┐              ┌──────────────┐
│   Web    │              │     API      │
│  (nginx) │              │  (FastAPI)   │
│          │              │              │
│ Serves   │              │ WebSocket    │
│ React    │              │ Manager      │
│ static   │              │ JWT Auth     │
│ files    │              │ REST API     │
└──────────┘              └──────┬───────┘
                                 │
                ┌────────────────┼────────────────┐
                ▼                ▼                ▼
         ┌──────────┐     ┌──────────┐    ┌──────────┐
         │ Postgres │     │  Redis   │    │   MT     │
         │          │     │          │    │ Worker   │
         │ - users  │     │ Channels:│    │ (pl↔en)  │
         │ - rooms  │     │  audio_  │    └──────────┘
         │ - seg    │     │  events  │
         │   ments  │     │  stt_    │
         │ - trans  │     │  events  │
         │   lations│     │  mt_     │
         │ - costs  │     │  events  │
         └──────────┘     │  cost_   │
                          │  events  │
                          └────┬─────┘
                               │
              ┌────────────────┼────────────────┬───────────────┐
              ▼                ▼                ▼               ▼
       ┌────────────┐   ┌────────────┐  ┌────────────┐  ┌────────────┐
       │    STT     │   │     MT     │  │Persistence │  │    Cost    │
       │   Router   │   │   Router   │  │  Service   │  │  Tracker   │
       │            │   │            │  │            │  │  Service   │
       │ Whisper    │   │ Routes to: │  │ Redis →    │  │ Redis →    │
       │ API calls  │   │ - Local    │  │ Postgres   │  │ Postgres   │
       │            │   │ - OpenAI   │  │            │  │            │
       └────────────┘   └────────────┘  └────────────┘  └────────────┘
```

### Message Flow

```
1. Browser VAD detects speech
   ↓
2. Audio chunks sent via WebSocket → API
   ↓
3. API publishes to Redis channel "audio_events"
   ↓
4. STT Router:
   - Receives from "audio_events"
   - Calls OpenAI Whisper API
   - Publishes to "stt_events" channel
   ↓
5. MT Router:
   - Subscribes to "stt_events"
   - Routes to local worker (pl↔en) or OpenAI (others)
   - Publishes to "mt_events" channel
   ↓
6. WS Manager (in API):
   - Subscribes to "stt_events" and "mt_events"
   - Broadcasts to all WebSocket clients in room
   ↓
7. Persistence Service:
   - Subscribes to "stt_events" and "mt_events"
   - Saves to PostgreSQL (segments, translations)
   ↓
8. Cost Tracker:
   - Subscribes to "cost_events"
   - Tracks API costs in room_costs table
```

### Redis Channels

| Channel | Purpose | Publisher | Subscribers |
|---------|---------|-----------|-------------|
| `audio_events` | Raw audio chunks from browser | API (WebSocket) | STT Router |
| `stt_events` | Transcription results (partial/final) | STT Router | MT Router, WS Manager, Persistence |
| `mt_events` | Translation results (partial/final) | MT Router | WS Manager, Persistence |
| `cost_events` | Cost tracking events | STT Router, MT Router | Cost Tracker |

---

## 🗄️ Database Schema

### Tables Overview

```sql
-- Authentication
users (id, email, password_hash, google_id, display_name, preferred_lang, created_at)

-- Rooms
rooms (id, code, owner_id, created_at, recording)
devices (id, room_id, name, created_at)

-- Transcriptions
segments (id, room_id, speaker_id, segment_id, revision, ts_iso, text, lang, final)

-- Translations (Smart Cache)
translations (id, room_id, segment_id, src_lang, tgt_lang, text, is_final, ts_iso, created_at)
  UNIQUE(room_id, segment_id, tgt_lang)  -- One translation per target language

-- Cost Tracking
room_costs (id, room_id, ts, pipeline, mode, units, unit_type, amount_usd)

-- Legacy (not actively used)
events (id, room_id, segment_id, revision, is_final, src_lang, text, translated_text, created_at)
```

### Detailed Schema

#### `users`
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),              -- NULL for Google OAuth users
    google_id VARCHAR(255) UNIQUE,           -- Google OAuth identifier
    display_name VARCHAR(120) DEFAULT '' NOT NULL,
    preferred_lang VARCHAR(16) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Indexes
CREATE UNIQUE INDEX ix_users_email ON users(email);
```

**Notes:**
- `password_hash` is NULL for users who signed up with Google OAuth
- `google_id` stores the Google OAuth subject (sub) field
- Email is the primary identifier for users

#### `rooms`
```sql
CREATE TABLE rooms (
    id SERIAL PRIMARY KEY,
    code VARCHAR(16) UNIQUE NOT NULL,        -- Human-readable room code
    owner_id INTEGER REFERENCES users(id) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    recording BOOLEAN DEFAULT FALSE NOT NULL
);

-- Indexes
CREATE UNIQUE INDEX ix_rooms_code ON rooms(code);
```

**Notes:**
- `code` is the human-readable identifier (e.g., "room-123")
- `owner_id` references the user who created the room
- `recording` flag (currently always set to true in persistence service)

#### `segments`
```sql
CREATE TABLE segments (
    id SERIAL PRIMARY KEY,
    room_id INTEGER REFERENCES rooms(id) NOT NULL,
    speaker_id VARCHAR(64) NOT NULL,         -- Email of speaker
    segment_id VARCHAR(64) NOT NULL,         -- Segment number
    revision INTEGER NOT NULL,
    ts_iso VARCHAR(40) NOT NULL,             -- ISO timestamp
    text TEXT NOT NULL,
    lang VARCHAR(8) NOT NULL,                -- Often "auto"
    final BOOLEAN NOT NULL
);

-- Indexes
CREATE INDEX ix_segments_room_id ON segments(room_id);
CREATE INDEX ix_segments_segment_id ON segments(segment_id);
```

**Notes:**
- Stores original transcription text
- `speaker_id` is the email address of the speaker
- `lang` is often "auto" (detected language)
- `final` indicates if this is a final or partial transcription

#### `translations`
```sql
CREATE TABLE translations (
    id SERIAL PRIMARY KEY,
    room_id VARCHAR(255) NOT NULL,           -- Room CODE (not ID!)
    segment_id INTEGER NOT NULL,
    src_lang VARCHAR(10) NOT NULL,
    tgt_lang VARCHAR(10) NOT NULL,           -- Target language
    text TEXT NOT NULL,
    is_final BOOLEAN DEFAULT FALSE,
    ts_iso TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(room_id, segment_id, tgt_lang)    -- One translation per language
);
```

**IMPORTANT:**
- `room_id` stores the room CODE (e.g., "room-123"), NOT the numeric ID!
- UNIQUE constraint ensures one translation per (room, segment, target_lang)
- Enables smart caching: translate once, retrieve for any user speaking that language

#### `room_costs`
```sql
CREATE TABLE room_costs (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT NOT NULL,                   -- Room code
    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    pipeline TEXT NOT NULL,                  -- 'stt', 'stt_partial', 'stt_final', 'mt'
    mode TEXT NOT NULL,                      -- 'local', 'openai'
    units BIGINT,                            -- Seconds (STT) or tokens (MT)
    unit_type TEXT,                          -- 'seconds', 'tokens'
    amount_usd NUMERIC(12,6) DEFAULT 0 NOT NULL,

    CHECK (mode IN ('local', 'openai')),
    CHECK (pipeline IN ('stt', 'stt_partial', 'stt_final', 'mt'))
);

-- Indexes
CREATE INDEX ix_room_costs_room_ts ON room_costs(room_id, ts DESC);
```

**Notes:**
- Tracks costs for STT (Whisper) and MT (GPT-4o-mini) API calls
- `pipeline` can be 'stt', 'stt_partial', 'stt_final', or 'mt'
- `mode` indicates whether local or OpenAI service was used
- `units` and `unit_type` track usage (seconds for STT, tokens for MT)

---

## 🔌 API Endpoints

### Base URL
- Production: `https://livetranslator.pawelgawliczek.cloud`
- Local: `http://localhost:9003`

### Authentication Endpoints (`/auth/*`)

#### POST `/auth/signup`
Register a new user with email/password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "display_name": "John Doe"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

#### POST `/auth/login`
Login with email/password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

#### GET `/auth/google/login`
Initiates Google OAuth flow. Redirects to Google consent screen.

#### GET `/auth/google/callback?code=...`
Google OAuth callback. Exchanges code for user info and returns JWT.

**Response:** Redirects to `/?token=...`

### Room Endpoints (`/rooms`)

#### GET `/rooms`
List all rooms for authenticated user.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
[
  {
    "id": 1,
    "code": "room-123",
    "owner_id": 1,
    "created_at": "2025-10-20T12:00:00"
  }
]
```

#### POST `/rooms`
Create a new room.

**Headers:**
```
Authorization: Bearer <token>
```

**Request:**
```json
{
  "code": "my-room"  // Optional, auto-generated if not provided
}
```

**Response:**
```json
{
  "id": 1,
  "code": "my-room",
  "owner_id": 1,
  "created_at": "2025-10-20T12:00:00"
}
```

### Cost Endpoints (`/costs/*`)

#### GET `/costs/room/{room_code}`
Get total costs for a room.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "total_cost_usd": 0.023456,
  "breakdown": {
    "stt": {
      "mode": "openai",
      "events": 45,
      "cost_usd": 0.012
    },
    "mt": {
      "mode": "openai",
      "events": 87,
      "cost_usd": 0.011
    }
  }
}
```

### History Endpoints (`/history/*`)

#### GET `/history/room/{room_code}?target_lang={lang}`
Get conversation history with on-demand translation.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `target_lang`: Target language for translations (e.g., "en", "pl", "ar")

**Response:**
```json
{
  "room_code": "room-123",
  "segments": [
    {
      "segment_id": 123,
      "speaker": "user@example.com",
      "text": "Hello world",
      "lang": "en",
      "translation": "Cześć świecie",
      "ts_iso": "2025-10-20T12:00:00"
    }
  ]
}
```

**Notes:**
- If translation doesn't exist in cache, it's generated on-demand
- Uses smart caching to avoid re-translating the same content

### Translation Endpoints

#### POST `/translate`
Translate text (synchronous).

**Request:**
```json
{
  "src": "en",
  "tgt": "pl",
  "text": "Hello world"
}
```

**Response:**
```json
{
  "text": "Cześć świecie"
}
```

#### GET `/translate/stream?q={text}&src={src}&tgt={tgt}`
Stream translation results (Server-Sent Events).

**Response:**
```
data: {"text": "Cześć"}
data: {"text": "Cześć świecie"}
```

### Health Endpoints

#### GET `/healthz`
Basic health check.

**Response:**
```json
{
  "ok": true
}
```

#### GET `/readyz`
Readiness check (verifies Redis, MT worker connectivity).

**Response:**
```json
{
  "ok": true
}
```

#### GET `/metrics`
Prometheus metrics endpoint.

---

## 🔌 WebSocket Protocol

### Connection

```
ws://localhost:9003/ws/rooms/{room_id}?token={jwt_token}
```

Or via header:
```
Authorization: Bearer {jwt_token}
```

### Client → Server Messages

#### Audio Chunk (Partial)
Sent every ~2 seconds during speech.

```json
{
  "type": "audio_chunk_partial",
  "roomId": "room-123",
  "segment_hint": 1234567890,
  "pcm16_base64": "AAECAwQFBgc...",
  "source_lang": "pl",
  "target_lang": "en"
}
```

#### Audio Chunk (Final)
Sent when speech ends.

```json
{
  "type": "audio_chunk",
  "roomId": "room-123",
  "seq": 123,
  "pcm16_base64": "AAECAwQFBgc...",
  "source_lang": "pl",
  "target_lang": "en"
}
```

#### Audio End
Sent when user stops speaking.

```json
{
  "type": "audio_end",
  "roomId": "room-123"
}
```

### Server → Client Messages

#### STT Partial
Real-time transcription (appears while speaking).

```json
{
  "type": "stt_partial",
  "segment_id": 123,
  "text": "Hello wor...",
  "lang": "en",
  "final": false,
  "speaker": "user@example.com",
  "ts_iso": "2025-10-20T12:00:00.123456"
}
```

#### STT Final
Final transcription (after speech ends).

```json
{
  "type": "stt_final",
  "segment_id": 123,
  "text": "Hello world",
  "lang": "en",
  "final": true,
  "speaker": "user@example.com",
  "ts_iso": "2025-10-20T12:00:00.789012"
}
```

#### Translation Partial
Real-time translation (updating).

```json
{
  "type": "translation_partial",
  "segment_id": 123,
  "text": "Cześć świ...",
  "src": "en",
  "tgt": "pl",
  "final": false,
  "ts_iso": "2025-10-20T12:00:01.000000"
}
```

#### Translation Final
Final translation.

```json
{
  "type": "translation_final",
  "segment_id": 123,
  "text": "Cześć świecie",
  "src": "en",
  "tgt": "pl",
  "final": true,
  "ts_iso": "2025-10-20T12:00:01.500000"
}
```

---

## ⚙️ Services

### API Service (`api/`)
**Container:** `api`
**Port:** 9003:8000
**Purpose:** Main FastAPI application

**Responsibilities:**
- WebSocket management
- REST API endpoints
- JWT authentication
- User/room management
- WebSocket broadcasting

**Key Files:**
- `main.py` - FastAPI app entry point
- `ws_manager.py` - WebSocket connection manager
- `auth.py` - Authentication endpoints
- `models.py` - SQLAlchemy models
- `jwt_tools.py` - JWT utilities

### STT Router (`api/routers/stt/`)
**Container:** `stt_router`
**Purpose:** Speech-to-text routing service

**Workflow:**
1. Subscribes to `audio_events` Redis channel
2. Accumulates partial audio chunks
3. Calls OpenAI Whisper API
4. Publishes results to `stt_events` channel
5. Publishes cost events to `cost_events` channel

**Key Files:**
- `router.py` - Main STT routing logic
- `openai_backend.py` - Whisper API integration

**Environment Variables:**
- `STT_INPUT_CHANNEL=audio_events`
- `STT_OUTPUT_EVENTS=stt_events`
- `LT_STT_PARTIAL_MODE=openai_chunked`
- `OPENAI_API_KEY=...`

### MT Router (`api/routers/mt/`)
**Container:** `mt_router`
**Purpose:** Machine translation routing service

**Workflow:**
1. Subscribes to `stt_events` Redis channel
2. Routes translation requests:
   - Polish ↔ English: Local worker (HTTP)
   - Other pairs: OpenAI GPT-4o-mini
3. Publishes results to `mt_events` channel
4. Publishes cost events to `cost_events` channel

**Key Files:**
- `router.py` - MT routing logic
- `openai_backend.py` - GPT-4o-mini translation

**Environment Variables:**
- `MT_INPUT_CHANNEL=mt_requests`
- `MT_OUTPUT_CHANNEL=mt_events`
- `STT_EVENTS_CHANNEL=stt_events`
- `LT_MT_MODE=hybrid`
- `OPENAI_API_KEY=...`
- `OPENAI_MT_MODEL=gpt-4o-mini`

### MT Worker (`workers/mt/`)
**Container:** `mt_worker`
**Port:** 8081
**Purpose:** Local translation worker for Polish ↔ English

**Endpoints:**
- `GET /health` - Health check
- `POST /translate/fast` - Fast translation (pl↔en only)

**Key Files:**
- `app.py` - FastAPI translation service

### Persistence Service (`api/services/`)
**Container:** `persistence`
**Purpose:** Save events to PostgreSQL

**Workflow:**
1. Subscribes to `stt_events` and `mt_events` channels
2. Listens for `stt_final` and `translation_final` messages
3. Saves to PostgreSQL:
   - `stt_final` → `segments` table
   - `translation_final` → `translations` table (with deduplication)

**Key Files:**
- `persistence_service.py` - Main persistence logic

**Notes:**
- Auto-creates rooms if they don't exist
- Uses UNIQUE constraint on translations to prevent duplicates
- Stores room CODE (not ID) in translations table

### Cost Tracker Service (`api/services/`)
**Container:** `cost_tracker`
**Purpose:** Track API usage costs

**Workflow:**
1. Subscribes to `cost_events` Redis channel
2. Receives cost events from STT/MT routers
3. Calculates costs based on pricing:
   - Whisper: $0.006 per minute
   - GPT-4o-mini input: $0.00015 per 1K tokens
   - GPT-4o-mini output: $0.0006 per 1K tokens
4. Saves to `room_costs` table

**Key Files:**
- `cost_tracker_service.py` - Cost tracking logic

**Environment Variables:**
- `COST_TRACKING_CHANNEL=cost_events`
- `OPENAI_PRICE_WHISPER_PER_MIN=0.006`
- `OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K=0.00015`
- `OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K=0.0006`

---

## 🎨 Frontend Structure

### Technology Stack
- React 18
- Vite (build tool)
- React Router v6
- @ricky0123/vad-web (Voice Activity Detection)

### File Structure

```
web/
├── index.html              # Entry HTML, PWA meta tags
├── vite.config.js          # Vite configuration
├── public/
│   ├── manifest.json       # PWA manifest
│   ├── icon-192.svg        # App icon (192x192)
│   └── icon-512.svg        # App icon (512x512)
└── src/
    ├── main.jsx            # App entry, routing, auth state
    ├── App.jsx             # (unused - routing in main.jsx)
    └── pages/
        ├── LandingPage.jsx      # Home page, token redirect
        ├── LoginPage.jsx        # Login + Google OAuth
        ├── SignupPage.jsx       # Registration
        ├── RoomsPage.jsx        # Room list, create room
        └── RoomPage.jsx         # Main chat interface
```

### Key Components

#### `main.jsx`
- App entry point
- Routing configuration
- Auth state management (localStorage)
- Token validation

#### `RoomPage.jsx`
Main chat interface with:
- WebSocket connection management
- Voice Activity Detection (VAD)
- Real-time transcription display
- Translation display
- Push-to-talk mode
- Language selection
- History loading
- Auto-scroll

**Key State:**
```javascript
- status: 'idle' | 'connecting' | 'streaming'
- vadStatus: Current VAD status text
- lines: Array of [segmentId, {source, translation}]
- sourceLang, targetLang: Selected languages
- pushToTalk: Boolean for PTT mode
```

**Key Refs:**
```javascript
- wsRef: WebSocket connection
- segsRef: Map of all segments (s-123, t-123)
- vadRef: Voice Activity Detection instance
- isRecordingRef: Recording state
```

### PWA Features

**Installation:**
1. Open in Safari/Chrome
2. Tap "Add to Home Screen"
3. Opens fullscreen without browser UI

**Files:**
- `/web/public/manifest.json` - App manifest
- `/web/index.html` - Meta tags for iOS
- `/web/public/icon-*.svg` - App icons

**Known Limitation:**
- Google OAuth exits PWA mode on iOS (Safari limitation)
- Use email/password login in PWA for fullscreen experience

---

## 🛠️ Development Guide

### Prerequisites
- Docker & Docker Compose
- Git
- OpenAI API key

### Environment Variables

Create `.env` file in project root:

```bash
# Database
POSTGRES_USER=livetranslator
POSTGRES_PASSWORD=changeme
POSTGRES_DB=livetranslator
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/5

# OpenAI
OPENAI_API_KEY=sk-...

# Translation
LT_STT_PARTIAL_MODE=openai_chunked
LT_MT_MODE=hybrid
LT_DEFAULT_TGT=en
OPENAI_MT_MODEL=gpt-4o-mini

# Pricing
OPENAI_PRICE_WHISPER_PER_MIN=0.006
OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K=0.00015
OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K=0.0006
```

### Secrets

Create `/opt/stack/secrets/` directory:

```bash
mkdir -p /opt/stack/secrets

# JWT secret (generate random string)
echo "your-secret-key-here" > /opt/stack/secrets/jwt_secret

# Google OAuth credentials (from Google Cloud Console)
echo "your-client-id" > /opt/stack/secrets/google_oauth_client_id.txt
echo "your-client-secret" > /opt/stack/secrets/google_oauth_client_secret.txt
```

### Running Locally

```bash
# Start all services
cd /opt/stack/livetranslator
docker compose up -d

# View logs
docker compose logs -f

# Check specific service
docker compose logs -f api
docker compose logs -f stt_router
docker compose logs -f mt_router

# Rebuild after code changes
docker compose up -d --build api
docker compose up -d --build web

# Stop all services
docker compose down
```

### Database Operations

```bash
# Connect to database
docker compose exec -T postgres psql -U livetranslator -d livetranslator

# Run SQL query
docker compose exec -T postgres psql -U livetranslator -d livetranslator -c "SELECT * FROM users;"

# Backup database
docker compose exec postgres pg_dump -U livetranslator livetranslator > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U livetranslator -d livetranslator
```

### Redis Monitoring

```bash
# Monitor all Redis activity
docker compose exec redis redis-cli -n 5 MONITOR

# Subscribe to specific channel
docker compose exec redis redis-cli -n 5 SUBSCRIBE stt_events
docker compose exec redis redis-cli -n 5 SUBSCRIBE mt_events
docker compose exec redis redis-cli -n 5 SUBSCRIBE cost_events
```

### Common Development Tasks

#### Adding a New API Endpoint

1. Define route in `api/main.py` or create new router
2. Add Pydantic models in `api/schemas.py`
3. Update database models if needed (`api/models.py`)
4. Rebuild API container: `docker compose up -d --build api`

#### Adding a New Frontend Page

1. Create component in `web/src/pages/`
2. Add route in `web/src/main.jsx`
3. Rebuild web container: `docker compose up -d --build web`

#### Modifying Database Schema

1. Update `api/models.py`
2. Create migration script or manually update database
3. Restart services: `docker compose restart api persistence`

---

## 🚀 Deployment

### Production Environment

**Domain:** `livetranslator.pawelgawliczek.cloud`

**Reverse Proxy:** Caddy (automatic HTTPS)

**Caddy Configuration (`/etc/caddy/Caddyfile`):**
```
livetranslator.pawelgawliczek.cloud {
    reverse_proxy /ws/* api:8000
    reverse_proxy /api/* api:8000
    reverse_proxy /auth/* api:8000
    reverse_proxy /rooms api:8000
    reverse_proxy /costs/* api:8000
    reverse_proxy /history/* api:8000
    reverse_proxy /* web:80

    encode gzip
    log
}
```

### Deployment Checklist

1. Update `.env` file with production values
2. Set up secrets in `/opt/stack/secrets/`
3. Configure Google OAuth redirect URI
4. Start services: `docker compose up -d`
5. Check logs: `docker compose logs -f`
6. Verify health: `curl https://livetranslator.../healthz`
7. Test WebSocket: Open app in browser

### Monitoring

**Logs:**
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api --tail=100

# Error logs only
docker compose logs api | grep -i error
```

**Metrics:**
- Prometheus: `https://livetranslator.../metrics`

**Health Checks:**
- Basic: `https://livetranslator.../healthz`
- Ready: `https://livetranslator.../readyz`

### Backup Strategy

**Database:**
```bash
# Daily backup script
docker compose exec postgres pg_dump -U livetranslator livetranslator > backup-$(date +%Y%m%d).sql
```

**Data Directories:**
- `/opt/stack/livetranslator/data/pg` - PostgreSQL data
- `/opt/stack/livetranslator/data/redis` - Redis data

---

## 🐛 Troubleshooting

### Common Issues

#### History not loading
- Check that `room_id` in translations table is room CODE, not numeric ID
- Verify JOIN in history API query

#### Messages stuck with "..."
- STT router should auto-finalize partials on `audio_end` event
- Check STT router logs for finalization messages

#### Desktop doesn't see mobile messages
- Both devices must have WebSocket connected (press Start button)
- Check WebSocket connection in browser console

#### STT costs not tracked
- Verify cost_events channel is not filtered in cost_tracker
- Check constraint on room_costs.pipeline includes 'stt'

#### Google OAuth exits PWA
- Expected Safari behavior when redirecting to external domain
- Use email/password login in PWA for fullscreen

### Debug Commands

```bash
# Check service status
docker compose ps

# Check service logs
docker compose logs -f <service>

# Check database connectivity
docker compose exec -T postgres psql -U livetranslator -d livetranslator -c "SELECT 1;"

# Check Redis connectivity
docker compose exec redis redis-cli -n 5 PING

# Check WebSocket connections
docker compose logs --tail=100 api | grep "ws_join\|ws_leave"

# Check API health
curl https://livetranslator.../healthz
curl https://livetranslator.../readyz
```

---

## 📊 Performance Metrics

### Typical Latency
- STT (Whisper): ~1-2 seconds for final
- MT (local pl↔en): ~100-300ms
- MT (OpenAI others): ~500-1500ms
- Total end-to-end: ~2-4 seconds

### Resource Usage (per container)
- API: ~500MB RAM, 0.5 CPU
- STT Router: ~300MB RAM
- MT Router: ~300MB RAM
- Web: ~50MB RAM
- PostgreSQL: ~200MB RAM
- Redis: ~50MB RAM

---

## 📝 Development Tips

1. **Always use React Router's `navigate()`** - Never `window.location.href` (breaks PWA)
2. **Store state in React, not localStorage** - Except auth token and preferences
3. **Use Authorization header** - `Bearer ${token}` for all API calls
4. **Auto-finalize partials** - Always send final when session ends
5. **Use room CODE not ID** - For translations table lookups
6. **Test multi-device** - Both must be recording to see broadcasts
7. **Check Redis channels** - Subscribe to debug message flow
8. **Monitor costs** - Track OpenAI API usage per room

---

## 📚 Additional Resources

- FastAPI Docs: https://fastapi.tiangolo.com/
- React Docs: https://react.dev/
- OpenAI Whisper API: https://platform.openai.com/docs/guides/speech-to-text
- OpenAI GPT-4o-mini: https://platform.openai.com/docs/models/gpt-4o-mini
- Redis PubSub: https://redis.io/docs/manual/pubsub/
- PostgreSQL Docs: https://www.postgresql.org/docs/

---

**Last Updated:** 2025-10-21
**Version:** 1.0.0

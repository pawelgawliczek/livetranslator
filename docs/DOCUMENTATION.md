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

**Speech-to-Text (STT):**
- **Multi-Provider Support** - 5 STT providers: Speechmatics, Google Cloud Speech v2, Azure Speech, Soniox, OpenAI Whisper
- **Language-Based Routing** - Database-driven provider selection per language for optimal quality
- **Quality Tiers** - Standard (best quality) vs Budget (cost-optimized)
- **Streaming Architecture** - Persistent WebSocket/gRPC connections for ultra-low latency (1.5-3s)
- **Connection Pooling** - One connection per (room, provider) tuple, reused for entire conversation
- **Late Final Blocking** - 3-layer detection prevents duplicate text from streaming providers
- **Health Monitoring** - Automatic fallback after 3 consecutive provider failures
- **Diarization** - Speaker identification across all providers
- **Real-time Partials** - Word-by-word accumulation as user speaks

**Machine Translation (MT):**
- **Multi-Provider Support** - 4 MT providers: DeepL, Google Cloud Translation, Amazon Translate, OpenAI GPT-4o-mini
- **Language-Pair Routing** - Database-driven provider selection optimized per language pair
- **European Language Optimization** - DeepL for PL, EN, ES, FR, DE, IT, PT, RU (superior quality)
- **Arabic Dialect Support** - OpenAI GPT-4o-mini optimized for Egyptian Arabic (Masri)
- **Translation Caching** - Partial translation cache reduces API calls by 30-40%
- **Arabic Throttling** - 2-second interval reduces costs by 50% for rapid speech
- **Translation Matrix** - Every participant gets all room languages automatically

**Admin Analytics:**
- **Cost Monitoring** - Per-room, per-provider cost breakdowns with date filtering
- **Multi-Speaker Analytics** - Translation cost matrix (N×(N-1) routing visualization)
- **Budget Tracking** - Monthly budgets with 80%/95%/100% alerts
- **Provider Usage** - Top cost drivers across 9 STT/MT providers

**Infrastructure:**
- **Provider Health Monitoring** - Real-time health checks with automatic failover
- **Cost Tracking** - Per-provider cost tracking with detailed breakdowns
- **Quality Metrics** - Latency, confidence, WER tracking for performance analysis
- **Configuration Cache** - 5-minute TTL with instant Redis pub/sub invalidation
- **Segment Tracking** - Redis-based synchronized counter with double-increment prevention

**User Experience:**
- **WebSocket-based** live updates with processing indicators
- **Visual Feedback** - Real-time speaking indicators, spinning icons, 28-language localization
- **Presence System** - Debounced join/leave notifications with 10-second grace period for packet-loss resistance
- **Active Language Tracking** - Language flags with counts in room header, participants sidebar with real-time updates
- **Toast Notifications** - Auto-dismissing presence notifications (join/leave/language change)
- **Welcome Banner** - Shows current participants when joining room
- **Progressive Web App** (PWA) support with mobile optimization
- **Google OAuth** + email/password authentication
- **History** with on-demand translation and export capabilities
- **Admin Panel** - Configure STT/MT providers per language with instant cache updates
- **Comprehensive Testing** - 98.5% test coverage (733 tests)

### Technology Stack
- **Frontend**: React 18 + Vite + React Router + i18next (internationalization)
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16
- **Cache/Queue**: Redis 7 with Pub/Sub
- **Reverse Proxy**: Caddy 2
- **STT Providers** (Language-based routing):
  - Speechmatics (persistent WebSocket streaming) - $0.08/hr ✅
  - Google Cloud Speech v2 (gRPC streaming) - $0.96/hr ✅
  - Azure Speech SDK (push audio stream) - $1.00/hr ✅
  - Soniox (REST API, budget tier) - $0.015/hr ✅
  - OpenAI Whisper (fallback) - $0.36/hr ✅
- **MT Providers** (Language-pair routing):
  - DeepL (European languages) - $10/1M chars ✅
  - Google Cloud Translation - $20/1M chars ✅
  - Amazon Translate - $15/1M chars ✅
  - OpenAI GPT-4o-mini (Arabic dialect) - $0.375/1k tokens ✅
- **Deployment**: Docker Compose
- **i18n**: 28 languages with full UI localization

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
       │ Language-  │   │ Routes to: │  │ Redis →    │  │ Redis →    │
       │ based      │   │ - Local    │  │ Postgres   │  │ Postgres   │
       │ routing    │   │ - OpenAI   │  │            │  │            │
       │ Streaming  │   │            │  │            │  │            │
       │ WebSocket  │   │            │  │            │  │            │
       │ Manager    │   │            │  │            │  │            │
       └────────────┘   └────────────┘  └────────────┘  └────────────┘
            │
            ▼
       ┌────────────────────────────────────────┐
       │   Streaming Manager (Connection Pool)  │
       │   ┌──────────┐  ┌──────────┐          │
       │   │ Room A   │  │ Room B   │   ...    │
       │   │ WS conn  │  │ WS conn  │          │
       │   └────┬─────┘  └────┬─────┘          │
       └────────┼─────────────┼─────────────────┘
                │             │
                ▼             ▼
       ┌────────────────────────────────────────┐
       │      Provider WebSocket Endpoints      │
       │  Speechmatics │ Google │ Azure │ ...   │
       └────────────────────────────────────────┘
```

### STT Streaming Architecture

**Multi-Provider Streaming with Language-Based Routing:**

```
Audio Chunk → STT Router → Language-Based Routing (Database Config)
                                    ↓
                         Query: stt_routing_config
                         (language, mode, quality_tier)
                                    ↓
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Speechmatics    Google Cloud v2    Azure Speech
              (WebSocket)     (gRPC Stream)      (Push Stream)
                    │               │               │
                    ▼               ▼               ▼
              Streaming Manager (Connection Pool)
                    │
         ┌──────────┼──────────────────┐
         ▼          ▼                  ▼
    Room A:SM  Room B:GV2        Room C:Azure
    WS conn    gRPC session      Push stream
         │          │                  │
         ├→ AddPartialTranscript (partials)
         ├→ AddTranscript (finals)
         ├→ Late Final Blocking (time-based)
         └→ Publish to stt_events channel
```

**Provider Selection Matrix:**

| Language | Mode | Quality Tier | Primary Provider | Fallback | Latency |
|----------|------|--------------|------------------|----------|---------|
| Polish (pl-PL) | partial | standard | Speechmatics | Google v2 | 1.5s |
| Arabic (ar-EG) | partial | standard | Google v2 | Azure | 2-3s |
| English (en-US) | partial | standard | Speechmatics | Google v2 | 1.5s |
| All languages | partial | budget | Soniox | Google v2 | 3-5s |
| Wildcard (*) | final | standard | Google v2 | Azure | 2-4s |

**Key Features:**
- **Multi-Provider Support** - 5 STT providers with automatic selection
- **One connection per (room, provider)** - Persistent streaming connections
- **Word-by-word streaming** - Real-time accumulation (Speechmatics, Google, Azure)
- **Language-based routing** - Database-driven provider selection per language
- **Quality tiers** - Standard (best quality) vs Budget (cost-optimized)
- **Health monitoring** - Automatic fallback after 3 consecutive provider failures
- **Connection pooling** - Efficient resource management via StreamingManager
- **Late final blocking** - 3-layer detection prevents duplicate text from late finals
- **Clean lifecycle** - Proper connection close with EndOfStream

```

### Message Flow

**Real-time Speech-to-Translation Pipeline with Optimizations:**

```
1. Browser VAD (Voice Activity Detection)
   - Detects speech start/end using energy-based RMS
   - 30-second safety timeout prevents runaway recordings
   - Resamples audio to 16kHz before sending
   ↓
2. Audio chunks → WebSocket → API
   - PCM16 base64-encoded chunks (~400ms each)
   - Sent continuously while speaking
   - "audio_end" signal when speech stops
   ↓
3. API → Redis "audio_events" channel
   - Publishes raw audio for STT processing
   ↓
4. STT Router (OPTIMIZED):
   ┌─────────────────────────────────────────┐
   │ A. During Speech (Partials):           │
   │    - Accumulates audio chunks           │
   │    - Only transcribes NEW audio         │
   │    - Builds context from last 2-3 sent. │
   │    - Calls OpenAI Whisper with context  │
   │    - Smart deduplication removes duplic.│
   │    - Strips ending punctuation          │
   │    - Publishes "stt_partial" events     │
   │                                         │
   │ B. After Speech (Parallel Processing): │
   │    1. Instant: Send accumulated partial │
   │       → processing: true                │
   │    2. Background: Re-transcribe full    │
   │       → Better punctuation & accuracy   │
   │    3. Quality: Send if text differs     │
   │       → processing: false               │
   │                                         │
   │ C. Conversation History:                │
   │    - Saves last 5 finalized sentences   │
   │    - Uses as context for next sentence  │
   │    - Improves accuracy 15-20%           │
   └─────────────────────────────────────────┘
   ↓
5. "stt_events" channel → Multiple Subscribers
   ├─→ MT Router (Translation)
   ├─→ WS Manager (Real-time broadcast)
   └─→ Persistence Service (Database)
   ↓
6. MT Router:
   - Receives stt_final events
   - Routes: pl↔en to local worker, others to OpenAI
   - Publishes to "mt_events" channel
   ↓
7. WS Manager (in API):
   - Subscribes to both "stt_events" and "mt_events"
   - Broadcasts to all WebSocket clients in room
   - Clients see:
     * ⋯ during speech (partial)
     * ⚙️ + "Refining quality..." (processing: true)
     * Final text (processing: false)
   ↓
8. Persistence Service:
   - Listens on "stt_events" and "mt_events"
   - Saves stt_final → segments table
   - Saves translation_final → translations table (with dedup)
   ↓
9. Cost Tracker:
   - Subscribes to "cost_events"
   - Tracks OpenAI API costs in room_costs table
   - Monitors: STT seconds, MT tokens
```

**Performance Characteristics:**
- **Partials**: Every ~400ms during speech (real-time feedback)
- **Instant Final**: <100ms after speech ends (zero perceived delay)
- **Quality Final**: +500-1500ms background refinement (non-blocking)
- **Context Accuracy**: +15-20% for proper names and technical terms
- **Deduplication**: Prevents context word overlap at word level

### Redis Channels

| Channel | Purpose | Publisher | Subscribers |
|---------|---------|-----------|-------------|
| `audio_events` | Raw audio chunks from browser | API (WebSocket) | STT Router |
| `stt_events` | Transcription results (partial/final) | STT Router | MT Router, WS Manager, Persistence |
| `mt_events` | Translation results (partial/final) | MT Router | WS Manager, Persistence |
| `cost_events` | Cost tracking events | STT Router, MT Router | Cost Tracker |
| `presence_events` | User presence updates (join/leave/language change) | PresenceManager | WS Manager |

---

## 🗄️ Database Schema

### Tables Overview

```sql
-- Authentication
users (id, email, password_hash, google_id, display_name, preferred_lang, is_admin, created_at)

-- Rooms
rooms (id, code, owner_id, created_at, recording)
devices (id, room_id, name, created_at)

-- Transcriptions
segments (id, room_id, speaker_id, segment_id, revision, ts_iso, text, lang, final, stt_provider, latency_ms)

-- Translations (Smart Cache)
translations (id, room_id, segment_id, src_lang, tgt_lang, text, is_final, ts_iso, mt_provider, context_used, glossary_used, created_at)
  UNIQUE(room_id, segment_id, tgt_lang)  -- One translation per target language

-- Provider Configuration (Language-Based Routing)
stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config, enabled)
  UNIQUE(language, mode, quality_tier)
mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config, enabled)
  UNIQUE(src_lang, tgt_lang, quality_tier)

-- Provider Health & Monitoring
provider_health (provider, service_type, status, consecutive_failures, last_check, response_time_ms)
  UNIQUE(provider, service_type)
quality_metrics (room_id, segment_id, provider, service_type, language, latency_ms, wer, confidence, diarization_speakers)

-- Cost Tracking
room_costs (id, room_id, ts, pipeline, mode, provider, units, unit_type, amount_usd)
provider_pricing (service, provider, pricing_model, unit_price, currency, effective_date)
  UNIQUE(service, provider, effective_date)

-- Admin Analytics
cost_budgets (id, period_type, budget_usd, alert_threshold_pct, critical_threshold_pct, is_active, created_at, updated_at, updated_by)
budget_alerts (id, budget_id, alert_type, period_start, period_end, actual_cost_usd, budget_usd, percentage_used, triggered_at, acknowledged_at, acknowledged_by)

-- System Settings
system_settings (id, key, value, updated_at)

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

#### `cost_budgets`
```sql
CREATE TABLE cost_budgets (
    id SERIAL PRIMARY KEY,
    period_type VARCHAR(20) NOT NULL DEFAULT 'monthly',  -- monthly, weekly, daily
    budget_usd NUMERIC(10, 2) NOT NULL,
    alert_threshold_pct INTEGER NOT NULL DEFAULT 80,
    critical_threshold_pct INTEGER NOT NULL DEFAULT 95,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_by INTEGER REFERENCES users(id)
);

CREATE INDEX idx_cost_budgets_active ON cost_budgets(is_active);
```

**Notes:**
- Admin-configurable cost budgets (monthly/weekly/daily)
- Alert thresholds trigger notifications at 80% and 95%
- Only one active budget per period type

#### `budget_alerts`
```sql
CREATE TABLE budget_alerts (
    id SERIAL PRIMARY KEY,
    budget_id INTEGER REFERENCES cost_budgets(id) ON DELETE CASCADE,
    alert_type VARCHAR(20) NOT NULL,                 -- warning, critical, exceeded
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    actual_cost_usd NUMERIC(10, 2) NOT NULL,
    budget_usd NUMERIC(10, 2) NOT NULL,
    percentage_used INTEGER NOT NULL,
    triggered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    acknowledged_by INTEGER REFERENCES users(id)
);

CREATE INDEX idx_budget_alerts_budget_id ON budget_alerts(budget_id);
CREATE INDEX idx_budget_alerts_triggered_at ON budget_alerts(triggered_at DESC);
```

**Notes:**
- Historical log of budget threshold breaches
- Alert types: warning (80%+), critical (95%+), exceeded (100%+)
- Acknowledgment tracking for admin follow-up

#### `room_costs`
```sql
CREATE TABLE room_costs (
    id BIGSERIAL PRIMARY KEY,
    room_id TEXT NOT NULL,                   -- Room code
    ts TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    pipeline TEXT NOT NULL,                  -- 'stt' or 'mt'
    mode TEXT NOT NULL,                      -- Legacy: provider name
    provider VARCHAR(50),                    -- New: actual provider used
    units BIGINT,                            -- Seconds (STT), characters/tokens (MT)
    unit_type TEXT,                          -- 'seconds', 'characters', 'tokens'
    amount_usd NUMERIC(12,6) DEFAULT 0 NOT NULL
);

-- Indexes
CREATE INDEX ix_room_costs_room_ts ON room_costs(room_id, ts DESC);
CREATE INDEX idx_room_costs_provider ON room_costs(provider);
CREATE INDEX idx_room_costs_pipeline_provider ON room_costs(pipeline, provider);
```

**Notes:**
- Tracks costs for all STT and MT provider API calls
- `pipeline` can be 'stt' or 'mt'
- `provider` indicates which provider was used (speechmatics, google_v2, deepl, etc.)
- `units` and `unit_type` track usage (seconds for STT, characters/tokens for MT)
- Costs calculated from `provider_pricing` table

#### `stt_routing_config`
```sql
CREATE TABLE stt_routing_config (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,           -- pl-PL, ar-EG, en-US, * (wildcard)
    mode VARCHAR(10) NOT NULL,               -- 'partial' or 'final'
    quality_tier VARCHAR(20) NOT NULL,       -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- speechmatics, google_v2, azure, soniox, openai
    provider_fallback VARCHAR(50),           -- Fallback if primary fails
    config JSONB DEFAULT '{}',               -- Provider-specific config
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(language, mode, quality_tier)
);

-- Indexes
CREATE INDEX idx_stt_routing_language ON stt_routing_config(language);
CREATE INDEX idx_stt_routing_mode ON stt_routing_config(mode);
CREATE INDEX idx_stt_routing_enabled ON stt_routing_config(enabled) WHERE enabled = TRUE;
```

**Notes:**
- Configures STT provider selection based on language, mode, and quality tier
- `language` supports wildcards (*) for default fallback
- `config` JSONB field stores provider-specific settings (diarization, max_delay, etc.)
- Enables per-language provider optimization

**Example config:**
```json
{
    "diarization": true,
    "max_delay": 1.5,
    "operating_point": "enhanced",
    "speaker_diarization_config": {"max_speakers": 10}
}
```

#### `mt_routing_config`
```sql
CREATE TABLE mt_routing_config (
    id SERIAL PRIMARY KEY,
    src_lang VARCHAR(10) NOT NULL,           -- Source language or * (wildcard)
    tgt_lang VARCHAR(10) NOT NULL,           -- Target language or * (wildcard)
    quality_tier VARCHAR(20) NOT NULL,       -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- deepl, google_translate, amazon_translate, openai
    provider_fallback VARCHAR(50),           -- Fallback if primary fails
    config JSONB DEFAULT '{}',               -- Provider-specific config
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(src_lang, tgt_lang, quality_tier)
);

-- Indexes
CREATE INDEX idx_mt_routing_lang_pair ON mt_routing_config(src_lang, tgt_lang);
CREATE INDEX idx_mt_routing_enabled ON mt_routing_config(enabled) WHERE enabled = TRUE;
```

**Notes:**
- Configures MT provider selection based on language pair and quality tier
- Supports wildcard (*) for source or target language defaults
- Optimizes for language-pair specific providers (e.g., DeepL for European languages)

**Example Routing:**
- PL ↔ EN: DeepL (primary) → Azure Translator (fallback)
- EN ↔ AR: OpenAI (primary) → Google Translate (fallback)
- Budget tier: Azure Translator → Google Translate

#### `provider_health`
```sql
CREATE TABLE provider_health (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,           -- Provider name
    service_type VARCHAR(10) NOT NULL,       -- 'stt' or 'mt'
    status VARCHAR(20) NOT NULL,             -- 'healthy', 'degraded', 'down'
    last_check TIMESTAMP NOT NULL,
    consecutive_failures INTEGER DEFAULT 0,  -- Triggers fallback after 3
    last_error TEXT,
    last_success TIMESTAMP,
    response_time_ms INTEGER,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(provider, service_type)
);

-- Indexes
CREATE INDEX idx_provider_health_status ON provider_health(provider, status);
CREATE INDEX idx_provider_health_service ON provider_health(service_type);
```

**Notes:**
- Monitors health of all STT and MT providers
- Automatic fallback triggered after 3 consecutive failures
- Status updates in real-time based on API responses

#### `provider_pricing`
```sql
CREATE TABLE provider_pricing (
    id SERIAL PRIMARY KEY,
    service VARCHAR(20) NOT NULL,            -- 'stt' or 'mt'
    provider VARCHAR(50) NOT NULL,           -- Provider name
    pricing_model VARCHAR(20) NOT NULL,      -- 'per_hour', 'per_minute', 'per_1k_tokens', 'per_1m_chars'
    unit_price NUMERIC(12,6) NOT NULL,       -- Price per unit
    currency VARCHAR(3) DEFAULT 'USD',
    notes TEXT,
    effective_date TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(service, provider, effective_date)
);

-- Indexes
CREATE INDEX idx_provider_pricing_service_provider ON provider_pricing(service, provider);
```

**Notes:**
- Stores pricing information for cost calculation
- Supports multiple pricing models (hourly, per-character, per-token)
- Historical pricing via effective_date

**Example Pricing:**
- Speechmatics: $0.08/hour
- Google Cloud Speech v2: $0.96/hour
- DeepL: $10/1M characters
- OpenAI GPT-4o-mini: $0.375/1k tokens

#### `quality_metrics`
```sql
CREATE TABLE quality_metrics (
    id BIGSERIAL PRIMARY KEY,
    room_id VARCHAR(255) NOT NULL,
    segment_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL,
    service_type VARCHAR(10) NOT NULL,       -- 'stt' or 'mt'
    language VARCHAR(10) NOT NULL,
    latency_ms INTEGER,
    wer FLOAT,                                -- Word Error Rate (if reference available)
    confidence FLOAT,                         -- Provider confidence score (0-1)
    diarization_speakers INTEGER,            -- Number of speakers detected
    fallback_used BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Indexes
CREATE INDEX idx_quality_metrics_room ON quality_metrics(room_id);
CREATE INDEX idx_quality_metrics_provider ON quality_metrics(provider);
CREATE INDEX idx_quality_metrics_timestamp ON quality_metrics(timestamp DESC);
```

**Notes:**
- Tracks performance metrics for quality analysis
- Enables provider performance comparison
- Used for optimizing routing decisions

---

## 🔌 API Endpoints

### Base URL
- Production: `https://livetranslator.pawelgawliczek.cloud`
- Local: `http://localhost:9003`

### API Structure
All API endpoints follow a consistent `/api/{resource}` pattern for better organization and maintainability:
- **Rooms**: `/api/rooms/*`
- **History**: `/api/history/*`
- **Costs**: `/api/costs/*`
- **Profile**: `/api/profile/*`
- **Guests**: `/api/guest/*`
- **Invites**: `/api/invites/*`
- **User History**: `/api/user/history/*`
- **Admin**: `/api/admin/*`
- **Budgets**: `/api/budgets/*`

**Note**: Authentication endpoints use `/auth/*` (without `/api/` prefix) as they are not RESTful resources but authentication flows.

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

### Room Endpoints (`/api/rooms`)

#### POST `/api/rooms`
Create a new room | Auth: Required | Request: `{"code": "my-room"}` (optional) | Response: `{id, code, owner_id, created_at}` | Errors: 400/401

#### GET `/api/rooms/{room_code}`
Get room details by room code | Auth: Required | Response: `{id, code, owner_id, created_at}` | Errors: 404/401

### Admin Analytics Endpoints (`/api/admin/*`)

#### GET `/api/admin/cost-analytics`
Get cost analytics with filtering | Auth: Admin | Query: `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&room_id=X&provider=Y` | Response: `{total_cost_usd, breakdown_by_provider, breakdown_by_pipeline, timeline}` | Errors: 401/403

#### GET `/api/admin/multi-speaker-overview`
Get multi-speaker translation cost matrix | Auth: Admin | Query: `?room_id=X&start_date=Y` | Response: `{rooms: [{room_id, speakers, translation_matrix, total_cost}]}` | Errors: 401/403

#### GET `/api/admin/top-cost-drivers`
Get top cost drivers | Auth: Admin | Query: `?period=day|week|month&limit=10` | Response: `{top_rooms, top_providers, cost_trends}` | Errors: 401/403

### Budget Endpoints (`/api/budgets/*`)

#### GET `/api/budgets`
List all budgets | Auth: Admin | Response: `[{id, period_type, budget_usd, alert_threshold_pct, is_active}]` | Errors: 401/403

#### POST `/api/budgets`
Create cost budget | Auth: Admin | Request: `{period_type: "monthly|weekly|daily", budget_usd, alert_threshold_pct: 80, critical_threshold_pct: 95}` | Response: `{id, ...}` | Errors: 400/401/403

#### PUT `/api/budgets/{budget_id}`
Update budget | Auth: Admin | Request: `{budget_usd?, alert_threshold_pct?}` | Response: `{id, ...}` | Errors: 400/401/403/404

#### DELETE `/api/budgets/{budget_id}`
Deactivate budget | Auth: Admin | Response: `{success: true}` | Errors: 401/403/404

#### GET `/api/budgets/{budget_id}/alerts`
Get budget alerts | Auth: Admin | Query: `?acknowledged=false` | Response: `[{id, alert_type, actual_cost_usd, percentage_used, triggered_at}]` | Errors: 401/403/404

### Cost Endpoints (`/api/costs/*`)

#### GET `/api/costs/room/{room_code}`
Get total costs for a room | Auth: Required | Response: `{total_cost_usd, breakdown: {stt: {mode, events, cost_usd}, mt: {...}}}` | Errors: 401/404

### History Endpoints (`/api/history/*`)

#### GET `/api/history/rooms`
Get list of rooms for authenticated user (user's own rooms + public rooms) | Auth: Required | Response: `[{id, code, created_at}]` | Errors: 401

#### GET `/api/history/room/{room_code}?target_lang={lang}`
Get conversation history with on-demand translation | Auth: Required | Query: `target_lang` (e.g., "en", "pl", "ar") | Response: `{room_code, segments: [{segment_id, speaker, text, lang, translation, ts_iso}]}` | Errors: 401/404

**Notes:**
- If translation doesn't exist in cache, it's generated on-demand
- Uses smart caching to avoid re-translating the same content

### Translation Endpoints

#### POST `/translate`
Translate text (synchronous) | Request: `{src, tgt, text}` | Response: `{text}` | Errors: 400

#### GET `/translate/stream?q={text}&src={src}&tgt={tgt}`
Stream translation results (Server-Sent Events) | Response: SSE stream | Errors: 400

### Health Endpoints

#### GET `/healthz`
Basic health check | Response: `{ok: true}` | Errors: 500

#### GET `/readyz`
Readiness check (verifies Redis, MT worker connectivity) | Response: `{ok: true}` | Errors: 500

#### GET `/metrics`
Prometheus metrics endpoint | Response: Prometheus text format | Errors: None

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

**Instant Result** (sent immediately when speech ends):
```json
{
  "type": "stt_final",
  "segment_id": 123,
  "revision": 0,
  "text": "Hello world",
  "lang": "en",
  "final": true,
  "processing": true,
  "speaker": "user@example.com",
  "ts_iso": "2025-10-20T12:00:00.789012"
}
```

**Quality Result** (sent after background refinement, if text improved):
```json
{
  "type": "stt_final",
  "segment_id": 123,
  "revision": 1,
  "text": "Hello world.",
  "lang": "en",
  "final": true,
  "processing": false,
  "speaker": "user@example.com",
  "ts_iso": "2025-10-20T12:00:01.234567"
}
```

**Fields:**
- `processing`: `true` = background refinement in progress, `false` = processing complete
- `revision`: Increments for quality updates (0 = instant, 1+ = refined)
- Quality result only sent if text differs from instant result

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

#### Presence Snapshot
Sent when a user connects or presence state changes. Contains complete participant list (idempotent).

```json
{
  "type": "presence_snapshot",
  "room_id": "room-123",
  "participants": [
    {
      "user_id": "456",
      "display_name": "john",
      "language": "en",
      "is_guest": false,
      "joined_at": "2025-10-24T12:00:00Z"
    }
  ],
  "language_counts": {
    "en": 2,
    "pl": 1
  },
  "timestamp": "2025-10-24T12:00:05Z"
}
```

**Frontend Display:** Updates participants panel and language flags in header

#### User Joined
Sent after 10-second grace period confirms user stayed in room.

```json
{
  "type": "user_joined",
  "room_id": "room-123",
  "triggered_by_user_id": "456",
  "participants": [...],
  "language_counts": {...},
  "timestamp": "2025-10-24T12:00:15Z"
}
```

**Frontend Display:** Toast notification: "🇬🇧 john joined with English"

#### User Left
Sent after 10-second grace period expires without reconnection.

```json
{
  "type": "user_left",
  "room_id": "room-123",
  "triggered_by_user_id": "456",
  "participants": [...],
  "language_counts": {...},
  "timestamp": "2025-10-24T12:15:20Z"
}
```

**Frontend Display:** Toast notification: "john left the room"

#### Language Changed
Sent when a user changes their language preference.

```json
{
  "type": "language_changed",
  "room_id": "room-123",
  "triggered_by_user_id": "456",
  "old_language": "en",
  "new_language": "ar",
  "participants": [...],
  "language_counts": {...},
  "timestamp": "2025-10-24T12:05:00Z"
}
```

**Frontend Display:** Toast notification: "🇪🇬 john changed to Arabic"

#### Set Language (Client → Server)
Sent when user changes their preferred language.

```json
{
  "type": "set_language",
  "language": "ar"
}
```

**Backend Actions:**
- Registers language with 15s TTL in Redis (`room:{room_id}:active_lang:{user_id}`)
- Triggers immediate language aggregation
- Updates presence state via PresenceManager
- Broadcasts `language_changed` event to all room participants
- Updates translation routing to include new language

---

### Active Language Tracking & Presence System

**Purpose:** Optimize translation costs by only translating to languages of active participants, while providing packet-loss resistant presence UI

**Dual-Layer Architecture:**

#### Layer 1: Translation Routing (Fast, Critical)
Used by MT router for determining which languages to translate to.

1. **Language Registration:** User language stored in Redis with 15s TTL
   - Key: `room:{room_id}:active_lang:{user_id}`
   - Value: ISO language code (e.g., "en", "pl", "ar")
   - TTL: 15 seconds (refreshed every 5s by status poll)

2. **Language Aggregation:** Active languages collected into set
   - Key: `room:{room_id}:target_languages`
   - Value: Set of active language codes
   - Updated on: user join, language change, status poll
   - Expiry: 30 seconds (safety)

3. **Translation Routing:** MT router reads `target_languages` set
   - Only translates to languages in the active set
   - Excludes source language from targets
   - Reduces unnecessary API calls and costs

4. **Automatic Cleanup:**
   - Language keys expire after 15s of inactivity
   - Status poll refreshes TTL every 5 seconds
   - User disconnect = no more polls = automatic removal

#### Layer 2: Presence UI (Debounced, User-Facing)
Managed by PresenceManager for packet-loss resistant user experience.

1. **Presence State:** User presence stored in Redis hash
   - Key: `room:{room_id}:presence_state`
   - Field: `user:{user_id}`
   - Value: JSON with display_name, language, joined_at, state

2. **Grace Period:** 10-second debounce for disconnect events
   - User disconnects → Marked as "disconnecting"
   - Timer set: `room:{room_id}:disconnect_timer:{user_id}` (10s TTL)
   - User reconnects within 10s → Silent, no notification
   - Timer expires → Broadcast "user_left" event

3. **Presence Events:** Broadcast via `presence_events` Redis channel
   - `presence_snapshot` - Complete participant list (idempotent)
   - `user_joined` - After confirming user stayed (post grace period)
   - `user_left` - After 10s grace period expires
   - `language_changed` - Immediate language change notification

4. **Background Cleanup:** PresenceManager cleanup task runs every 5s
   - Scans for expired disconnect timers
   - Removes users from presence state
   - Broadcasts final "user_left" events

**Frontend Display:**
- **Room Header:** Language flags with counts (e.g., "🇬🇧 2 🇵🇱 1 🇪🇬 1") + participants button
- **Participants Panel:** Collapsible sidebar showing all active participants with languages
- **Toast Notifications:** Auto-dismissing (5s) presence notifications with 15s debouncing
- **Welcome Banner:** Shows current participants when joining (10s auto-dismiss)
- **No Chat Spam:** System messages removed from chat transcript

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
- `routers/cost_budgets.py` - Budget management

### STT Router (`api/routers/stt/`)
**Container:** `stt_router`
**Purpose:** Multi-provider speech-to-text routing service with language-based provider selection

**Architecture:**
```
api/routers/stt/
├── router.py                    # Main routing logic
├── language_router.py           # Provider selection
├── streaming_manager.py         # Connection pooling
├── Backend Implementations:
├── speechmatics_backend.py      # Speechmatics API
├── google_v2_backend.py         # Google Cloud Speech v2
├── azure_backend.py             # Azure Speech Service
├── soniox_backend.py            # Soniox Budget API
└── openai_backend.py            # OpenAI Whisper (fallback)
```

**Workflow:**
1. Subscribes to `stt_input` Redis channel (receives audio chunks)
2. **Language-Based Routing:** Queries `stt_routing_config` table based on:
   - Language (pl-PL, ar-EG, en-US, etc.)
   - Mode (partial or final)
   - Quality tier (standard or budget)
4. **Provider Selection:** Returns primary + fallback providers from database
5. **Streaming Connection Management:**
   - Gets or creates persistent connection via StreamingManager
   - One WebSocket/gRPC connection per (room, provider) tuple
   - Reuses connection for entire conversation
6. **Audio Processing:**
   - Streaming providers: Send audio directly to WebSocket/gRPC
   - Batch providers: Accumulate audio, transcribe on audio_end
7. **Late Final Blocking:** 3-layer detection prevents duplicate text from late finals
8. **Publishes Results:** `stt_events` channel with partial/final events
10. **Cost Tracking:** Publishes to `cost_events` channel
11. **Health Monitoring:** Updates `provider_health` on success/failure

**Supported Providers:**

| Provider | Type | Streaming | Diarization | Cost/Hour | Best For |
|----------|------|-----------|-------------|-----------|----------|
| Speechmatics | WebSocket | ✓ | ✓ Speaker | $0.08 | Polish, English (ultra-fast) |
| Google Cloud v2 | gRPC | ✓ | ✓ Multi | $0.96 | Arabic, multi-language |
| Azure Speech | Push Stream | ✓ | ✓ Real-time | $1.00 | General purpose |
| Soniox | REST | ✗ | ✓ Basic | $0.015 | Budget tier |
| OpenAI Whisper | REST | ✗ | ✗ | $0.36 | Fallback |

**Key Features:**
- **Multi-Provider Support:** 5 STT providers with automatic selection
- **Language-Based Routing:** Database-driven provider selection per language
- **Quality Tiers:** Standard (best quality) vs Budget (cost-optimized)
- **Health Monitoring:** Automatic fallback after 3 consecutive failures
- **Connection Pooling:** Persistent WebSocket/gRPC connections per room
- **Late Final Blocking:** Time-based, threshold, and content-based detection
- **Conversation Context:** Tracks last 5 sentences for improved accuracy
- **Segment Tracking:** Redis-based synchronized counter
- **Cache Invalidation:** 5-minute TTL with instant Redis pub/sub updates
**Key Files:**
- `router.py` - Main STT routing logic with message processing
- `language_router.py` - Provider selection based on language/mode/tier
- `streaming_manager.py` - WebSocket/gRPC connection pooling
- `speechmatics_backend.py` - Speechmatics WebSocket implementation
- `google_v2_backend.py` - Google Cloud Speech v2 gRPC implementation
- `azure_backend.py` - Azure push audio stream implementation
- `soniox_backend.py` - Soniox REST API implementation
- `openai_backend.py` - OpenAI Whisper REST API (fallback)

**Environment Variables:**
- `STT_INPUT_CHANNEL=stt_input`
- `STT_OUTPUT_EVENTS=stt_events`
- `STT_QUALITY_TIER=standard` (or 'budget')
- `POSTGRES_DSN=postgresql://...`
- `REDIS_URL=redis://...`
- `SPEECHMATICS_API_KEY=...`
- `SPEECHMATICS_REGION=eu2`
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/creds.json`
- `GOOGLE_CLOUD_PROJECT=...`
- `AZURE_SPEECH_KEY=...`
- `AZURE_SPEECH_REGION=eastus`
- `SONIOX_API_KEY=...`
- `OPENAI_API_KEY=...`

**Provider Selection Logic:**
1. Query database: `SELECT * FROM stt_routing_config WHERE language=? AND mode=? AND quality_tier=?`
2. If not found, try wildcard: `WHERE language='*' AND mode=? AND quality_tier=?`
3. Check provider health: If primary is 'down', use fallback
4. Return provider configuration with JSONB config

**Performance Notes:**
- Streaming providers: 1.5-3s latency (real-time)
- Batch providers: 3-5s latency (post-processing)
- Connection pooling reduces overhead (no per-request auth)
- Cache reduces database queries (5-minute TTL + instant invalidation)
- Late final blocking prevents duplicate segments

### MT Router (`api/routers/mt/`)
**Container:** `mt_router`
**Purpose:** Multi-provider machine translation routing service with language-pair optimization

**Architecture:**
```
api/routers/mt/
├── router.py                    # Main routing logic
├── Backend Implementations:
├── deepl_backend.py             # DeepL API (European languages)
├── google_backend.py            # Google Cloud Translation
├── amazon_backend.py            # Amazon Translate
└── openai_backend.py            # OpenAI GPT-4o-mini (Arabic)
```

**Workflow:**
1. Subscribes to `stt_events` Redis channel
2. **Language-Pair Routing:** Queries `mt_routing_config` table based on:
   - Source language (en, pl, ar, etc.)
   - Target language (en, pl, ar, etc.)
   - Quality tier (standard or budget)
3. **Provider Selection:** Returns primary + fallback providers from database
4. **Translation Matrix:** Translates to all target languages in room
5. **Caching & Throttling:**
   - Partial translation caching (skip redundant API calls)
   - Arabic translation throttling (2s interval to reduce costs)
6. **Automatic Fallback:** If primary fails, try fallback provider
7. **Publishes Results:** `mt_events` channel with translation events
8. **Cost Tracking:** Publishes to `cost_events` channel (skips cached translations)
9. **Health Monitoring:** Updates `provider_health` on success/failure

**Supported Providers:**

| Provider | Type | Best For | Cost Model | Pricing |
|----------|------|----------|------------|---------|
| DeepL | REST API | European languages (PL, EN, ES, FR, DE, IT, PT, RU) | Per character | $10/1M chars |
| Google Cloud Translation | REST API | Multi-language, fallback | Per character | $20/1M chars |
| Amazon Translate | REST API | Multi-language, budget | Per character | $15/1M chars |
| OpenAI GPT-4o-mini | Chat API | Arabic dialect (Egyptian), high-quality | Per token | $0.375/1k tokens |

**Language-Pair Routing Examples:**
- **Polish ↔ English:** DeepL (primary) → Azure Translator (fallback)
- **English ↔ Arabic:** OpenAI (primary) → Google Translate (fallback)
- **Spanish ↔ French:** DeepL (primary) → Azure Translator (fallback)
- **Budget tier (any pair):** Azure Translator → Google Translate

**Key Features:**
- **Multi-Provider Support:** 4 MT providers with automatic selection
- **Language-Pair Routing:** Database-driven provider selection per language pair
- **Quality Tiers:** Standard (best quality) vs Budget (cost-optimized)
- **Health Monitoring:** Automatic fallback after consecutive failures
- **Partial Translation Caching:** Skips re-translating unchanged partial text
- **Arabic Throttling:** 2-second interval to reduce GPT-4o costs
- **Translation Matrix:** Every participant gets all room languages
- **Context Support:** DeepL supports context for improved quality
- **Dialect Optimization:** OpenAI GPT-4o-mini optimized for Egyptian Arabic (Masri)

**Key Files:**
- `router.py` - Main MT routing logic with caching and throttling
- `deepl_backend.py` - DeepL API integration
- `google_backend.py` - Google Cloud Translation API
- `amazon_backend.py` - Amazon Translate with AWS Signature v4 auth
- `openai_backend.py` - OpenAI GPT-4o-mini with Arabic dialect prompts

**Environment Variables:**
- `STT_EVENTS_CHANNEL=stt_events`
- `MT_OUTPUT_CHANNEL=mt_events`
- `COST_TRACKING_CHANNEL=cost_events`
- `POSTGRES_DSN=postgresql://...`
- `REDIS_URL=redis://...`
- `DEEPL_API_KEY=...`
- `GOOGLE_TRANSLATE_API_KEY=...`
- `AWS_ACCESS_KEY_ID=...`
- `AWS_SECRET_ACCESS_KEY=...`
- `AWS_REGION=us-east-1`
- `OPENAI_API_KEY=...`
- `OPENAI_MT_MODEL=gpt-4o-mini`
- `ARABIC_THROTTLE_SECONDS=2.0`

**Provider Selection Logic:**
1. Query database: `SELECT * FROM mt_routing_config WHERE src_lang=? AND tgt_lang=? AND quality_tier=?`
2. Try partial wildcards: `(src_lang, *, tier)`, `(*, tgt_lang, tier)`, `(*, *, tier)`
3. Check provider health: If primary is 'down', use fallback
4. Return provider configuration

**Cost Optimization:**
- **Caching:** Partial translations cached, skip redundant API calls
- **Throttling:** Arabic translations limited to 2s intervals
- **Quality Tiers:** Budget tier uses cheaper providers
- **Provider Selection:** Best provider per language pair (DeepL for European, Google for others)

**Performance Notes:**
- DeepL latency: 100-300ms
- Google Translate latency: 200-500ms
- OpenAI GPT-4o-mini latency: 500-1500ms
- Caching reduces API calls by ~30-40% for partial translations
- Arabic throttling reduces costs by ~50% for rapid speech

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

## 🌍 Internationalization (i18n)

### Overview
LiveTranslator supports **12 languages** with complete UI translations using i18next. All pages and components are fully translated, providing a native experience for users worldwide.

### Supported Languages
1. 🇬🇧 **English (en)** - English
2. 🇵🇱 **Polski (pl)** - Polish
3. 🇪🇸 **Español (es)** - Spanish
4. 🇫🇷 **Français (fr)** - French
5. 🇩🇪 **Deutsch (de)** - German
6. 🇸🇦 **العربية (ar)** - Arabic (with RTL support)
7. 🇮🇹 **Italiano (it)** - Italian
8. 🇵🇹 **Português (pt)** - Portuguese
9. 🇷🇺 **Русский (ru)** - Russian
10. 🇨🇳 **中文 (zh)** - Chinese (Simplified)
11. 🇯🇵 **日本語 (ja)** - Japanese
12. 🇰🇷 **한국어 (ko)** - Korean

### Translation System Architecture

```
web/src/
├── i18n.js                    # i18next configuration
├── locales/                   # Translation files
│   ├── en.json               # English (source)
│   ├── pl.json               # Polish
│   ├── es.json               # Spanish
│   ├── fr.json               # French
│   ├── de.json               # German
│   ├── ar.json               # Arabic
│   ├── it.json               # Italian
│   ├── pt.json               # Portuguese
│   ├── ru.json               # Russian
│   ├── zh.json               # Chinese
│   ├── ja.json               # Japanese
│   └── ko.json               # Korean
├── utils/
│   └── languageSync.js       # Language synchronization utilities
└── components/
    └── LanguageSelector.jsx  # Language selector dropdown
```

### Translation Coverage

**All pages are fully translated:**
- Landing Page
- Login/Signup Pages
- Rooms Management Page
- Profile Page (all tabs: Settings, Account, History)
- Room Chat Interface

**Translation sections:**
- `common` - Common UI elements (buttons, labels, states)
- `nav` - Navigation items
- `auth` - Authentication pages
- `rooms` - Room management
- `room` - Live chat interface
- `profile` - User profile settings
- `settings` - Application settings
- `errors` - Error messages
- `languages` - Language names
- `landing` - Landing page
- `joinPage` - Join room via invite
- `profileTabs` - Profile tab sections

### Language Synchronization

The application uses a unified language system that syncs across:
1. **UI Language**: Controls all interface text
2. **User Profile**: Stores preferred language in database
3. **LocalStorage**: Persists language selection
4. **Translation Language**: Auto-sets target language for real-time translation

**Key Features:**
- Language changes are immediate (no page reload)
- Language preference synced with user profile (if logged in)
- Falls back to browser language on first visit
- Maintains language selection across sessions

### Usage in Components

```jsx
import { useTranslation } from "react-i18next";

function MyComponent() {
  const { t } = useTranslation();

  return (
    <div>
      <h1>{t('common.title')}</h1>
      <button>{t('common.submit')}</button>
    </div>
  );
}
```

### Adding New Translations

1. Add translation key to `/web/src/locales/en.json`
2. Copy the key to all other language files
3. Translate the values for each language
4. Use in component: `{t('section.key')}`
5. Rebuild web container: `docker compose build web`

### Language Detection

i18next automatically detects language from:
1. LocalStorage (`lt_user_language` key)
2. Browser language settings
3. Falls back to English if not found

## 🎨 Frontend Structure

### Technology Stack
- React 18
- Vite (build tool)
- React Router v6
- i18next + react-i18next (internationalization)
- i18next-browser-languagedetector (language detection)
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
    ├── pages/
    │   ├── LandingPage.jsx      # Home page, token redirect
    │   ├── LoginPage.jsx        # Login + Google OAuth
    │   ├── SignupPage.jsx       # Registration
    │   ├── RoomsPage.jsx        # Room list, create room
    │   ├── RoomPage.jsx         # Main chat interface
    │   ├── ProfilePage.jsx      # User profile with tabs
    │   ├── AdminCostAnalyticsPage.jsx # Admin analytics
    │   └── AdminMultiSpeakerPage.jsx # Multi-speaker analytics
    └── components/
        └── admin/
            ├── BudgetTracker.jsx      # Budget monitoring
            ├── MultiSpeakerOverviewCard.jsx # Translation matrix
            └── TopCostDrivers.jsx     # Cost drivers
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
- Real-time transcription display with speaking indicators
- Translation display
- Push-to-talk mode
- Language selection
- History loading
- Auto-scroll
- Active speaker tracking with real-time indicators

**Key State:**
```javascript
- status: 'idle' | 'connecting' | 'streaming'
- vadStatus: Current VAD status text
- lines: Array of [segmentId, {source, translation}]
- sourceLang, targetLang: Selected languages
- pushToTalk: Boolean for PTT mode
- activeSpeakers: Map<speaker, {segmentId, timestamp}> - Tracks who is speaking
```

**Key Refs:**
```javascript
- wsRef: WebSocket connection
- segsRef: Map of all segments (s-123, t-123)
- vadRef: Voice Activity Detection instance
- isRecordingRef: Recording state
```

**Visual Feedback System:**

The UI provides real-time visual feedback during speech transcription:

1. **Speaking Status Indicator**
   - Appears immediately when someone starts speaking
   - Shows pulsing card with spinning microphone icon 🎤
   - Displays: "👤 [User] is speaking..."
   - Pulses to draw attention (fade in/out animation)

2. **Partial Transcriptions**
   - Color: Light gray (#bbb) - indicates tentative text
   - Spinning blue ellipsis (⋯) - shows active transcription
   - Updates in real-time as speech continues

3. **Final Transcriptions**
   - Color: Bright white (#fff) - indicates confirmed text
   - Shows "⚙️ Refining quality..." during background processing
   - Localized processing messages in 28 languages

4. **Color Hierarchy**
   ```
   Partials (#bbb, lighter)  →  Less prominent, temporary
   Finals (#fff, bright)     →  Most visible, confirmed
   ```

**Visual Flow:**
```
User starts speaking
  ↓
🎤 Pulsing "is speaking..." indicator appears
  ↓
First partial → Light gray text with spinning blue ⋯
  ↓
More partials → Text updates, stays light gray with spinner
  ↓
Final arrives → "is speaking" indicator disappears
  ↓
Text turns WHITE + ⚙️ "Refining quality..." message
  ↓
Complete! Final remains bright white (most visible)
```

**Animations:**
- `@keyframes spin` - Rotates spinner icons continuously
- `@keyframes pulse` - Fades speaking indicator (opacity 1 ↔ 0.6)

#### `AdminCostAnalyticsPage.jsx`
Admin cost analytics dashboard with:
- Date range filtering
- Per-room cost breakdowns
- Provider usage charts
- Cost trends over time
- Export capabilities

#### `AdminMultiSpeakerPage.jsx`
Multi-speaker translation analytics with:
- Translation cost matrix visualization
- N×(N-1) routing breakdown
- Speaker-to-speaker cost mapping
- Room-level aggregation

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

### ⚠️ CRITICAL: Docker Build Verification

**ALWAYS verify files exist before `docker compose up --build`!**

This is a **common issue** that causes stuck builds with no error messages:

```bash
# ❌ WRONG - Can fail silently if files missing
docker compose up -d --build api

# ✅ CORRECT - Verify files first, then build
ls -la api/main.py api/requirements.txt
docker compose up -d --build api
```

**Common missing files that break builds:**
- `api/requirements.txt`
- `workers/stt/requirements.txt`
- `workers/mt/requirements.txt`
- `web/package.json`
- `Dockerfile` in service directories

**Symptoms:** Build hangs indefinitely, no errors, container shows "created" but never "running"

**Recovery:** `docker compose down` → verify files → rebuild

---

### Prerequisites
- Docker & Docker Compose
- Git
- OpenAI API key

### Database & Redis Connections

**PostgreSQL (Production):**
- **Connection String:** `postgresql://lt_user:$POSTGRES_PASSWORD@postgres:5432/livetranslator`
- **Host:** `postgres` (container) / `localhost` (host)
- **User:** `lt_user`
- **Password:** `$POSTGRES_PASSWORD` (from `.env`)
- **Database:** `livetranslator`
- **Port:** `5432`

**Redis (Production):**
- **Connection String:** `redis://redis:6379/5`
- **Host:** `redis` (container) / `localhost` (host)
- **Port:** `6379`
- **Database:** `5` (application database)

### Environment Variables

Create `.env` file in project root:

```bash
# Database
POSTGRES_USER=lt_user
POSTGRES_PASSWORD=<your-secure-password>
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

Create `$SECRETS_DIR/` directory:

```bash
mkdir -p $SECRETS_DIR

# JWT secret (generate random string)
echo "your-secret-key-here" > $SECRETS_DIR/jwt_secret

# Google OAuth credentials (from Google Cloud Console)
echo "your-client-id" > $SECRETS_DIR/google_oauth_client_id.txt
echo "your-client-secret" > $SECRETS_DIR/google_oauth_client_secret.txt
```

### Running Locally

```bash
# Start all services
cd $PROJECT_ROOT
docker compose up -d

# View logs
docker compose logs -f

# Check specific service
docker compose logs -f api
docker compose logs -f stt_router
docker compose logs -f mt_router

# Rebuild after code changes (VERIFY FILES FIRST!)
ls -la api/main.py api/requirements.txt  # Verify files exist
docker compose up -d --build api
docker compose up -d --build --no-cache web  # Always --no-cache for web!

# Stop all services
docker compose down
```

### Database Operations

```bash
# Connect to database (production credentials)
docker compose exec -T postgres psql -U lt_user -d livetranslator

# With password in command
PGPASSWORD=$POSTGRES_PASSWORD docker compose exec -T postgres psql -U lt_user -d livetranslator

# Run SQL query
docker compose exec -T postgres psql -U lt_user -d livetranslator -c "SELECT * FROM users;"

# Apply migration
cat migrations/025_cost_budgets.sql | PGPASSWORD=$POSTGRES_PASSWORD docker compose exec -T postgres psql -U lt_user -d livetranslator

# Backup database
docker compose exec postgres pg_dump -U lt_user livetranslator > backup.sql

# Restore database
cat backup.sql | docker compose exec -T postgres psql -U lt_user -d livetranslator
```

### Redis Monitoring

```bash
# Monitor all Redis activity
docker compose exec redis redis-cli -n 5 MONITOR

# Subscribe to specific channel
docker compose exec redis redis-cli -n 5 SUBSCRIBE stt_events
docker compose exec redis redis-cli -n 5 SUBSCRIBE mt_events
docker compose exec redis redis-cli -n 5 SUBSCRIBE cost_events
docker compose exec redis redis-cli -n 5 SUBSCRIBE presence_events

# Check Redis keys
docker compose exec redis redis-cli -n 5 KEYS "room:*"
docker compose exec redis redis-cli -n 5 GET "room:test-room:segment_counter"
docker compose exec redis redis-cli -n 5 SMEMBERS "room:test-room:target_languages"
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
3. Rebuild web container: `docker compose up -d --build --no-cache web`

#### Modifying Database Schema

1. Update `api/models.py`
2. Create migration script in `migrations/###_name.sql`
3. Apply migration via psql
4. Restart services: `docker compose restart api persistence`

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
2. Set up secrets in `$SECRETS_DIR/`
3. Configure Google OAuth redirect URI
4. Apply database migrations (`migrations/*.sql`)
6. Start services: `docker compose up -d`
7. Check logs: `docker compose logs -f`
8. Verify health: `curl https://livetranslator.../healthz`
9. Test WebSocket: Open app in browser

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
- `$PROJECT_ROOT/data/pg` - PostgreSQL data
- `$PROJECT_ROOT/data/redis` - Redis data

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

## 🧪 Testing

See `.claude/test-strategy.md` for complete testing documentation.

**Quick Summary:**
- **Total Tests:** 733 tests (722 passing, 11 skipped)
- **Test Coverage:** 98.5% across all test suites
- **Duration:** ~32 seconds (Python), 5-15 minutes (Playwright)

**Test Categories:**
- Unit Tests: 199 tests (100% pass rate)
- Integration Tests: 282 tests (98%+ pass rate)
- E2E Tests (Python): 79 tests (100% pass rate)
- E2E Tests (Playwright): 109 tests

---

## 📝 Development Process (MANDATORY)

### Feature Development Workflow

**For ALL new features, follow this process strictly:**

#### 1. Business Analyst (BA) - Requirements Validation (5-10 min)
**Questions to Answer:**
- Are acceptance criteria clear and testable?
- What are the edge cases?
- How do we measure success?
- Are there regulatory requirements (GDPR, data privacy)?
- What's the user impact if this fails?

**Business Decisions (MANDATORY):**
- **Identify ALL business decisions** in the feature (pricing, policies, thresholds, vendors)
- **Classify each decision** by impact:
  - 🔴 **Critical**: Revenue, legal, security (fail-open/closed, retry policies, vendor selection)
  - ⚠️ **Medium**: UX, branding, costs (email tone, retention periods, alert thresholds)
  - ℹ️ **Minor**: Technical defaults (connection pools, cache TTL, rate limits)
- **Present Critical + Medium decisions to stakeholder for approval**
- **Document decisions made** and who approved them

**Example Critical Decisions:**
- Fail-open vs fail-closed when external service is down? (Reliability vs UX)
- Use SendGrid ($15/mo) or AWS SES ($0.10/1k)? (Recurring cost)
- Grace period: 3 days or 7 days? (User retention vs data retention)

**E2E Test Case Design (MANDATORY):**
- **Identify all critical and major user paths** affected by this feature
- **Design E2E test scenarios** covering:
  - Happy path (primary user journey)
  - Error cases (provider failures, invalid input, auth issues)
  - Edge cases (first-time users, concurrent sessions)
- **Specify test data requirements** (test users, room states, provider configs)
- **Document expected outcomes** for each scenario

**Deliverable**: Validated user story + business decisions document + E2E test case design

#### 2. Software Architect - Technical Design (10-20 min)
**Before Implementation:**
- Database schema changes (migrations needed?)
- API endpoint design (REST conventions, auth, rate limiting)
- Security analysis (OWASP top 10, auth, input validation)
- Scalability considerations (caching, indexes, connection pooling)
- Integration points with existing code
- Code snippets for critical parts (DB queries, WebSocket handlers, etc.)

**Deliverable**: Technical design document with security review

#### 3. Project Manager - Approval Gate (5 min)
- Review architect's design
- Present to stakeholders for approval
- Identify risks and get sign-off
- **No coding starts without approval**

#### 4. Full-Stack Engineer - Implementation
- Follow architect's design exactly
- Use provided code snippets
- Add comprehensive error handling
- Write integration tests

**Deliverable**: Working code + tests

#### 5. Software Architect - Post-Implementation Review (10-15 min)
**After Implementation (MANDATORY):**
- Review all code changes
- Verify design was followed
- Check for security issues
- Identify performance problems
- Database connection leaks?
- Race conditions?
- Error handling complete?

**Deliverable**: Architecture review report (APPROVED / NEEDS CHANGES / REJECTED)

#### 6. QA Engineer - Testing
**Integration Tests (Backend):**
- Test service integration with real Redis/PostgreSQL
- Mock external APIs only
- Cover edge cases and error handling

**E2E Tests (Full Stack) - MANDATORY:**
- **Implement E2E test cases designed by BA** (from Step 1)
- **All critical and major user paths MUST have working E2E coverage**
- Use Playwright for browser-based flows
- Use pytest for API-only flows
- Verify end-to-end user journeys work as expected

**Manual Testing Checklist:**
- Visual verification of UI changes
- Cross-browser compatibility (if UI changes)
- Performance testing (if applicable)

**Security Testing (if applicable):**
- OWASP top 10 validation
- Auth/authorization edge cases
- Input validation and injection prevention

**Deliverable**: Test report with pass/fail status + E2E test coverage for all critical paths

#### 7. Project Manager - Final Report
- Summary of what was built
- Test results
- Known issues (if any)
- Deployment checklist

---

### Why This Process Matters

**Real Example (US-005, US-006, US-007)**:

**Without Process**:
- ❌ 3 critical bugs introduced (DB connection leak, missing import, no grace period enforcement)
- ❌ 50 minutes total (30 min implementation + 20 min fixes)
- ❌ Production-blocking issues

**With Process**:
- ✅ Architect catches issues in design phase
- ✅ 40 minutes total (10 min design + 25 min implementation + 5 min review)
- ✅ Zero critical bugs
- ✅ Production-ready on first attempt

**Time Saved**: 10 minutes + zero rework + confidence

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
9. **Always --no-cache for web** - Docker caching breaks Vite builds

---

## 📚 Additional Resources

- FastAPI Docs: https://fastapi.tiangolo.com/
- React Docs: https://react.dev/
- OpenAI Whisper API: https://platform.openai.com/docs/guides/speech-to-text
- OpenAI GPT-4o-mini: https://platform.openai.com/docs/models/gpt-4o-mini
- Redis PubSub: https://redis.io/docs/manual/pubsub/
- PostgreSQL Docs: https://www.postgresql.org/docs/

---

## 📝 Changelog

### Version 1.5.0 (2025-11-06)
**Admin Analytics**

**Admin Analytics:**
- Cost analytics dashboard with date filtering and room breakdown
- Multi-speaker translation cost matrix (N×(N-1) routing visualization)
- Top cost drivers analysis (rooms, providers, trends)
- Budget tracking system with configurable alerts (80%/95%/100%)
- Budget alert log with acknowledgment tracking
- Provider usage reports across 9 STT/MT providers
- Cost trend visualization over time

**Database Changes:**
- New tables: `cost_budgets`, `budget_alerts`
- Enhanced `room_costs` table with provider-specific tracking

**Frontend Enhancements:**
- New pages: `AdminCostAnalyticsPage`, `AdminMultiSpeakerPage`
- New components: `BudgetTracker`, `MultiSpeakerOverviewCard`, `TopCostDrivers`

**API Endpoints Added:**
- `/api/admin/cost-analytics` - Admin cost reports
- `/api/admin/multi-speaker-overview` - Translation matrix
- `/api/admin/top-cost-drivers` - Cost driver analysis
- `/api/budgets/*` - Budget management

### Version 1.4.0 (2025-10-24)
**Presence System Rewrite with Packet-Loss Resistance**

**Presence System:**
- Complete rewrite of user presence tracking with dual-layer architecture
- Added PresenceManager with Redis-backed state management
- Implemented 10-second grace period for disconnect debouncing
- Packet-loss resistant notifications (no spam during network instability)
- Silent reconnection handling (no notification if reconnect within 10s)
- Background cleanup task for expired disconnections

**Frontend Enhancements:**
- New NotificationToast component with auto-dismiss (5s) and debouncing (10s)
- New ParticipantsPanel sidebar showing all active participants
- Language flags with counts in room header (e.g., "🇬🇧 2 🇵🇱 1")
- Welcome banner on join showing current participants (10s auto-dismiss)
- Removed system messages from chat transcript (now use toast notifications)
- Presence events now idempotent (include full participant list)

**Backend Changes:**
- New `presence_events` Redis channel for presence updates
- Separation of concerns: Translation routing (fast) vs Presence UI (debounced)
- PresenceManager cleanup task runs every 5 seconds
- Updated WebSocket protocol with new presence event types
- Removed `active_languages` from status endpoint response

**Key Benefits:**
- No notification flood during rapid connect/disconnect
- Graceful handling of browser refresh and network interruptions
- Better UX with dedicated presence UI (not mixed with chat)
- Translation routing preserved exactly as-is (critical path untouched)

### Version 1.3.0 (2025-10-23)
**Multi-Provider Architecture & Language-Based Routing**

**STT Enhancements:**
- Added 5 STT providers: Speechmatics, Google Cloud Speech v2, Azure Speech, Soniox, OpenAI Whisper
- Implemented language-based routing via `stt_routing_config` database table
- Added StreamingManager for persistent WebSocket/gRPC connection pooling
- Implemented 3-layer late final blocking (time-based, threshold, content-based)
- Added provider health monitoring with automatic fallback
- Support for quality tiers: standard (best quality) vs budget (cost-optimized)
- Native WebSocket for Speechmatics, gRPC for Google v2, push streams for Azure

**MT Enhancements:**
- Added 4 MT providers: DeepL, Google Cloud Translation, Amazon Translate, OpenAI GPT-4o-mini
- Implemented language-pair routing via `mt_routing_config` database table
- DeepL optimization for European language pairs (PL, EN, ES, FR, DE, IT, PT, RU)
- OpenAI GPT-4o-mini optimization for Egyptian Arabic (Masri) dialect
- Partial translation caching (reduces API calls by 30-40%)
- Arabic translation throttling (2s interval, reduces costs by 50%)
- AWS Signature v4 authentication for Amazon Translate

**Database Schema:**
- New tables: `stt_routing_config`, `mt_routing_config`, `provider_health`, `provider_pricing`, `quality_metrics`
- Enhanced `segments` table: Added `stt_provider`, `latency_ms` columns
- Enhanced `translations` table: Added `mt_provider`, `context_used`, `glossary_used` columns
- Enhanced `room_costs` table: Added `provider` column for multi-provider cost tracking

**Infrastructure:**
- 5-minute configuration cache with instant Redis pub/sub invalidation
- Automatic provider fallback after 3 consecutive failures
- Per-provider pricing configuration for accurate cost tracking
- Quality metrics collection for performance analysis

### Version 1.2.0 (2025-10-22)
- Added comprehensive test suite with 93% coverage
- UI speaking indicators with real-time feedback
- Segment tracking improvements with Redis-based synchronization

---

**Last Updated:** 2026-03-03
**LiveTranslator** - Open Source Real-Time Translation Platform

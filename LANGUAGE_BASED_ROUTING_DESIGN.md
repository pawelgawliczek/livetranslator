# Language-Based STT/MT Routing Design

**Date:** 2025-10-22
**Status:** Design Phase
**Purpose:** Replace per-room configuration with global language-based routing

---

## 🎯 Core Concept

**OLD (Phase 0.1-0.3 - Being Removed):**
- ❌ Per-room STT provider overrides (`rooms.stt_partial_provider`, `rooms.stt_final_provider`)
- ❌ Admin can override per room
- ❌ Simple mode selection (openai_chunked, deepgram, elevenlabs, local, none)

**NEW (Quality-Focused Architecture):**
- ✅ **Global language-based routing**
- ✅ **Separate configuration for partial and final modes per language**
- ✅ **Automatic provider selection based on detected/selected language**
- ✅ **No per-room overrides** (simplifies admin and improves consistency)

---

## 📊 Configuration Matrix

### **STT Configuration Dimensions**

| Dimension | Values | Description |
|-----------|--------|-------------|
| **Language** | pl-PL, ar-EG, en-US, en-GB, es-ES, fr-FR, de-DE, etc. | Detected or user-selected language |
| **Mode** | partial, final | Partial (real-time) vs Final (post-speech) |
| **Quality Tier** | standard, budget | Standard quality vs Budget mode |

### **Example Configuration**

#### **Polish (pl-PL)**
| Mode | Quality Tier | Primary | Fallback | Config |
|------|-------------|---------|----------|--------|
| Partial | Standard | Speechmatics | Google v2 | `diarization=true, max_delay=1500ms` |
| Final | Standard | Speechmatics | Google v2 | `diarization=true` |
| Partial | Budget | Soniox | Google v2 | `diarization=true` |
| Final | Budget | Soniox | Google v2 | `diarization=true` |

#### **Arabic (ar-EG)**
| Mode | Quality Tier | Primary | Fallback | Config |
|------|-------------|---------|----------|--------|
| Partial | Standard | Google v2 | Azure Speech | `diarization=true, stability=0.8` |
| Final | Standard | Google v2 | Azure Speech | `diarization=true` |
| Partial | Budget | Soniox | Google v2 | `diarization=true` |
| Final | Budget | Soniox | Google v2 | `diarization=true` |

#### **English (en-US, en-GB)**
| Mode | Quality Tier | Primary | Fallback | Config |
|------|-------------|---------|----------|--------|
| Partial | Standard | Speechmatics | Google v2 | `diarization=true, max_delay=1500ms` |
| Final | Standard | Speechmatics | Google v2 | `diarization=true` |
| Partial | Budget | Soniox | Google v2 | `diarization=true` |
| Final | Budget | Soniox | Google v2 | `diarization=true` |

---

## 🗄️ Database Schema

### **New Schema (Replaces Old)**

```sql
-- Remove old per-room columns
ALTER TABLE rooms DROP COLUMN IF EXISTS stt_partial_provider;
ALTER TABLE rooms DROP COLUMN IF EXISTS stt_final_provider;

-- New global language-based routing configuration
CREATE TABLE stt_routing_config (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,          -- pl-PL, ar-EG, en-US, en-GB, es-ES, etc.
    mode VARCHAR(10) NOT NULL,              -- 'partial' or 'final'
    quality_tier VARCHAR(20) NOT NULL,      -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- speechmatics, google_v2, azure, soniox
    provider_fallback VARCHAR(50),          -- Fallback if primary fails
    config JSONB,                           -- Provider-specific config
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(language, mode, quality_tier)    -- One config per language/mode/tier combination
);

CREATE INDEX idx_stt_routing_language ON stt_routing_config(language);
CREATE INDEX idx_stt_routing_mode ON stt_routing_config(mode);

-- MT routing configuration (language pairs)
CREATE TABLE mt_routing_config (
    id SERIAL PRIMARY KEY,
    src_lang VARCHAR(10) NOT NULL,          -- Source language (en, pl, ar, etc.)
    tgt_lang VARCHAR(10) NOT NULL,          -- Target language (en, pl, ar, etc.)
    quality_tier VARCHAR(20) NOT NULL,      -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- deepl, azure_translator, google_translate
    provider_fallback VARCHAR(50),          -- Fallback if primary fails
    config JSONB,                           -- Provider-specific config
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(src_lang, tgt_lang, quality_tier)  -- One config per pair/tier
);

CREATE INDEX idx_mt_routing_lang_pair ON mt_routing_config(src_lang, tgt_lang);

-- Provider health status (for automatic fallback)
CREATE TABLE provider_health (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,          -- speechmatics, google_v2, azure, etc.
    service_type VARCHAR(10) NOT NULL,      -- 'stt' or 'mt'
    status VARCHAR(20) NOT NULL,            -- 'healthy', 'degraded', 'down'
    last_check TIMESTAMP NOT NULL,
    consecutive_failures INTEGER DEFAULT 0,
    last_error TEXT,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(provider, service_type)
);

CREATE INDEX idx_provider_health_status ON provider_health(provider, status);
```

### **Seed Data**

```sql
-- STT Routing Configuration (Standard Tier)
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Polish
    ('pl-PL', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('pl-PL', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced"}'),

    -- Arabic (Egyptian)
    ('ar-EG', 'partial', 'standard', 'google_v2', 'azure',
     '{"diarization": true, "stability_threshold": 0.8}'),
    ('ar-EG', 'final', 'standard', 'google_v2', 'azure',
     '{"diarization": true}'),

    -- English (US)
    ('en-US', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('en-US', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced"}'),

    -- English (GB)
    ('en-GB', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('en-GB', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced"}'),

    -- Generic fallback for other languages
    ('*', 'partial', 'standard', 'google_v2', 'azure',
     '{"diarization": true, "stability_threshold": 0.8}'),
    ('*', 'final', 'standard', 'google_v2', 'azure',
     '{"diarization": true}');

-- STT Routing Configuration (Budget Tier)
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('*', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}');

-- MT Routing Configuration (Standard Tier)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Polish ↔ English (DeepL best)
    ('pl', 'en', 'standard', 'deepl', 'azure_translator', '{}'),
    ('en', 'pl', 'standard', 'deepl', 'azure_translator', '{}'),

    -- English ↔ European languages (DeepL)
    ('en', 'es', 'standard', 'deepl', 'azure_translator', '{}'),
    ('en', 'fr', 'standard', 'deepl', 'azure_translator', '{}'),
    ('en', 'de', 'standard', 'deepl', 'azure_translator', '{}'),
    ('en', 'it', 'standard', 'deepl', 'azure_translator', '{}'),
    ('en', 'pt', 'standard', 'deepl', 'azure_translator', '{}'),

    -- Polish ↔ European languages (DeepL)
    ('pl', 'es', 'standard', 'deepl', 'azure_translator', '{}'),
    ('pl', 'fr', 'standard', 'deepl', 'azure_translator', '{}'),
    ('pl', 'de', 'standard', 'deepl', 'azure_translator', '{}'),

    -- English/Polish ↔ Non-European (Azure best)
    ('en', 'ar', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('en', 'ru', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('en', 'zh', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('en', 'ja', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('en', 'ko', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'ar', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'ru', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'zh', 'standard', 'azure_translator', 'google_translate', '{}'),

    -- Reverse pairs
    ('ar', 'en', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('ru', 'en', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('zh', 'en', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('ja', 'en', 'standard', 'azure_translator', 'google_translate', '{}'),
    ('ko', 'en', 'standard', 'azure_translator', 'google_translate', '{}'),

    -- Generic fallback
    ('*', '*', 'standard', 'azure_translator', 'google_translate', '{}');

-- MT Routing Configuration (Budget Tier)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', '*', 'budget', 'azure_translator', 'google_translate', '{}');

-- Provider Health Initialization
INSERT INTO provider_health (provider, service_type, status, last_check) VALUES
    ('speechmatics', 'stt', 'healthy', NOW()),
    ('google_v2', 'stt', 'healthy', NOW()),
    ('azure', 'stt', 'healthy', NOW()),
    ('soniox', 'stt', 'healthy', NOW()),
    ('deepl', 'mt', 'healthy', NOW()),
    ('azure_translator', 'mt', 'healthy', NOW()),
    ('google_translate', 'mt', 'healthy', NOW());
```

---

## 🏗️ Architecture Changes

### **Old Flow (Per-Room)**
```
Audio → API → Redis → STT Router
                          ↓
               Check room.stt_partial_provider
                          ↓
              If NULL → Check system_settings
                          ↓
              Route to provider (openai, local, deepgram)
```

### **New Flow (Language-Based)**
```
Audio → API → Redis → STT Router
                          ↓
               Detect language (from room settings or audio)
                          ↓
               Query stt_routing_config(language, mode='partial', tier)
                          ↓
               Get provider + config (e.g., speechmatics + diarization)
                          ↓
               Check provider_health
                          ↓
               If unhealthy → Use fallback provider
                          ↓
               Route to provider with language-specific config
```

### **Key Components to Update**

#### **1. Settings Fetcher → Language Router**
**Old:** `api/routers/stt/settings_fetcher.py`
- Fetches room-specific settings
- Falls back to global defaults
- Returns (partial_mode, final_mode)

**New:** `api/routers/stt/language_router.py`
```python
async def get_stt_provider_for_language(
    language: str,
    mode: str,  # 'partial' or 'final'
    quality_tier: str = 'standard'
) -> Dict[str, Any]:
    """
    Get STT provider configuration for a specific language and mode.

    Returns:
    {
        'provider': 'speechmatics',
        'fallback': 'google_v2',
        'config': {
            'diarization': True,
            'max_delay': 0.4,
            'operating_point': 'enhanced'
        }
    }
    """
    # Query stt_routing_config table
    config = await db.fetchrow("""
        SELECT provider_primary, provider_fallback, config
        FROM stt_routing_config
        WHERE language = $1 AND mode = $2 AND quality_tier = $3 AND enabled = TRUE
        LIMIT 1
    """, language, mode, quality_tier)

    # Fallback to wildcard if language not found
    if not config:
        config = await db.fetchrow("""
            SELECT provider_primary, provider_fallback, config
            FROM stt_routing_config
            WHERE language = '*' AND mode = $2 AND quality_tier = $3 AND enabled = TRUE
            LIMIT 1
        """, mode, quality_tier)

    # Check provider health
    provider = config['provider_primary']
    health = await check_provider_health(provider, 'stt')

    if health['status'] != 'healthy':
        provider = config['provider_fallback']
        print(f"[Router] Primary provider {config['provider_primary']} unhealthy, using fallback {provider}")

    return {
        'provider': provider,
        'fallback': config['provider_fallback'],
        'config': config['config']
    }
```

#### **2. STT Router Updates**
**File:** `api/routers/stt/router.py`

**Old logic:**
```python
# Get room-specific settings
partial_mode, final_mode = await get_room_stt_settings(room)

# Route based on mode
if partial_mode == "local":
    # ...
elif partial_mode == "openai_chunked":
    # ...
```

**New logic:**
```python
# Get language from room or detect from audio
language = data.get("source_lang") or data.get("language_hint") or "auto"
quality_tier = data.get("quality_tier", "standard")  # From user settings

# Route partial messages
if msg_type == "audio_chunk_partial":
    provider_config = await language_router.get_stt_provider_for_language(
        language=language,
        mode='partial',
        quality_tier=quality_tier
    )

    provider = provider_config['provider']
    config = provider_config['config']

    if provider == 'speechmatics':
        result = await speechmatics_backend.transcribe_stream(audio_b64, language, config)
    elif provider == 'google_v2':
        result = await google_v2_backend.transcribe_stream(audio_b64, language, config)
    elif provider == 'soniox':
        result = await soniox_backend.transcribe_stream(audio_b64, language, config)
    # ...

# Route final messages
elif msg_type == "audio_chunk":
    provider_config = await language_router.get_stt_provider_for_language(
        language=language,
        mode='final',
        quality_tier=quality_tier
    )
    # ... similar routing logic
```

#### **3. MT Router Updates**
**File:** `api/routers/mt/router.py`

**Old logic:**
```python
# Simple routing: pl↔en to local, others to OpenAI
if (src_lang, tgt_lang) in [("pl", "en"), ("en", "pl")]:
    # Local worker
else:
    # OpenAI
```

**New logic:**
```python
async def get_mt_provider_for_pair(
    src_lang: str,
    tgt_lang: str,
    quality_tier: str = 'standard'
) -> Dict[str, Any]:
    """Get MT provider for language pair."""

    # Query mt_routing_config table
    config = await db.fetchrow("""
        SELECT provider_primary, provider_fallback, config
        FROM mt_routing_config
        WHERE src_lang = $1 AND tgt_lang = $2 AND quality_tier = $3 AND enabled = TRUE
        LIMIT 1
    """, src_lang, tgt_lang, quality_tier)

    # Fallback to wildcard
    if not config:
        config = await db.fetchrow("""
            SELECT provider_primary, provider_fallback, config
            FROM mt_routing_config
            WHERE (src_lang = $1 AND tgt_lang = '*') OR (src_lang = '*' AND tgt_lang = $2) OR (src_lang = '*' AND tgt_lang = '*')
            AND quality_tier = $3 AND enabled = TRUE
            ORDER BY
                CASE
                    WHEN src_lang = $1 AND tgt_lang = '*' THEN 1
                    WHEN src_lang = '*' AND tgt_lang = $2 THEN 2
                    ELSE 3
                END
            LIMIT 1
        """, src_lang, tgt_lang, quality_tier)

    # Check provider health
    provider = config['provider_primary']
    health = await check_provider_health(provider, 'mt')

    if health['status'] != 'healthy':
        provider = config['provider_fallback']

    return {
        'provider': provider,
        'fallback': config['provider_fallback'],
        'config': config['config']
    }

# In MT router loop
provider_config = await get_mt_provider_for_pair(src_lang, tgt_lang, quality_tier)
provider = provider_config['provider']

if provider == 'deepl':
    result = await deepl_backend.translate(text, src_lang, tgt_lang, context, glossary)
elif provider == 'azure_translator':
    result = await azure_translator_backend.translate(text, src_lang, tgt_lang, context, glossary)
elif provider == 'google_translate':
    result = await google_translate_backend.translate(text, src_lang, tgt_lang)
```

---

## 🎨 Admin Panel Updates

### **Old UI (Room-Level Settings)**
```
Room Settings → STT Configuration
├─ Partial Provider: [Dropdown: openai_chunked, deepgram, local, none]
└─ Final Provider: [Dropdown: openai, elevenlabs, local, none]
```

### **New UI (Global Language-Based)**
```
Admin Panel → STT Routing Configuration

┌─────────────────────────────────────────────────────────────────┐
│ STT Routing Configuration                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Language: [Dropdown: pl-PL, ar-EG, en-US, en-GB, *, Add New...]│
│                                                                 │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ Partial Mode Configuration                                │   │
│ ├───────────────────────────────────────────────────────────┤   │
│ │ Standard Tier:                                            │   │
│ │   Primary:  [Speechmatics ▼] Fallback: [Google v2 ▼]    │   │
│ │   Config:   ☑ Diarization  Max Delay: [1500ms]           │   │
│ │   Status:   🟢 Healthy                                    │   │
│ │                                                           │   │
│ │ Budget Tier:                                              │   │
│ │   Primary:  [Soniox ▼]       Fallback: [Google v2 ▼]    │   │
│ │   Config:   ☑ Diarization                                │   │
│ │   Status:   🟢 Healthy                                    │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ Final Mode Configuration                                  │   │
│ ├───────────────────────────────────────────────────────────┤   │
│ │ Standard Tier:                                            │   │
│ │   Primary:  [Speechmatics ▼] Fallback: [Google v2 ▼]    │   │
│ │   Config:   ☑ Diarization                                │   │
│ │   Status:   🟢 Healthy                                    │   │
│ │                                                           │   │
│ │ Budget Tier:                                              │   │
│ │   Primary:  [Soniox ▼]       Fallback: [Google v2 ▼]    │   │
│ │   Config:   ☑ Diarization                                │   │
│ │   Status:   🟢 Healthy                                    │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [Save Configuration]  [Test Connection]  [View Metrics]        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Configured Languages                                            │
├─────────────────────────────────────────────────────────────────┤
│ pl-PL (Polish)        Speechmatics (P/F)   🟢 Healthy          │
│ ar-EG (Arabic)        Google v2 (P/F)      🟢 Healthy          │
│ en-US (English)       Speechmatics (P/F)   🟢 Healthy          │
│ en-GB (English UK)    Speechmatics (P/F)   🟢 Healthy          │
│ * (Fallback)          Google v2 (P/F)      🟢 Healthy          │
└─────────────────────────────────────────────────────────────────┘
```

### **MT Routing Configuration**
```
Admin Panel → MT Routing Configuration

┌─────────────────────────────────────────────────────────────────┐
│ MT Routing Configuration                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Source Language: [Polish ▼]  Target Language: [English ▼]     │
│                                                                 │
│ ┌───────────────────────────────────────────────────────────┐   │
│ │ Standard Tier:                                            │   │
│ │   Primary:  [DeepL ▼]        Fallback: [Azure ▼]        │   │
│ │   Features: ☑ Context Window  ☑ Custom Glossary          │   │
│ │   Status:   🟢 Healthy                                    │   │
│ │                                                           │   │
│ │ Budget Tier:                                              │   │
│ │   Primary:  [Azure ▼]        Fallback: [Google ▼]       │   │
│ │   Status:   🟢 Healthy                                    │   │
│ └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│ [Save Configuration]  [Test Translation]  [View Quality Stats] │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Configured Language Pairs (Standard Tier)                      │
├─────────────────────────────────────────────────────────────────┤
│ pl → en              DeepL             🟢 Healthy  (WER: 8%)   │
│ en → pl              DeepL             🟢 Healthy  (WER: 9%)   │
│ en → ar              Azure Translator  🟢 Healthy  (WER: 14%)  │
│ en → es              DeepL             🟢 Healthy  (WER: 7%)   │
│ * → *  (Fallback)    Azure Translator  🟢 Healthy              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 API Endpoints

### **New Admin Endpoints**

#### **GET /api/admin/routing/stt**
Get all STT routing configurations.

**Response:**
```json
{
  "configs": [
    {
      "language": "pl-PL",
      "mode": "partial",
      "quality_tier": "standard",
      "provider_primary": "speechmatics",
      "provider_fallback": "google_v2",
      "config": {
        "diarization": true,
        "max_delay": 1.5,
        "operating_point": "enhanced"
      },
      "enabled": true,
      "health": "healthy"
    },
    {
      "language": "pl-PL",
      "mode": "final",
      "quality_tier": "standard",
      "provider_primary": "speechmatics",
      "provider_fallback": "google_v2",
      "config": {
        "diarization": true,
        "operating_point": "enhanced"
      },
      "enabled": true,
      "health": "healthy"
    }
  ]
}
```

#### **POST /api/admin/routing/stt**
Create or update STT routing configuration.

**Request:**
```json
{
  "language": "pl-PL",
  "mode": "partial",
  "quality_tier": "standard",
  "provider_primary": "speechmatics",
  "provider_fallback": "google_v2",
  "config": {
    "diarization": true,
    "max_delay": 1.5
  }
}
```

**Response:**
```json
{
  "message": "STT routing configuration updated",
  "config_id": 123
}
```

#### **GET /api/admin/routing/mt**
Get all MT routing configurations.

#### **POST /api/admin/routing/mt**
Create or update MT routing configuration.

#### **GET /api/admin/providers/health**
Get health status of all providers.

**Response:**
```json
{
  "providers": [
    {
      "provider": "speechmatics",
      "service_type": "stt",
      "status": "healthy",
      "last_check": "2025-10-22T12:00:00Z",
      "consecutive_failures": 0
    },
    {
      "provider": "deepl",
      "service_type": "mt",
      "status": "healthy",
      "last_check": "2025-10-22T12:00:00Z",
      "consecutive_failures": 0
    }
  ]
}
```

---

## 🔄 Migration Steps

### **Step 1: Database Migration**
```sql
-- File: migrations/006_language_based_routing.sql

BEGIN;

-- Remove old per-room configuration
ALTER TABLE rooms DROP COLUMN IF EXISTS stt_partial_provider;
ALTER TABLE rooms DROP COLUMN IF EXISTS stt_final_provider;

-- Remove old system_settings (if used for STT defaults)
DELETE FROM system_settings WHERE key IN ('stt_partial_provider_default', 'stt_final_provider_default');

-- Create new tables (see schema above)
-- ... (full schema from above)

COMMIT;
```

### **Step 2: Code Changes**
1. **Remove** `api/routers/stt/settings_fetcher.py`
2. **Create** `api/routers/stt/language_router.py`
3. **Update** `api/routers/stt/router.py` (language-based routing)
4. **Update** `api/routers/mt/router.py` (pair-based routing)
5. **Remove** per-room STT settings API endpoints
6. **Create** new admin routing config API endpoints

### **Step 3: Frontend Changes**
1. **Remove** `web/src/components/RoomSTTSettings.jsx` (per-room settings)
2. **Update** `web/src/pages/AdminSettingsPage.jsx` (new routing UI)
3. **Add** language-based routing configuration UI
4. **Add** provider health monitoring dashboard

### **Step 4: Testing**
1. Test each language routing (pl-PL, ar-EG, en-US)
2. Test fallback behavior (primary provider down)
3. Test quality tier switching (standard vs budget)
4. Test wildcard fallback (unsupported language)
5. Verify no room-specific overrides work (should use global)

---

## 🎯 Benefits of This Design

### **1. Simplicity**
- ❌ No per-room configuration complexity
- ✅ Single source of truth (global admin config)
- ✅ Consistent behavior across all rooms

### **2. Quality Focus**
- ✅ Best provider per language automatically selected
- ✅ Separate partial/final optimization
- ✅ Diarization always on (critical for quality)

### **3. Scalability**
- ✅ Easy to add new languages
- ✅ Easy to add new providers
- ✅ Centralized health monitoring
- ✅ Automatic fallback on provider issues

### **4. Cost Optimization**
- ✅ Budget mode for cost-conscious users
- ✅ Language-specific provider selection (use cheaper where quality holds)
- ✅ Automatic cost tracking per provider

### **5. Maintainability**
- ✅ Clear routing logic (no per-room overrides to debug)
- ✅ Easy to test (global config, not per-room)
- ✅ Centralized admin control

---

## 📝 Next Steps

1. ✅ Review this design with stakeholders
2. ✅ Create database migration script
3. ✅ Implement language router
4. ✅ Update STT/MT routers
5. ✅ Build new admin UI
6. ✅ Test with real audio
7. ✅ Document provider selection guide

---

**Last Updated:** 2025-10-22
**Status:** Design Complete - Ready for Implementation Review

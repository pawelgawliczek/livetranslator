# Admin Message Debug Feature - Implementation Plan

**Status:** ✅ Complete - All Phases + Testing Done
**Priority:** Medium
**Total Effort:** 13 hours (development + testing)
**Created:** 2025-10-28
**Completed:** 2025-10-28
**Branch:** `feature/admin-debug-tracking`

## Progress Tracker

| Phase | Status | Time | Commit |
|-------|--------|------|--------|
| **Phase 0** | ✅ Complete | 2h | [168ba93](../../commit/168ba93) |
| **Phase 1** | ✅ Complete | 2h | [225def7](../../commit/225def7) |
| **Phase 2** | ✅ Complete | 2h | [5d59a87](../../commit/5d59a87) |
| **Phase 3** | ✅ Complete | 1h | [ed0ab62](../../commit/ed0ab62) |
| **Phase 4** | ✅ Complete | 1h | [b159ac6](../../commit/b159ac6) |
| **Phase 5** | ✅ Complete | 2h | [6c08f2f](../../commit/6c08f2f) |
| **Bug Fixes** | ✅ Complete | 1h | [a1a7544](../../commit/a1a7544), [a46f063](../../commit/a46f063), [dfd05f1](../../commit/dfd05f1) |
| **Testing** | ✅ Complete | 2h | [f61503c](../../commit/f61503c) |

### Phase 0 Summary ✅

**Completed:** 2025-10-28
**Duration:** 2 hours
**Commit:** `168ba93` - "feat(phase-0): add segment_id to cost tracking for per-message attribution"

**Changes:**
- ✅ Database migration 010: Added `segment_id` column to `room_costs` table
- ✅ Updated `RoomCost` model with `segment_id` field
- ✅ Updated STT router cost events (3 locations)
- ✅ Updated MT router cost events (character & token-based)
- ✅ Updated cost tracker service to persist `segment_id`
- ✅ All tests passing (415/415)

**Benefits Unlocked:**
- Complete audit trail for cost tracking
- Per-message cost attribution from database
- Foundation for Redis debug feature (Phase 1-5)
- Historical cost queries beyond 24h TTL

### Phase 1 Summary ✅

**Completed:** 2025-10-28
**Duration:** 2 hours
**Commit:** `225def7` - "feat(phase-1): add debug tracker service with comprehensive unit tests"

**Changes:**
- ✅ Created `api/services/debug_tracker.py` with all functions
- ✅ Implemented `calculate_stt_cost()` for 6 providers (Speechmatics, Google V2, Azure, Soniox, OpenAI, local)
- ✅ Implemented `calculate_mt_cost()` for 5 providers (DeepL, Azure Translator, Google Translate, GPT-4o-mini, GPT-4o)
- ✅ Implemented `create_stt_debug_info()` - Initialize debug data in Redis
- ✅ Implemented `append_mt_debug_info()` - Append MT translations
- ✅ Implemented `get_debug_info()` - Retrieve debug data
- ✅ Created 40 comprehensive unit tests
- ✅ All tests passing (671/671, 100% pass rate)

**Benefits Unlocked:**
- Accurate cost calculations for all STT/MT providers
- Redis storage with 24-hour TTL
- Fire-and-forget error handling (no impact on message processing)
- Complete debug structure ready for router integration

---

## Table of Contents

1. [Feature Overview](#feature-overview)
2. [Requirements](#requirements)
3. [Data Structure](#data-structure)
4. [Implementation Plan](#implementation-plan)
5. [Testing Strategy](#testing-strategy)
6. [Performance Assessment](#performance-assessment)
7. [Timeline](#timeline)

---

## Feature Overview

### Problem
Admins need visibility into the message processing pipeline to debug issues, understand costs, and verify routing decisions.

### Solution
Add a small debug icon (🔍) to each message that only admins can see. Clicking it opens a modal showing:
- STT processing details (provider, latency, cost)
- MT processing details for each target language (provider, latency, cost, throttling)
- Routing decisions and fallback status
- Complete cost breakdown with per-message accuracy

### User Flow

```
Admin sees message → Clicks 🔍 icon → Modal shows debug info
                                      ↓
                         ┌─────────────────────────────┐
                         │  STT Processing             │
                         │  - Provider: Speechmatics   │
                         │  - Latency: 234ms           │
                         │  - Cost: $0.00042           │
                         ├─────────────────────────────┤
                         │  MT Processing              │
                         │  pl→en | DeepL | 89ms       │
                         │         Cost: $0.00022      │
                         │  pl→ar | GPT-4o | 2756ms    │
                         │         Cost: $0.00135      │
                         │         Throttled: Yes      │
                         ├─────────────────────────────┤
                         │  Total Cost: $0.00199       │
                         └─────────────────────────────┘
```

---

## Requirements

### Functional Requirements

#### FR1: Redis Debug Data Storage
- **MUST** store per-message debug data in Redis with key `debug:segment:{segment_id}`
- **MUST** include STT provider, language, latency, audio duration, cost breakdown
- **MUST** include MT provider, language pair, latency, cost breakdown for each translation
- **MUST** include routing decision reason ("pl-PL/final/standard → speechmatics (primary)")
- **MUST** include fallback status (true/false)
- **MUST** include throttling status and delay (for Arabic partial translations)
- **MUST** set 24-hour TTL on Redis keys (auto-cleanup)
- **MUST** calculate exact per-message costs using provider rates

#### FR2: Backend API
- **MUST** create endpoint `GET /api/admin/message-debug/{segment_id}`
- **MUST** require admin authentication (HTTP 403 for non-admins)
- **MUST** return HTTP 404 if segment_id not found in Redis
- **MUST** return complete debug JSON including costs, routing, latencies

#### FR3: Frontend Debug Icon
- **MUST** display debug icon (🔍 or ⓘ) on each message
- **MUST** show icon ONLY if `user.is_admin === true`
- **MUST** position icon in top-right corner of message (non-intrusive)
- **MUST** work on mobile (touch-friendly, responsive)

#### FR4: Frontend Debug Modal
- **MUST** open modal when debug icon clicked
- **MUST** fetch debug data from `/api/admin/message-debug/{segment_id}`
- **MUST** display STT section with provider, language, latency, cost
- **MUST** display MT section(s) for each translation with provider, language pair, latency, cost
- **MUST** display total cost (STT + all MT)
- **MUST** show routing reason and fallback status
- **MUST** show throttling info (if applicable)
- **MUST** handle loading states and errors gracefully

### Non-Functional Requirements

#### NFR1: Performance
- **MUST** add <2ms latency to STT/MT processing (async Redis writes)
- **MUST** use async non-blocking writes (fire-and-forget pattern)
- **MUST NOT** impact message processing if Redis fails (try/catch)
- **MUST** keep memory usage <1KB per message

#### NFR2: Security
- **MUST** verify admin status from database (not JWT) on every API call
- **MUST** prevent non-admins from accessing debug data (403 Forbidden)
- **MUST NOT** expose debug icon in DOM for non-admins (client-side check)

#### NFR3: Data Retention
- **MUST** automatically delete debug data after 24 hours (Redis TTL)
- **MUST NOT** store debug data in PostgreSQL (Redis only)
- **SHOULD** handle Redis memory limits gracefully (allkeys-lru policy)

#### NFR4: Error Handling
- **MUST** continue message processing if debug tracking fails
- **MUST** log errors to console (but don't block pipeline)
- **MUST** show user-friendly error in modal if API call fails

---

## Data Structure

### Redis Key Schema

```
Key: debug:segment:{segment_id}
TTL: 86400 seconds (24 hours)
Type: String (JSON)
```

### JSON Structure

```json
{
  "segment_id": 123,
  "room_code": "abc123",
  "timestamp": "2025-10-28T14:32:18.456Z",

  "stt": {
    "provider": "speechmatics",
    "language": "pl-PL",
    "mode": "final",
    "latency_ms": 234,
    "audio_duration_sec": 3.5,
    "cost_usd": 0.00042,
    "cost_breakdown": {
      "unit_type": "seconds",
      "units": 3.5,
      "rate_per_unit": 0.00012
    },
    "routing_reason": "pl-PL/final/standard → speechmatics (primary)",
    "fallback_triggered": false,
    "text": "Dzień dobry wszystkim"
  },

  "mt": [
    {
      "src_lang": "pl",
      "tgt_lang": "en",
      "provider": "deepl",
      "latency_ms": 89,
      "cost_usd": 0.00022,
      "cost_breakdown": {
        "unit_type": "characters",
        "units": 22,
        "rate_per_1000_chars": 0.01
      },
      "routing_reason": "pl→en/standard → deepl (primary)",
      "fallback_triggered": false,
      "throttled": false,
      "text": "Good morning everyone"
    },
    {
      "src_lang": "pl",
      "tgt_lang": "ar",
      "provider": "gpt-4o-mini",
      "latency_ms": 2756,
      "cost_usd": 0.00135,
      "cost_breakdown": {
        "unit_type": "tokens",
        "input_tokens": 28,
        "output_tokens": 15,
        "rate_input_per_1k": 0.00015,
        "rate_output_per_1k": 0.0006
      },
      "routing_reason": "pl→ar/standard → gpt-4o-mini (primary)",
      "fallback_triggered": false,
      "throttled": true,
      "throttle_delay_ms": 2300,
      "throttle_reason": "Arabic partial throttling (max 1 req/2.5s)",
      "text": "صباح الخير للجميع"
    }
  ],

  "totals": {
    "stt_cost_usd": 0.00042,
    "mt_cost_usd": 0.00157,
    "total_cost_usd": 0.00199,
    "mt_translations": 2
  }
}
```

### Cost Calculation Formulas

#### STT Cost
```python
# Provider-specific rates
RATES = {
    "speechmatics": 0.00012 / second,  # $0.50/hour
    "google_v2": 0.006 / second,       # $0.006/minute
    "azure": 0.001 / second,           # $1/1000 seconds
}

cost_usd = audio_duration_sec * RATES[provider]
```

#### MT Cost (Character-based)
```python
# DeepL, Azure Translator
RATES = {
    "deepl": 20.00 / 1_000_000,        # $20/1M chars
    "azure_translator": 10.00 / 1_000_000
}

cost_usd = (characters / 1_000_000) * RATES[provider]
```

#### MT Cost (Token-based)
```python
# GPT-4o, GPT-4o-mini
RATES = {
    "gpt-4o-mini": {
        "input": 0.00015 / 1000,   # $0.15/1M tokens
        "output": 0.0006 / 1000    # $0.60/1M tokens
    }
}

cost_usd = (input_tokens / 1000) * input_rate + (output_tokens / 1000) * output_rate
```

---

## Implementation Plan

### Phase 0: Add segment_id to Cost Tracking ✅ **COMPLETE**

**Duration:** 2 hours (completed 2025-10-28)
**Commit:** [168ba93](../../commit/168ba93)

**Purpose:** Fix existing gap in cost tracking to enable per-message cost analysis

This phase adds `segment_id` to the `room_costs` table and updates cost event publishers to include segment_id. This enables:
- Complete audit trail (track every $ to specific messages)
- Debug feature validation (Redis vs DB)
- Historical cost queries (beyond 24h TTL)
- Future analytics (cost per speaker, language pair, etc.)

#### Step 1: Database Migration (5 minutes)

**File:** `migrations/010_add_segment_id_to_room_costs.sql` (NEW)

```sql
-- Migration 010: Add segment_id to room_costs for per-message cost tracking
-- Purpose: Enable exact cost attribution to specific messages

BEGIN;

-- Add segment_id column (nullable for backward compatibility)
ALTER TABLE room_costs
ADD COLUMN segment_id INTEGER;

-- Add index for segment_id lookups
CREATE INDEX idx_room_costs_segment_id
ON room_costs(segment_id)
WHERE segment_id IS NOT NULL;

-- Add composite index for room + segment queries
CREATE INDEX idx_room_costs_room_segment
ON room_costs(room_id, segment_id)
WHERE segment_id IS NOT NULL;

COMMENT ON COLUMN room_costs.segment_id IS 'Link to segments table for per-message cost tracking';

COMMIT;
```

**Run migration:**
```bash
docker compose exec -T postgres psql -U lt_user -d livetranslator < migrations/010_add_segment_id_to_room_costs.sql
```

#### Step 2: Update STT Router Cost Events (15 minutes)

**File:** `api/routers/stt/router.py` (MODIFY)

**Location 1:** Line ~535-542 (audio_end handler)
```python
# BEFORE
cost_event = {
    "room_id": room,
    "pipeline": "stt",
    "mode": provider_config["provider"],
    "units": duration_sec,
    "unit_type": "seconds"
}

# AFTER
cost_event = {
    "room_id": room,
    "pipeline": "stt",
    "mode": provider_config["provider"],
    "units": duration_sec,
    "unit_type": "seconds",
    "segment_id": segment_id  # NEW
}
```

**Location 2:** Line ~616-624 (finalize handler)
**Location 3:** Line ~758-765 (instant mode)

Apply same change to all 3 locations where STT cost events are published.

#### Step 3: Update MT Router Cost Events (10 minutes)

**File:** `api/routers/mt/router.py` (MODIFY)

**Location:** Line ~421-443 (translation cost tracking)

```python
# Character-based providers
cost_event = {
    "type": "cost_event",
    "room_id": room,
    "pipeline": "mt",
    "mode": backend_name,
    "units": translation_result["char_count"],
    "unit_type": "characters",
    "provider": backend_name,
    "segment_id": segment_id  # NEW
}

# Token-based providers
cost_event = {
    "type": "cost_event",
    "room_id": room,
    "pipeline": "mt",
    "mode": backend_name,
    "units": translation_result["tokens"],
    "unit_type": "tokens",
    "provider": backend_name,
    "segment_id": segment_id  # NEW
}
```

#### Step 4: Update Cost Tracker Service (10 minutes)

**File:** `api/services/cost_tracker_service.py` (MODIFY)

**Location:** Line ~113-141

```python
# Extract segment_id from event
segment_id = data.get("segment_id")  # NEW

# Store in database with segment_id
async with db_pool.acquire() as conn:
    await conn.execute(
        """
        INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, segment_id, ts)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        """,
        room_id, pipeline, mode, provider, units, unit_type, float(cost), segment_id  # NEW
    )

# Update log
print(f"[Cost Tracker] ✓ {room_id} seg={segment_id}: {pipeline}/{provider} {units}{unit_type} = ${cost:.6f}")
```

#### Step 5: Update Models (5 minutes)

**File:** `api/models.py` (MODIFY)

**Location:** Line ~52-63

```python
class RoomCost(Base):
    __tablename__ = "room_costs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    room_id: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    pipeline: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(Text)
    units: Mapped[Optional[int]] = mapped_column(BigInteger)
    unit_type: Mapped[Optional[str]] = mapped_column(Text)
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer)  # NEW
```

#### Step 6: Update Tests (1 hour)

**File:** `api/tests/test_cost_tracking_integration.py` (MODIFY)

Add new test:
```python
async def test_cost_events_include_segment_id(db_pool, redis_client, clean_room):
    """Verify cost events include segment_id and persist to database"""
    room = clean_room
    segment_id = 123

    # Publish cost event with segment_id
    cost_event = {
        "room_id": room,
        "pipeline": "stt",
        "provider": "speechmatics",
        "mode": "speechmatics",
        "units": 60,
        "unit_type": "seconds",
        "segment_id": segment_id
    }
    await redis_client.publish("cost_events", json.dumps(cost_event))
    await asyncio.sleep(0.5)

    # Verify segment_id in database
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM room_costs WHERE room_id = $1 AND segment_id = $2",
            room, segment_id
        )

    assert result is not None
    assert result['segment_id'] == segment_id
```

**Verification Steps:**
1. Run migration
2. Restart cost tracker service
3. Send test message
4. Verify segment_id appears in room_costs table
5. Run tests

---

### Phase 1: Backend - Debug Tracker Service (2-3 hours)

#### File: `api/services/debug_tracker.py` (NEW)

**Functions:**

```python
async def create_stt_debug_info(
    redis: Redis,
    segment_id: int,
    room_code: str,
    stt_data: dict,
    routing_info: dict
) -> None:
    """Create initial debug info with STT data"""

async def append_mt_debug_info(
    redis: Redis,
    segment_id: int,
    mt_data: dict,
    routing_info: dict
) -> None:
    """Append MT translation data to existing debug info"""

async def get_debug_info(
    redis: Redis,
    segment_id: int
) -> dict | None:
    """Retrieve debug info from Redis"""

def calculate_stt_cost(provider: str, duration_sec: float) -> float:
    """Calculate STT cost based on provider rates"""

def calculate_mt_cost(
    provider: str,
    units: int,
    unit_type: str,  # "characters" or "tokens"
    input_tokens: int = 0,
    output_tokens: int = 0
) -> float:
    """Calculate MT cost based on provider rates"""
```

**Provider Pricing Constants:**

```python
STT_PRICING = {
    "speechmatics": {"per_second": 0.00012},     # $0.50/hour
    "google_v2": {"per_second": 0.0001},         # $0.006/minute
    "azure": {"per_second": 0.001},
    "soniox": {"per_second": 0.00003},           # Budget
    "openai": {"per_minute": 0.006},
    "local": {"per_second": 0.0}
}

MT_PRICING = {
    "deepl": {"per_1m_chars": 20.00},
    "azure_translator": {"per_1m_chars": 10.00},
    "google_translate": {"per_1m_chars": 20.00},
    "gpt-4o-mini": {
        "input_per_1k": 0.00015,
        "output_per_1k": 0.0006
    },
    "gpt-4o": {
        "input_per_1k": 0.005,
        "output_per_1k": 0.015
    }
}
```

---

### Phase 2: Backend - Integrate into Routers (2-3 hours)

#### File: `api/routers/stt/router.py` (MODIFY)

**Location:** After STT final event is emitted (~line 450)

```python
# Existing code emits stt_final event
await r.publish("stt_events", json.dumps(stt_final_event))

# NEW: Track debug info
try:
    from api.services.debug_tracker import create_stt_debug_info

    routing_info = {
        "routing_reason": f"{language}/{mode}/{quality_tier} → {provider} (primary)",
        "fallback_triggered": used_fallback  # Track if fallback was used
    }

    stt_data = {
        "provider": provider,
        "language": language,
        "mode": mode,
        "latency_ms": latency_ms,
        "audio_duration_sec": audio_duration,
        "text": text
    }

    await create_stt_debug_info(r, segment_id, room_code, stt_data, routing_info)
    print(f"[STT Router] 🐛 Debug info created: segment={segment_id}")
except Exception as e:
    print(f"[STT Router] ⚠️  Debug tracking failed: {e}")
    # Continue - debug is optional
```

#### File: `api/routers/mt/router.py` (MODIFY)

**Location:** After translation completed (~line 430)

```python
# Existing code emits translation event and tracks cost
await r.publish("mt_events", json.dumps(translation_event))
await r.publish("cost_events", json.dumps(cost_event))

# NEW: Track debug info
try:
    from api.services.debug_tracker import append_mt_debug_info

    routing_info = {
        "routing_reason": f"{src_lang}→{tgt_lang}/{quality_tier} → {provider} (primary)",
        "fallback_triggered": used_fallback,
        "throttled": was_throttled,
        "throttle_delay_ms": throttle_delay if was_throttled else 0,
        "throttle_reason": "Arabic partial throttling (max 1 req/2.5s)" if was_throttled else None
    }

    mt_data = {
        "src_lang": src_lang,
        "tgt_lang": tgt_lang,
        "provider": provider,
        "latency_ms": latency_ms,
        "text": translated_text,
        "char_count": char_count if unit_type == "characters" else None,
        "input_tokens": input_tokens if unit_type == "tokens" else None,
        "output_tokens": output_tokens if unit_type == "tokens" else None
    }

    await append_mt_debug_info(r, segment_id, mt_data, routing_info)
    print(f"[MT Router] 🐛 Debug info updated: segment={segment_id} {src_lang}→{tgt_lang}")
except Exception as e:
    print(f"[MT Router] ⚠️  Debug tracking failed: {e}")
    # Continue - debug is optional
```

---

### Phase 3: Backend - Admin API Endpoint (1 hour)

#### File: `api/routers/admin_api.py` (MODIFY)

**Add endpoint:**

```python
@router.get("/message-debug/{segment_id}")
async def get_message_debug_info(
    segment_id: int,
    current_user: User = Depends(require_admin),
    redis: Redis = Depends(get_redis)
):
    """
    Get debug information for a specific message.

    Requires admin privileges.
    Returns detailed STT/MT processing info including costs, routing, latencies.

    **Returns:**
    - 200: Debug info JSON
    - 403: Non-admin user (handled by require_admin dependency)
    - 404: Segment not found or TTL expired
    """
    from api.services.debug_tracker import get_debug_info

    debug_info = await get_debug_info(redis, segment_id)

    if not debug_info:
        raise HTTPException(
            status_code=404,
            detail=f"Debug info not found for segment {segment_id} (may have expired after 24h)"
        )

    return debug_info
```

---

### Phase 4: Frontend - Debug Icon (1-2 hours)

#### File: `web/src/pages/RoomPage.jsx` (MODIFY)

**Location:** Message rendering section (~line 1800)

**Step 1: Add state for debug modal**

```javascript
const [debugModalOpen, setDebugModalOpen] = useState(false);
const [debugSegmentId, setDebugSegmentId] = useState(null);

const openDebugModal = (segmentId) => {
  setDebugSegmentId(segmentId);
  setDebugModalOpen(true);
};
```

**Step 2: Modify message rendering to add icon**

```javascript
// In renderMessage function (around line 1850)
const showDebugIcon = user?.is_admin === true;

return (
  <div className="message-container" style={{position: 'relative'}}>
    {/* Existing message content */}
    <div className="message-text">{text}</div>

    {/* NEW: Debug icon (top-right corner) */}
    {showDebugIcon && segmentId && (
      <button
        onClick={() => openDebugModal(segmentId)}
        className="debug-icon-btn"
        title="Debug message processing"
        aria-label="Show debug information"
      >
        🔍
      </button>
    )}
  </div>
);
```

**Step 3: Add CSS for icon**

```css
/* In RoomPage.jsx or separate CSS file */
.debug-icon-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(100, 100, 100, 0.2);
  border: none;
  border-radius: 4px;
  padding: 4px 6px;
  font-size: 12px;
  cursor: pointer;
  opacity: 0.3;
  transition: opacity 0.2s;
}

.debug-icon-btn:hover {
  opacity: 1;
  background: rgba(100, 100, 100, 0.4);
}

/* Mobile responsive */
@media (max-width: 768px) {
  .debug-icon-btn {
    font-size: 14px;
    padding: 6px 8px;
  }
}
```

---

### Phase 5: Frontend - Debug Modal Component (2-3 hours)

#### File: `web/src/components/MessageDebugModal.jsx` (NEW)

```javascript
import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './MessageDebugModal.css';

export default function MessageDebugModal({ isOpen, onClose, segmentId, token }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [debugInfo, setDebugInfo] = useState(null);

  useEffect(() => {
    if (!isOpen || !segmentId) return;

    const fetchDebugInfo = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/admin/message-debug/${segmentId}`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Debug info not found (may have expired after 24h)');
          }
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        setDebugInfo(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchDebugInfo();
  }, [isOpen, segmentId, token]);

  if (!isOpen) return null;

  return (
    <div className="debug-modal-overlay" onClick={onClose}>
      <div className="debug-modal" onClick={(e) => e.stopPropagation()}>
        <div className="debug-modal-header">
          <h2>Message Debug Info</h2>
          <button onClick={onClose} className="debug-modal-close">×</button>
        </div>

        <div className="debug-modal-content">
          {loading && <div className="debug-loading">Loading debug info...</div>}

          {error && (
            <div className="debug-error">
              <strong>Error:</strong> {error}
            </div>
          )}

          {debugInfo && (
            <>
              {/* Metadata */}
              <div className="debug-section">
                <h3>Metadata</h3>
                <table className="debug-table">
                  <tbody>
                    <tr>
                      <td>Segment ID:</td>
                      <td><code>{debugInfo.segment_id}</code></td>
                    </tr>
                    <tr>
                      <td>Room Code:</td>
                      <td><code>{debugInfo.room_code}</code></td>
                    </tr>
                    <tr>
                      <td>Timestamp:</td>
                      <td>{new Date(debugInfo.timestamp).toLocaleString()}</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* STT Section */}
              {debugInfo.stt && (
                <div className="debug-section">
                  <h3>STT Processing</h3>
                  <table className="debug-table">
                    <tbody>
                      <tr>
                        <td>Provider:</td>
                        <td><strong>{debugInfo.stt.provider}</strong></td>
                      </tr>
                      <tr>
                        <td>Language:</td>
                        <td>{debugInfo.stt.language}</td>
                      </tr>
                      <tr>
                        <td>Mode:</td>
                        <td>{debugInfo.stt.mode}</td>
                      </tr>
                      <tr>
                        <td>Latency:</td>
                        <td>{debugInfo.stt.latency_ms}ms</td>
                      </tr>
                      <tr>
                        <td>Audio Duration:</td>
                        <td>{debugInfo.stt.audio_duration_sec}s</td>
                      </tr>
                      <tr>
                        <td>Cost:</td>
                        <td className="debug-cost">
                          ${debugInfo.stt.cost_usd.toFixed(6)}
                          <span className="debug-cost-detail">
                            ({debugInfo.stt.cost_breakdown.units} {debugInfo.stt.cost_breakdown.unit_type}
                            @ ${debugInfo.stt.cost_breakdown.rate_per_unit.toFixed(6)}/unit)
                          </span>
                        </td>
                      </tr>
                      <tr>
                        <td>Routing:</td>
                        <td className="debug-routing">{debugInfo.stt.routing_reason}</td>
                      </tr>
                      <tr>
                        <td>Fallback Used:</td>
                        <td>{debugInfo.stt.fallback_triggered ? '✅ Yes' : '❌ No'}</td>
                      </tr>
                      <tr>
                        <td>Text:</td>
                        <td className="debug-text">"{debugInfo.stt.text}"</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}

              {/* MT Section */}
              {debugInfo.mt && debugInfo.mt.length > 0 && (
                <div className="debug-section">
                  <h3>MT Processing ({debugInfo.mt.length} translation{debugInfo.mt.length > 1 ? 's' : ''})</h3>

                  {debugInfo.mt.map((translation, idx) => (
                    <div key={idx} className="debug-translation">
                      <h4>{translation.src_lang} → {translation.tgt_lang}</h4>
                      <table className="debug-table">
                        <tbody>
                          <tr>
                            <td>Provider:</td>
                            <td><strong>{translation.provider}</strong></td>
                          </tr>
                          <tr>
                            <td>Latency:</td>
                            <td>{translation.latency_ms}ms</td>
                          </tr>
                          <tr>
                            <td>Cost:</td>
                            <td className="debug-cost">
                              ${translation.cost_usd.toFixed(6)}
                              <span className="debug-cost-detail">
                                {translation.cost_breakdown.unit_type === 'tokens' ? (
                                  `(${translation.cost_breakdown.input_tokens} in + ${translation.cost_breakdown.output_tokens} out tokens)`
                                ) : (
                                  `(${translation.cost_breakdown.units} ${translation.cost_breakdown.unit_type})`
                                )}
                              </span>
                            </td>
                          </tr>
                          <tr>
                            <td>Routing:</td>
                            <td className="debug-routing">{translation.routing_reason}</td>
                          </tr>
                          <tr>
                            <td>Fallback Used:</td>
                            <td>{translation.fallback_triggered ? '✅ Yes' : '❌ No'}</td>
                          </tr>
                          {translation.throttled && (
                            <>
                              <tr>
                                <td>Throttled:</td>
                                <td className="debug-throttled">
                                  ✅ Yes ({translation.throttle_delay_ms}ms delay)
                                </td>
                              </tr>
                              <tr>
                                <td>Throttle Reason:</td>
                                <td>{translation.throttle_reason}</td>
                              </tr>
                            </>
                          )}
                          <tr>
                            <td>Text:</td>
                            <td className="debug-text">"{translation.text}"</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              )}

              {/* Totals Section */}
              {debugInfo.totals && (
                <div className="debug-section debug-totals">
                  <h3>Cost Summary</h3>
                  <table className="debug-table">
                    <tbody>
                      <tr>
                        <td>STT Cost:</td>
                        <td className="debug-cost-value">${debugInfo.totals.stt_cost_usd.toFixed(6)}</td>
                      </tr>
                      <tr>
                        <td>MT Cost ({debugInfo.totals.mt_translations} translations):</td>
                        <td className="debug-cost-value">${debugInfo.totals.mt_cost_usd.toFixed(6)}</td>
                      </tr>
                      <tr className="debug-total-row">
                        <td><strong>Total Cost:</strong></td>
                        <td className="debug-cost-total"><strong>${debugInfo.totals.total_cost_usd.toFixed(6)}</strong></td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
```

#### File: `web/src/components/MessageDebugModal.css` (NEW)

```css
.debug-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 20px;
}

.debug-modal {
  background: #1a1a1a;
  border-radius: 8px;
  max-width: 800px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
}

.debug-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #333;
}

.debug-modal-header h2 {
  margin: 0;
  font-size: 20px;
  color: #fff;
}

.debug-modal-close {
  background: none;
  border: none;
  font-size: 32px;
  color: #888;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  line-height: 32px;
  transition: color 0.2s;
}

.debug-modal-close:hover {
  color: #fff;
}

.debug-modal-content {
  overflow-y: auto;
  padding: 20px;
  flex: 1;
}

.debug-loading {
  text-align: center;
  padding: 40px;
  color: #888;
}

.debug-error {
  background: #3a1a1a;
  border: 1px solid #aa3333;
  border-radius: 4px;
  padding: 16px;
  color: #ff6666;
}

.debug-section {
  margin-bottom: 24px;
  background: #242424;
  border-radius: 6px;
  padding: 16px;
}

.debug-section h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #4a9eff;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.debug-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #ffaa44;
}

.debug-translation {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #333;
}

.debug-translation:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.debug-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.debug-table td {
  padding: 6px 8px;
  border-bottom: 1px solid #333;
  color: #ccc;
}

.debug-table td:first-child {
  width: 140px;
  font-weight: 500;
  color: #999;
}

.debug-table code {
  background: #333;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #4af;
}

.debug-cost {
  color: #4af;
  font-weight: 600;
}

.debug-cost-detail {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: #888;
  margin-top: 2px;
}

.debug-cost-value {
  color: #4af;
  font-weight: 600;
  text-align: right;
}

.debug-cost-total {
  color: #4f4;
  font-size: 16px;
  font-weight: 700;
  text-align: right;
}

.debug-total-row {
  border-top: 2px solid #4a9eff;
}

.debug-routing {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #ffaa44;
}

.debug-throttled {
  color: #ffaa44;
}

.debug-text {
  font-style: italic;
  color: #aaa;
}

.debug-totals {
  background: #1a2a1a;
  border: 1px solid #2a5a2a;
}

/* Mobile responsive */
@media (max-width: 768px) {
  .debug-modal {
    max-width: 100%;
    margin: 0;
    border-radius: 0;
    max-height: 100vh;
  }

  .debug-table td:first-child {
    width: 120px;
  }
}
```

#### File: `web/src/pages/RoomPage.jsx` (MODIFY - Import and use modal)

```javascript
// Add import at top
import MessageDebugModal from '../components/MessageDebugModal';

// In component JSX (at end, before closing div)
return (
  <div className="room-page">
    {/* Existing room content */}

    {/* NEW: Debug modal */}
    <MessageDebugModal
      isOpen={debugModalOpen}
      onClose={() => setDebugModalOpen(false)}
      segmentId={debugSegmentId}
      token={token}
    />
  </div>
);
```

---

## Testing Strategy

### Unit Tests (6 tests, ~1 hour)

**File:** `tests/unit/test_debug_tracker.py`

```python
import pytest
from api.services.debug_tracker import (
    calculate_stt_cost,
    calculate_mt_cost,
    create_stt_debug_info,
    append_mt_debug_info
)

class TestDebugTrackerCostCalculations:
    def test_calculate_stt_cost_speechmatics(self):
        """Test Speechmatics STT cost calculation"""
        cost = calculate_stt_cost("speechmatics", 3.5)
        assert abs(cost - 0.00042) < 0.000001  # $0.50/hr = $0.00012/sec

    def test_calculate_stt_cost_google(self):
        """Test Google STT cost calculation"""
        cost = calculate_stt_cost("google_v2", 60.0)
        assert abs(cost - 0.006) < 0.0001  # $0.006/minute

    def test_calculate_mt_cost_deepl_characters(self):
        """Test DeepL MT cost (character-based)"""
        cost = calculate_mt_cost("deepl", 500, "characters")
        assert abs(cost - 0.00001) < 0.000001  # $20/1M chars

    def test_calculate_mt_cost_gpt4o_tokens(self):
        """Test GPT-4o-mini MT cost (token-based)"""
        cost = calculate_mt_cost(
            "gpt-4o-mini", 100, "tokens",
            input_tokens=28, output_tokens=15
        )
        # (28 * 0.00015 / 1000) + (15 * 0.0006 / 1000) = 0.0000042 + 0.000009 = 0.0000132
        assert abs(cost - 0.0000132) < 0.0000001

    def test_create_debug_info_structure(self):
        """Test debug info JSON structure is valid"""
        # Mock Redis, create debug info
        # Verify all required fields present
        # Verify totals calculated correctly

    def test_append_mt_translation_to_existing(self):
        """Test appending MT data to existing STT debug info"""
        # Create STT debug info
        # Append first MT translation
        # Append second MT translation
        # Verify mt[] array has 2 entries
        # Verify totals updated
```

---

### Integration Tests (10 tests, ~2-3 hours)

**File:** `api/tests/test_debug_tracking_integration.py`

```python
import pytest
import redis.asyncio as redis
import json

@pytest.mark.integration
class TestDebugTrackingIntegration:
    async def test_stt_router_creates_debug_info(self, redis_client, room_code):
        """Test STT router creates debug:segment:{id} key"""
        # Simulate STT final event processing
        # Verify Redis key exists
        # Verify TTL = 86400

    async def test_mt_router_appends_to_debug_info(self, redis_client, room_code):
        """Test MT router appends translation to existing debug info"""
        # Create initial STT debug info
        # Simulate MT translation event
        # Verify mt[] array contains translation
        # Verify totals updated

    async def test_debug_info_includes_routing_decision(self, redis_client):
        """Verify routing reason is stored correctly"""
        # Check routing_reason format
        # "pl-PL/final/standard → speechmatics (primary)"

    async def test_debug_info_includes_fallback_status(self, redis_client):
        """Test fallback_triggered flag is set correctly"""
        # Scenario 1: Primary succeeds → fallback_triggered=false
        # Scenario 2: Primary fails, fallback succeeds → fallback_triggered=true

    async def test_debug_info_includes_throttle_status(self, redis_client):
        """Test Arabic throttling is captured"""
        # Send pl→ar translation
        # Verify throttled=true
        # Verify throttle_delay_ms present

    async def test_debug_ttl_24_hours(self, redis_client):
        """Verify Redis TTL is 24 hours"""
        # Create debug info
        # Check TTL = 86400 seconds

    async def test_admin_api_returns_debug_info(self, client, admin_token):
        """Test GET /api/admin/message-debug/{segment_id}"""
        # Create debug info in Redis
        # Call API endpoint
        # Verify JSON response matches Redis data

    async def test_admin_api_requires_admin(self, client, user_token):
        """Test non-admin gets 403"""
        # Call API with regular user token
        # Expect HTTP 403

    async def test_admin_api_404_for_missing_segment(self, client, admin_token):
        """Test API returns 404 for non-existent segment"""
        # Call API with invalid segment_id
        # Expect HTTP 404

    async def test_debug_tracking_error_doesnt_block_pipeline(self, redis_client):
        """Test STT/MT continues if debug tracking fails"""
        # Mock Redis failure
        # Verify STT/MT events still published
        # Verify no exception raised
```

---

### E2E Tests (4 tests, ~1-2 hours)

**File:** `api/tests/test_debug_tracking_e2e.py`

```python
@pytest.mark.e2e
class TestDebugTrackingE2E:
    async def test_complete_message_debug_flow(self):
        """Test full pipeline: Audio → STT → MT → Debug API"""
        # 1. Send 3-second Polish audio
        # 2. Verify STT event received (Speechmatics)
        # 3. Verify MT events received (pl→en, pl→ar)
        # 4. Fetch debug info via API
        # 5. Verify complete structure:
        #    - STT: provider, latency, cost
        #    - MT[0]: pl→en, DeepL, cost
        #    - MT[1]: pl→ar, GPT-4o-mini, cost, throttled
        #    - Totals: sum of costs

    async def test_multi_language_room_debug_tracking(self):
        """Test debug tracking with multiple participants"""
        # 3 participants: pl, en, ar
        # One speaks (pl)
        # Generates 2 translations (pl→en, pl→ar)
        # Verify debug info has 2 MT entries

    async def test_provider_fallback_in_debug(self):
        """Test fallback scenario is captured"""
        # Mock DeepL failure
        # Verify debug shows:
        #   - fallback_triggered: true
        #   - routing_reason mentions primary failed
```

**File:** `tests/e2e/tests/admin-debug-icon.spec.js` (Playwright)

```javascript
const { test, expect } = require('@playwright/test');

test.describe('Admin Debug Icon', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: Login as admin, create room, send test message
  });

  test('should show debug icon only for admin users', async ({ page }) => {
    // Login as admin
    await page.goto('/room/test123');

    // Verify debug icon visible
    const debugIcon = page.locator('.debug-icon-btn');
    await expect(debugIcon).toBeVisible();

    // Logout, login as regular user
    await page.click('[data-testid="logout"]');
    await loginAsUser(page, 'user@example.com');
    await page.goto('/room/test123');

    // Verify icon NOT visible
    await expect(debugIcon).not.toBeVisible();
  });

  test('should open debug modal on icon click', async ({ page }) => {
    await page.goto('/room/test123');

    // Click debug icon
    await page.click('.debug-icon-btn');

    // Verify modal opens
    const modal = page.locator('.debug-modal');
    await expect(modal).toBeVisible();

    // Verify sections present
    await expect(page.locator('h3:has-text("STT Processing")')).toBeVisible();
    await expect(page.locator('h3:has-text("MT Processing")')).toBeVisible();
    await expect(page.locator('h3:has-text("Cost Summary")')).toBeVisible();
  });

  test('should display accurate cost information', async ({ page }) => {
    await page.goto('/room/test123');
    await page.click('.debug-icon-btn');

    // Verify cost fields present
    const sttCost = page.locator('.debug-table:has-text("STT Cost")');
    await expect(sttCost).toContainText('$');

    const totalCost = page.locator('.debug-cost-total');
    await expect(totalCost).toContainText('$');
  });

  test('should close modal on X button click', async ({ page }) => {
    await page.goto('/room/test123');
    await page.click('.debug-icon-btn');

    const modal = page.locator('.debug-modal');
    await expect(modal).toBeVisible();

    // Click close button
    await page.click('.debug-modal-close');

    await expect(modal).not.toBeVisible();
  });
});
```

---

### Test Coverage Goals

- **Unit tests:** 100% of cost calculation functions
- **Integration tests:** 90% of debug_tracker.py and admin API
- **E2E tests:** Critical user flows (admin viewing debug info)
- **Overall target:** 85%+ coverage for new code

---

## Performance Assessment

### Expected Impact

| Metric | Current | With Feature | Change |
|--------|---------|--------------|--------|
| **STT Latency** | 234ms | 235ms | +1ms (+0.4%) |
| **MT Latency** | 89ms | 90ms | +1ms (+1.1%) |
| **Redis Memory/msg** | 0 bytes | 500-800 bytes | +0.5-0.8 KB |
| **CPU Overhead** | 0% | <0.01% | Negligible |

### Redis Memory Calculation

**Single message (3 target languages):**
```
STT debug data:    ~200 bytes
MT debug data:     ~100 bytes × 3 = 300 bytes
Metadata + totals: ~100 bytes
Total:             ~600 bytes × 24h TTL
```

**Busy room (100 messages/day):**
```
100 msgs × 600 bytes = 60 KB/day (auto-cleanup after 24h)
```

**Very busy system (10,000 messages/day across all rooms):**
```
10,000 msgs × 600 bytes = 6 MB (manageable)
```

### Performance Testing

**Load test scenario:**
```python
# Simulate 10 concurrent users sending messages
# Measure:
# - Average latency increase (<2ms acceptable)
# - Redis memory usage (<10MB for 1000 messages)
# - No errors/exceptions in debug tracking
```

---

## Timeline

### Development Phases

| Phase | Description | Duration | Dependencies |
|-------|-------------|----------|--------------|
| **Phase 0** | Add segment_id to Cost Tracking | 2 hours | None |
| **Phase 1** | Debug Tracker Service | 2-3 hours | Phase 0 |
| **Phase 2** | Integrate into STT/MT Routers | 2-3 hours | Phase 1 |
| **Phase 3** | Admin API Endpoint | 1 hour | Phase 1, 2 |
| **Phase 4** | Frontend Debug Icon | 1-2 hours | Phase 3 |
| **Phase 5** | Frontend Debug Modal | 2-3 hours | Phase 3 |
| **Testing** | Unit + Integration + E2E | 6-9 hours | All phases |

**Total Estimated Time:** 16-23 hours (including testing)

**Suggested Sprint:** 2-3 working days

---

## Open Questions

1. **Provider pricing accuracy:**
   - Should pricing be configurable via environment variables?
   - Should we fetch real-time pricing from provider APIs?
   - **Recommendation:** Start with hardcoded constants, make configurable later

2. **Debug data retention:**
   - Is 24 hours sufficient? (Current plan)
   - Should admins be able to extend TTL for specific messages?
   - **Recommendation:** Start with 24h, add admin "pin message" feature later

3. **Performance monitoring:**
   - Should we add metrics to track debug tracking overhead?
   - **Recommendation:** Add optional Prometheus metrics (disabled by default)

4. **Mobile UX:**
   - Is 🔍 icon touch-friendly enough on mobile?
   - Should modal be full-screen on mobile?
   - **Recommendation:** Test on real devices, adjust if needed

---

## Success Criteria

### Must Have (MVP)
- ✅ Admin can click debug icon on any message
- ✅ Modal displays STT provider, latency, cost
- ✅ Modal displays MT provider(s), latency, cost per translation
- ✅ Total cost calculated accurately
- ✅ Data expires after 24 hours
- ✅ Non-admins cannot see icon or access API
- ✅ Performance impact <2ms per message

### Nice to Have (Future)
- Export debug info as JSON
- Real-time debug mode (live updates as message processes)
- Debug info includes audio quality metrics
- Compare costs across different provider configurations
- Historical cost trends per room

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Redis memory full | High | Low | TTL auto-cleanup, allkeys-lru policy |
| Debug tracking fails | Low | Medium | Try/catch, fire-and-forget pattern |
| Performance degradation | High | Low | Async writes, load testing |
| Cost calculation incorrect | Medium | Medium | Unit tests, manual verification |
| Modal too slow on mobile | Medium | Low | Lazy loading, skeleton UI |

---

## Future Enhancements

1. **Export functionality:** Download debug info as JSON file
2. **Real-time mode:** Live updates as message processes (WebSocket)
3. **Cost analytics:** Aggregate costs by provider, language, time
4. **Provider comparison:** "What if we used DeepL instead of Azure?"
5. **Message replay:** Re-process message with different provider to compare results
6. **Audio quality metrics:** SNR, background noise level, speech clarity
7. **Diarization accuracy:** Speaker attribution correctness

---

## Appendix

### Related Files

**Backend:**
- [api/routers/stt/router.py](api/routers/stt/router.py) - STT router (modify)
- [api/routers/mt/router.py](api/routers/mt/router.py) - MT router (modify)
- [api/routers/admin_api.py](api/routers/admin_api.py) - Admin API (modify)
- `api/services/debug_tracker.py` - Debug tracker service (NEW)

**Frontend:**
- [web/src/pages/RoomPage.jsx](web/src/pages/RoomPage.jsx) - Room page (modify)
- `web/src/components/MessageDebugModal.jsx` - Debug modal (NEW)
- `web/src/components/MessageDebugModal.css` - Modal styles (NEW)

**Tests:**
- `tests/unit/test_debug_tracker.py` (NEW)
- `api/tests/test_debug_tracking_integration.py` (NEW)
- `api/tests/test_debug_tracking_e2e.py` (NEW)
- `tests/e2e/tests/admin-debug-icon.spec.js` (NEW)

### References

- [Migration 006: Language-based routing](migrations/006_language_based_routing.sql) - Provider config schema
- [Cost Tracker](api/cost_tracker.py) - Existing cost calculation logic
- [Admin API](api/routers/admin_api.py) - Admin authentication pattern
- [Models](api/models.py) - Database schema

---

**Document Version:** 1.1
**Last Updated:** 2025-10-28
**Status:** Phase 0 Complete - Ready for Phase 1

# Segment ID Tracking Analysis

**Date:** 2025-10-28
**Purpose:** Identify gaps in segment_id tracking across the system

---

## Current State

### ✅ Tables/Systems WITH segment_id Tracking

| Component | segment_id Field | Notes |
|-----------|------------------|-------|
| **segments** table | ✅ `segment_id` VARCHAR(64) | Primary STT results storage |
| **translations** table | ✅ `segment_id` INTEGER | MT results linked to segments |
| **quality_metrics** table | ✅ `segment_id` INTEGER | Quality/performance tracking (from migration 006) |
| **events** table | ✅ `segment_id` INTEGER | Legacy event system (currently empty, not used) |

---

### ❌ Tables/Systems MISSING segment_id Tracking

#### **1. room_costs Table** ⚠️ **CRITICAL GAP**

**Current Schema:**
```sql
CREATE TABLE room_costs (
    id         BIGSERIAL PRIMARY KEY,
    room_id    TEXT NOT NULL,
    ts         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pipeline   TEXT NOT NULL,              -- 'stt' or 'mt'
    mode       TEXT NOT NULL,              -- Provider name
    provider   VARCHAR(50),
    units      BIGINT,
    unit_type  TEXT,                       -- 'seconds', 'characters', 'tokens'
    amount_usd NUMERIC(12,6) NOT NULL DEFAULT 0
);
```

**Missing:** `segment_id` column

**Impact:**
- ❌ Cannot trace which message generated which cost
- ❌ Cannot calculate exact per-message costs from database
- ❌ Cannot audit cost discrepancies at message level
- ❌ Cannot analyze cost patterns per speaker/conversation segment
- ❌ Must use Redis for debug feature (no historical cost lookup)

**Location:** [api/models.py:52-63](api/models.py#L52-L63)

---

#### **2. Cost Event Messages (Redis)** ⚠️ **CRITICAL GAP**

**Current Format:**
```python
# STT cost event (api/routers/stt/router.py:535-542)
cost_event = {
    "room_id": room,
    "pipeline": "stt",
    "mode": provider_config["provider"],
    "units": duration_sec,
    "unit_type": "seconds"
    # MISSING: "segment_id": segment_id
}

# MT cost event (api/routers/mt/router.py:421-429)
cost_event = {
    "type": "cost_event",
    "room_id": room,
    "pipeline": "mt",
    "mode": backend_name,
    "units": translation_result["char_count"],
    "unit_type": "characters",
    "provider": backend_name
    # MISSING: "segment_id": segment_id
}
```

**Impact:**
- ❌ Cost tracker service cannot link costs to segments
- ❌ Cannot validate debug info against database costs
- ❌ Cannot aggregate costs per message retroactively

**Locations:**
- [api/routers/stt/router.py:535-542](api/routers/stt/router.py#L535-L542)
- [api/routers/stt/router.py:616-624](api/routers/stt/router.py#L616-L624)
- [api/routers/stt/router.py:758-765](api/routers/stt/router.py#L758-L765)
- [api/routers/mt/router.py:421-443](api/routers/mt/router.py#L421-L443)

---

## Recommendation: Add segment_id to Cost Tracking

### Benefits

1. **Complete Audit Trail**
   - Track every dollar spent to specific messages
   - Debug cost anomalies (why was this message expensive?)
   - Validate billing accuracy

2. **Historical Analysis**
   - Analyze costs per speaker over time
   - Identify high-cost conversation patterns
   - Optimize provider selection based on historical data

3. **Integration with Debug Feature**
   - Validate Redis debug info against database
   - Provide fallback if Redis expires (query from DB)
   - Enable cost queries for messages older than 24 hours

4. **Compliance & Transparency**
   - Show users exact cost breakdown per message
   - Audit provider billing against our tracking
   - Meet financial reporting requirements

---

## Implementation Plan

### Phase 1: Database Schema Change (5 minutes)

**Migration:** `migrations/010_add_segment_id_to_room_costs.sql`

```sql
BEGIN;

-- Add segment_id column to room_costs
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

**Note:** Column is nullable for backward compatibility (existing rows won't have segment_id).

---

### Phase 2: Update Cost Event Publishers (30 minutes)

#### **2a. STT Router** - [api/routers/stt/router.py](api/routers/stt/router.py)

**Location 1:** Line 535-542 (audio_end handler)
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

**Location 2:** Line 616-624 (finalize handler)
```python
cost_event = {
    "room_id": room,
    "pipeline": "stt",
    "provider": session["provider"],
    "mode": session["provider"],
    "units": audio_duration,
    "unit_type": "seconds",
    "segment_id": segment_id  # NEW
}
```

**Location 3:** Line 758-765 (instant mode)
```python
cost_event = {
    "room_id": room,
    "pipeline": "stt",
    "mode": provider_config["provider"],
    "units": audio_duration,
    "unit_type": "seconds",
    "segment_id": segment_id  # NEW
}
```

---

#### **2b. MT Router** - [api/routers/mt/router.py](api/routers/mt/router.py)

**Location:** Line 421-443 (translation handler)

```python
# Character-based providers (DeepL, Azure, Google)
cost_event = {
    "type": "cost_event",
    "room_id": room,
    "pipeline": "mt",
    "mode": backend_name,
    "units": translation_result["char_count"],
    "unit_type": "characters",
    "provider": backend_name,
    "segment_id": segment_id  # NEW - already available in context
}

# Token-based providers (OpenAI)
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

---

### Phase 3: Update Cost Tracker Service (10 minutes)

**File:** [api/services/cost_tracker_service.py](api/services/cost_tracker_service.py)

**Location:** Line 113-141 (event handler)

```python
# Extract fields (support multiple event formats)
room_id = data.get("room_id")
pipeline = data.get("pipeline") or data.get("service")
provider = data.get("provider") or data.get("mode")
mode = data.get("mode") or provider
units = data.get("units", 0)
unit_type = data.get("unit_type", "seconds")
segment_id = data.get("segment_id")  # NEW - extract segment_id

# ... validation ...

# Store in database
async with db_pool.acquire() as conn:
    await conn.execute(
        """
        INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, segment_id, ts)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
        """,
        room_id, pipeline, mode, provider, units, unit_type, float(cost), segment_id  # NEW
    )

# Update log message
print(f"[Cost Tracker] ✓ {room_id} seg={segment_id}: {pipeline}/{provider} {units}{unit_type} = ${cost:.6f}")
```

---

### Phase 4: Update Tests (1 hour)

#### **Test File:** `api/tests/test_cost_tracking_integration.py`

**Add new test:**
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

    # Wait for cost tracker to process
    await asyncio.sleep(0.5)

    # Verify segment_id stored in database
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM room_costs WHERE room_id = $1 AND segment_id = $2",
            room, segment_id
        )

    assert result is not None
    assert result['segment_id'] == segment_id
    assert result['pipeline'] == 'stt'
    assert result['provider'] == 'speechmatics'
```

**Update existing tests:**
```python
async def test_aggregate_costs_by_segment(db_pool, clean_room):
    """Test aggregating costs per segment"""
    room = clean_room

    # Insert costs for multiple segments
    async with db_pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO room_costs (room_id, segment_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
            VALUES
                ($1, 100, 'stt', 'speechmatics', 'speechmatics', 3, 'seconds', 0.00036, NOW()),
                ($1, 100, 'mt', 'deepl', 'deepl', 500, 'characters', 0.00001, NOW()),
                ($1, 101, 'stt', 'speechmatics', 'speechmatics', 5, 'seconds', 0.00060, NOW()),
                ($1, 101, 'mt', 'deepl', 'deepl', 800, 'characters', 0.000016, NOW())
        """, room)

    # Aggregate by segment
    async with db_pool.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                segment_id,
                SUM(amount_usd) as total_cost,
                COUNT(*) as event_count
            FROM room_costs
            WHERE room_id = $1
            GROUP BY segment_id
            ORDER BY segment_id
        """, room)

    assert len(results) == 2
    assert results[0]['segment_id'] == 100
    assert abs(float(results[0]['total_cost']) - 0.00037) < 0.000001  # STT + MT
    assert results[1]['segment_id'] == 101
```

---

## Migration Considerations

### Backward Compatibility

**Old cost events (without segment_id):**
- ✅ Will still work (column is nullable)
- ✅ Will insert NULL for segment_id
- ✅ No breaking changes to existing code

**New cost events (with segment_id):**
- ✅ Will populate segment_id column
- ✅ Enable per-message cost tracking
- ✅ Integrate with debug feature

### Data Retention

**Existing room_costs rows:**
- Keep as-is (segment_id = NULL)
- Aggregate costs still work
- Only new messages will have segment_id

**Query patterns:**
```sql
-- Total room costs (works with or without segment_id)
SELECT SUM(amount_usd) FROM room_costs WHERE room_id = 'abc123';

-- Per-message costs (only for messages after migration)
SELECT segment_id, SUM(amount_usd)
FROM room_costs
WHERE room_id = 'abc123' AND segment_id IS NOT NULL
GROUP BY segment_id;

-- Messages without cost tracking (old or free providers)
SELECT s.segment_id, s.text
FROM segments s
LEFT JOIN room_costs rc ON s.segment_id = rc.segment_id::text
WHERE s.room_id = 123 AND rc.id IS NULL;
```

---

## Impact on Debug Feature

### Before Migration (Current Plan)

**Redis-only approach:**
- Store debug info in Redis with 24h TTL
- No historical cost lookup (data expires)
- Cannot validate against database

**Limitations:**
- ❌ Costs unavailable after 24 hours
- ❌ No way to audit historical costs per message
- ❌ Debug info and database costs disconnected

---

### After Migration (Enhanced)

**Hybrid approach: Redis + Database:**

**Redis debug info (24h TTL):**
- Complete debug data (routing, latency, throttling, costs)
- Fast lookups for recent messages
- Detailed breakdown with all metadata

**Database room_costs (permanent):**
- segment_id links costs to messages
- Historical cost queries (any time range)
- Audit trail for billing

**Admin API enhancement:**
```python
@router.get("/message-debug/{segment_id}")
async def get_message_debug_info(
    segment_id: int,
    current_user: User = Depends(require_admin),
    redis: Redis = Depends(get_redis),
    db_pool = Depends(get_db_pool)
):
    """Get debug info with fallback to database"""

    # Try Redis first (fast, detailed)
    debug_info = await get_debug_info(redis, segment_id)

    if debug_info:
        return debug_info

    # Fallback to database (slower, basic cost data only)
    async with db_pool.acquire() as conn:
        costs = await conn.fetch("""
            SELECT pipeline, provider, units, unit_type, amount_usd, ts
            FROM room_costs
            WHERE segment_id = $1
            ORDER BY ts
        """, segment_id)

        if not costs:
            raise HTTPException(404, "Debug info expired and no database record found")

        # Build basic debug info from database
        return {
            "segment_id": segment_id,
            "note": "Redis debug info expired, showing database cost records only",
            "costs": [dict(row) for row in costs],
            "total_cost_usd": sum(row['amount_usd'] for row in costs)
        }
```

**Benefits:**
- ✅ Complete debug info for recent messages (Redis)
- ✅ Cost data available forever (database)
- ✅ Audit trail for compliance
- ✅ Validate debug calculations against database

---

## Timeline

| Phase | Description | Effort | Dependencies |
|-------|-------------|--------|--------------|
| **Phase 1** | Database migration | 5 min | None |
| **Phase 2** | Update STT/MT routers | 30 min | Phase 1 |
| **Phase 3** | Update cost tracker service | 10 min | Phase 1 |
| **Phase 4** | Update tests | 1 hour | Phase 2, 3 |
| **Total** | **~2 hours** | | |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Migration fails | Low | High | Test in staging, add rollback script |
| Null segment_ids in events | Medium | Low | Column is nullable, queries handle NULL |
| Performance degradation | Low | Medium | Index on segment_id, monitor query times |
| Cost tracker breaks | Low | High | Test thoroughly, add error handling |

---

## Decision Required

### Option 1: Add segment_id to room_costs NOW ✅ **RECOMMENDED**

**Pros:**
- Complete cost tracking from day 1
- Debug feature can validate against database
- Historical cost analysis possible
- Clean architecture (all tracking uses segment_id)

**Cons:**
- Small migration effort (~2 hours)
- Schema change requires downtime (minimal, <30 seconds)

**Timeline:** Include in debug feature implementation (Phase 0)

---

### Option 2: Defer to Later ❌ **NOT RECOMMENDED**

**Pros:**
- Faster debug feature delivery (no migration)
- No schema changes now

**Cons:**
- Technical debt accumulates
- Debug feature limited to Redis only (24h)
- No historical cost analysis
- Will need migration eventually anyway
- Missing opportunity to fix gap while implementing debug feature

**Timeline:** Debug feature now, migration later (more work total)

---

## Recommendation

**Add segment_id to room_costs as Phase 0 of the debug feature implementation.**

**Rationale:**
1. Small effort (2 hours) for major benefit
2. Makes debug feature more powerful (historical fallback)
3. Fixes existing gap in cost tracking
4. Enables future analytics and auditing
5. Clean implementation from day 1

---

## Additional Tracking Opportunities (Future)

Beyond segment_id, consider tracking these for even better visibility:

1. **Speaker tracking in room_costs**
   - Add `speaker_id` column
   - Track costs per participant
   - Enable per-user billing

2. **Language pair tracking in room_costs**
   - Add `src_lang`, `tgt_lang` for MT costs
   - Analyze which language pairs are expensive
   - Optimize provider selection per pair

3. **Latency tracking in room_costs**
   - Add `latency_ms` column
   - Correlate cost with latency
   - Identify slow/expensive providers

4. **Session tracking**
   - Add `session_id` to track conversation sessions
   - Aggregate costs per session
   - Analyze session-level metrics

---

## Summary

**Current State:**
- ✅ segments, translations, quality_metrics have segment_id
- ❌ room_costs missing segment_id (critical gap)
- ❌ cost events missing segment_id

**Recommendation:**
- ✅ Add segment_id to room_costs (Migration 010)
- ✅ Update STT/MT routers to include segment_id in cost events
- ✅ Update cost tracker service to persist segment_id
- ✅ Enhance debug feature to use both Redis (fast) + DB (historical)

**Effort:** ~2 hours
**Impact:** High (complete cost audit trail, better debug feature, future analytics)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-28
**Status:** Awaiting decision

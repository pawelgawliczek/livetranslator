# Room Cleanup Service - Documentation

## Overview

The room cleanup service automatically **archives and deletes** abandoned rooms (where the admin has been absent for 30+ minutes) while preserving all billing data, historical metrics, and user information.

**NEW (2025-10-21):** Rooms are now archived to `room_archive` table before deletion, preserving historical data including:
- Duration, STT minutes, cost, participants, and message count
- Users can view their complete room history including deleted rooms via the history API

## Service Details

**Container:** `room_cleanup`
**Script:** [api/services/room_cleanup_service.py](api/services/room_cleanup_service.py)
**Status:** ✅ Working (as of 2025-10-21)

### Configuration

Environment variables (set in [docker-compose.yml](docker-compose.yml#L248)):

```bash
ROOM_CLEANUP_INTERVAL=300      # Check every 5 minutes (300 seconds)
ADMIN_ABSENT_THRESHOLD=30      # Delete rooms after 30 minutes of admin absence
```

### How It Works

1. **Every 5 minutes**, the service queries for rooms where:
   - `admin_left_at` is NOT NULL
   - `admin_left_at` < NOW() - 30 minutes

2. **Archives the room** to `room_archive` table with pre-calculated metrics:
   - Total participants (COUNT DISTINCT from `room_participants`)
   - Total messages (COUNT from `segments` WHERE final = true)
   - Duration in minutes (created_at to now)
   - STT minutes and costs (from `room_costs`)
   - MT costs (from `room_costs`)

3. **Deletes the room**, which CASCADE deletes:
   - `segments` (transcription messages)
   - `devices` (device records)
   - `events` (event records)
   - `room_participants` (participant list)

4. **Preserves** (NO foreign key, won't be deleted):
   - `room_archive` - **NEW**: Historical room data with metrics ✅
   - `room_costs` - Uses `room_code` (string) not `room_id` (FK) ✅
   - `translations` - Uses `room_code` (string) not `room_id` (FK) ✅
   - `users` - Never touched ✅
   - `user_subscriptions` - Never touched ✅
   - `user_usage` - Never touched ✅

## Database Schema

### Foreign Key Constraints (WITH CASCADE)

As of migration [003_fix_room_cleanup_cascade.sql](migrations/003_fix_room_cleanup_cascade.sql):

```sql
-- These CASCADE when room is deleted:
segments.room_id          → rooms.id  ON DELETE CASCADE
devices.room_id           → rooms.id  ON DELETE CASCADE
events.room_id            → rooms.id  ON DELETE CASCADE
room_participants.room_id → rooms.id  ON DELETE CASCADE
```

### Room Archive Table (NEW - Migration 004)

**Purpose:** Preserve room history after deletion for user visibility and analytics

As of migration [004_add_room_archive.sql](migrations/004_add_room_archive.sql):

```sql
CREATE TABLE room_archive (
    id SERIAL PRIMARY KEY,
    room_code VARCHAR(12) UNIQUE NOT NULL,
    owner_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL,
    archived_at TIMESTAMP DEFAULT NOW(),

    -- Room settings
    recording BOOLEAN,
    is_public BOOLEAN,
    requires_login BOOLEAN,
    max_participants INTEGER,

    -- Pre-calculated metrics (captured at archive time)
    total_participants INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    duration_minutes NUMERIC(10, 2) DEFAULT 0,
    stt_minutes NUMERIC(10, 2) DEFAULT 0,
    stt_cost_usd NUMERIC(12, 6) DEFAULT 0,
    mt_cost_usd NUMERIC(12, 6) DEFAULT 0,
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,

    archive_reason VARCHAR(50) DEFAULT 'cleanup'
);
```

**Benefits:**
- Users can see complete room history via `/api/user/history`
- Historical metrics are pre-calculated for performance
- No need to JOIN deleted room data at query time
- Preserves audit trail for billing/support

### No Foreign Key (PRESERVED on room deletion)

```sql
-- These use room_code (string), no FK:
room_costs.room_id      = 'q-mh0ly685'  (room code as TEXT, not FK)
translations.room_id    = 'q-mh0ly685'  (room code as VARCHAR, not FK)
room_archive.room_code  = 'q-mh0ly685'  (room code as VARCHAR, not FK)
```

## User Quota System

### Three Subscription Tiers

The LiveTranslator platform offers **three subscription tiers** with different quotas and features:

| Tier | Monthly STT Quota | Monthly MT Tokens | Price | Features |
|------|-------------------|-------------------|-------|----------|
| **Free** | **60 minutes** (1 hour) | 100,000 tokens | **$0** | - Basic real-time translation<br>- No history persistence<br>- Limited quota |
| **Plus** | **Custom quota** | Custom | **$9.99/month** | - Increased quota<br>- History persistence<br>- Export capabilities<br>- Priority support |
| **Pro** | **Unlimited** (NULL) | Unlimited | **$29.99/month** | - Unlimited usage<br>- Full history persistence<br>- Advanced AI features<br>- Video chat (planned)<br>- Premium support |

### Free Tier Limitations

**Important:** Free tier users get **1 hour (60 minutes) of STT per month**. This quota:
- Resets at the start of each billing period
- Is tracked via the `room_costs` table
- Is enforced by the billing API
- **Persists even after room cleanup** ✅

This means free users can use the service for conversations totaling up to 1 hour per month, after which they need to upgrade to continue using STT features.

### How Quotas Are Tracked

1. **STT usage is logged** in `room_costs` table:
   - `pipeline = 'stt_final'`
   - `units` = seconds of audio
   - `room_id` = room code (string)

2. **Billing API calculates usage** from `room_costs`:
   - Endpoint: `GET /api/billing/usage`
   - Aggregates STT seconds → minutes
   - Groups by billing period
   - File: [api/billing_api.py:38](api/billing_api.py#L38)

3. **Even after room deletion**, costs remain in `room_costs` ✅

### Example Query

```sql
-- Get user's total STT usage for current billing period
SELECT
    SUM(units) / 60.0 as total_stt_minutes,
    SUM(amount_usd) as total_cost_usd
FROM room_costs rc
JOIN rooms r ON rc.room_id = r.code
WHERE r.owner_id = 123  -- user_id
  AND rc.pipeline = 'stt_final'
  AND rc.ts >= '2025-10-01'  -- billing_period_start
  AND rc.ts < '2025-11-01';  -- billing_period_end
```

## What Happens When a Room is Deleted?

### ✅ PRESERVED (for billing/history)

- **User accounts** - All user data intact
- **Subscription info** - Plan, billing periods, quotas
- **Usage costs** - `room_costs` table (uses room_code string)
- **Translation cache** - `translations` table (uses room_code string)
- **Billing history** - User can see STT minutes used for deleted rooms

### ❌ DELETED (transient data)

- **Room metadata** - `rooms` table entry
- **Messages** - `segments` table (CASCADE)
- **Participants** - `room_participants` table (CASCADE)
- **Devices** - `devices` table (CASCADE)
- **Events** - `events` table (CASCADE)

## Unit Tests

### Test Coverage

Comprehensive unit tests are provided in [api/tests/test_room_cleanup_service.py](api/tests/test_room_cleanup_service.py):

**Test Categories:**
1. **Abandoned Room Detection** - Verifies rooms with admin_left_at > 30 minutes are identified
2. **Active Room Preservation** - Ensures active rooms are NOT deleted
3. **Configuration Tests** - Validates environment variable settings (interval, threshold)
4. **Error Handling** - Tests graceful handling of database errors
5. **Cascade Deletion** - Verifies segments, devices, events, participants are deleted
6. **Data Preservation** - Confirms room_costs, users, subscriptions are preserved
7. **Quota System Integration** - Validates billing data remains queryable after cleanup

### Running the Tests

```bash
# Run all cleanup service tests
pytest api/tests/test_room_cleanup_service.py -v

# Run with coverage
pytest api/tests/test_room_cleanup_service.py --cov=api.services.room_cleanup_service --cov-report=html

# Run specific test
pytest api/tests/test_room_cleanup_service.py::TestRoomCleanupService::test_cleanup_finds_abandoned_rooms -v
```

### Test Results

All tests should pass, verifying:
- ✅ Configuration is loaded correctly
- ✅ Abandoned rooms are identified
- ✅ Active rooms are ignored
- ✅ Errors are handled gracefully
- ✅ Database commits occur on success
- ✅ Data preservation design is correct

## Integration Testing

### Verified Test Results (2025-10-21)

```sql
-- Test room: q-mh0ly685
-- Before deletion:
--   Segments: 33
--   Room costs: 63
--   Users: 6

-- After deletion:
--   Segments: 0 (cascade deleted) ✅
--   Room costs: 63 (PRESERVED) ✅
--   Users: 6 (unchanged) ✅
```

### How to Test Manually

```sql
-- 1. Mark a room as abandoned
UPDATE rooms
SET admin_left_at = NOW() - INTERVAL '31 minutes'
WHERE code = 'test-room';

-- 2. Wait for cleanup service (5 min) OR run manual deletion:
DELETE FROM rooms WHERE code = 'test-room';

-- 3. Verify data preserved:
SELECT COUNT(*) FROM room_costs WHERE room_id = 'test-room';  -- Should still have records
SELECT COUNT(*) FROM segments WHERE room_id = (SELECT id FROM rooms WHERE code = 'test-room');  -- Should be 0
```

## Monitoring the Service

### Check Service Status

```bash
docker compose ps room_cleanup
```

### View Logs

```bash
# Recent logs
docker compose logs room_cleanup --tail=50

# Follow logs
docker compose logs -f room_cleanup

# Search for cleanup events
docker compose logs room_cleanup | grep "Deleting room"
```

### Log Examples

```
[Room Cleanup] Starting...
  Interval: 300s
  Threshold: 30 minutes
  Database: postgres:5432/livetranslator

[Room Cleanup] No abandoned rooms found
[Room Cleanup] Found 4 abandoned rooms to delete
[Room Cleanup] Deleting room q-mh0gir37 (admin absent for 62 minutes)
[Room Cleanup] ✓ Deleted 4 abandoned rooms
```

## Troubleshooting

### Issue: Foreign Key Violation Errors

**Symptom:**
```
[Room Cleanup] ✗ Error during cleanup: violates foreign key constraint
```

**Solution:**
Migration [003_fix_room_cleanup_cascade.sql](migrations/003_fix_room_cleanup_cascade.sql) fixes this by adding CASCADE constraints. Verify with:

```sql
SELECT constraint_name, table_name, delete_rule
FROM information_schema.referential_constraints
WHERE constraint_name LIKE '%room_id%';
```

All should show `delete_rule = 'CASCADE'`.

### Issue: User Loses Billing History

**This should NOT happen** because `room_costs` has no FK to rooms.

**Verify:**
```sql
-- Check if room_costs has FK (should return 0 rows)
SELECT constraint_name
FROM information_schema.table_constraints
WHERE table_name = 'room_costs'
  AND constraint_type = 'FOREIGN KEY';
```

## Future Enhancements

### Potential Improvements

1. **Soft delete** - Add `deleted_at` column to rooms instead of hard delete
2. **Configurable retention** - Keep room metadata for X days before cleanup
3. **User notification** - Email users before their rooms are deleted
4. **Archive mode** - Move old rooms to archive table instead of deleting
5. **Quota warnings** - Alert users when approaching monthly limit

### Related Files

- [api/services/room_cleanup_service.py](api/services/room_cleanup_service.py) - Main cleanup logic
- [api/billing_api.py](api/billing_api.py) - Quota tracking and billing
- [api/models.py](api/models.py) - Database models
- [migrations/003_fix_room_cleanup_cascade.sql](migrations/003_fix_room_cleanup_cascade.sql) - CASCADE fix
- [docker-compose.yml](docker-compose.yml#L248) - Service configuration

---

**Last Updated:** 2025-10-21
**Status:** ✅ Working correctly

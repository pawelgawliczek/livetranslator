-- Migration 010: Add segment_id to room_costs for per-message cost tracking
-- Created: 2025-10-28
-- Purpose: Enable exact cost attribution to specific messages for debug tracking and analytics

BEGIN;

-- Add segment_id column (nullable for backward compatibility)
ALTER TABLE room_costs
ADD COLUMN segment_id INTEGER;

-- Add index for segment_id lookups
CREATE INDEX idx_room_costs_segment_id
ON room_costs(segment_id)
WHERE segment_id IS NOT NULL;

-- Add composite index for room + segment queries (common pattern for per-message cost lookup)
CREATE INDEX idx_room_costs_room_segment
ON room_costs(room_id, segment_id)
WHERE segment_id IS NOT NULL;

COMMENT ON COLUMN room_costs.segment_id IS 'Link to segments table for per-message cost tracking. NULL for legacy records before this migration.';

COMMIT;

-- Verification
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 010 completed successfully';
    RAISE NOTICE '📊 segment_id column added to room_costs';
    RAISE NOTICE '🔍 Indexes created for efficient queries';
END $$;

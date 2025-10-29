-- Migration 011: Change room_costs.units from bigint to numeric(12,3)
-- Created: 2025-10-29
-- Purpose: Fix cost calculation precision - store fractional seconds instead of truncating
--          Speechmatics bills to the second (not rounded to minutes), but bigint was truncating
--          fractional seconds (e.g., 3.245s → 3s), causing undercharging

BEGIN;

-- Step 1: Drop dependent view
DROP VIEW IF EXISTS cost_analysis;

-- Step 2: Alter the column type from bigint to numeric(12,3)
-- This preserves existing integer values while allowing future fractional values
ALTER TABLE room_costs
ALTER COLUMN units TYPE NUMERIC(12, 3);

COMMENT ON COLUMN room_costs.units IS 'Usage units with fractional precision (e.g., 3.245 seconds, 1234.567 tokens). Changed from bigint to numeric(12,3) to support fractional seconds for accurate STT billing.';

-- Step 3: Recreate the cost_analysis view
CREATE VIEW cost_analysis AS
SELECT room_id,
    pipeline AS service,
    provider,
    mode,
    count(*) AS event_count,
    sum(units) AS total_units,
    unit_type,
    sum(amount_usd) AS total_cost_usd,
    min(ts) AS first_event,
    max(ts) AS last_event
FROM room_costs rc
WHERE provider IS NOT NULL
GROUP BY room_id, pipeline, provider, mode, unit_type
ORDER BY max(ts) DESC;

COMMIT;

-- Verification
DO $$
DECLARE
    col_type text;
    sample_count int;
BEGIN
    -- Check column type
    SELECT data_type INTO col_type
    FROM information_schema.columns
    WHERE table_name = 'room_costs' AND column_name = 'units';

    IF col_type = 'numeric' THEN
        RAISE NOTICE '✅ Migration 011 completed successfully';
        RAISE NOTICE '📊 units column type changed from bigint to numeric(12,3)';

        -- Count existing records
        SELECT COUNT(*) INTO sample_count FROM room_costs;
        RAISE NOTICE '🔢 Existing records preserved: %', sample_count;

        RAISE NOTICE '💡 Future cost tracking will now store fractional seconds (e.g., 3.245s instead of 3s)';
    ELSE
        RAISE EXCEPTION '❌ Migration failed: column type is % instead of numeric', col_type;
    END IF;
END $$;

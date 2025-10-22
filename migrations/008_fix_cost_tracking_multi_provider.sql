-- Migration 008: Fix Cost Tracking for Multi-Provider Support
-- Date: 2025-10-22
-- Purpose: Remove constraints blocking multi-provider costs and add provider pricing table

-- Step 1: Remove restrictive mode constraint from room_costs
ALTER TABLE room_costs DROP CONSTRAINT IF EXISTS room_costs_mode_chk;

-- Step 2: Add provider column to room_costs (stores actual provider used)
ALTER TABLE room_costs ADD COLUMN IF NOT EXISTS provider VARCHAR(50);

-- Step 3: Backfill provider column from mode column for existing data
UPDATE room_costs SET provider = mode WHERE provider IS NULL;

-- Step 4: Create provider_pricing table for centralized pricing
CREATE TABLE IF NOT EXISTS provider_pricing (
    id SERIAL PRIMARY KEY,
    service VARCHAR(20) NOT NULL,  -- 'stt' or 'mt'
    provider VARCHAR(50) NOT NULL,  -- 'speechmatics', 'google_v2', 'openai', etc.
    pricing_model VARCHAR(20) NOT NULL,  -- 'per_minute', 'per_hour', 'per_1k_tokens', 'per_1m_chars'
    unit_price NUMERIC(12,6) NOT NULL,  -- Price per unit
    currency VARCHAR(3) DEFAULT 'USD',
    notes TEXT,
    effective_date TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(service, provider, effective_date)
);

-- Step 5: Insert STT provider pricing
INSERT INTO provider_pricing (service, provider, pricing_model, unit_price, notes) VALUES
    -- STT Providers (convert all to per_hour for consistency)
    ('stt', 'speechmatics', 'per_hour', 0.08, 'Speechmatics real-time streaming - $0.08/hr'),
    ('stt', 'google_v2', 'per_hour', 1.44, 'Google Cloud Speech v2 - $0.024/min = $1.44/hr'),
    ('stt', 'azure', 'per_hour', 1.00, 'Azure Speech SDK - ~$1.00/hr standard'),
    ('stt', 'soniox', 'per_hour', 0.015, 'Soniox budget tier - $0.00025/min = $0.015/hr'),
    ('stt', 'openai', 'per_hour', 0.36, 'OpenAI Whisper API - $0.006/min = $0.36/hr'),

    -- MT Providers (per 1M characters)
    ('mt', 'deepl', 'per_1m_chars', 10.00, 'DeepL Pro API - $10/1M chars'),
    ('mt', 'azure_translator', 'per_1m_chars', 10.00, 'Azure Translator - $10/1M chars'),
    ('mt', 'openai', 'per_1k_tokens', 0.375, 'OpenAI GPT-4o-mini - avg $0.15 input + $0.60 output')
ON CONFLICT (service, provider, effective_date) DO UPDATE SET
    unit_price = EXCLUDED.unit_price,
    notes = EXCLUDED.notes,
    updated_at = NOW();

-- Step 6: Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_room_costs_provider ON room_costs(provider);
CREATE INDEX IF NOT EXISTS idx_room_costs_pipeline_provider ON room_costs(pipeline, provider);
CREATE INDEX IF NOT EXISTS idx_provider_pricing_service_provider ON provider_pricing(service, provider);

-- Step 7: Add view for easy cost analysis
CREATE OR REPLACE VIEW cost_analysis AS
SELECT
    rc.room_id,
    rc.pipeline as service,
    rc.provider,
    rc.mode,
    COUNT(*) as event_count,
    SUM(rc.units) as total_units,
    rc.unit_type,
    SUM(rc.amount_usd) as total_cost_usd,
    MIN(rc.ts) as first_event,
    MAX(rc.ts) as last_event
FROM room_costs rc
WHERE rc.provider IS NOT NULL
GROUP BY rc.room_id, rc.pipeline, rc.provider, rc.mode, rc.unit_type
ORDER BY last_event DESC;

-- Step 8: Add function to get current pricing
CREATE OR REPLACE FUNCTION get_provider_price(
    p_service VARCHAR,
    p_provider VARCHAR
) RETURNS NUMERIC AS $$
DECLARE
    v_price NUMERIC;
BEGIN
    SELECT unit_price INTO v_price
    FROM provider_pricing
    WHERE service = p_service
      AND provider = p_provider
      AND effective_date <= NOW()
    ORDER BY effective_date DESC
    LIMIT 1;

    RETURN COALESCE(v_price, 0);
END;
$$ LANGUAGE plpgsql;

-- Verification queries
-- SELECT * FROM provider_pricing ORDER BY service, provider;
-- SELECT * FROM cost_analysis LIMIT 20;
-- SELECT get_provider_price('stt', 'speechmatics');

-- Migration 015: Add TTS (Text-to-Speech) Feature
-- Created: 2025-11-01
-- Purpose: Enable real-time text-to-speech for translations

BEGIN;

-- ============================================================================
-- STEP 1: Create TTS routing configuration table
-- ============================================================================

CREATE TABLE IF NOT EXISTS tts_routing_config (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,          -- en, pl, ar, es, fr, de, etc.
    quality_tier VARCHAR(20) NOT NULL,      -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- google_tts, azure_tts, amazon_tts, openai_tts
    provider_fallback VARCHAR(50),          -- Fallback if primary fails
    config JSONB DEFAULT '{}',              -- Provider-specific config (voice, pitch, rate, etc.)
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(language, quality_tier)          -- One config per language/tier combination
);

CREATE INDEX IF NOT EXISTS idx_tts_routing_language ON tts_routing_config(language);
CREATE INDEX IF NOT EXISTS idx_tts_routing_enabled ON tts_routing_config(enabled) WHERE enabled = TRUE;

COMMENT ON TABLE tts_routing_config IS 'Global TTS provider routing configuration based on language and quality tier';
COMMENT ON COLUMN tts_routing_config.language IS 'ISO language code (en, pl, ar, etc.) or * for wildcard fallback';
COMMENT ON COLUMN tts_routing_config.quality_tier IS 'standard (best quality) or budget (cost-optimized)';
COMMENT ON COLUMN tts_routing_config.config IS 'JSON config: {voice_id: "en-US-Wavenet-D", pitch: 0.0, speaking_rate: 1.0, etc.}';

-- ============================================================================
-- STEP 2: Add user TTS preferences to users table
-- ============================================================================

-- TTS enabled by default for user
ALTER TABLE users ADD COLUMN IF NOT EXISTS tts_enabled BOOLEAN DEFAULT TRUE NOT NULL;

-- Per-language voice preferences (JSON: {en: "en-US-Wavenet-D", pl: "pl-PL-Wavenet-A", ...})
ALTER TABLE users ADD COLUMN IF NOT EXISTS tts_voice_preferences JSONB DEFAULT '{}' NOT NULL;

-- Global TTS settings
ALTER TABLE users ADD COLUMN IF NOT EXISTS tts_volume FLOAT DEFAULT 1.0 NOT NULL CHECK (tts_volume >= 0.0 AND tts_volume <= 2.0);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tts_rate FLOAT DEFAULT 1.0 NOT NULL CHECK (tts_rate >= 0.25 AND tts_rate <= 4.0);
ALTER TABLE users ADD COLUMN IF NOT EXISTS tts_pitch FLOAT DEFAULT 0.0 NOT NULL CHECK (tts_pitch >= -20.0 AND tts_pitch <= 20.0);

COMMENT ON COLUMN users.tts_enabled IS 'Whether TTS is enabled for this user';
COMMENT ON COLUMN users.tts_voice_preferences IS 'Per-language voice selection: {en: "en-US-Wavenet-D", pl: "pl-PL-Wavenet-A"}';
COMMENT ON COLUMN users.tts_volume IS 'TTS playback volume (0.0 - 2.0, default 1.0)';
COMMENT ON COLUMN users.tts_rate IS 'TTS speaking rate (0.25 - 4.0, default 1.0)';
COMMENT ON COLUMN users.tts_pitch IS 'TTS voice pitch in semitones (-20.0 to 20.0, default 0.0)';

-- ============================================================================
-- STEP 3: Add room TTS settings to rooms table
-- ============================================================================

-- TTS enabled by default for room
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS tts_enabled BOOLEAN DEFAULT TRUE NOT NULL;

-- Per-language voice overrides for room (optional, overrides user preferences)
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS tts_voice_overrides JSONB DEFAULT '{}' NOT NULL;

COMMENT ON COLUMN rooms.tts_enabled IS 'Whether TTS is enabled for this room (can be disabled to save costs)';
COMMENT ON COLUMN rooms.tts_voice_overrides IS 'Room-level voice overrides per language: {en: "en-US-Wavenet-D", pl: "pl-PL-Wavenet-A"}';

-- ============================================================================
-- STEP 4: Add TTS provider pricing to provider_pricing table
-- ============================================================================

-- Ensure provider_pricing table exists (created in migration 002)
-- Add TTS provider pricing entries

INSERT INTO provider_pricing (service, provider, pricing_model, unit_price, currency, notes) VALUES
    ('tts', 'google_tts', 'per_character', 0.000016, 'USD', 'Google Cloud TTS Standard voices - $16 per 1M characters'),
    ('tts', 'google_tts_wavenet', 'per_character', 0.000016, 'USD', 'Google Cloud TTS WaveNet voices - $16 per 1M characters'),
    ('tts', 'google_tts_neural2', 'per_character', 0.000016, 'USD', 'Google Cloud TTS Neural2 voices - $16 per 1M characters'),
    ('tts', 'azure_tts', 'per_character', 0.000016, 'USD', 'Azure TTS Standard voices - $16 per 1M characters'),
    ('tts', 'azure_tts_neural', 'per_character', 0.000020, 'USD', 'Azure TTS Neural voices - $20 per 1M characters'),
    ('tts', 'amazon_tts', 'per_character', 0.000004, 'USD', 'Amazon Polly Standard voices - $4 per 1M characters'),
    ('tts', 'amazon_tts_neural', 'per_character', 0.000016, 'USD', 'Amazon Polly Neural voices - $16 per 1M characters'),
    ('tts', 'openai_tts', 'per_character', 0.000015, 'USD', 'OpenAI TTS (tts-1) - $15 per 1M characters'),
    ('tts', 'openai_tts_hd', 'per_character', 0.000030, 'USD', 'OpenAI TTS HD (tts-1-hd) - $30 per 1M characters')
ON CONFLICT (service, provider, effective_date) DO UPDATE
    SET unit_price = EXCLUDED.unit_price,
        notes = EXCLUDED.notes,
        updated_at = NOW();

-- ============================================================================
-- STEP 5: Seed data - TTS routing configuration (Standard Tier)
-- ============================================================================

-- English - Google TTS Neural2 (best quality)
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('en', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "en-US-Neural2-D", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "MALE"}');

-- Polish - Google TTS Neural2
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pl', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "pl-PL-Wavenet-A", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- Arabic - Azure TTS Neural (better Arabic support)
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('ar', 'standard', 'azure_tts', 'google_tts',
     '{"voice_id": "ar-EG-SalmaNeural", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- Spanish - Google TTS Neural2
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('es', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "es-ES-Neural2-A", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- French - Google TTS Neural2
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('fr', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "fr-FR-Neural2-A", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- German - Google TTS Neural2
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('de', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "de-DE-Neural2-A", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- Italian - Google TTS Neural2
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('it', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "it-IT-Neural2-A", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- Portuguese - Google TTS Neural2
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pt', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "pt-PT-Wavenet-A", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- Russian - Azure TTS Neural
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('ru', 'standard', 'azure_tts', 'google_tts',
     '{"voice_id": "ru-RU-SvetlanaNeural", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "FEMALE"}');

-- Generic fallback for other languages (*)
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', 'standard', 'google_tts', 'azure_tts',
     '{"voice_id": "en-US-Neural2-D", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "MALE"}');

-- ============================================================================
-- STEP 6: Seed data - TTS routing configuration (Budget Tier)
-- ============================================================================

-- Budget mode uses Amazon Polly Standard (cheapest at $4/1M chars)
INSERT INTO tts_routing_config (language, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', 'budget', 'amazon_tts', 'google_tts',
     '{"voice_id": "Matthew", "pitch": 0.0, "speaking_rate": 1.0, "voice_gender": "MALE"}');

-- ============================================================================
-- STEP 7: Add TTS provider health monitoring
-- ============================================================================

INSERT INTO provider_health (provider, service_type, status, last_check) VALUES
    ('google_tts', 'tts', 'healthy', NOW()),
    ('azure_tts', 'tts', 'healthy', NOW()),
    ('amazon_tts', 'tts', 'healthy', NOW()),
    ('openai_tts', 'tts', 'healthy', NOW())
ON CONFLICT (provider, service_type) DO NOTHING;

-- ============================================================================
-- STEP 8: Insert migration record
-- ============================================================================

INSERT INTO schema_migrations (version, name, applied_at)
VALUES ('015', 'add_tts_feature', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- ============================================================================
-- Migration complete!
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Migration 015 completed successfully';
    RAISE NOTICE '📊 TTS routing configs: %', (SELECT COUNT(*) FROM tts_routing_config);
    RAISE NOTICE '🏥 TTS provider health entries: %', (SELECT COUNT(*) FROM provider_health WHERE service_type = 'tts');
END $$;

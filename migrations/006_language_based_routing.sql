-- Migration 006: Language-Based Routing Configuration
-- Created: 2025-10-22
-- Purpose: Replace per-room STT configuration with global language-based routing
--          Add support for multi-provider STT/MT with automatic fallback

BEGIN;

-- ============================================================================
-- STEP 1: Remove old per-room configuration
-- ============================================================================

-- Remove per-room STT provider overrides (from Phase 0.1-0.3)
ALTER TABLE rooms DROP COLUMN IF EXISTS stt_partial_provider;
ALTER TABLE rooms DROP COLUMN IF EXISTS stt_final_provider;

-- Clean up old system_settings entries (if they exist)
DELETE FROM system_settings WHERE key IN ('stt_partial_provider_default', 'stt_final_provider_default');

-- ============================================================================
-- STEP 2: Create language-based STT routing configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS stt_routing_config (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,          -- pl-PL, ar-EG, en-US, en-GB, es-ES, *, etc.
    mode VARCHAR(10) NOT NULL,              -- 'partial' or 'final'
    quality_tier VARCHAR(20) NOT NULL,      -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- speechmatics, google_v2, azure, soniox, openai, local
    provider_fallback VARCHAR(50),          -- Fallback if primary fails
    config JSONB DEFAULT '{}',              -- Provider-specific config (diarization, max_delay, etc.)
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(language, mode, quality_tier)    -- One config per language/mode/tier combination
);

CREATE INDEX idx_stt_routing_language ON stt_routing_config(language);
CREATE INDEX idx_stt_routing_mode ON stt_routing_config(mode);
CREATE INDEX idx_stt_routing_enabled ON stt_routing_config(enabled) WHERE enabled = TRUE;

COMMENT ON TABLE stt_routing_config IS 'Global STT provider routing configuration based on language, mode, and quality tier';
COMMENT ON COLUMN stt_routing_config.language IS 'ISO language code (pl-PL, ar-EG, en-US, etc.) or * for wildcard fallback';
COMMENT ON COLUMN stt_routing_config.mode IS 'partial (real-time streaming) or final (post-speech quality)';
COMMENT ON COLUMN stt_routing_config.quality_tier IS 'standard (best quality) or budget (cost-optimized)';
COMMENT ON COLUMN stt_routing_config.config IS 'JSON config: {diarization: true, max_delay: 1.5, stability_threshold: 0.8, etc.}';

-- ============================================================================
-- STEP 3: Create language-pair-based MT routing configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS mt_routing_config (
    id SERIAL PRIMARY KEY,
    src_lang VARCHAR(10) NOT NULL,          -- Source language (en, pl, ar, etc.) or * for wildcard
    tgt_lang VARCHAR(10) NOT NULL,          -- Target language (en, pl, ar, etc.) or * for wildcard
    quality_tier VARCHAR(20) NOT NULL,      -- 'standard' or 'budget'
    provider_primary VARCHAR(50) NOT NULL,   -- deepl, azure_translator, google_translate, openai
    provider_fallback VARCHAR(50),          -- Fallback if primary fails
    config JSONB DEFAULT '{}',              -- Provider-specific config (context, glossary, etc.)
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(src_lang, tgt_lang, quality_tier)  -- One config per language pair/tier
);

CREATE INDEX idx_mt_routing_lang_pair ON mt_routing_config(src_lang, tgt_lang);
CREATE INDEX idx_mt_routing_enabled ON mt_routing_config(enabled) WHERE enabled = TRUE;

COMMENT ON TABLE mt_routing_config IS 'Global MT provider routing configuration based on language pairs and quality tier';
COMMENT ON COLUMN mt_routing_config.src_lang IS 'Source language ISO code or * for wildcard';
COMMENT ON COLUMN mt_routing_config.tgt_lang IS 'Target language ISO code or * for wildcard';
COMMENT ON COLUMN mt_routing_config.config IS 'JSON config: {use_context: true, use_glossary: true, formality: "default", etc.}';

-- ============================================================================
-- STEP 4: Create provider health monitoring table
-- ============================================================================

CREATE TABLE IF NOT EXISTS provider_health (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL,          -- speechmatics, google_v2, azure, soniox, deepl, etc.
    service_type VARCHAR(10) NOT NULL,      -- 'stt' or 'mt'
    status VARCHAR(20) NOT NULL,            -- 'healthy', 'degraded', 'down'
    last_check TIMESTAMP NOT NULL,
    consecutive_failures INTEGER DEFAULT 0,
    last_error TEXT,
    last_success TIMESTAMP,
    response_time_ms INTEGER,               -- Average response time
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(provider, service_type)
);

CREATE INDEX idx_provider_health_status ON provider_health(provider, status);
CREATE INDEX idx_provider_health_service ON provider_health(service_type);

COMMENT ON TABLE provider_health IS 'Real-time health status of STT/MT providers for automatic fallback';
COMMENT ON COLUMN provider_health.consecutive_failures IS 'Triggers fallback after 3 consecutive failures';

-- ============================================================================
-- STEP 5: Enhance segments table with provider tracking
-- ============================================================================

ALTER TABLE segments ADD COLUMN IF NOT EXISTS stt_provider VARCHAR(50);
ALTER TABLE segments ADD COLUMN IF NOT EXISTS latency_ms INTEGER;

CREATE INDEX idx_segments_provider ON segments(stt_provider) WHERE stt_provider IS NOT NULL;

COMMENT ON COLUMN segments.stt_provider IS 'STT provider used (speechmatics, google_v2, azure, soniox, openai, local)';
COMMENT ON COLUMN segments.latency_ms IS 'Time from audio_end to final transcription (milliseconds)';

-- ============================================================================
-- STEP 6: Enhance translations table with provider tracking
-- ============================================================================

ALTER TABLE translations ADD COLUMN IF NOT EXISTS mt_provider VARCHAR(50);
ALTER TABLE translations ADD COLUMN IF NOT EXISTS context_used BOOLEAN DEFAULT FALSE;
ALTER TABLE translations ADD COLUMN IF NOT EXISTS glossary_used BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_translations_provider ON translations(mt_provider) WHERE mt_provider IS NOT NULL;

COMMENT ON COLUMN translations.mt_provider IS 'MT provider used (deepl, azure_translator, google_translate, openai)';
COMMENT ON COLUMN translations.context_used IS 'Whether conversation context was used for this translation';
COMMENT ON COLUMN translations.glossary_used IS 'Whether custom glossary was applied for this translation';

-- ============================================================================
-- STEP 7: Create quality metrics table
-- ============================================================================

CREATE TABLE IF NOT EXISTS quality_metrics (
    id BIGSERIAL PRIMARY KEY,
    room_id VARCHAR(255) NOT NULL,
    segment_id INTEGER NOT NULL,
    provider VARCHAR(50) NOT NULL,
    service_type VARCHAR(10) NOT NULL,      -- 'stt' or 'mt'
    language VARCHAR(10) NOT NULL,
    latency_ms INTEGER,
    wer FLOAT,                               -- Word Error Rate (if reference available)
    confidence FLOAT,                        -- Provider confidence score (0-1)
    diarization_speakers INTEGER,           -- Number of speakers detected
    fallback_used BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_quality_metrics_room ON quality_metrics(room_id);
CREATE INDEX idx_quality_metrics_provider ON quality_metrics(provider);
CREATE INDEX idx_quality_metrics_timestamp ON quality_metrics(timestamp DESC);

COMMENT ON TABLE quality_metrics IS 'Quality and performance metrics for STT/MT providers';
COMMENT ON COLUMN quality_metrics.wer IS 'Word Error Rate compared to reference (0-1, lower is better)';

-- ============================================================================
-- STEP 8: Seed data - STT routing configuration (Standard Tier)
-- ============================================================================

-- Polish (pl-PL) - Speechmatics best for Polish accuracy
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pl-PL', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('pl-PL', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}');

-- Arabic (ar-EG) - Google v2 primary, Azure fallback
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('ar-EG', 'partial', 'standard', 'google_v2', 'azure',
     '{"diarization": true, "stability_threshold": 0.8, "interim_results": true}'),
    ('ar-EG', 'final', 'standard', 'google_v2', 'azure',
     '{"diarization": true}');

-- English (US) - Speechmatics to reduce vendor spread
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('en-US', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('en-US', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}');

-- English (GB) - Speechmatics
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('en-GB', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('en-GB', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}');

-- Generic fallback for other languages (*)
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', 'partial', 'standard', 'google_v2', 'azure',
     '{"diarization": true, "stability_threshold": 0.8, "interim_results": true}'),
    ('*', 'final', 'standard', 'google_v2', 'azure',
     '{"diarization": true}');

-- ============================================================================
-- STEP 9: Seed data - STT routing configuration (Budget Tier)
-- ============================================================================

-- Budget mode uses Soniox for all languages (80% cheaper)
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('*', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}');

-- ============================================================================
-- STEP 10: Seed data - MT routing configuration (Standard Tier)
-- ============================================================================

-- Polish ↔ English (DeepL best for European languages)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pl', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}');

-- English ↔ European languages (DeepL)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('en', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}');

-- Polish ↔ European languages (DeepL)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pl', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}');

-- English/Polish ↔ Non-European (Azure Translator best)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('en', 'ar', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('en', 'ru', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('en', 'zh', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('en', 'ja', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('en', 'ko', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('pl', 'ar', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('pl', 'ru', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('pl', 'zh', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('ar', 'en', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('ru', 'en', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('zh', 'en', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('ja', 'en', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('ko', 'en', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('ar', 'pl', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('ru', 'pl', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}'),
    ('zh', 'pl', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}');

-- Generic fallback for unsupported language pairs
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', '*', 'standard', 'azure_translator', 'google_translate', '{"use_context": true}');

-- ============================================================================
-- STEP 11: Seed data - MT routing configuration (Budget Tier)
-- ============================================================================

-- Budget mode uses Azure Translator for all pairs (cheaper than DeepL)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('*', '*', 'budget', 'azure_translator', 'google_translate', '{}');

-- ============================================================================
-- STEP 12: Seed data - Provider health initialization
-- ============================================================================

INSERT INTO provider_health (provider, service_type, status, last_check) VALUES
    ('speechmatics', 'stt', 'healthy', NOW()),
    ('google_v2', 'stt', 'healthy', NOW()),
    ('azure', 'stt', 'healthy', NOW()),
    ('soniox', 'stt', 'healthy', NOW()),
    ('openai', 'stt', 'healthy', NOW()),
    ('local', 'stt', 'healthy', NOW()),
    ('deepl', 'mt', 'healthy', NOW()),
    ('azure_translator', 'mt', 'healthy', NOW()),
    ('google_translate', 'mt', 'healthy', NOW()),
    ('openai', 'mt', 'healthy', NOW())
ON CONFLICT (provider, service_type) DO NOTHING;

-- ============================================================================
-- STEP 13: Update room_costs table to track new providers
-- ============================================================================

-- Add check constraint for new providers (will be validated on insert)
-- Note: We keep the existing constraint flexible to allow new providers without migration

COMMENT ON TABLE room_costs IS 'Cost tracking for STT/MT API usage - supports multiple providers';
COMMENT ON COLUMN room_costs.mode IS 'Provider name: speechmatics, google_v2, azure, soniox, deepl, azure_translator, google_translate, openai, local';

COMMIT;

-- ============================================================================
-- Migration complete!
-- ============================================================================

-- Verify migration
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 006 completed successfully';
    RAISE NOTICE '📊 STT routing configs: %', (SELECT COUNT(*) FROM stt_routing_config);
    RAISE NOTICE '📊 MT routing configs: %', (SELECT COUNT(*) FROM mt_routing_config);
    RAISE NOTICE '🏥 Provider health entries: %', (SELECT COUNT(*) FROM provider_health);
END $$;

-- Migration 007: European Language Support
-- Created: 2025-10-22
-- Purpose: Add STT and MT configurations for European languages
--          Spanish, French, German, Italian, Portuguese (EU/BR), Russian

BEGIN;

-- ============================================================================
-- STEP 1: STT Configuration - Spanish (es-ES)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('es-ES', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('es-ES', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('es-ES', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('es-ES', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 2: STT Configuration - French (fr-FR)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('fr-FR', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('fr-FR', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('fr-FR', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('fr-FR', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 3: STT Configuration - German (de-DE)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('de-DE', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('de-DE', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('de-DE', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('de-DE', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 4: STT Configuration - Italian (it-IT)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('it-IT', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('it-IT', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('it-IT', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('it-IT', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 5: STT Configuration - Portuguese EU (pt-PT)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('pt-PT', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('pt-PT', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('pt-PT', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('pt-PT', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 6: STT Configuration - Portuguese BR (pt-BR)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('pt-BR', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('pt-BR', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('pt-BR', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('pt-BR', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 7: STT Configuration - Russian (ru-RU)
-- ============================================================================

INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config) VALUES
    -- Standard Tier
    ('ru-RU', 'partial', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "max_delay": 1.5, "operating_point": "enhanced"}'),
    ('ru-RU', 'final', 'standard', 'speechmatics', 'google_v2',
     '{"diarization": true, "operating_point": "enhanced", "max_delay": 4.0, "max_delay_mode": "flexible", "enable_entities": true, "punctuation_overrides": {"sensitivity": 0.7}, "speaker_diarization_config": {"max_speakers": 10}}'),

    -- Budget Tier
    ('ru-RU', 'partial', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}'),
    ('ru-RU', 'final', 'budget', 'soniox', 'google_v2',
     '{"diarization": true}')
ON CONFLICT (language, mode, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 8: MT Configuration - Spanish (es) translations
-- ============================================================================

-- Spanish ↔ English (both directions, both tiers)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('es', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'en', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('en', 'es', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Spanish ↔ Polish
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('es', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'pl', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'es', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Spanish ↔ Other European languages
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('es', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('es', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'es', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 9: MT Configuration - French (fr) translations
-- ============================================================================

-- French ↔ English (both directions, both tiers)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('fr', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'en', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('en', 'fr', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- French ↔ Polish
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('fr', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'pl', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'fr', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- French ↔ Other European languages
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('fr', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('fr', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'fr', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 10: MT Configuration - German (de) translations
-- ============================================================================

-- German ↔ English (both directions, both tiers)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('de', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'en', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('en', 'de', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- German ↔ Polish
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('de', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'pl', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'de', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- German ↔ Other European languages
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('de', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('de', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'de', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 11: MT Configuration - Italian (it) translations
-- ============================================================================

-- Italian ↔ English
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('it', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'en', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('en', 'it', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Italian ↔ Polish
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('it', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'pl', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'it', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Italian ↔ Other European languages
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('it', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('it', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'it', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 12: MT Configuration - Portuguese (pt) translations
-- ============================================================================

-- Portuguese ↔ English (handles both pt-PT and pt-BR)
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pt', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'en', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('en', 'pt', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Portuguese ↔ Polish
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pt', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pt', 'pl', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'pt', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Portuguese ↔ Other European languages
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('pt', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'pt', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- ============================================================================
-- STEP 13: MT Configuration - Russian (ru) translations
-- ============================================================================

-- Russian ↔ English
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('ru', 'en', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('en', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'en', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('en', 'ru', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

-- Russian ↔ Polish
INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config) VALUES
    ('ru', 'pl', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('pl', 'ru', 'standard', 'deepl', 'azure_translator', '{"use_context": true, "use_glossary": true}'),
    ('ru', 'pl', 'budget', 'azure_translator', 'google_translate', '{}'),
    ('pl', 'ru', 'budget', 'azure_translator', 'google_translate', '{}')
ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE SET
    provider_primary = EXCLUDED.provider_primary,
    provider_fallback = EXCLUDED.provider_fallback,
    config = EXCLUDED.config,
    updated_at = NOW();

COMMIT;

-- ============================================================================
-- Migration complete!
-- ============================================================================

-- Verify migration
DO $$
DECLARE
    stt_count INTEGER;
    mt_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO stt_count FROM stt_routing_config;
    SELECT COUNT(*) INTO mt_count FROM mt_routing_config;

    RAISE NOTICE '✅ Migration 007 completed successfully';
    RAISE NOTICE '📊 Total STT routing configs: %', stt_count;
    RAISE NOTICE '📊 Total MT routing configs: %', mt_count;
    RAISE NOTICE '🌍 Added 7 European languages: Spanish, French, German, Italian, Portuguese (EU/BR), Russian';
    RAISE NOTICE '🎯 Added % new language pairs for MT', (mt_count - (SELECT COUNT(*) FROM mt_routing_config WHERE created_at < NOW() - INTERVAL '1 second'));
END $$;

-- Migration 021: Extend system_settings for admin UI
-- Purpose: Add metadata columns for feature flags and rate limits management
-- US-003: System Settings Page

BEGIN;

-- Add metadata columns to system_settings
ALTER TABLE system_settings
  ADD COLUMN IF NOT EXISTS value_type VARCHAR(20) DEFAULT 'string',
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS category VARCHAR(50),
  ADD COLUMN IF NOT EXISTS updated_by INTEGER REFERENCES users(id);

-- Add index for category filtering
CREATE INDEX IF NOT EXISTS idx_system_settings_category
  ON system_settings(category);

COMMENT ON COLUMN system_settings.value_type IS 'Data type: string, boolean, integer, json';
COMMENT ON COLUMN system_settings.description IS 'Human-readable description for admin UI';
COMMENT ON COLUMN system_settings.category IS 'Category: stt, mt, performance, ui';
COMMENT ON COLUMN system_settings.updated_by IS 'User ID of admin who last updated this setting';

-- Seed feature flag data (with ON CONFLICT DO UPDATE for idempotency)
INSERT INTO system_settings (key, value, value_type, description, category) VALUES
    -- STT Feature Flags
    ('enable_diarization', 'true', 'boolean', 'Enable speaker identification across all providers', 'stt'),
    ('max_speakers_per_room', '10', 'integer', 'Maximum speakers in multi-speaker mode', 'stt'),
    ('enable_final_transcription', 'true', 'boolean', 'Enable final STT pass after speech ends', 'stt'),

    -- MT Feature Flags
    ('enable_translation_cache', 'true', 'boolean', 'Cache partial translations to reduce API calls', 'mt'),
    ('enable_arabic_throttling', 'true', 'boolean', 'Apply 2-second throttle for Arabic MT', 'mt'),

    -- Performance/Rate Limits
    ('stt_max_concurrent_connections', '100', 'integer', 'Max active STT WebSocket streams', 'performance'),
    ('mt_requests_per_minute_per_user', '60', 'integer', 'Per-user MT rate limit', 'performance'),
    ('api_requests_per_minute_global', '1000', 'integer', 'Global API rate limit', 'performance'),
    ('max_room_participants', '50', 'integer', 'Hard limit per room', 'performance')
ON CONFLICT (key) DO UPDATE SET
    value_type = EXCLUDED.value_type,
    description = EXCLUDED.description,
    category = EXCLUDED.category;

COMMIT;

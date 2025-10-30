-- Migration 012: Add user audio settings
-- Created: 2025-10-30
-- Purpose: Enable per-user audio configuration (microphone selection and voice activation threshold)

-- Add audio_threshold column to users table (default 0.02 for backward compatibility)
ALTER TABLE users ADD COLUMN IF NOT EXISTS audio_threshold FLOAT DEFAULT 0.02;

-- Add preferred_mic_device_id column to users table (NULL = use browser default)
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_mic_device_id VARCHAR(255) DEFAULT NULL;

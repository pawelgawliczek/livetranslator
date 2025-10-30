-- Migration 013: Add multi-speaker diarization support
-- Created: 2025-10-30
-- Purpose: Enable automatic speaker identification and per-speaker translations

-- Add discovery_mode column to rooms table
-- Values: 'disabled' (default), 'enabled', 'locked'
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS discovery_mode VARCHAR(20) DEFAULT 'disabled' NOT NULL;

-- Add speakers_locked column to rooms table
-- When true, prevents re-discovery and speaker changes
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS speakers_locked BOOLEAN DEFAULT FALSE NOT NULL;

-- Create room_speakers table for storing discovered speakers
CREATE TABLE IF NOT EXISTS room_speakers (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    speaker_id INTEGER NOT NULL,  -- Auto-assigned during discovery (0, 1, 2, ...)
    display_name VARCHAR(120) NOT NULL,
    language VARCHAR(10) NOT NULL,
    color VARCHAR(7) NOT NULL,  -- Hex color like #FF5733
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Create indexes for room_speakers
CREATE INDEX IF NOT EXISTS ix_room_speakers_room_id ON room_speakers(room_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_room_speakers_room_speaker ON room_speakers(room_id, speaker_id);

-- Add speaker_id to events table
-- NULL for single-speaker mode, populated in multi-speaker mode
ALTER TABLE events ADD COLUMN IF NOT EXISTS speaker_id INTEGER DEFAULT NULL;

-- Create index for speaker_id in events
CREATE INDEX IF NOT EXISTS ix_events_speaker_id ON events(speaker_id);

-- Insert migration record
INSERT INTO schema_migrations (version, name, applied_at)
VALUES ('13', 'add_multi_speaker_diarization', NOW())
ON CONFLICT (version) DO NOTHING;

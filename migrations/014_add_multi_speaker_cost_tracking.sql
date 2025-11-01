-- Migration 014: Add multi-speaker cost tracking fields
-- Adds speaker_id and target_speaker_id to room_costs table for tracking per-speaker and per-translation-pair costs

-- Add speaker_id field (nullable for backward compatibility)
ALTER TABLE room_costs
ADD COLUMN IF NOT EXISTS speaker_id INTEGER;

-- Add target_speaker_id field (nullable for backward compatibility)
ALTER TABLE room_costs
ADD COLUMN IF NOT EXISTS target_speaker_id INTEGER;

-- Add index for multi-speaker cost queries
CREATE INDEX IF NOT EXISTS ix_room_costs_room_speaker ON room_costs(room_id, speaker_id);
CREATE INDEX IF NOT EXISTS ix_room_costs_translation_pair ON room_costs(room_id, speaker_id, target_speaker_id);

-- Add comments for documentation
COMMENT ON COLUMN room_costs.speaker_id IS 'Source speaker ID for multi-speaker mode (NULL for single-speaker)';
COMMENT ON COLUMN room_costs.target_speaker_id IS 'Target speaker ID for multi-speaker translations (NULL for single-speaker)';

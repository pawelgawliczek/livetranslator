-- Migration: Add invite system support
-- Date: 2025-10-21
-- Description: Adds fields to rooms table and creates room_participants table

-- Add new fields to rooms table
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS requires_login BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS max_participants INTEGER DEFAULT 10 NOT NULL;

-- Create room_participants table
CREATE TABLE IF NOT EXISTS room_participants (
    id SERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    session_id VARCHAR(64),
    display_name VARCHAR(120) NOT NULL,
    spoken_language VARCHAR(10) NOT NULL,
    joined_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
    left_at TIMESTAMP WITHOUT TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE NOT NULL
);

-- Create indexes for room_participants
CREATE INDEX IF NOT EXISTS idx_room_participants_room_id ON room_participants(room_id);
CREATE INDEX IF NOT EXISTS idx_room_participants_user_id ON room_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_room_participants_session_id ON room_participants(session_id);
CREATE INDEX IF NOT EXISTS idx_room_participants_is_active ON room_participants(is_active);

-- Add comment
COMMENT ON TABLE room_participants IS 'Tracks participants in rooms (both authenticated users and anonymous guests)';
COMMENT ON COLUMN room_participants.user_id IS 'User ID if authenticated, NULL for anonymous users';
COMMENT ON COLUMN room_participants.session_id IS 'Session ID for anonymous users';
COMMENT ON COLUMN room_participants.spoken_language IS 'Language code (e.g., en, pl, ar) - determines translation targets';

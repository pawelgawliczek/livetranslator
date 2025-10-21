-- Migration 004: Add room_archive table to preserve room history after cleanup
-- This ensures users can still see their room history (duration, cost, participants)
-- even after rooms are deleted by the cleanup service

-- Create room_archive table
CREATE TABLE IF NOT EXISTS room_archive (
    id SERIAL PRIMARY KEY,
    room_code VARCHAR(12) NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP NOT NULL,
    archived_at TIMESTAMP DEFAULT NOW() NOT NULL,
    recording BOOLEAN NOT NULL,
    is_public BOOLEAN DEFAULT false,
    requires_login BOOLEAN DEFAULT false,
    max_participants INTEGER DEFAULT 10,

    -- Aggregated metrics (calculated at archive time)
    total_participants INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    duration_minutes NUMERIC(10, 2) DEFAULT 0,
    stt_minutes NUMERIC(10, 2) DEFAULT 0,
    stt_cost_usd NUMERIC(12, 6) DEFAULT 0,
    mt_cost_usd NUMERIC(12, 6) DEFAULT 0,
    total_cost_usd NUMERIC(12, 6) DEFAULT 0,

    -- Reason for archival
    archive_reason VARCHAR(50) DEFAULT 'cleanup',

    UNIQUE(room_code)
);

-- Add indexes for efficient queries
CREATE INDEX ix_room_archive_owner_id ON room_archive(owner_id);
CREATE INDEX ix_room_archive_archived_at ON room_archive(archived_at DESC);
CREATE INDEX ix_room_archive_owner_archived ON room_archive(owner_id, archived_at DESC);

-- Add comment
COMMENT ON TABLE room_archive IS 'Archive of deleted rooms preserving historical metrics for user history';

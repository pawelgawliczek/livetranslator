-- Migration: Fix room cleanup by adding ON DELETE CASCADE
-- This allows room_cleanup_service to delete abandoned rooms
-- while preserving usage data in room_costs table

BEGIN;

-- Drop existing foreign key constraints
ALTER TABLE segments DROP CONSTRAINT IF EXISTS segments_room_id_fkey;
ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_room_id_fkey;
ALTER TABLE events DROP CONSTRAINT IF EXISTS events_room_id_fkey;
ALTER TABLE room_participants DROP CONSTRAINT IF EXISTS room_participants_room_id_fkey;

-- Recreate with ON DELETE CASCADE
-- This allows deletion of rooms to cascade to related records
ALTER TABLE segments
    ADD CONSTRAINT segments_room_id_fkey
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE;

ALTER TABLE devices
    ADD CONSTRAINT devices_room_id_fkey
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE;

ALTER TABLE events
    ADD CONSTRAINT events_room_id_fkey
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE;

ALTER TABLE room_participants
    ADD CONSTRAINT room_participants_room_id_fkey
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE;

COMMIT;

-- NOTE: room_costs and translations tables are NOT affected
-- They use room_code (string) not room_id (FK), so they persist
-- This preserves user billing history even after room deletion

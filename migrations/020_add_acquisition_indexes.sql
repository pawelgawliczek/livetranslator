-- Migration 020: Add indexes for user acquisition metrics
-- Purpose: Optimize queries for admin user acquisition analytics (US-004)
-- Date: 2025-11-04

-- Index on users.created_at for date range queries
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at);

-- Composite index on rooms for activation queries
CREATE INDEX IF NOT EXISTS idx_rooms_owner_created ON rooms(owner_id, created_at);

-- Comments for documentation
COMMENT ON INDEX idx_users_created_at IS 'US-004: Optimize user signup queries by date range';
COMMENT ON INDEX idx_rooms_owner_created IS 'US-004: Optimize activation queries (user first room creation)';

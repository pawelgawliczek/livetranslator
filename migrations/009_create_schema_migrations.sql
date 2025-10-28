-- Migration 009: Create schema migrations tracking table
-- Created: 2025-10-28
-- Purpose: Track which migrations have been applied to prevent schema drift between environments

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP DEFAULT NOW() NOT NULL,
    checksum VARCHAR(64),  -- SHA256 hash of migration file to detect tampering
    execution_time_ms INTEGER
);

CREATE INDEX idx_schema_migrations_applied_at ON schema_migrations(applied_at);

COMMENT ON TABLE schema_migrations IS 'Tracks applied database migrations to ensure schema consistency across environments';
COMMENT ON COLUMN schema_migrations.version IS 'Migration version number (e.g., 001, 002, 010)';
COMMENT ON COLUMN schema_migrations.name IS 'Human-readable migration name from filename';
COMMENT ON COLUMN schema_migrations.checksum IS 'SHA256 hash of migration file to detect modifications';
COMMENT ON COLUMN schema_migrations.execution_time_ms IS 'Time taken to execute this migration';

-- Record that this migration has been applied
INSERT INTO schema_migrations (version, name, checksum)
VALUES ('009', '009_create_schema_migrations', NULL)
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 009 completed successfully';
    RAISE NOTICE '📊 schema_migrations table created for tracking applied migrations';
    RAISE NOTICE '🔍 Index created on applied_at for efficient queries';
    RAISE NOTICE '📝 This enables automatic migration tracking to prevent schema drift';
END $$;

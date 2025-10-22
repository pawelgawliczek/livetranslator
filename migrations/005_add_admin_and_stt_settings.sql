-- Migration 005: Add admin user support and STT provider settings
-- Created: 2025-10-22
-- Purpose: Enable admin controls for STT provider testing and per-room overrides

-- Add is_admin flag to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE NOT NULL;

-- Add STT provider overrides to rooms table (NULL = use global default)
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS stt_partial_provider VARCHAR(50) DEFAULT NULL;
ALTER TABLE rooms ADD COLUMN IF NOT EXISTS stt_final_provider VARCHAR(50) DEFAULT NULL;

-- Create system_settings table for global configuration
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Insert default STT settings
INSERT INTO system_settings (key, value) VALUES
    ('stt_partial_provider_default', 'openai_chunked'),
    ('stt_final_provider_default', 'openai')
ON CONFLICT (key) DO NOTHING;

-- Grant admin to YOU@example.com
UPDATE users SET is_admin = TRUE WHERE email = 'YOU@example.com';

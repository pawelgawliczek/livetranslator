-- Migration 024: Add created_at index for audit log viewer performance
-- Date: 2025-11-04
-- Purpose: Optimize default date range queries on admin_audit_log table

-- Add standalone created_at index for efficient date range filtering
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at
ON admin_audit_log(created_at DESC);

-- Note: Existing indexes from Migration 016:
-- - idx_admin_audit_log_admin (admin_id, created_at DESC)
-- - idx_admin_audit_log_target_user (target_user_id, created_at DESC)
-- - idx_admin_audit_log_action (action, created_at DESC)

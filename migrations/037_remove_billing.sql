-- Migration 037: Remove billing/subscription system for open source
-- LiveTranslator is going open source - all users get unrestricted access.
-- Self-hosters pay for their own API keys directly.
-- Keeps: cost_budgets, budget_alerts, guest_sessions (admin cost monitoring + guest controls)

-- Drop materialized views that reference billing tables
DROP MATERIALIZED VIEW IF EXISTS admin_financial_summary CASCADE;
DROP MATERIALIZED VIEW IF EXISTS admin_tier_analysis CASCADE;

-- Drop billing-related functions
DROP FUNCTION IF EXISTS get_user_quota_available(INTEGER) CASCADE;
DROP FUNCTION IF EXISTS deduct_quota_with_lock(INTEGER, INTEGER, TEXT) CASCADE;

-- Drop billing tables (order matters for FK constraints)
DROP TABLE IF EXISTS quota_transactions CASCADE;
DROP TABLE IF EXISTS payment_transactions CASCADE;
DROP TABLE IF EXISTS webhook_events CASCADE;
DROP TABLE IF EXISTS sponsorship_relationships CASCADE;
DROP TABLE IF EXISTS pending_gifts CASCADE;
DROP TABLE IF EXISTS essential_mode_sessions CASCADE;
DROP TABLE IF EXISTS credit_packages CASCADE;
DROP TABLE IF EXISTS user_subscriptions CASCADE;
DROP TABLE IF EXISTS subscription_tiers CASCADE;
DROP TABLE IF EXISTS admin_audit_log CASCADE;
DROP TABLE IF EXISTS user_usage CASCADE;
DROP TABLE IF EXISTS email_notifications CASCADE;

-- Drop metrics tables (AI development tracking - not needed for open source)
DROP TABLE IF EXISTS ai_agent_contributions CASCADE;
DROP TABLE IF EXISTS ai_development_metrics CASCADE;
DROP TABLE IF EXISTS metrics_snapshots CASCADE;
DROP TABLE IF EXISTS quality_metrics CASCADE;
DROP TABLE IF EXISTS complexity_snapshots CASCADE;
DROP TABLE IF EXISTS function_complexity CASCADE;

-- Drop billing columns from room_participants
ALTER TABLE room_participants DROP COLUMN IF EXISTS quota_used_seconds;
ALTER TABLE room_participants DROP COLUMN IF EXISTS is_using_admin_quota;
ALTER TABLE room_participants DROP COLUMN IF EXISTS quota_source;

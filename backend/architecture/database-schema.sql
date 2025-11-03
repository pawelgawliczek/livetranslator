-- ========================================
-- LiveTranslator Tier System + iOS App
-- Database Schema Design - Phase 1
-- ========================================
-- Created: 2025-11-03
-- Version: 1.1 (Updated per Business Analyst review)
--
-- IMPORTANT: This migration extends existing schema from 002_add_subscription_billing.sql
-- New tables: subscription_tiers, quota_transactions, payment_transactions, credit_packages, admin_audit_log
-- Modified tables: user_subscriptions (add bonus_credits_seconds, grace_quota_seconds, stripe/apple IDs)
-- Modified tables: room_participants (add quota_used_seconds, is_using_admin_quota)
--
-- Design Decisions:
-- 1. Quota tracked in SECONDS (not minutes) for precision (STT/MT/TTS all second-based)
-- 2. Dual payment platforms: Stripe (Web) + Apple (iOS)
-- 3. Quota pooling: participant → admin fallback (waterfall model)
-- 4. Bonus credits stored per-user, deducted before monthly quota
-- 5. Materialized views for admin analytics (refresh daily)
-- 6. Grace quota for payment failures (7-day buffer)
-- ========================================

-- ========================================
-- 1. SUBSCRIPTION TIERS (Static Configuration)
-- ========================================
-- Defines available subscription plans with quotas and features
-- NOTE: Prices stored as monthly USD, features stored as JSONB for flexibility

CREATE TABLE IF NOT EXISTS subscription_tiers (
    id SERIAL PRIMARY KEY,
    tier_name VARCHAR(20) UNIQUE NOT NULL,                  -- 'free', 'plus', 'pro'
    display_name VARCHAR(50) NOT NULL,                      -- 'Free', 'Plus', 'Pro'
    monthly_price_usd NUMERIC(10,2) NOT NULL DEFAULT 0,     -- $0, $29, $199
    monthly_quota_hours NUMERIC(6,2),                       -- NULL = unlimited
    monthly_quota_messages INTEGER,                         -- NULL = unlimited (future)
    features JSONB NOT NULL DEFAULT '[]',                   -- ["Feature 1", "Feature 2"]
    provider_tier VARCHAR(20) DEFAULT 'standard',           -- 'free', 'standard', 'premium'
    stripe_price_id VARCHAR(100),                           -- Stripe API price ID
    apple_product_id VARCHAR(100),                          -- App Store product ID
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Seed data: Define 3 tiers
INSERT INTO subscription_tiers (tier_name, display_name, monthly_price_usd, monthly_quota_hours, features, provider_tier, stripe_price_id, apple_product_id) VALUES
('free', 'Free', 0, 0.167, '["10 minutes per month", "Apple STT/MT/TTS (iOS)", "Speechmatics STT (Web)", "Browser Web Speech API (Web)", "Basic support"]', 'free', NULL, NULL),
('plus', 'Plus', 29, 2, '["2 hours per month", "Premium STT providers", "Premium MT providers", "Client-side TTS only", "Email support", "History export (PDF/TXT)"]', 'standard', 'price_plus_monthly_prod', 'com.livetranslator.plus.monthly'),
('pro', 'Pro', 199, 10, '["10 hours per month", "All premium providers", "Server-side TTS (Google/AWS/Azure)", "Priority support", "Advanced analytics", "API access", "History export (PDF/TXT)"]', 'premium', 'price_pro_monthly_prod', 'com.livetranslator.pro.monthly')
ON CONFLICT (tier_name) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_subscription_tiers_active ON subscription_tiers(is_active) WHERE is_active = TRUE;
COMMENT ON TABLE subscription_tiers IS 'Subscription tier definitions (free/plus/pro)';
COMMENT ON COLUMN subscription_tiers.monthly_quota_hours IS 'Monthly quota in hours (NULL = unlimited, 0.167 = 10 minutes)';
COMMENT ON COLUMN subscription_tiers.provider_tier IS 'Provider routing tier: free (Apple/Browser only), standard (Speechmatics/DeepL), premium (all providers)';
COMMENT ON COLUMN subscription_tiers.stripe_price_id IS 'Stripe Price ID for API integration';
COMMENT ON COLUMN subscription_tiers.apple_product_id IS 'Apple App Store product ID for IAP';

-- ========================================
-- 2. USER SUBSCRIPTIONS (Extended)
-- ========================================
-- Extends existing user_subscriptions table from Migration 002
-- Add bonus credits, grace quota, payment platform IDs, and tier reference

ALTER TABLE user_subscriptions
ADD COLUMN IF NOT EXISTS tier_id INTEGER REFERENCES subscription_tiers(id),
ADD COLUMN IF NOT EXISTS bonus_credits_seconds INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN IF NOT EXISTS grace_quota_seconds INTEGER DEFAULT 0 NOT NULL,
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS apple_customer_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS apple_transaction_id VARCHAR(255),
ADD COLUMN IF NOT EXISTS apple_original_transaction_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS auto_renew BOOLEAN DEFAULT TRUE;

-- Migrate existing data: Map plan names to tier_id
UPDATE user_subscriptions SET tier_id = (SELECT id FROM subscription_tiers WHERE tier_name = user_subscriptions.plan)
WHERE tier_id IS NULL AND plan IS NOT NULL;

-- Add constraint: tier_id required after migration
-- ALTER TABLE user_subscriptions ALTER COLUMN tier_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_tier_id ON user_subscriptions(tier_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_stripe ON user_subscriptions(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_apple ON user_subscriptions(apple_customer_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_billing_end ON user_subscriptions(billing_period_end)
    WHERE status = 'active'; -- For monthly reset cron job

COMMENT ON COLUMN user_subscriptions.bonus_credits_seconds IS 'Purchased credits in seconds (deducted before monthly quota)';
COMMENT ON COLUMN user_subscriptions.grace_quota_seconds IS 'Grace period quota after payment failure (7 days @ current tier quota)';
COMMENT ON COLUMN user_subscriptions.stripe_customer_id IS 'Stripe customer ID (Web payments)';
COMMENT ON COLUMN user_subscriptions.stripe_subscription_id IS 'Stripe subscription ID (UNIQUE for single active subscription)';
COMMENT ON COLUMN user_subscriptions.apple_customer_id IS 'Apple customer ID from StoreKit 2 (iOS payments)';
COMMENT ON COLUMN user_subscriptions.apple_original_transaction_id IS 'Apple original_transaction_id (UNIQUE, links renewals)';
COMMENT ON COLUMN user_subscriptions.auto_renew IS 'Auto-renew subscription (Stripe) or active subscription (Apple)';

-- ========================================
-- 3. QUOTA TRANSACTIONS (Real-Time Tracking)
-- ========================================
-- Tracks every quota deduction with attribution to user, room, and provider
-- Used for: real-time quota checks, cost attribution, admin analytics

CREATE TABLE IF NOT EXISTS quota_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL,
    room_code VARCHAR(16),                                  -- Denormalized for performance
    transaction_type VARCHAR(20) NOT NULL,                  -- 'deduct', 'grant', 'manual_grant', 'refund', 'reset'
    amount_seconds INTEGER NOT NULL,                        -- Positive = grant, Negative = deduct
    quota_type VARCHAR(20) NOT NULL,                        -- 'monthly', 'bonus', 'admin_fallback', 'grace'
    provider_used VARCHAR(50),                              -- STT/MT/TTS provider (e.g., 'speechmatics', 'deepl')
    service_type VARCHAR(10),                               -- 'stt', 'mt', 'tts'
    description TEXT,                                       -- Human-readable description
    metadata JSONB DEFAULT '{}',                            -- Extra data (e.g., granted_by, expires_date)
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_quota_transactions_user ON quota_transactions(user_id, created_at DESC);
CREATE INDEX idx_quota_transactions_room ON quota_transactions(room_id);
CREATE INDEX idx_quota_transactions_type ON quota_transactions(transaction_type);
CREATE INDEX idx_quota_transactions_provider ON quota_transactions(provider_used);
CREATE INDEX idx_quota_transactions_user_period ON quota_transactions(user_id, created_at)
    WHERE created_at >= NOW() - INTERVAL '30 days'; -- For quota usage queries

COMMENT ON TABLE quota_transactions IS 'Real-time quota tracking with provider attribution';
COMMENT ON COLUMN quota_transactions.transaction_type IS 'deduct (usage), grant (purchase), manual_grant (admin grant), refund (admin), reset (monthly)';
COMMENT ON COLUMN quota_transactions.quota_type IS 'monthly (tier quota), bonus (purchased credits), admin_fallback (used admin quota), grace (payment failure buffer)';
COMMENT ON COLUMN quota_transactions.amount_seconds IS 'Positive = grant/refund, Negative = deduct';
COMMENT ON COLUMN quota_transactions.metadata IS 'Extra data: {granted_by: admin_id, expires_date: ISO8601, reason: "..."}';

-- ========================================
-- 4. PAYMENT TRANSACTIONS (Dual Platform)
-- ========================================
-- Tracks all payments from Stripe (Web) and Apple (iOS)
-- Used for: revenue tracking, refunds, admin financial dashboard

CREATE TABLE IF NOT EXISTS payment_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(20) NOT NULL,                          -- 'stripe', 'apple'
    transaction_type VARCHAR(20) NOT NULL,                  -- 'subscription', 'credit_purchase', 'refund'
    amount_usd NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',

    -- Stripe fields
    stripe_payment_intent_id VARCHAR(255),
    stripe_invoice_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),

    -- Apple fields
    apple_transaction_id VARCHAR(255) UNIQUE,               -- Must be unique (prevent duplicate processing)
    apple_original_transaction_id VARCHAR(255),
    apple_product_id VARCHAR(100),
    apple_receipt_data TEXT,

    -- Common fields
    status VARCHAR(20) NOT NULL,                            -- 'pending', 'succeeded', 'failed', 'refunded'
    failure_reason TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    completed_at TIMESTAMP
);

CREATE INDEX idx_payment_transactions_user ON payment_transactions(user_id, created_at DESC);
CREATE INDEX idx_payment_transactions_platform ON payment_transactions(platform);
CREATE INDEX idx_payment_transactions_status ON payment_transactions(status, created_at);
CREATE INDEX idx_payment_transactions_stripe_intent ON payment_transactions(stripe_payment_intent_id);
CREATE INDEX idx_payment_transactions_apple_txn ON payment_transactions(apple_transaction_id);

COMMENT ON TABLE payment_transactions IS 'All payments from Stripe (Web) and Apple (iOS)';
COMMENT ON COLUMN payment_transactions.platform IS 'stripe (Web) or apple (iOS)';
COMMENT ON COLUMN payment_transactions.apple_transaction_id IS 'UNIQUE to prevent duplicate IAP processing';
COMMENT ON COLUMN payment_transactions.apple_receipt_data IS 'Base64-encoded Apple receipt for verification';

-- ========================================
-- 5. CREDIT PACKAGES (Purchasable Quotas)
-- ========================================
-- Defines available credit packages for purchase (top-up model)
-- Example: Buy 4 hours for $19

CREATE TABLE IF NOT EXISTS credit_packages (
    id SERIAL PRIMARY KEY,
    package_name VARCHAR(50) NOT NULL,                      -- '1hr', '4hr', '8hr', '20hr'
    display_name VARCHAR(100) NOT NULL,                     -- '1 Hour', '4 Hours (Best Value!)'
    hours NUMERIC(6,2) NOT NULL,                            -- 1, 4, 8, 20
    price_usd NUMERIC(10,2) NOT NULL,                       -- $5, $19, $35, $80
    discount_percent NUMERIC(5,2) DEFAULT 0,                -- 0%, 10%, 20%
    stripe_price_id VARCHAR(100),                           -- Stripe Price ID
    apple_product_id VARCHAR(100),                          -- App Store product ID
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Seed data: Define 4 credit packages
INSERT INTO credit_packages (package_name, display_name, hours, price_usd, discount_percent, sort_order, stripe_price_id, apple_product_id) VALUES
('1hr', '1 Hour', 1, 5, 0, 1, 'price_1hr_prod', 'com.livetranslator.credits.1hr'),
('4hr', '4 Hours', 4, 19, 5, 2, 'price_4hr_prod', 'com.livetranslator.credits.4hr'),
('8hr', '8 Hours (Best Value!)', 8, 35, 12.5, 3, 'price_8hr_prod', 'com.livetranslator.credits.8hr'),
('20hr', '20 Hours (Enterprise)', 20, 80, 20, 4, 'price_20hr_prod', 'com.livetranslator.credits.20hr')
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_credit_packages_active ON credit_packages(is_active, sort_order);
COMMENT ON TABLE credit_packages IS 'Purchasable credit packages (top-up model)';
COMMENT ON COLUMN credit_packages.discount_percent IS 'Discount vs base rate ($5/hr)';

-- ========================================
-- 6. ROOM PARTICIPANTS (Extended for Quota Pooling)
-- ========================================
-- Tracks which users are in which rooms + quota used per participant
-- Used for: quota pooling (participant → admin fallback)

CREATE TABLE IF NOT EXISTS room_participants (
    id BIGSERIAL PRIMARY KEY,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    participant_email VARCHAR(255) NOT NULL,                -- Email or guest identifier
    display_name VARCHAR(120),
    is_guest BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,                         -- Room owner

    -- Quota tracking per participant
    quota_used_seconds INTEGER DEFAULT 0 NOT NULL,          -- Seconds used by this participant in this room
    is_using_admin_quota BOOLEAN DEFAULT FALSE,             -- Currently using admin's quota
    quota_source VARCHAR(20),                               -- 'own', 'admin', 'none' (tracks whose quota was used)

    joined_at TIMESTAMP DEFAULT NOW() NOT NULL,
    left_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_room_participants_room ON room_participants(room_id);
CREATE INDEX IF NOT EXISTS idx_room_participants_user ON room_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_room_participants_active ON room_participants(room_id, left_at) WHERE left_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_room_participants_quota ON room_participants(room_id, is_using_admin_quota);

COMMENT ON TABLE room_participants IS 'Tracks participants per room with quota attribution';
COMMENT ON COLUMN room_participants.quota_used_seconds IS 'Seconds of quota used by this participant in this room';
COMMENT ON COLUMN room_participants.is_using_admin_quota IS 'TRUE if currently consuming admin quota';
COMMENT ON COLUMN room_participants.quota_source IS 'Whose quota was used: own (participant), admin (room owner), none (guest exhausted admin quota)';

-- ========================================
-- 7. ADMIN AUDIT LOG (Compliance)
-- ========================================
-- Tracks all admin actions for security and compliance
-- Required for: Credit grants, user modifications, tier changes

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,                            -- 'grant_credits', 'modify_user', 'delete_user', 'adjust_quota'
    target_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    target_room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL,
    details JSONB NOT NULL DEFAULT '{}',                    -- Action-specific data (e.g., seconds granted, reason)
    ip_address INET,                                        -- Admin's IP address
    user_agent TEXT,                                        -- Admin's browser/client
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_admin_audit_log_admin ON admin_audit_log(admin_id, created_at DESC);
CREATE INDEX idx_admin_audit_log_target_user ON admin_audit_log(target_user_id, created_at DESC);
CREATE INDEX idx_admin_audit_log_action ON admin_audit_log(action, created_at DESC);

COMMENT ON TABLE admin_audit_log IS 'Audit trail for all admin actions (security + compliance)';
COMMENT ON COLUMN admin_audit_log.action IS 'Action type: grant_credits, modify_user, delete_user, adjust_quota, etc.';
COMMENT ON COLUMN admin_audit_log.details IS 'Action-specific JSON: {seconds: 1800, reason: "Refund for issue #1234"}';

-- ========================================
-- 8. ADMIN ANALYTICS VIEWS (Materialized)
-- ========================================
-- Pre-computed views for admin dashboard (refresh daily via cron)

-- 8.1 Financial Summary (Revenue vs Costs)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_financial_summary AS
SELECT
    DATE_TRUNC('day', created_at) AS day,
    platform,
    SUM(CASE WHEN status = 'succeeded' THEN amount_usd ELSE 0 END) AS revenue_usd,
    COUNT(*) AS transaction_count
FROM payment_transactions
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', created_at), platform
ORDER BY day DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_financial_day_platform ON admin_financial_summary(day DESC, platform);

-- 8.2 Tier Analysis (Revenue & Profit by Tier)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_tier_analysis AS
SELECT
    st.tier_name,
    st.display_name,
    st.monthly_price_usd,
    COUNT(DISTINCT us.user_id) AS active_users,
    SUM(st.monthly_price_usd) AS monthly_recurring_revenue,
    -- Costs calculated from room_costs table (joined via user rooms)
    COALESCE(SUM(costs.total_cost), 0) AS total_costs_usd,
    SUM(st.monthly_price_usd) - COALESCE(SUM(costs.total_cost), 0) AS gross_profit_usd
FROM subscription_tiers st
LEFT JOIN user_subscriptions us ON st.id = us.tier_id AND us.status = 'active'
LEFT JOIN rooms r ON r.owner_id = us.user_id
LEFT JOIN LATERAL (
    SELECT SUM(amount_usd) AS total_cost
    FROM room_costs
    WHERE room_id = r.code
    AND ts >= us.billing_period_start
    AND ts < us.billing_period_end
) costs ON TRUE
GROUP BY st.id, st.tier_name, st.display_name, st.monthly_price_usd
ORDER BY st.id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_tier_analysis_name ON admin_tier_analysis(tier_name);

-- 8.3 User Metrics (Acquisition, Activation, Engagement)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_user_metrics AS
SELECT
    DATE_TRUNC('day', u.created_at) AS signup_date,
    COUNT(*) AS new_signups,
    COUNT(CASE WHEN r.id IS NOT NULL THEN 1 END) AS activated_users,  -- Created at least 1 room
    COUNT(CASE WHEN r.created_at <= u.created_at + INTERVAL '5 minutes' THEN 1 END) AS fast_activation  -- Room within 5min
FROM users u
LEFT JOIN rooms r ON r.owner_id = u.id AND r.created_at <= u.created_at + INTERVAL '1 day'
WHERE u.created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', u.created_at)
ORDER BY signup_date DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_user_metrics_date ON admin_user_metrics(signup_date DESC);

-- 8.4 Provider Costs (Cost Breakdown by Provider)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_provider_costs AS
SELECT
    provider,
    pipeline AS service_type,                               -- 'stt' or 'mt'
    COUNT(*) AS event_count,
    SUM(amount_usd) AS total_cost_usd,
    AVG(amount_usd) AS avg_cost_per_event,
    SUM(units) AS total_units,
    unit_type
FROM room_costs
WHERE ts >= NOW() - INTERVAL '30 days'
AND provider IS NOT NULL
GROUP BY provider, pipeline, unit_type
ORDER BY total_cost_usd DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_provider_costs_provider ON admin_provider_costs(provider, service_type);

-- Refresh function for all materialized views
CREATE OR REPLACE FUNCTION refresh_admin_views()
RETURNS VOID AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY admin_financial_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY admin_tier_analysis;
    REFRESH MATERIALIZED VIEW CONCURRENTLY admin_user_metrics;
    REFRESH MATERIALIZED VIEW CONCURRENTLY admin_provider_costs;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_admin_views IS 'Refresh all admin materialized views (run daily via cron at 2am UTC)';

-- ========================================
-- 9. HELPER FUNCTIONS (Quota Logic)
-- ========================================

-- 9.1 Get user's available quota (bonus + monthly + grace)
CREATE OR REPLACE FUNCTION get_user_quota_available(p_user_id INTEGER)
RETURNS INTEGER AS $$
DECLARE
    v_bonus_seconds INTEGER;
    v_grace_seconds INTEGER;
    v_monthly_quota_hours NUMERIC;
    v_used_seconds INTEGER;
    v_available_seconds INTEGER;
BEGIN
    -- Get user subscription
    SELECT
        us.bonus_credits_seconds,
        us.grace_quota_seconds,
        st.monthly_quota_hours
    INTO v_bonus_seconds, v_grace_seconds, v_monthly_quota_hours
    FROM user_subscriptions us
    JOIN subscription_tiers st ON us.tier_id = st.id
    WHERE us.user_id = p_user_id
    AND us.status = 'active';

    IF NOT FOUND THEN
        RETURN 0;  -- No active subscription
    END IF;

    -- Calculate monthly quota in seconds
    IF v_monthly_quota_hours IS NULL THEN
        RETURN 999999999;  -- Unlimited
    END IF;

    -- Get used seconds in current billing period
    SELECT COALESCE(SUM(-amount_seconds), 0)
    INTO v_used_seconds
    FROM quota_transactions
    WHERE user_id = p_user_id
    AND transaction_type = 'deduct'
    AND created_at >= (SELECT billing_period_start FROM user_subscriptions WHERE user_id = p_user_id);

    -- Available = Bonus + Monthly + Grace - Used
    v_available_seconds := v_bonus_seconds + (v_monthly_quota_hours * 3600)::INTEGER + v_grace_seconds - v_used_seconds;

    RETURN GREATEST(v_available_seconds, 0);  -- Never negative
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_user_quota_available IS 'Returns available quota in seconds (bonus + monthly + grace - used)';

-- ========================================
-- 10. MIGRATION NOTES
-- ========================================

-- BACKWARD COMPATIBILITY:
-- - Existing user_subscriptions.plan column preserved (migrated to tier_id)
-- - Existing user_subscriptions.monthly_quota_minutes preserved (now in tiers table as hours)
-- - Existing user_usage table still functional (quota_transactions is additive)
-- - Existing room_costs table unchanged (quota_transactions references it)

-- NEW FEATURES ADDED (per BA review):
-- - grace_quota_seconds: 7-day buffer after payment failure
-- - is_using_admin_quota: Real-time flag for quota pool UI
-- - admin_audit_log: Compliance trail for manual credit grants
-- - Unique constraints: apple_transaction_id, apple_original_transaction_id, stripe_subscription_id
-- - Performance indexes: billing_end, quota_transactions period, status+timestamp

-- NEW QUOTA TRACKING FLOW:
-- 1. STT/MT/TTS event occurs → room_costs record created (existing)
-- 2. Quota deduction → quota_transactions record created (NEW)
-- 3. Real-time check: SELECT get_user_quota_available(user_id)
-- 4. If quota exhausted → Check room admin's quota
-- 5. If admin exhausted → Downgrade to free providers

-- DEPLOYMENT STEPS:
-- 1. Run this migration on staging
-- 2. Verify existing subscriptions migrated correctly
-- 3. Test quota pooling with 2 users (participant + admin)
-- 4. Test Stripe webhook (use test mode)
-- 5. Test Apple IAP verification (sandbox)
-- 6. Run on production during low-traffic window
-- 7. Monitor logs for quota deduction events
-- 8. Schedule cron job: 0 2 * * * psql -c "SELECT refresh_admin_views();"

-- PERFORMANCE TARGETS (with indexes):
-- - Quota check: <100ms (p95), <200ms (p99)
-- - Admin dashboard: <3s uncached, <500ms cached
-- - Payment webhook processing: <500ms (p95)
-- - Materialized view refresh: <10 minutes (daily 2am)

-- ========================================
-- END OF SCHEMA - VERSION 1.1
-- ========================================

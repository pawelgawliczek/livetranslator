-- Migration: Add subscription and billing system
-- Date: 2025-10-21
-- Description: Adds user_subscriptions and user_usage tables for subscription management and billing

-- Create user_subscriptions table
CREATE TABLE IF NOT EXISTS user_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    plan VARCHAR(20) DEFAULT 'free' NOT NULL,
    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    monthly_quota_minutes INTEGER,
    billing_period_start TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
    billing_period_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create index for user_subscriptions
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id ON user_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_status ON user_subscriptions(status);

-- Create user_usage table
CREATE TABLE IF NOT EXISTS user_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_code VARCHAR(16) NOT NULL,
    billing_period_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    stt_minutes NUMERIC(12, 2) DEFAULT 0 NOT NULL,
    stt_cost_usd NUMERIC(12, 6) DEFAULT 0 NOT NULL,
    mt_cost_usd NUMERIC(12, 6) DEFAULT 0 NOT NULL,
    total_cost_usd NUMERIC(12, 6) DEFAULT 0 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create indexes for user_usage
CREATE INDEX IF NOT EXISTS idx_user_usage_user_id ON user_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_user_usage_billing_period ON user_usage(user_id, billing_period_start);
CREATE INDEX IF NOT EXISTS idx_user_usage_room_code ON user_usage(room_code);

-- Add comments
COMMENT ON TABLE user_subscriptions IS 'User subscription plans (free, plus, pro)';
COMMENT ON COLUMN user_subscriptions.plan IS 'Subscription plan: free, plus, or pro';
COMMENT ON COLUMN user_subscriptions.status IS 'Subscription status: active, cancelled, or expired';
COMMENT ON COLUMN user_subscriptions.monthly_quota_minutes IS 'Monthly STT quota in minutes (NULL means unlimited)';
COMMENT ON COLUMN user_subscriptions.billing_period_start IS 'Start of current billing period';
COMMENT ON COLUMN user_subscriptions.billing_period_end IS 'End of current billing period';

COMMENT ON TABLE user_usage IS 'Tracks user usage per room per billing period';
COMMENT ON COLUMN user_usage.stt_minutes IS 'STT minutes used in this room for this billing period';
COMMENT ON COLUMN user_usage.stt_cost_usd IS 'STT cost in USD for this room';
COMMENT ON COLUMN user_usage.mt_cost_usd IS 'Machine translation cost in USD for this room';
COMMENT ON COLUMN user_usage.total_cost_usd IS 'Total cost in USD for this room';

-- Create default free subscription for existing users
INSERT INTO user_subscriptions (user_id, plan, status, monthly_quota_minutes, billing_period_start, billing_period_end)
SELECT
    id,
    'free',
    'active',
    60, -- 1 hour per month for free tier
    DATE_TRUNC('month', NOW()),
    DATE_TRUNC('month', NOW()) + INTERVAL '1 month'
FROM users
WHERE id NOT IN (SELECT user_id FROM user_subscriptions);

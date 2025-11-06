-- Migration 026: Add grace_period_end for failed payment handling
-- US-007: Failed Payment Handling

-- Add grace_period_end column to track payment failure grace period
ALTER TABLE user_subscriptions
ADD COLUMN IF NOT EXISTS grace_period_end TIMESTAMP;

-- Add index for grace period cleanup queries
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_grace_period
ON user_subscriptions(grace_period_end)
WHERE grace_period_end IS NOT NULL;

-- Comment for documentation
COMMENT ON COLUMN user_subscriptions.grace_period_end IS
'Timestamp when grace period expires after payment failure. User will be downgraded to Free tier after this time.';

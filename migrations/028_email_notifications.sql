-- Migration 028: Email notifications system
-- US-012: Email Notifications

-- 1. Add email_notifications_enabled flag to users table
ALTER TABLE users
ADD COLUMN IF NOT EXISTS email_notifications_enabled BOOLEAN DEFAULT TRUE NOT NULL;

COMMENT ON COLUMN users.email_notifications_enabled IS 'User preference for receiving email notifications (GDPR consent)';

-- 2. Create email_notifications tracking table
CREATE TABLE IF NOT EXISTS email_notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type VARCHAR(50) NOT NULL,  -- 'quota_80', 'quota_100', 'welcome', 'payment_failed'
    billing_period_start TIMESTAMP,  -- For deduplication (NULL for welcome emails)
    sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
    delivery_status VARCHAR(20) DEFAULT 'sent' NOT NULL,  -- 'sent', 'failed'
    web3forms_response JSONB,  -- Store API response for debugging

    -- Metadata
    user_email VARCHAR(255) NOT NULL,  -- Snapshot of email at send time
    subject VARCHAR(255) NOT NULL,
    quota_percentage INTEGER,  -- For quota emails (80, 100)
    tier_name VARCHAR(50)  -- For welcome emails
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_email_notifications_user_id
    ON email_notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_email_notifications_user_type_period
    ON email_notifications(user_id, notification_type, billing_period_start);

CREATE INDEX IF NOT EXISTS idx_email_notifications_sent_at
    ON email_notifications(sent_at DESC);

-- Unique constraint for 100% quota exhaustion (once per billing period)
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_notifications_quota_100_unique
    ON email_notifications(user_id, notification_type, billing_period_start)
    WHERE notification_type = 'quota_100' AND delivery_status = 'sent';

COMMENT ON TABLE email_notifications IS 'Tracks all email notifications sent to users (US-012)';
COMMENT ON COLUMN email_notifications.notification_type IS 'Type: quota_80, quota_100, welcome, payment_failed';
COMMENT ON COLUMN email_notifications.billing_period_start IS 'Used for deduplication (NULL for one-time emails like welcome)';
COMMENT ON COLUMN email_notifications.web3forms_response IS 'Full API response from Web3Forms for debugging';

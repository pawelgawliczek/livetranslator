-- ============================================================================
-- Migration 023: Notification Management System
-- US-008: In-app notification system for admin broadcasts
-- Created: 2025-11-04
-- ============================================================================

-- ============================================================================
-- Notifications Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    message TEXT NOT NULL CHECK (LENGTH(message) <= 500),
    type VARCHAR(20) NOT NULL CHECK (type IN ('info', 'warning', 'success', 'error')),
    target VARCHAR(20) NOT NULL CHECK (target IN ('all', 'free', 'plus', 'pro', 'individual')),
    target_user_id INT REFERENCES users(id) ON DELETE SET NULL,
    schedule_type VARCHAR(20) NOT NULL CHECK (schedule_type IN ('immediate', 'scheduled')),
    scheduled_for TIMESTAMP,
    expires_in_seconds INT,
    is_dismissible BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'sent', 'expired', 'cancelled')),
    created_by INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Validation constraints
    CONSTRAINT scheduled_time_required CHECK (
        (schedule_type = 'immediate') OR
        (schedule_type = 'scheduled' AND scheduled_for IS NOT NULL)
    ),
    CONSTRAINT individual_target_user CHECK (
        (target != 'individual') OR
        (target = 'individual' AND target_user_id IS NOT NULL)
    ),
    CONSTRAINT scheduled_for_future CHECK (
        (schedule_type = 'immediate') OR
        (scheduled_for IS NULL) OR
        (scheduled_for > created_at)
    )
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status);
CREATE INDEX IF NOT EXISTS idx_notifications_scheduled_for ON notifications(scheduled_for) WHERE status = 'scheduled';
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_created_by ON notifications(created_by);

-- ============================================================================
-- Notification Deliveries Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS notification_deliveries (
    id BIGSERIAL PRIMARY KEY,
    notification_id INT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delivered_at TIMESTAMP NOT NULL DEFAULT NOW(),
    read_at TIMESTAMP,
    dismissed_at TIMESTAMP,

    UNIQUE(notification_id, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_user ON notification_deliveries(user_id, delivered_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_notification ON notification_deliveries(notification_id);
CREATE INDEX IF NOT EXISTS idx_notification_deliveries_unread ON notification_deliveries(user_id) WHERE dismissed_at IS NULL;

-- ============================================================================
-- Comments
-- ============================================================================
COMMENT ON TABLE notifications IS 'Admin-created notifications for in-app broadcast';
COMMENT ON COLUMN notifications.target IS 'Recipient targeting: all, free, plus, pro, or individual user';
COMMENT ON COLUMN notifications.schedule_type IS 'Delivery timing: immediate (send now) or scheduled (send at scheduled_for)';
COMMENT ON COLUMN notifications.expires_in_seconds IS 'Auto-expire after N seconds from sent_at (NULL = never expires)';
COMMENT ON COLUMN notifications.status IS 'Lifecycle: draft → scheduled/sent → expired/cancelled';

COMMENT ON TABLE notification_deliveries IS 'Tracks which users received which notifications';
COMMENT ON COLUMN notification_deliveries.read_at IS 'When user opened notification panel and viewed it';
COMMENT ON COLUMN notification_deliveries.dismissed_at IS 'When user explicitly dismissed notification';

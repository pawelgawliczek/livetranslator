-- Migration 027: Webhook events for retry logic
-- US-011: Webhook Retry Logic

CREATE TABLE IF NOT EXISTS webhook_events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,  -- Stripe event.id (for idempotency)
    event_type VARCHAR(100) NOT NULL,       -- checkout.session.completed, etc.
    payload JSONB NOT NULL,                 -- Full webhook payload
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed, abandoned
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_retry_at TIMESTAMP,
    next_retry_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for retry worker queries
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON webhook_events(status);
CREATE INDEX IF NOT EXISTS idx_webhook_events_next_retry ON webhook_events(next_retry_at) WHERE status = 'failed';
CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type ON webhook_events(event_type);

-- Index for cleanup (completed events retention)
CREATE INDEX IF NOT EXISTS idx_webhook_events_completed_at ON webhook_events(completed_at) WHERE status = 'completed';

COMMENT ON TABLE webhook_events IS 'Stores Stripe webhook events for retry logic and audit trail (US-011)';
COMMENT ON COLUMN webhook_events.event_id IS 'Stripe event.id (unique per event, used for idempotency)';
COMMENT ON COLUMN webhook_events.retry_count IS 'Number of retry attempts (max 5)';
COMMENT ON COLUMN webhook_events.next_retry_at IS 'Scheduled time for next retry (exponential backoff)';

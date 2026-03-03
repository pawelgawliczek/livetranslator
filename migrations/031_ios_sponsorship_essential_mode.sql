-- ========================================
-- Migration 031: iOS Sponsorship & Essential Mode
-- Date: 2025-11-07
-- Changes:
--   1. Essential Mode quota tracking
--   2. Sponsorship relationships (per-room)
--   3. Guest sessions with device fingerprinting
--   4. Essential Mode server-side timing sessions
--   5. Pending gifts (email-based claiming)
--   6. Room settings (auto-sponsor, provider_type)
--   7. Row-level lock function for atomic quota deduction
-- ========================================

BEGIN;

-- ========================================
-- 1. Essential Mode Quota
-- ========================================

ALTER TABLE user_subscriptions
ADD COLUMN IF NOT EXISTS essential_quota_seconds INTEGER DEFAULT 1800 NOT NULL;

COMMENT ON COLUMN user_subscriptions.essential_quota_seconds IS
'Essential Mode quota (on-device processing). Default: 1800 seconds (30 min). Resets monthly on billing_period_end.';

-- Constraint: Prevent negative quota
ALTER TABLE user_subscriptions
ADD CONSTRAINT chk_essential_quota_positive
CHECK (essential_quota_seconds >= 0);

-- ========================================
-- 2. Sponsorship Relationships (Per-Room)
-- ========================================

CREATE TABLE sponsorship_relationships (
    id SERIAL PRIMARY KEY,
    sponsor_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sponsored_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,

    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    -- Status values: 'active', 'grace_period', 'ended'

    quota_used_seconds INTEGER DEFAULT 0 NOT NULL,
    -- Total quota sponsored in this conversation

    started_at TIMESTAMP DEFAULT NOW() NOT NULL,
    ended_at TIMESTAMP,

    grace_started_at TIMESTAMP,
    -- When sponsor left (1-minute grace period starts)

    grace_ends_at TIMESTAMP,
    -- When grace period expires (started_at + 60 seconds)

    -- Constraints
    CONSTRAINT no_self_sponsorship CHECK (sponsor_user_id != sponsored_user_id),
    CONSTRAINT chk_sponsorship_dates CHECK (ended_at IS NULL OR ended_at > started_at),
    CONSTRAINT chk_grace_dates CHECK (grace_ends_at IS NULL OR grace_ends_at > grace_started_at),
    CONSTRAINT chk_quota_positive CHECK (quota_used_seconds >= 0)
);

-- Indexes for performance
CREATE INDEX idx_sponsorship_active
ON sponsorship_relationships(room_id, status)
WHERE status = 'active';

CREATE INDEX idx_sponsorship_grace
ON sponsorship_relationships(room_id, status, grace_ends_at)
WHERE status = 'grace_period';

CREATE INDEX idx_sponsorship_sponsor
ON sponsorship_relationships(sponsor_user_id, status);

CREATE INDEX idx_sponsorship_sponsored
ON sponsorship_relationships(sponsored_user_id, room_id);

-- Per-room sponsorship: One active sponsor per guest per room
CREATE UNIQUE INDEX idx_one_sponsor_per_guest_per_room
ON sponsorship_relationships(sponsored_user_id, room_id)
WHERE status IN ('active', 'grace_period');

COMMENT ON TABLE sponsorship_relationships IS
'Per-room sponsorship. PM Decision: No monthly limit (Pro quota unlimited). Each room requires new sponsorship offer.';

-- ========================================
-- 3. Guest Sessions (Device Fingerprinting)
-- ========================================

CREATE TABLE guest_sessions (
    id SERIAL PRIMARY KEY,
    session_token UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    device_fingerprint VARCHAR(255) NOT NULL,
    -- iOS: IDFV or UUID, Web: Canvas + WebGL + User-Agent hash

    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    user_name VARCHAR(100) NOT NULL,
    language_code VARCHAR(10) NOT NULL,

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '1 hour') NOT NULL,
    -- PM Decision: 1-hour session TTL

    last_activity_at TIMESTAMP DEFAULT NOW(),
    -- Updated every 60 seconds, used for 10-minute disconnect grace

    total_duration_seconds INTEGER DEFAULT 0 NOT NULL,
    -- Total active time in this session

    disconnected_at TIMESTAMP,
    -- When user last disconnected (NULL if currently connected)

    CONSTRAINT chk_guest_duration_positive CHECK (total_duration_seconds >= 0),
    CONSTRAINT chk_guest_expires_after_created CHECK (expires_at > created_at)
);

-- Indexes
CREATE INDEX idx_guest_sessions_device
ON guest_sessions(device_fingerprint, expires_at);

CREATE INDEX idx_guest_sessions_room
ON guest_sessions(room_id, expires_at);

CREATE INDEX idx_guest_sessions_token
ON guest_sessions(session_token);

-- Prevent multiple active sessions per device per room
-- Note: Cannot use NOW() in partial index (not immutable)
-- Instead, we'll handle this logic in application layer or use a scheduled cleanup job
CREATE UNIQUE INDEX idx_one_guest_session_per_device_per_room
ON guest_sessions(device_fingerprint, room_id, expires_at);

COMMENT ON TABLE guest_sessions IS
'Guest sessions with device fingerprinting. PM Decision: 1-hour TTL, 10-min reconnect grace, prevents quota farming via fresh rejoins.';

-- ========================================
-- 4. Essential Mode Sessions (Server-Side Timing)
-- ========================================

CREATE TABLE essential_mode_sessions (
    id SERIAL PRIMARY KEY,
    session_token UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    room_id INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,

    started_at TIMESTAMP DEFAULT NOW() NOT NULL,
    ended_at TIMESTAMP,

    last_activity_at TIMESTAMP DEFAULT NOW(),
    -- Updated with each transcript submission

    paused_at TIMESTAMP,
    -- When iOS app backgrounded (pause quota deduction)

    total_duration_seconds INTEGER DEFAULT 0 NOT NULL,
    -- Server-calculated duration (authoritative)

    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    -- Status values: 'active', 'paused', 'ended'

    CONSTRAINT chk_essential_status CHECK (status IN ('active', 'paused', 'ended')),
    CONSTRAINT chk_essential_duration_positive CHECK (total_duration_seconds >= 0),
    CONSTRAINT chk_essential_ended_after_started CHECK (ended_at IS NULL OR ended_at >= started_at)
);

-- Indexes
CREATE INDEX idx_essential_sessions_user
ON essential_mode_sessions(user_id, status);

CREATE INDEX idx_essential_sessions_room
ON essential_mode_sessions(room_id, status);

CREATE INDEX idx_essential_sessions_token
ON essential_mode_sessions(session_token);

-- One active Essential Mode session per user per room
CREATE UNIQUE INDEX idx_one_essential_session_per_user_per_room
ON essential_mode_sessions(user_id, room_id)
WHERE status IN ('active', 'paused');

COMMENT ON TABLE essential_mode_sessions IS
'Server-side timing for Essential Mode quota. PM Decision Q5: Pure server-side (no client input). Tracks START/STOP events.';

-- ========================================
-- 5. Enhanced Quota Transactions
-- ========================================

-- Add balance_after_seconds if not exists (for quota tracking)
ALTER TABLE quota_transactions
ADD COLUMN IF NOT EXISTS balance_after_seconds INTEGER;

-- Add sponsorship tracking column
ALTER TABLE quota_transactions
ADD COLUMN IF NOT EXISTS sponsored_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

COMMENT ON COLUMN quota_transactions.sponsored_by_user_id IS
'If this quota was sponsored by another user, references sponsor user_id. NULL for own quota.';

-- Index for sponsorship tracking
CREATE INDEX idx_quota_transactions_sponsor
ON quota_transactions(sponsored_by_user_id, created_at DESC)
WHERE sponsored_by_user_id IS NOT NULL;

-- Index for quota type queries (already exists but ensure it's optimized)
CREATE INDEX IF NOT EXISTS idx_quota_transactions_quota_type
ON quota_transactions(user_id, quota_type, created_at DESC);

-- ========================================
-- 6. Pending Gifts (Email-Based Claiming)
-- ========================================

CREATE TABLE pending_gifts (
    id SERIAL PRIMARY KEY,
    giver_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255) NOT NULL,
    recipient_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    -- NULL until claimed

    credit_package_id INTEGER NOT NULL REFERENCES credit_packages(id),
    amount_seconds INTEGER NOT NULL,

    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    -- Status values: 'pending', 'claimed', 'expired', 'refunded'

    claim_token UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    -- Sent in email claim link

    expires_at TIMESTAMP DEFAULT (NOW() + INTERVAL '24 hours') NOT NULL,
    -- PM Decision: 24-hour expiration

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    claimed_at TIMESTAMP,

    stripe_payment_intent_id VARCHAR(255),
    -- For refund tracking if expired

    CONSTRAINT chk_gift_amount_positive CHECK (amount_seconds > 0),
    CONSTRAINT chk_gift_expires_after_created CHECK (expires_at > created_at),
    CONSTRAINT chk_gift_status CHECK (status IN ('pending', 'claimed', 'expired', 'refunded'))
);

-- Indexes
CREATE INDEX idx_pending_gifts_recipient
ON pending_gifts(recipient_email, status);

CREATE INDEX idx_pending_gifts_giver
ON pending_gifts(giver_user_id, status);

CREATE INDEX idx_pending_gifts_token
ON pending_gifts(claim_token);

CREATE INDEX idx_pending_gifts_expiration
ON pending_gifts(expires_at, status)
WHERE status = 'pending';

COMMENT ON TABLE pending_gifts IS
'PM Decision Q9: Email-based gifting. Guest receives email with claim link. Expires in 24 hours.';

-- ========================================
-- 7. Room Settings
-- ========================================

ALTER TABLE rooms
ADD COLUMN IF NOT EXISTS auto_sponsor_guests BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS provider_type VARCHAR(20) DEFAULT 'premium_providers' NOT NULL;

-- Provider types: 'premium_providers', 'essential_mode'
COMMENT ON COLUMN rooms.provider_type IS
'Provider mode for this room. Values: premium_providers (cloud STT/MT), essential_mode (iOS on-device)';

COMMENT ON COLUMN rooms.auto_sponsor_guests IS
'Pro users only: Automatically sponsor guests when their quota runs out. PM Decision: Default OFF (user opts in).';

-- Add constraint for provider type
ALTER TABLE rooms
ADD CONSTRAINT chk_provider_type CHECK (provider_type IN ('premium_providers', 'essential_mode'));

-- Update existing rooms (backward compatibility)
-- Set provider_type based on owner's tier
UPDATE rooms r
SET provider_type = CASE
    WHEN EXISTS (
        SELECT 1 FROM user_subscriptions us
        JOIN subscription_tiers st ON us.tier_id = st.id
        WHERE us.user_id = r.owner_id
        AND st.tier_name = 'free'
        AND us.bonus_credits_seconds <= 300  -- Less than 5 minutes
    ) THEN 'essential_mode'
    ELSE 'premium_providers'
END
WHERE provider_type = 'premium_providers';  -- Only update defaults

-- Index
CREATE INDEX idx_rooms_provider_type
ON rooms(provider_type);

-- ========================================
-- 8. Enhanced Payment Transactions (Idempotency)
-- ========================================

-- Add gift tracking
ALTER TABLE payment_transactions
ADD COLUMN IF NOT EXISTS gift_id INTEGER REFERENCES pending_gifts(id) ON DELETE SET NULL;

COMMENT ON COLUMN payment_transactions.gift_id IS
'If this payment was for a gift, references pending_gifts.id';

-- Index for gift lookups
CREATE INDEX idx_payment_transactions_gift
ON payment_transactions(gift_id)
WHERE gift_id IS NOT NULL;

-- ========================================
-- 9. System Settings (Feature Flags)
-- ========================================

INSERT INTO system_settings (key, value, updated_at, value_type, description, category)
VALUES
    ('feature_flag_sponsorship', 'true', NOW(), 'boolean', 'Enable sponsorship relationships', 'features'),
    ('feature_flag_essential_mode', 'true', NOW(), 'boolean', 'Enable Essential Mode on-device processing', 'features'),
    ('feature_flag_in_room_purchase', 'true', NOW(), 'boolean', 'Enable in-room credit purchases', 'features'),
    ('feature_flag_gifting', 'false', NOW(), 'boolean', 'Enable quota gifting (Phase 2)', 'features'),
    ('quota_grace_buffer_seconds', '60', NOW(), 'integer', 'Grace period for quota exhaustion (1 minute)', 'quota'),
    ('guest_session_ttl_seconds', '3600', NOW(), 'integer', 'Guest session TTL (1 hour)', 'sessions'),
    ('sponsorship_grace_seconds', '60', NOW(), 'integer', 'Grace period when sponsor leaves (1 minute)', 'quota'),
    ('guest_reconnect_grace_seconds', '600', NOW(), 'integer', 'Guest reconnect grace period (10 minutes)', 'sessions')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at;

-- ========================================
-- 10. Functions (Quota Deduction with Locking)
-- ========================================

-- Function: Deduct quota with row-level locks (atomicity)
CREATE OR REPLACE FUNCTION deduct_quota_with_lock(
    p_user_id INTEGER,
    p_amount_seconds INTEGER,
    p_room_id INTEGER,
    p_quota_type VARCHAR(20) DEFAULT 'premium'
) RETURNS TABLE(
    success BOOLEAN,
    source VARCHAR(20),
    remaining_seconds INTEGER,
    error_message TEXT
) AS $$
DECLARE
    v_available INTEGER;
    v_subscription RECORD;
    v_tier_quota_seconds INTEGER;
    v_used_monthly_seconds INTEGER;
BEGIN
    -- Validate inputs
    IF p_amount_seconds <= 0 THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, 0, 'Amount must be positive';
        RETURN;
    END IF;

    -- Lock user's subscription row (CRITICAL for atomicity)
    -- NOWAIT ensures immediate failure if row already locked (prevents deadlocks)
    SELECT * INTO v_subscription
    FROM user_subscriptions
    WHERE user_id = p_user_id
    FOR UPDATE NOWAIT;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, 0, 'User subscription not found';
        RETURN;
    END IF;

    -- Calculate available quota based on type
    IF p_quota_type = 'premium' THEN
        -- Waterfall: bonus credits first, then monthly quota
        v_available := v_subscription.bonus_credits_seconds;

        IF v_available < p_amount_seconds THEN
            -- Not enough bonus credits, check monthly quota
            -- Get tier's monthly quota limit
            SELECT COALESCE(st.monthly_quota_hours * 3600, 0)
            INTO v_tier_quota_seconds
            FROM subscription_tiers st
            WHERE st.id = v_subscription.tier_id;

            -- Calculate how much monthly quota has been used this billing period
            SELECT COALESCE(SUM(-amount_seconds), 0)
            INTO v_used_monthly_seconds
            FROM quota_transactions
            WHERE user_id = p_user_id
            AND quota_type = 'premium'
            AND amount_seconds < 0  -- Only deductions
            AND created_at >= v_subscription.billing_period_start
            AND created_at < COALESCE(v_subscription.billing_period_end, NOW() + INTERVAL '1 year');

            -- Add remaining monthly quota to available
            v_available := v_available + GREATEST(0, v_tier_quota_seconds - v_used_monthly_seconds);
        END IF;

    ELSIF p_quota_type = 'essential' THEN
        v_available := v_subscription.essential_quota_seconds;

    ELSIF p_quota_type = 'grace' THEN
        v_available := v_subscription.grace_quota_seconds;

    ELSE
        RETURN QUERY SELECT FALSE, NULL::VARCHAR, 0, 'Invalid quota type: ' || p_quota_type;
        RETURN;
    END IF;

    -- Check if sufficient quota
    IF v_available < p_amount_seconds THEN
        RETURN QUERY SELECT FALSE, p_quota_type, v_available, 'Insufficient quota';
        RETURN;
    END IF;

    -- Deduct quota (atomically)
    IF p_quota_type = 'premium' THEN
        -- Deduct from bonus credits first
        IF v_subscription.bonus_credits_seconds >= p_amount_seconds THEN
            UPDATE user_subscriptions
            SET bonus_credits_seconds = bonus_credits_seconds - p_amount_seconds
            WHERE user_id = p_user_id;

            -- Record transaction
            INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, room_id, quota_type, balance_after_seconds)
            VALUES (p_user_id, 'deduct', -p_amount_seconds, p_room_id, 'bonus', v_subscription.bonus_credits_seconds - p_amount_seconds);
        ELSE
            -- Split deduction: use all bonus credits, then monthly
            IF v_subscription.bonus_credits_seconds > 0 THEN
                UPDATE user_subscriptions
                SET bonus_credits_seconds = 0
                WHERE user_id = p_user_id;

                -- Record bonus credit depletion
                INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, room_id, quota_type, balance_after_seconds)
                VALUES (p_user_id, 'deduct', -v_subscription.bonus_credits_seconds, p_room_id, 'bonus', 0);
            END IF;

            -- Record monthly quota deduction
            INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, room_id, quota_type, balance_after_seconds)
            VALUES (p_user_id, 'deduct', -(p_amount_seconds - v_subscription.bonus_credits_seconds), p_room_id, 'premium', v_available - p_amount_seconds);
        END IF;

    ELSIF p_quota_type = 'essential' THEN
        UPDATE user_subscriptions
        SET essential_quota_seconds = essential_quota_seconds - p_amount_seconds
        WHERE user_id = p_user_id;

        -- Record transaction
        INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, room_id, quota_type, balance_after_seconds)
        VALUES (p_user_id, 'deduct', -p_amount_seconds, p_room_id, 'essential', v_subscription.essential_quota_seconds - p_amount_seconds);

    ELSIF p_quota_type = 'grace' THEN
        UPDATE user_subscriptions
        SET grace_quota_seconds = grace_quota_seconds - p_amount_seconds
        WHERE user_id = p_user_id;

        -- Record transaction
        INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, room_id, quota_type, balance_after_seconds)
        VALUES (p_user_id, 'deduct', -p_amount_seconds, p_room_id, 'grace', v_subscription.grace_quota_seconds - p_amount_seconds);
    END IF;

    -- Return success with updated remaining quota
    RETURN QUERY SELECT TRUE, p_quota_type, v_available - p_amount_seconds, NULL::TEXT;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION deduct_quota_with_lock IS
'PM Decision Q1: Use PostgreSQL row-level locks for atomic quota deduction. Prevents race conditions in sponsorship.';

COMMIT;

-- ========================================
-- Rollback Script (Run if migration fails)
-- ========================================

-- BEGIN;
--
-- DROP FUNCTION IF EXISTS deduct_quota_with_lock(INTEGER, INTEGER, INTEGER, VARCHAR);
-- DROP TABLE IF EXISTS essential_mode_sessions;
-- DROP TABLE IF EXISTS guest_sessions;
-- DROP TABLE IF EXISTS pending_gifts;
-- DROP TABLE IF EXISTS sponsorship_relationships;
--
-- ALTER TABLE user_subscriptions DROP CONSTRAINT IF EXISTS chk_essential_quota_positive;
-- ALTER TABLE user_subscriptions DROP COLUMN IF EXISTS essential_quota_seconds;
-- ALTER TABLE quota_transactions DROP COLUMN IF EXISTS balance_after_seconds;
-- ALTER TABLE quota_transactions DROP COLUMN IF EXISTS sponsored_by_user_id;
-- ALTER TABLE payment_transactions DROP COLUMN IF EXISTS gift_id;
-- ALTER TABLE rooms DROP CONSTRAINT IF EXISTS chk_provider_type;
-- ALTER TABLE rooms DROP COLUMN IF EXISTS auto_sponsor_guests;
-- ALTER TABLE rooms DROP COLUMN IF EXISTS provider_type;
--
-- DELETE FROM system_settings WHERE key IN (
--     'feature_flag_sponsorship',
--     'feature_flag_essential_mode',
--     'feature_flag_in_room_purchase',
--     'feature_flag_gifting',
--     'quota_grace_buffer_seconds',
--     'guest_session_ttl_seconds',
--     'sponsorship_grace_seconds',
--     'guest_reconnect_grace_seconds'
-- );
--
-- COMMIT;

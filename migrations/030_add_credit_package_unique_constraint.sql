-- ========================================
-- Migration 030: Add unique constraint to credit_packages.package_name
-- ========================================
-- Created: 2025-11-06
-- Purpose: Fix test fixture re-seeding by adding unique constraint
--          Required for ON CONFLICT (package_name) to work
-- ========================================

BEGIN;

-- Add unique constraint to package_name (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'credit_packages_package_name_key'
    ) THEN
        ALTER TABLE credit_packages
        ADD CONSTRAINT credit_packages_package_name_key UNIQUE (package_name);
    END IF;
END $$;

-- Re-seed data with proper conflict handling
INSERT INTO subscription_tiers (tier_name, display_name, monthly_price_usd, monthly_quota_hours, features, provider_tier, stripe_price_id, apple_product_id)
VALUES
('free', 'Free', 0, 0.167, '["10 minutes per month"]'::jsonb, 'free', NULL, NULL),
('plus', 'Plus', 29, 2, '["2 hours per month"]'::jsonb, 'standard', 'price_plus_monthly_prod', 'com.livetranslator.plus.monthly'),
('pro', 'Pro', 199, 10, '["10 hours per month"]'::jsonb, 'premium', 'price_pro_monthly_prod', 'com.livetranslator.pro.monthly')
ON CONFLICT (tier_name) DO UPDATE SET
    monthly_quota_hours = EXCLUDED.monthly_quota_hours,
    display_name = EXCLUDED.display_name;

INSERT INTO credit_packages (package_name, display_name, hours, price_usd, discount_percent, sort_order, stripe_price_id, apple_product_id)
VALUES
('1hr', '1 Hour', 1, 5, 0, 1, 'price_1hr_prod', 'com.livetranslator.credits.1hr'),
('4hr', '4 Hours', 4, 19, 5, 2, 'price_4hr_prod', 'com.livetranslator.credits.4hr'),
('8hr', '8 Hours (Best Value!)', 8, 35, 12.5, 3, 'price_8hr_prod', 'com.livetranslator.credits.8hr'),
('20hr', '20 Hours (Enterprise)', 20, 80, 20, 4, 'price_20hr_prod', 'com.livetranslator.credits.20hr')
ON CONFLICT (package_name) DO UPDATE SET
    hours = EXCLUDED.hours,
    price_usd = EXCLUDED.price_usd,
    discount_percent = EXCLUDED.discount_percent;

-- Insert migration record
INSERT INTO schema_migrations (version, name, applied_at)
VALUES ('030', 'add_credit_package_unique_constraint', NOW())
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verify
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 030 completed successfully';
    RAISE NOTICE '📊 Subscription tiers: %', (SELECT COUNT(*) FROM subscription_tiers);
    RAISE NOTICE '💳 Credit packages: %', (SELECT COUNT(*) FROM credit_packages);
END $$;

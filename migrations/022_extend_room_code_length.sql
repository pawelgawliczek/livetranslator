-- Migration 022: Extend room code length for test compatibility
-- Reason: Tests use timestamp-based codes (37 chars), schema limited to 12

-- Drop dependent materialized view
DROP MATERIALIZED VIEW IF EXISTS admin_tier_analysis;

-- Extend room code column
ALTER TABLE rooms
  ALTER COLUMN code TYPE varchar(64);

-- Recreate materialized view with same definition
CREATE MATERIALIZED VIEW admin_tier_analysis AS
SELECT
  st.tier_name,
  st.display_name,
  st.monthly_price_usd,
  COUNT(DISTINCT us.user_id) AS active_users,
  SUM(st.monthly_price_usd) AS monthly_recurring_revenue,
  COALESCE(SUM(costs.total_cost), 0) AS total_costs_usd,
  SUM(st.monthly_price_usd) - COALESCE(SUM(costs.total_cost), 0) AS gross_profit_usd
FROM subscription_tiers st
LEFT JOIN user_subscriptions us ON st.id = us.tier_id AND us.status = 'active'
LEFT JOIN rooms r ON r.owner_id = us.user_id
LEFT JOIN LATERAL (
  SELECT SUM(amount_usd) AS total_cost
  FROM room_costs
  WHERE room_id = r.code::text
    AND ts >= us.billing_period_start
    AND ts < us.billing_period_end
) costs ON true
GROUP BY st.id, st.tier_name, st.display_name, st.monthly_price_usd
ORDER BY st.id;

-- Recreate index
CREATE UNIQUE INDEX idx_admin_tier_analysis_name ON admin_tier_analysis(tier_name);

-- Refresh view with current data
REFRESH MATERIALIZED VIEW admin_tier_analysis;

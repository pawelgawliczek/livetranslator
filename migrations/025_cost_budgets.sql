-- Migration 025: Cost Budgets and Alerts
-- Purpose: Allow admins to set monthly cost budgets and receive alerts
-- Phase 5A: Analytics Enhancements

BEGIN;

-- Create cost_budgets table
CREATE TABLE IF NOT EXISTS cost_budgets (
  id SERIAL PRIMARY KEY,
  period_type VARCHAR(20) NOT NULL DEFAULT 'monthly', -- 'monthly', 'weekly', 'daily'
  budget_usd DECIMAL(10, 2) NOT NULL,
  alert_threshold_pct INTEGER NOT NULL DEFAULT 80, -- Alert when reaching this % of budget
  critical_threshold_pct INTEGER NOT NULL DEFAULT 95, -- Critical alert threshold
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_by INTEGER REFERENCES users(id)
);

-- Create budget_alerts table to track when alerts were triggered
CREATE TABLE IF NOT EXISTS budget_alerts (
  id SERIAL PRIMARY KEY,
  budget_id INTEGER NOT NULL REFERENCES cost_budgets(id) ON DELETE CASCADE,
  alert_type VARCHAR(20) NOT NULL, -- 'warning', 'critical', 'exceeded'
  period_start TIMESTAMP NOT NULL,
  period_end TIMESTAMP NOT NULL,
  actual_cost_usd DECIMAL(10, 2) NOT NULL,
  budget_usd DECIMAL(10, 2) NOT NULL,
  percentage_used INTEGER NOT NULL,
  triggered_at TIMESTAMP NOT NULL DEFAULT NOW(),
  acknowledged_at TIMESTAMP,
  acknowledged_by INTEGER REFERENCES users(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_cost_budgets_active ON cost_budgets(is_active);
CREATE INDEX IF NOT EXISTS idx_budget_alerts_budget_id ON budget_alerts(budget_id);
CREATE INDEX IF NOT EXISTS idx_budget_alerts_triggered_at ON budget_alerts(triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_budget_alerts_acknowledged ON budget_alerts(acknowledged_at) WHERE acknowledged_at IS NULL;

-- Comments
COMMENT ON TABLE cost_budgets IS 'Cost budgets for monitoring and alerts';
COMMENT ON TABLE budget_alerts IS 'Historical log of budget alerts';
COMMENT ON COLUMN cost_budgets.alert_threshold_pct IS 'Send warning alert at this percentage';
COMMENT ON COLUMN cost_budgets.critical_threshold_pct IS 'Send critical alert at this percentage';
COMMENT ON COLUMN budget_alerts.alert_type IS 'warning (80%+), critical (95%+), exceeded (100%+)';

COMMIT;

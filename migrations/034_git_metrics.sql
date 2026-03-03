-- Migration 034: AI Metrics - Git Analysis (Phase 0B)
-- Purpose: Add FTRR, Code Churn, Defect Escape, Iteration Depth fields
-- References: TEMP_architect_phase0_review.md (Phase 0B: Git Analysis Foundation)

BEGIN;

-- First-Time-Right Rate (FTRR)
-- Tracks if code was written correctly on first attempt (no fix commits within 24h)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS fix_commits_24h INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS first_time_right BOOLEAN DEFAULT true;

-- Code Churn Rate
-- Tracks lines modified/deleted within 14 days of creation (instability indicator)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS churn_lines_modified INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS churn_lines_deleted INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS churn_rate_percent NUMERIC(5,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS churn_measured_at TIMESTAMP;

-- Defect Escape Rate
-- Tracks bugs that escaped to production vs caught pre-deployment
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS production_bugs INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS predeployment_bugs INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS defect_escape_rate NUMERIC(5,2) DEFAULT 0;

-- Iteration Depth
-- Tracks number of revision rounds per task (rework indicator)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS iteration_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS revision_commits INTEGER DEFAULT 0;

-- Add constraints
ALTER TABLE ai_development_metrics
ADD CONSTRAINT chk_churn_rate_range CHECK (churn_rate_percent >= 0 AND churn_rate_percent <= 100),
ADD CONSTRAINT chk_escape_rate_range CHECK (defect_escape_rate >= 0 AND defect_escape_rate <= 100),
ADD CONSTRAINT chk_iteration_positive CHECK (iteration_count >= 0);

-- Add indexes for queries
CREATE INDEX IF NOT EXISTS idx_ai_metrics_ftrr ON ai_development_metrics(first_time_right);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_churn_measured ON ai_development_metrics(churn_measured_at DESC);

-- Add column comments for documentation
COMMENT ON COLUMN ai_development_metrics.first_time_right IS 'True if no fix commits within 24h of initial commit (FTRR metric)';
COMMENT ON COLUMN ai_development_metrics.fix_commits_24h IS 'Count of fix/bug/hotfix commits within 24 hours of file creation';
COMMENT ON COLUMN ai_development_metrics.churn_rate_percent IS 'Code churn: (lines modified+deleted within 14 days) / total lines added × 100';
COMMENT ON COLUMN ai_development_metrics.churn_measured_at IS 'Timestamp when churn was last calculated (nightly background job)';
COMMENT ON COLUMN ai_development_metrics.defect_escape_rate IS 'Defect escape rate: production bugs / (production + predeployment bugs) × 100';
COMMENT ON COLUMN ai_development_metrics.production_bugs IS 'Bugs that escaped to production (direct commits to main with fix/bug/hotfix)';
COMMENT ON COLUMN ai_development_metrics.predeployment_bugs IS 'Bugs caught before production (merge commits with fix/bug/hotfix)';
COMMENT ON COLUMN ai_development_metrics.iteration_count IS 'Number of revision commits (revert, fix, update, correct, amend)';
COMMENT ON COLUMN ai_development_metrics.revision_commits IS 'Alias for iteration_count (revision rounds per task)';

COMMIT;

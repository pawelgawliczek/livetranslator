-- Migration 033: AI Metrics - User-Requested Core (Phase 0A)
-- Purpose: Add PTC, IPIDR, AES, AWE, TCI baseline tracking
-- References: TEMP_architect_phase0_review.md, TEMP_blog_metrics_design.md

BEGIN;

-- Prompts-to-Completion (PTC) - Track user prompts from start to approval
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS prompts_to_completion INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS implementation_prompts INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS review_prompts INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS approval_prompts INTEGER DEFAULT 0;

-- In-Process Issue Discovery Rate (IPIDR) - Bugs/reworks during development
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS issues_found INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS issues_critical INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS issues_high INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS issues_medium INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS issues_low INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS issue_discovery_phase VARCHAR(50), -- 'implementation', 'review', 'testing'
ADD COLUMN IF NOT EXISTS time_to_fix_avg_minutes NUMERIC(10,2);

-- Approval Efficiency Score (AES) - First-review approval rate
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS approval_status VARCHAR(50), -- 'first_review', 'minor_revisions', 'major_revisions', 'rejected'
ADD COLUMN IF NOT EXISTS approval_efficiency_score NUMERIC(5,2),
ADD COLUMN IF NOT EXISTS revision_count INTEGER DEFAULT 0;

-- Agent Workflow Effectiveness (AWE) - Compare before/after agent changes
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS agent_workflow_version VARCHAR(100), -- 'v1.0-baseline', 'v1.1-explore-agent'
ADD COLUMN IF NOT EXISTS agent_changes_description TEXT,
ADD COLUMN IF NOT EXISTS comparison_period_start TIMESTAMP,
ADD COLUMN IF NOT EXISTS comparison_period_end TIMESTAMP;

-- TCI Baseline Calculator - Human baseline formula metadata
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS human_baseline_hours NUMERIC(10,2),
ADD COLUMN IF NOT EXISTS complexity_factor NUMERIC(5,2), -- 0.25, 1.0, 3.0, 8.0, 12.0
ADD COLUMN IF NOT EXISTS familiarity_factor NUMERIC(5,2), -- 1.5, 1.0, 0.7
ADD COLUMN IF NOT EXISTS type_factor NUMERIC(5,2); -- 0.8, 1.0, 1.2, 1.5, 1.8

-- Add constraints
ALTER TABLE ai_development_metrics
ADD CONSTRAINT chk_prompts_positive CHECK (prompts_to_completion >= 0),
ADD CONSTRAINT chk_issues_positive CHECK (issues_found >= 0),
ADD CONSTRAINT chk_aes_score_range CHECK (approval_efficiency_score IS NULL OR (approval_efficiency_score BETWEEN 0 AND 100)),
ADD CONSTRAINT chk_baseline_positive CHECK (human_baseline_hours IS NULL OR human_baseline_hours >= 0);

-- Add indexes for queries
CREATE INDEX IF NOT EXISTS idx_ai_metrics_workflow_version ON ai_development_metrics(agent_workflow_version);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_approval_status ON ai_development_metrics(approval_status);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_updated ON ai_development_metrics(updated_at DESC);

-- Add column comments for documentation
COMMENT ON COLUMN ai_development_metrics.prompts_to_completion IS 'Total user prompts from task start to approval (PTC metric)';
COMMENT ON COLUMN ai_development_metrics.issues_found IS 'Bugs/reworks found during development, not in production (IPIDR metric)';
COMMENT ON COLUMN ai_development_metrics.approval_efficiency_score IS 'Score 0-100: 100=first review, 80=minor revisions, 50=major, 0=rejected (AES metric)';
COMMENT ON COLUMN ai_development_metrics.agent_workflow_version IS 'Version tag for agent workflow comparison (e.g., v1.0-baseline) for AWE metric';
COMMENT ON COLUMN ai_development_metrics.human_baseline_hours IS 'Calculated human baseline using TCI formula: 2hrs × Complexity × Familiarity × Type';
COMMENT ON COLUMN ai_development_metrics.complexity_factor IS 'TCI complexity: trivial=0.25, simple=1.0, medium=3.0, complex=8.0, security=12.0';
COMMENT ON COLUMN ai_development_metrics.familiarity_factor IS 'TCI familiarity: new=1.5, familiar=1.0, expert=0.7';
COMMENT ON COLUMN ai_development_metrics.type_factor IS 'TCI type: bug=0.8, feature=1.0, refactor=1.2, architecture=1.5, integration=1.8';

COMMIT;

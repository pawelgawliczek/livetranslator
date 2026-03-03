-- Migration 036: AI Agent Contributions Tracking
-- Purpose: Track individual agent performance per feature for detailed analysis
-- User Story: "I want to see which agent used how much time and tokens per feature"

BEGIN;

-- Agent-level breakdown per feature
CREATE TABLE IF NOT EXISTS ai_agent_contributions (
    id SERIAL PRIMARY KEY,

    -- Link to parent feature
    feature_id INTEGER NOT NULL REFERENCES ai_development_metrics(id) ON DELETE CASCADE,

    -- Agent identification
    agent_name VARCHAR(50) NOT NULL, -- 'project-manager', 'business-analyst', 'software-architect', 'full-stack', 'automation-qa', 'devops-engineer', 'security-auditor'
    agent_role VARCHAR(100), -- Human-readable: 'Project Manager', 'Business Analyst', etc.

    -- Time tracking
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_minutes NUMERIC(10,2), -- Actual time spent by agent

    -- Token usage
    tokens_used INTEGER DEFAULT 0,

    -- Interaction metrics
    prompts_received INTEGER DEFAULT 0, -- User prompts directed to this agent
    iterations INTEGER DEFAULT 0, -- Number of back-and-forth rounds

    -- Output metrics
    loc_written INTEGER DEFAULT 0, -- Lines of code written by this agent
    tests_written INTEGER DEFAULT 0, -- Test LOC written
    files_created INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,

    -- Quality metrics
    issues_found INTEGER DEFAULT 0, -- Issues discovered by this agent
    review_comments INTEGER DEFAULT 0, -- Comments/suggestions provided

    -- Agent-specific metadata
    task_description TEXT, -- What this agent was asked to do
    deliverables TEXT, -- What this agent produced (e.g., "TEMP_requirements.md")
    notes TEXT, -- Additional context

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_duration_positive CHECK (duration_minutes IS NULL OR duration_minutes >= 0),
    CONSTRAINT chk_tokens_positive CHECK (tokens_used >= 0),
    CONSTRAINT chk_loc_positive CHECK (loc_written >= 0),
    CONSTRAINT unique_feature_agent UNIQUE (feature_id, agent_name)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_agent_contrib_feature ON ai_agent_contributions(feature_id);
CREATE INDEX IF NOT EXISTS idx_agent_contrib_agent ON ai_agent_contributions(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_contrib_created ON ai_agent_contributions(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE ai_agent_contributions IS
'Tracks individual agent contributions per feature for detailed analysis of agent effectiveness';

COMMENT ON COLUMN ai_agent_contributions.feature_id IS
'Links to ai_development_metrics.id to associate agent work with specific feature';

COMMENT ON COLUMN ai_agent_contributions.agent_name IS
'Agent identifier matching .claude/agents/*.md filename (e.g., "full-stack", "software-architect")';

COMMENT ON COLUMN ai_agent_contributions.tokens_used IS
'Total tokens consumed by this agent for this feature (input + output tokens)';

COMMENT ON COLUMN ai_agent_contributions.duration_minutes IS
'Actual wall-clock time this agent spent on the feature (can be calculated from started_at/completed_at)';

-- Seed example data for Week 1 (Migration 031)
-- This shows how agents contributed to the iOS Sponsorship schema feature
INSERT INTO ai_agent_contributions (
    feature_id, agent_name, agent_role,
    started_at, completed_at, duration_minutes,
    tokens_used, prompts_received, iterations,
    loc_written, tests_written, files_created, files_modified,
    issues_found, review_comments,
    task_description, deliverables
)
SELECT
    (SELECT id FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1' LIMIT 1),
    'project-manager', 'Project Manager',
    '2025-11-07 09:00:00', '2025-11-07 09:15:00', 15,
    8000, 1, 0,
    0, 0, 0, 0,
    0, 0,
    'Plan iOS sponsorship schema migration, coordinate team',
    'TEMP_context.md, Todo list, Team coordination'
WHERE EXISTS (SELECT 1 FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1')
ON CONFLICT (feature_id, agent_name) DO NOTHING;

INSERT INTO ai_agent_contributions (
    feature_id, agent_name, agent_role,
    started_at, completed_at, duration_minutes,
    tokens_used, prompts_received, iterations,
    loc_written, tests_written, files_created, files_modified,
    issues_found, review_comments,
    task_description, deliverables
)
SELECT
    (SELECT id FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1' LIMIT 1),
    'software-architect', 'Software Architect',
    '2025-11-07 09:15:00', '2025-11-07 10:00:00', 45,
    35000, 0, 2,
    0, 0, 0, 0,
    0, 8,
    'Review schema design, ensure referential integrity, index optimization',
    'TEMP_design.md, Schema review, Index recommendations'
WHERE EXISTS (SELECT 1 FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1')
ON CONFLICT (feature_id, agent_name) DO NOTHING;

INSERT INTO ai_agent_contributions (
    feature_id, agent_name, agent_role,
    started_at, completed_at, duration_minutes,
    tokens_used, prompts_received, iterations,
    loc_written, tests_written, files_created, files_modified,
    issues_found, review_comments,
    task_description, deliverables
)
SELECT
    (SELECT id FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1' LIMIT 1),
    'full-stack', 'Full-Stack Developer',
    '2025-11-07 10:00:00', '2025-11-07 14:30:00', 270,
    65000, 1, 3,
    970, 450, 1, 1,
    0, 0,
    'Write migration SQL: 4 tables, 8 indexes, 10 constraints, tests',
    'migrations/031_ios_sponsorship_essential_mode.sql, 13 integration tests'
WHERE EXISTS (SELECT 1 FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1')
ON CONFLICT (feature_id, agent_name) DO NOTHING;

INSERT INTO ai_agent_contributions (
    feature_id, agent_name, agent_role,
    started_at, completed_at, duration_minutes,
    tokens_used, prompts_received, iterations,
    loc_written, tests_written, files_created, files_modified,
    issues_found, review_comments,
    task_description, deliverables
)
SELECT
    (SELECT id FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1' LIMIT 1),
    'automation-qa', 'QA Engineer',
    '2025-11-07 14:30:00', '2025-11-07 15:00:00', 30,
    12000, 0, 1,
    0, 0, 0, 0,
    0, 2,
    'Validate test coverage, run integration tests, verify constraints',
    'Test execution report, Coverage validation'
WHERE EXISTS (SELECT 1 FROM ai_development_metrics WHERE week_number = 1 AND phase = 'phase_1')
ON CONFLICT (feature_id, agent_name) DO NOTHING;

-- View for easy agent performance analysis
CREATE OR REPLACE VIEW v_agent_performance AS
SELECT
    adm.id as feature_id,
    adm.week_number,
    adm.phase,
    adm.feature_name,
    adm.actual_days,
    adm.lines_of_code as feature_loc,
    adm.tokens_used as feature_total_tokens,

    aac.agent_name,
    aac.agent_role,
    aac.duration_minutes,
    aac.tokens_used as agent_tokens,
    aac.prompts_received,
    aac.loc_written,
    aac.tests_written,

    -- Percentage contributions
    CASE
        WHEN adm.tokens_used > 0 THEN (aac.tokens_used::float / adm.tokens_used * 100)
        ELSE 0
    END as token_contribution_percent,

    CASE
        WHEN adm.lines_of_code > 0 THEN (aac.loc_written::float / adm.lines_of_code * 100)
        ELSE 0
    END as loc_contribution_percent,

    -- Efficiency metrics
    CASE
        WHEN aac.loc_written > 0 THEN (aac.tokens_used::float / aac.loc_written)
        ELSE 0
    END as agent_tokens_per_loc,

    CASE
        WHEN aac.duration_minutes > 0 THEN (aac.loc_written::float / aac.duration_minutes)
        ELSE 0
    END as agent_loc_per_minute

FROM ai_development_metrics adm
INNER JOIN ai_agent_contributions aac ON aac.feature_id = adm.id
WHERE adm.phase != 'snapshot'
ORDER BY adm.week_number DESC, aac.started_at ASC;

COMMENT ON VIEW v_agent_performance IS
'Aggregates agent contributions with percentage breakdowns for performance analysis';

COMMIT;

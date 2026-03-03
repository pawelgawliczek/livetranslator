-- Migration 032: AI Development Metrics Tracking
-- Purpose: Track AI-assisted development effectiveness for research/blog posts

CREATE TABLE IF NOT EXISTS ai_development_metrics (
    id SERIAL PRIMARY KEY,

    -- Feature identification
    week_number INTEGER NOT NULL,
    phase VARCHAR(20) NOT NULL,
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,

    -- Time tracking (core metrics)
    estimated_days NUMERIC(5,2) NOT NULL,
    actual_days NUMERIC(5,2) NOT NULL,
    velocity_ratio NUMERIC(5,2) NOT NULL,  -- AI vs Human multiplier
    lead_time_hours NUMERIC(5,2),
    human_baseline_days NUMERIC(5,2),  -- For comparison graphs

    -- Quality metrics
    static_analysis_issues INTEGER DEFAULT 0,
    test_coverage_percent NUMERIC(5,2) DEFAULT 0,
    tests_passing INTEGER DEFAULT 0,
    tests_total INTEGER DEFAULT 0,
    bugs_in_review INTEGER DEFAULT 0,
    hotfixes_required INTEGER DEFAULT 0,
    quality_score NUMERIC(5,2) DEFAULT 0,

    -- Code metrics
    lines_of_code INTEGER DEFAULT 0,
    lines_of_tests INTEGER DEFAULT 0,
    files_created INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,

    -- Interaction metrics (NEW - for blog insights)
    user_prompts INTEGER DEFAULT 0,
    agent_handoffs INTEGER DEFAULT 0,
    iterations INTEGER DEFAULT 0,
    loc_per_prompt NUMERIC(8,2) DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    tokens_per_loc NUMERIC(8,2) DEFAULT 0,

    -- Cost analysis (NEW - for ROI calculations)
    human_estimated_cost_usd NUMERIC(10,2),  -- Baseline cost
    ai_actual_cost_usd NUMERIC(10,2),         -- Token costs
    cost_savings_usd NUMERIC(10,2),
    cost_savings_percent NUMERIC(5,2),

    -- Timestamps
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_positive_metrics CHECK (
        estimated_days > 0 AND
        actual_days > 0 AND
        velocity_ratio > 0 AND
        quality_score >= 0 AND quality_score <= 100
    ),
    CONSTRAINT chk_tests_valid CHECK (tests_passing <= tests_total)
);

CREATE INDEX IF NOT EXISTS idx_ai_metrics_week ON ai_development_metrics(week_number);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_phase ON ai_development_metrics(phase);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_created ON ai_development_metrics(created_at DESC);

-- Seed Week 1 data (Migration 031)
INSERT INTO ai_development_metrics (
    week_number, phase, feature_name, feature_description,
    estimated_days, actual_days, velocity_ratio, lead_time_hours, human_baseline_days,
    static_analysis_issues, test_coverage_percent, tests_passing, tests_total,
    bugs_in_review, hotfixes_required, quality_score,
    lines_of_code, lines_of_tests, files_created, files_modified,
    user_prompts, agent_handoffs, iterations, loc_per_prompt, tokens_used, tokens_per_loc,
    human_estimated_cost_usd, ai_actual_cost_usd, cost_savings_usd, cost_savings_percent,
    started_at, completed_at
) VALUES (
    1, 'phase_1', 'Migration 031 - iOS Sponsorship Schema',
    'Database schema for iOS Sponsorship & Essential Mode: 4 tables, 8 indexes, 10 constraints, row-level lock function',
    5.0, 0.6, 7.0, 6.0, 5.0,
    0, 100.0, 13, 13,
    0, 0, 100.0,
    970, 450, 2, 0,
    2, 3, 0, 485, 120000, 124,
    5000.00, 60.00, 4940.00, 98.80,
    '2025-11-07 09:00:00', '2025-11-07 15:00:00'
)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE ai_development_metrics IS
'Tracks AI-assisted development effectiveness for research and blog content. Compares AI vs human developer metrics.';

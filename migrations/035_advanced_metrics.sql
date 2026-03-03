-- Migration 035: AI Metrics - Advanced Metrics (Phase 0C)
-- Purpose: Add remaining 11 metrics for comprehensive development analysis
-- References: TEMP_blog_metrics_design.md, TEMP_architect_phase0_review.md

BEGIN;

-- Planning-to-Execution Ratio
-- Time spent designing vs implementing (higher = more upfront planning)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS ba_time_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS architect_time_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS fullstack_time_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS planning_execution_ratio NUMERIC(10,2) DEFAULT 0;

-- Agent Specialization Efficiency
-- % of tasks routed to optimal agent on first try (PM routing accuracy)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS tasks_correct_agent INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS tasks_redelegated INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS specialization_efficiency NUMERIC(5,2) DEFAULT 100;

-- Context Switch Overhead
-- Time spent on coordination vs coding (agent handoff overhead)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS coordination_time_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS coding_time_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS context_switch_overhead_percent NUMERIC(5,2) DEFAULT 0;

-- Refactor Intentionality Score
-- % of refactors that are planned vs reactive (proactive vs firefighting)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS planned_refactors INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS reactive_refactors INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS refactor_intentionality_score NUMERIC(5,2) DEFAULT 100;

-- API Cost Efficiency
-- Claude API cost per 1000 LOC delivered
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS api_cost_per_1k_loc NUMERIC(10,2) DEFAULT 0;

-- Time-to-Market Compression
-- Project milestones completed vs traditional estimates
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS milestone_actual_days NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS milestone_baseline_days NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS time_to_market_compression_percent NUMERIC(5,2) DEFAULT 0;

-- Knowledge Transfer Latency
-- Time for new agent to become productive (onboarding speed)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS onboarding_time_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS first_successful_task_hours NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS explore_agent_calls INTEGER DEFAULT 0;

-- Cognitive Load Reduction
-- Complexity of tasks AI handles vs human must review
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS ai_task_complexity_avg NUMERIC(5,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS human_review_complexity_avg NUMERIC(5,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS cognitive_load_reduction_ratio NUMERIC(5,2) DEFAULT 1.0;

-- Test Coverage Trends (formalize existing test_coverage_percent)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS test_coverage_delta NUMERIC(5,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS test_to_code_ratio NUMERIC(5,2) DEFAULT 0;

-- Cost Per Feature (formalize existing cost_savings_usd)
ALTER TABLE ai_development_metrics
ADD COLUMN IF NOT EXISTS cost_per_feature_usd NUMERIC(10,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS hourly_rate_usd NUMERIC(10,2) DEFAULT 150.00;

-- AI Acceleration Factor (formalize existing velocity_ratio)
-- Already exists as velocity_ratio, no new column needed

-- Add constraints
ALTER TABLE ai_development_metrics
ADD CONSTRAINT chk_specialization_range CHECK (specialization_efficiency >= 0 AND specialization_efficiency <= 100),
ADD CONSTRAINT chk_context_overhead_range CHECK (context_switch_overhead_percent >= 0 AND context_switch_overhead_percent <= 100),
ADD CONSTRAINT chk_refactor_intentionality_range CHECK (refactor_intentionality_score >= 0 AND refactor_intentionality_score <= 100),
ADD CONSTRAINT chk_time_to_market_range CHECK (time_to_market_compression_percent >= 0 AND time_to_market_compression_percent <= 100);

-- Add indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_ai_metrics_planning_ratio ON ai_development_metrics(planning_execution_ratio);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_agent_efficiency ON ai_development_metrics(specialization_efficiency);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_context_overhead ON ai_development_metrics(context_switch_overhead_percent);
CREATE INDEX IF NOT EXISTS idx_ai_metrics_refactor_score ON ai_development_metrics(refactor_intentionality_score);

-- Add column comments for documentation
COMMENT ON COLUMN ai_development_metrics.planning_execution_ratio IS 'Planning-to-Execution Ratio: (BA + Architect time) / FullStack time. Higher = more upfront planning';
COMMENT ON COLUMN ai_development_metrics.specialization_efficiency IS 'Agent Specialization Efficiency: tasks_correct_agent / total_tasks × 100. PM routing accuracy';
COMMENT ON COLUMN ai_development_metrics.context_switch_overhead_percent IS 'Context Switch Overhead: coordination_time / total_time × 100. Agent handoff cost';
COMMENT ON COLUMN ai_development_metrics.refactor_intentionality_score IS 'Refactor Intentionality: planned_refactors / total_refactors × 100. Proactive vs reactive';
COMMENT ON COLUMN ai_development_metrics.api_cost_per_1k_loc IS 'API Cost Efficiency: total_api_cost / (total_loc / 1000). Cost per 1000 lines delivered';
COMMENT ON COLUMN ai_development_metrics.time_to_market_compression_percent IS 'Time-to-Market Compression: 1 - (actual_days / baseline_days). Launch speed improvement';
COMMENT ON COLUMN ai_development_metrics.onboarding_time_hours IS 'Knowledge Transfer Latency: Time for agent to become productive on codebase';
COMMENT ON COLUMN ai_development_metrics.cognitive_load_reduction_ratio IS 'Cognitive Load Reduction: avg_complexity(AI_tasks) / avg_complexity(human_review_tasks)';
COMMENT ON COLUMN ai_development_metrics.test_to_code_ratio IS 'Test-to-Code Ratio: test_loc / production_loc. Industry benchmark: 1.2:1 (Google)';
COMMENT ON COLUMN ai_development_metrics.cost_per_feature_usd IS 'Cost Per Feature: (dev_hours × hourly_rate + api_costs) / feature_points';

COMMIT;

-- Migration 029: Metrics Dashboard Tables
-- Purpose: Store daily snapshots of codebase metrics for health monitoring and refactoring decisions
-- Phase 1: MVP tables for overview + complexity tracking

BEGIN;

-- Table 1: metrics_snapshots (daily aggregated metrics)
CREATE TABLE IF NOT EXISTS metrics_snapshots (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,

    -- LOC metrics
    total_loc INTEGER NOT NULL,
    api_loc INTEGER NOT NULL,
    web_loc INTEGER NOT NULL,
    test_loc INTEGER NOT NULL,

    -- Test metrics
    test_pass_rate FLOAT NOT NULL CHECK (test_pass_rate >= 0 AND test_pass_rate <= 100),
    test_count INTEGER NOT NULL DEFAULT 0,

    -- Complexity metrics
    avg_complexity FLOAT NOT NULL DEFAULT 0,

    -- Health score (0-100 calculated from sub-metrics)
    health_score INTEGER NOT NULL CHECK (health_score >= 0 AND health_score <= 100),

    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE metrics_snapshots IS 'Daily aggregated codebase metrics for health dashboard';
COMMENT ON COLUMN metrics_snapshots.health_score IS 'Weighted average: 40% test_pass_rate + 30% complexity_score + 20% test_coverage + 10% test_ratio';
COMMENT ON COLUMN metrics_snapshots.date IS 'Snapshot date (daily granularity, collected at 02:00 UTC)';

CREATE INDEX IF NOT EXISTS idx_metrics_date ON metrics_snapshots(date DESC);

-- Table 2: complexity_snapshots (per-file complexity data)
CREATE TABLE IF NOT EXISTS complexity_snapshots (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    file_path VARCHAR(500) NOT NULL,

    -- Complexity metrics
    avg_ccn FLOAT NOT NULL DEFAULT 0,
    max_ccn INTEGER NOT NULL DEFAULT 0,
    total_loc INTEGER NOT NULL DEFAULT 0,
    function_count INTEGER NOT NULL DEFAULT 0,

    -- Critical path flag (hardcoded list: payments, billing, quota, auth, websocket)
    is_critical_path BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT NOW() NOT NULL,

    UNIQUE(date, file_path)
);

COMMENT ON TABLE complexity_snapshots IS 'Per-file complexity metrics for refactoring prioritization';
COMMENT ON COLUMN complexity_snapshots.is_critical_path IS 'Hardcoded: payments, billing, quota, auth, websocket files';
COMMENT ON COLUMN complexity_snapshots.avg_ccn IS 'Average cyclomatic complexity per function (lizard output)';
COMMENT ON COLUMN complexity_snapshots.max_ccn IS 'Maximum cyclomatic complexity in file';

CREATE INDEX IF NOT EXISTS idx_complexity_date ON complexity_snapshots(date DESC);
CREATE INDEX IF NOT EXISTS idx_complexity_date_critical ON complexity_snapshots(date DESC, is_critical_path) WHERE is_critical_path = TRUE;
CREATE INDEX IF NOT EXISTS idx_complexity_date_ccn ON complexity_snapshots(date DESC, avg_ccn DESC);

-- Table 3: function_complexity (function-level detail for drill-down)
CREATE TABLE IF NOT EXISTS function_complexity (
    id SERIAL PRIMARY KEY,
    snapshot_id INTEGER REFERENCES complexity_snapshots(id) ON DELETE CASCADE,

    -- Function identification
    function_name VARCHAR(255) NOT NULL,

    -- Complexity metrics
    ccn INTEGER NOT NULL,
    loc INTEGER NOT NULL,
    parameter_count INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE function_complexity IS 'Function-level complexity for detailed refactoring analysis';
COMMENT ON COLUMN function_complexity.ccn IS 'Cyclomatic complexity number (McCabe metric)';

CREATE INDEX IF NOT EXISTS idx_function_snapshot ON function_complexity(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_function_ccn ON function_complexity(ccn DESC);

COMMIT;

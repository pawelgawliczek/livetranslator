#!/bin/bash
#
# Temporary Metrics Management for AI Development
#
# Usage:
#   ./scripts/metrics_temp.sh init <feature_name>    # Start tracking new feature
#   ./scripts/metrics_temp.sh add-agent <agent_name> # Record agent contribution
#   ./scripts/metrics_temp.sh show                   # Display current metrics
#   ./scripts/metrics_temp.sh commit                 # Save to database and cleanup
#   ./scripts/metrics_temp.sh reset                  # Discard current metrics
#

METRICS_FILE="/tmp/feature_metrics.json"
AGENTS_FILE="/tmp/agent_contributions.json"

# Initialize new feature tracking
init_feature() {
    local feature_name="$1"
    if [ -z "$feature_name" ]; then
        echo "Error: Feature name required"
        echo "Usage: $0 init <feature_name>"
        exit 1
    fi

    cat > "$METRICS_FILE" <<EOF
{
  "feature_name": "$feature_name",
  "started_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "phase": "phase_1",
  "week_number": 3,
  "description": "",
  "estimated_days": 0.0,
  "user_prompts": 0,
  "notes": []
}
EOF

    cat > "$AGENTS_FILE" <<EOF
[]
EOF

    echo "✅ Initialized tracking for: $feature_name"
    echo "📁 Metrics file: $METRICS_FILE"
    echo "📁 Agents file: $AGENTS_FILE"
}

# Add agent contribution
add_agent() {
    local agent_name="$1"

    if [ ! -f "$AGENTS_FILE" ]; then
        echo "Error: No feature tracking initialized. Run: $0 init <feature_name>"
        exit 1
    fi

    echo ""
    echo "Recording contribution for agent: $agent_name"
    echo "Press Ctrl+C to cancel, or provide the following information:"
    echo ""

    read -p "Agent role (e.g., Full-Stack Developer): " agent_role
    read -p "Duration in minutes: " duration_minutes
    read -p "Tokens used: " tokens_used
    read -p "LOC written (0 if not applicable): " loc_written
    read -p "Tests written (0 if not applicable): " tests_written
    read -p "Prompts received (0 if coordinated by PM): " prompts_received
    read -p "Task description: " task_description
    read -p "Deliverables: " deliverables

    # Create agent entry
    local agent_entry=$(cat <<EOF
{
  "agent_name": "$agent_name",
  "agent_role": "$agent_role",
  "started_at": "$(date -u -d "$duration_minutes minutes ago" +"%Y-%m-%dT%H:%M:%S")",
  "completed_at": "$(date -u +"%Y-%m-%dT%H:%M:%S")",
  "duration_minutes": $duration_minutes,
  "tokens_used": $tokens_used,
  "prompts_received": $prompts_received,
  "loc_written": $loc_written,
  "tests_written": $tests_written,
  "task_description": "$task_description",
  "deliverables": "$deliverables"
}
EOF
)

    # Append to agents array
    local temp_file="${AGENTS_FILE}.tmp"
    jq ". += [$agent_entry]" "$AGENTS_FILE" > "$temp_file" && mv "$temp_file" "$AGENTS_FILE"

    echo "✅ Recorded contribution for $agent_name"
}

# Show current metrics
show_metrics() {
    if [ ! -f "$METRICS_FILE" ]; then
        echo "No feature tracking initialized."
        exit 0
    fi

    echo ""
    echo "==================================="
    echo "Current Feature Metrics"
    echo "==================================="
    echo ""

    echo "Feature:"
    jq -r '"  Name: \(.feature_name)\n  Phase: \(.phase)\n  Week: \(.week_number)\n  Started: \(.started_at)\n  Prompts: \(.user_prompts)"' "$METRICS_FILE"

    echo ""
    echo "Agent Contributions:"
    if [ ! -f "$AGENTS_FILE" ]; then
        echo "  (none recorded)"
    else
        jq -r '.[] | "  - \(.agent_name) (\(.agent_role))\n    Duration: \(.duration_minutes) min | Tokens: \(.tokens_used) | LOC: \(.loc_written) | Tests: \(.tests_written)\n    Task: \(.task_description)"' "$AGENTS_FILE"
    fi

    echo ""
    echo "Totals:"
    if [ -f "$AGENTS_FILE" ]; then
        local total_time=$(jq '[.[].duration_minutes] | add' "$AGENTS_FILE")
        local total_tokens=$(jq '[.[].tokens_used] | add' "$AGENTS_FILE")
        local total_loc=$(jq '[.[].loc_written] | add' "$AGENTS_FILE")
        local total_tests=$(jq '[.[].tests_written] | add' "$AGENTS_FILE")
        echo "  Time: $total_time minutes"
        echo "  Tokens: $total_tokens"
        echo "  LOC: $total_loc"
        echo "  Tests: $total_tests"
    fi
    echo ""
}

# Commit metrics to database
commit_metrics() {
    if [ ! -f "$METRICS_FILE" ] || [ ! -f "$AGENTS_FILE" ]; then
        echo "Error: No metrics to commit"
        exit 1
    fi

    echo ""
    echo "Current metrics:"
    show_metrics
    echo ""
    read -p "Commit these metrics to database? (y/n): " confirm

    if [ "$confirm" != "y" ]; then
        echo "Aborted."
        exit 0
    fi

    # Calculate totals
    local total_minutes=$(jq '[.[].duration_minutes] | add' "$AGENTS_FILE")
    local total_tokens=$(jq '[.[].tokens_used] | add' "$AGENTS_FILE")
    local total_loc=$(jq '[.[].loc_written] | add' "$AGENTS_FILE")
    local total_tests=$(jq '[.[].tests_written] | add' "$AGENTS_FILE")
    local actual_days=$(echo "scale=3; $total_minutes / 1440" | bc)

    # Additional metrics needed
    echo ""
    echo "Additional metrics needed for database:"
    read -p "Human baseline estimate (days): " baseline_days
    read -p "Quality score (0-100): " quality_score
    read -p "Tests passing: " tests_passing
    read -p "Tests total: " tests_total

    local velocity_ratio=$(echo "scale=2; $baseline_days / $actual_days" | bc)
    local tokens_per_loc=$(echo "scale=2; $total_tokens / $total_loc" | bc)

    # Extract feature info
    local feature_name=$(jq -r '.feature_name' "$METRICS_FILE")
    local phase=$(jq -r '.phase' "$METRICS_FILE")
    local week_number=$(jq -r '.week_number' "$METRICS_FILE")
    local started_at=$(jq -r '.started_at' "$METRICS_FILE")
    local completed_at=$(date -u +"%Y-%m-%dT%H:%M:%S")
    local description=$(jq -r '.description' "$METRICS_FILE")

    # Create feature record
    echo ""
    echo "Creating feature record..."

    FEATURE_ID=$(PGPASSWORD=${POSTGRES_PASSWORD} docker compose exec -T postgres psql -U lt_user -d livetranslator -t -c "
INSERT INTO ai_development_metrics (
  week_number, phase, feature_name, feature_description,
  estimated_days, actual_days, velocity_ratio, human_baseline_days,
  quality_score, lines_of_code, lines_of_tests,
  tests_passing, tests_total,
  user_prompts, tokens_used, tokens_per_loc,
  started_at, completed_at
) VALUES (
  $week_number, '$phase', '$feature_name', '$description',
  0.0, $actual_days, $velocity_ratio, $baseline_days,
  $quality_score, $total_loc, $total_tests,
  $tests_passing, $tests_total,
  $(jq -r '.user_prompts' "$METRICS_FILE"), $total_tokens, $tokens_per_loc,
  '$started_at', '$completed_at'
) RETURNING id;
" | tr -d ' ')

    echo "✅ Feature ID: $FEATURE_ID"

    # Insert agent contributions
    echo "Recording agent contributions..."

    jq -c '.[]' "$AGENTS_FILE" | while read -r agent; do
        local agent_name=$(echo "$agent" | jq -r '.agent_name')
        local agent_role=$(echo "$agent" | jq -r '.agent_role')
        local started=$(echo "$agent" | jq -r '.started_at')
        local completed=$(echo "$agent" | jq -r '.completed_at')
        local duration=$(echo "$agent" | jq -r '.duration_minutes')
        local tokens=$(echo "$agent" | jq -r '.tokens_used')
        local prompts=$(echo "$agent" | jq -r '.prompts_received')
        local loc=$(echo "$agent" | jq -r '.loc_written')
        local tests=$(echo "$agent" | jq -r '.tests_written')
        local task=$(echo "$agent" | jq -r '.task_description' | sed "s/'/''/g")
        local deliverables=$(echo "$agent" | jq -r '.deliverables' | sed "s/'/''/g")

        PGPASSWORD=${POSTGRES_PASSWORD} docker compose exec -T postgres psql -U lt_user -d livetranslator -c "
INSERT INTO ai_agent_contributions (
  feature_id, agent_name, agent_role,
  started_at, completed_at, duration_minutes,
  tokens_used, prompts_received,
  loc_written, tests_written,
  task_description, deliverables
) VALUES (
  $FEATURE_ID, '$agent_name', '$agent_role',
  '$started', '$completed', $duration,
  $tokens, $prompts,
  $loc, $tests,
  '$task', '$deliverables'
) ON CONFLICT (feature_id, agent_name)
  DO UPDATE SET
    duration_minutes = EXCLUDED.duration_minutes,
    tokens_used = EXCLUDED.tokens_used,
    loc_written = EXCLUDED.loc_written,
    tests_written = EXCLUDED.tests_written,
    completed_at = EXCLUDED.completed_at;
" > /dev/null

        echo "  ✅ $agent_name"
    done

    echo ""
    echo "✅ All metrics committed to database (Feature ID: $FEATURE_ID)"
    echo ""
    read -p "Clean up temporary files? (y/n): " cleanup

    if [ "$cleanup" = "y" ]; then
        rm -f "$METRICS_FILE" "$AGENTS_FILE"
        echo "✅ Temporary files removed"
    else
        echo "📁 Temporary files preserved at:"
        echo "   $METRICS_FILE"
        echo "   $AGENTS_FILE"
    fi
}

# Reset/discard current metrics
reset_metrics() {
    if [ ! -f "$METRICS_FILE" ] && [ ! -f "$AGENTS_FILE" ]; then
        echo "No metrics to reset."
        exit 0
    fi

    echo ""
    echo "Current metrics:"
    show_metrics
    echo ""
    read -p "Discard these metrics? (y/n): " confirm

    if [ "$confirm" = "y" ]; then
        rm -f "$METRICS_FILE" "$AGENTS_FILE"
        echo "✅ Metrics discarded"
    else
        echo "Aborted."
    fi
}

# Main command dispatcher
case "$1" in
    init)
        init_feature "$2"
        ;;
    add-agent)
        add_agent "$2"
        ;;
    show)
        show_metrics
        ;;
    commit)
        commit_metrics
        ;;
    reset)
        reset_metrics
        ;;
    *)
        echo "Usage: $0 {init|add-agent|show|commit|reset} [args]"
        echo ""
        echo "Commands:"
        echo "  init <feature_name>    Start tracking new feature"
        echo "  add-agent <agent_name> Record agent contribution"
        echo "  show                   Display current metrics"
        echo "  commit                 Save to database and cleanup"
        echo "  reset                  Discard current metrics"
        exit 1
        ;;
esac

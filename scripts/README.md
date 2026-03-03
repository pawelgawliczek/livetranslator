# Scripts

## Metrics backfill (`backfill_metrics.py`)

Backfills historical code metrics (LOC, complexity, health scores) from git history into the database.

Runs inside the `metrics_collector` Docker container. Uses `cloc` and `lizard` to analyze the codebase at each commit.

```bash
# Dry run first
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --days 7 --dry-run

# Actually backfill
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --days 7

# Monthly snapshots since project start
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --monthly-since 2024-01-01
```

Takes ~3-5 minutes per date. Idempotent (safe to re-run).

# Metrics Backfill Script

Backfills historical metrics from git history into the database for the Metrics Dashboard.

## Overview

The `backfill_metrics.py` script:
- Finds git commits for target dates
- Creates temporary checkouts of the codebase at each commit
- Runs `cloc` and `lizard` to collect metrics
- Calculates health scores
- Inserts data into the database (idempotent with `ON CONFLICT`)

## Requirements

- Runs inside the `metrics_collector` Docker container (has cloc, lizard, asyncpg installed)
- Requires read-write access to `/opt/stack/livetranslator` (configured in docker-compose.yml)
- Uses `/tmp` for temporary checkouts

## Usage

### Basic Commands

```bash
# Backfill last 7 days (dry run first!)
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --days 7 --dry-run

# Actually backfill last 7 days
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --days 7

# Backfill last 30 days
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --days 30

# Add monthly snapshots since project start
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --monthly-since 2024-01-01

# Combine daily and monthly
docker compose exec metrics_collector python /opt/stack/livetranslator/scripts/backfill_metrics.py --days 30 --monthly-since 2024-01-01
```

### Command-Line Options

- `--days N` - Backfill last N days (default: 0)
- `--monthly-since YYYY-MM-DD` - Add monthly snapshots from date to 30 days ago
- `--dry-run` - Show what would be collected without writing to database

## Output Example

```
Metrics Historical Backfill
==================================================
Target dates: 7 daily + 0 monthly = 7 total
Date range: 2025-10-30 to 2025-11-05

Processing 2025-10-30 (1/7)...
  Commit: abc123d
  LOC: 63,474 (API: 31,784, Web: 28,633, Tests: 3,057)
  Health: 64/100
  Saved to database
  Status: SUCCESS

Processing 2025-10-31 (2/7)...
  Commit: def456e
  LOC: 64,128 (API: 31,890, Web: 29,181, Tests: 3,057)
  Health: 65/100
  Saved to database
  Status: SUCCESS

...

==================================================
Summary
==================================================
Processed: 7 dates
Success: 7
Failed: 0

Duration: 20.5 minutes

Backfill complete! Database contains 7 historical snapshots.
```

## Performance

- ~3-5 minutes per date (depends on codebase size)
- 7 days: ~20-35 minutes
- 30 days: ~1.5-2.5 hours
- Use `--dry-run` first to estimate time

## Verification

Check database after backfill:

```bash
PGPASSWORD=${POSTGRES_PASSWORD} docker compose exec -T postgres psql -U lt_user -d livetranslator \
  -c "SELECT date, health_score, total_loc FROM metrics_snapshots ORDER BY date DESC LIMIT 10;"
```

## How It Works

1. **Generate target dates** - Based on --days and --monthly-since arguments
2. **Find commits** - Uses `git log --before="YYYY-MM-DD"` to find closest commit
3. **Create temp checkout** - Clones repo to `/tmp/metrics_backfill_*` and checks out commit
4. **Collect metrics** - Runs cloc (LOC) and lizard (complexity) on temp checkout
5. **Calculate health score** - Based on test pass rate, complexity, and test ratio
6. **Save to database** - Uses `ON CONFLICT` for idempotency (safe to re-run)
7. **Cleanup** - Removes temp directory

## Troubleshooting

### "No commit found"

No git commit exists for that date. Skip or choose a different date range.

### "Failed to create temp checkout"

- Check `/tmp` has space (needs ~200MB per checkout)
- Verify git is installed in container

### "Failed to save to database"

- Check POSTGRES_DSN environment variable
- Verify database schema is up-to-date (run migrations)

### Script is slow

- Normal: ~3-5 minutes per date due to cloc/lizard analysis
- Run with `--days 1 --dry-run` first to test
- Consider backfilling only important dates (monthly snapshots)

## Safety

- **Idempotent**: Safe to re-run (uses `ON CONFLICT DO UPDATE`)
- **Read-only**: Original codebase is never modified
- **Isolated**: Uses temporary directories for checkouts
- **Atomic**: Each date is processed independently

## Integration with Metrics Dashboard

Backfilled data appears immediately in the Metrics Dashboard:
- `/admin/metrics` - View trends over time
- Health score, LOC, complexity trends
- Compare current vs historical metrics

## Future Improvements

- Parallel processing for multiple dates
- Resume from last successful date
- Export/import metrics for backup
- Incremental backfill (only missing dates)

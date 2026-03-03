#!/usr/bin/env python3
"""
Metrics Historical Backfill Script

Backfills historical metrics from git history into the database.
Uses the same collection logic as the metrics collector service.

Run inside metrics_collector container:
    docker compose exec metrics_collector python /codebase/scripts/backfill_metrics.py --days 7 --dry-run

Usage:
    python scripts/backfill_metrics.py --days 30
    python scripts/backfill_metrics.py --monthly-since 2024-01-01
    python scripts/backfill_metrics.py --days 30 --monthly-since 2024-01-01 --dry-run
"""

import argparse
import asyncio
import asyncpg
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# Detect if running in container or on host
if os.path.exists('/app/collect_metrics.py'):
    # Running in metrics_collector container
    sys.path.insert(0, '/app')
    CODEBASE_PATH = os.getenv('CODEBASE_PATH', '/opt/stack/livetranslator')
else:
    # Running on host (for development)
    sys.path.insert(0, str(Path(__file__).parent.parent / 'docker' / 'metrics_collector'))
    CODEBASE_PATH = str(Path(__file__).parent.parent)

# Override paths in collect_metrics module
import collect_metrics
collect_metrics.CODEBASE_PATH = CODEBASE_PATH
collect_metrics.CRITICAL_PATHS_FILE = os.path.join(CODEBASE_PATH, 'api/config/critical_paths.json')

# Import collection functions from the collector
from collect_metrics import (
    collect_cloc_metrics,
    collect_complexity_metrics,
    collect_test_metrics,
    calculate_health_score,
    load_critical_paths,
    POSTGRES_DSN
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


def configure_git_safe_directory():
    """Configure git to trust the codebase directory (needed in container)"""
    try:
        # Add both the directory and .git subdirectory
        for path in [CODEBASE_PATH, f"{CODEBASE_PATH}/.git"]:
            subprocess.run(
                ['git', 'config', '--global', '--add', 'safe.directory', path],
                capture_output=True,
                check=False
            )
    except Exception as e:
        logger.warning(f"Failed to configure git safe.directory: {e}")


def get_git_commit_for_date(target_date: date) -> Optional[str]:
    """
    Find git commit closest to target date.
    Returns commit hash or None if no commit found.
    """
    try:
        # Format date for git (YYYY-MM-DD 23:59:59 to get end of day)
        date_str = f"{target_date.strftime('%Y-%m-%d')} 23:59:59"

        result = subprocess.run(
            ['git', 'log', f'--before={date_str}', '--max-count=1', '--format=%H'],
            cwd=CODEBASE_PATH,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0 or not result.stdout.strip():
            return None

        return result.stdout.strip()

    except Exception as e:
        logger.error(f"Failed to get commit for {target_date}: {e}")
        return None


def get_current_branch() -> str:
    """Get current git branch name"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=CODEBASE_PATH,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        logger.error(f"Failed to get current branch: {e}")
        return "main"


def create_temp_checkout(commit_hash: str) -> Optional[str]:
    """
    Create a temporary checkout of a commit.
    Uses /tmp for writable space when main codebase is read-only.
    Returns the temporary directory path or None on failure.
    """
    try:
        import tempfile
        import shutil

        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='metrics_backfill_')

        # Clone the repo to temp directory (local clone is fast)
        result = subprocess.run(
            ['git', 'clone', '--shared', '--no-checkout', CODEBASE_PATH, temp_dir],
            capture_output=True,
            text=True,
            check=False,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(f"Failed to clone repo: {result.stderr}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        # Checkout the specific commit
        result = subprocess.run(
            ['git', 'checkout', commit_hash],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=30
        )

        if result.returncode != 0:
            logger.error(f"Failed to checkout commit in temp dir: {result.stderr}")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

        return temp_dir

    except Exception as e:
        logger.error(f"Failed to create temp checkout: {e}")
        return None


def cleanup_temp_checkout(temp_dir: str):
    """Remove temporary checkout directory"""
    try:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception as e:
        logger.warning(f"Failed to remove temp directory {temp_dir}: {e}")


async def save_metrics_to_db(
    snapshot_date: date,
    loc_metrics: Dict[str, Any],
    complexity_metrics: Dict[str, Any],
    test_metrics: Dict[str, Any],
    pool: asyncpg.Pool,
    dry_run: bool = False
) -> bool:
    """
    Save collected metrics to database (idempotent).
    Returns True on success, False on failure.
    """
    try:
        # Calculate derived metrics
        test_ratio = loc_metrics['test_loc'] / loc_metrics['total_loc'] if loc_metrics['total_loc'] > 0 else 0

        # Calculate average complexity across all files
        if complexity_metrics:
            total_avg_ccn = sum(m['avg_ccn'] for m in complexity_metrics.values())
            avg_complexity = round(total_avg_ccn / len(complexity_metrics), 2) if complexity_metrics else 0
        else:
            avg_complexity = 0

        # Calculate health score
        health_score = calculate_health_score(
            test_pass_rate=test_metrics['test_pass_rate'],
            avg_complexity=avg_complexity,
            test_ratio=test_ratio
        )

        if dry_run:
            logger.info(f"  [DRY RUN] Would save: health={health_score}, LOC={loc_metrics['total_loc']}, complexity={avg_complexity}")
            return True

        async with pool.acquire() as conn:
            # Insert metrics snapshot (idempotent with ON CONFLICT)
            await conn.execute("""
                INSERT INTO metrics_snapshots (
                    date, total_loc, api_loc, web_loc, test_loc,
                    test_pass_rate, test_count, avg_complexity, health_score
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (date)
                DO UPDATE SET
                    total_loc = EXCLUDED.total_loc,
                    api_loc = EXCLUDED.api_loc,
                    web_loc = EXCLUDED.web_loc,
                    test_loc = EXCLUDED.test_loc,
                    test_pass_rate = EXCLUDED.test_pass_rate,
                    test_count = EXCLUDED.test_count,
                    avg_complexity = EXCLUDED.avg_complexity,
                    health_score = EXCLUDED.health_score,
                    created_at = NOW()
            """,
                snapshot_date,
                loc_metrics.get('total_loc', 0),
                loc_metrics.get('api_loc', 0),
                loc_metrics.get('web_loc', 0),
                loc_metrics.get('test_loc', 0),
                test_metrics['test_pass_rate'],
                test_metrics['test_count'],
                avg_complexity,
                health_score
            )

            # Insert complexity snapshots (batch)
            if complexity_metrics:
                complexity_rows = []
                for file_path, metrics in complexity_metrics.items():
                    complexity_rows.append((
                        snapshot_date,
                        file_path,
                        metrics['avg_ccn'],
                        metrics['max_ccn'],
                        metrics['total_loc'],
                        metrics['function_count'],
                        metrics['is_critical_path']
                    ))

                # Batch insert with ON CONFLICT
                await conn.executemany("""
                    INSERT INTO complexity_snapshots (
                        date, file_path, avg_ccn, max_ccn, total_loc, function_count, is_critical_path
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (date, file_path)
                    DO UPDATE SET
                        avg_ccn = EXCLUDED.avg_ccn,
                        max_ccn = EXCLUDED.max_ccn,
                        total_loc = EXCLUDED.total_loc,
                        function_count = EXCLUDED.function_count,
                        is_critical_path = EXCLUDED.is_critical_path,
                        created_at = NOW()
                """, complexity_rows)

                # Insert function complexity (for files with functions)
                for file_path, metrics in complexity_metrics.items():
                    if not metrics['functions']:
                        continue

                    # Get snapshot_id for this file
                    snapshot_id = await conn.fetchval("""
                        SELECT id FROM complexity_snapshots
                        WHERE date = $1 AND file_path = $2
                    """, snapshot_date, file_path)

                    if snapshot_id:
                        # Delete old function records
                        await conn.execute("""
                            DELETE FROM function_complexity WHERE snapshot_id = $1
                        """, snapshot_id)

                        # Insert new function records
                        function_rows = [
                            (snapshot_id, f['name'], f['ccn'], f['loc'], f['parameter_count'])
                            for f in metrics['functions']
                        ]

                        await conn.executemany("""
                            INSERT INTO function_complexity (
                                snapshot_id, function_name, ccn, loc, parameter_count
                            )
                            VALUES ($1, $2, $3, $4, $5)
                        """, function_rows)

        logger.info(f"  Health: {health_score}/100")
        return True

    except Exception as e:
        logger.error(f"  Failed to save to database: {e}")
        return False


async def process_date(
    target_date: date,
    critical_paths: List[str],
    pool: asyncpg.Pool,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Process a single date: find commit, create temp checkout, collect metrics, save.
    Returns dict with status and metrics.
    """
    result = {
        'date': target_date,
        'success': False,
        'commit': None,
        'error': None,
        'metrics': None
    }

    temp_dir = None

    try:
        # Find commit for this date
        commit = get_git_commit_for_date(target_date)
        if not commit:
            result['error'] = 'no_commit'
            logger.warning(f"  No commit found")
            return result

        result['commit'] = commit[:7]
        logger.info(f"  Commit: {commit[:7]}")

        # Create temporary checkout
        temp_dir = create_temp_checkout(commit)
        if not temp_dir:
            result['error'] = 'checkout_failed'
            return result

        # Temporarily override CODEBASE_PATH in collect_metrics module
        original_codebase_path = collect_metrics.CODEBASE_PATH
        collect_metrics.CODEBASE_PATH = temp_dir

        try:
            # Collect metrics from temp directory
            loc_metrics = await collect_cloc_metrics()
            if not loc_metrics:
                result['error'] = 'cloc_failed'
                return result

            complexity_metrics = await collect_complexity_metrics(critical_paths)
            if not complexity_metrics:
                result['error'] = 'lizard_failed'
                return result

            test_metrics = await collect_test_metrics()

            # Save to database
            success = await save_metrics_to_db(
                target_date,
                loc_metrics,
                complexity_metrics,
                test_metrics,
                pool,
                dry_run
            )

            if success:
                result['success'] = True
                result['metrics'] = {
                    'total_loc': loc_metrics['total_loc'],
                    'api_loc': loc_metrics['api_loc'],
                    'web_loc': loc_metrics['web_loc'],
                    'test_loc': loc_metrics['test_loc']
                }
                logger.info(f"  LOC: {loc_metrics['total_loc']:,} (API: {loc_metrics['api_loc']:,}, Web: {loc_metrics['web_loc']:,}, Tests: {loc_metrics['test_loc']:,})")
                if not dry_run:
                    logger.info(f"  Saved to database")
                else:
                    logger.info(f"  [DRY RUN] Would save to database")
            else:
                result['error'] = 'save_failed'

        finally:
            # Restore original CODEBASE_PATH
            collect_metrics.CODEBASE_PATH = original_codebase_path

    except Exception as e:
        logger.error(f"  Unexpected error: {e}")
        result['error'] = str(e)

    finally:
        # Always cleanup temp directory
        if temp_dir:
            cleanup_temp_checkout(temp_dir)

    return result


def generate_target_dates(days: int, monthly_since: Optional[str]) -> List[date]:
    """
    Generate list of target dates to backfill.
    Returns sorted list (oldest first).
    """
    today = date.today()
    target_dates = set()

    # Add daily dates
    if days > 0:
        for i in range(1, days + 1):
            target_dates.add(today - timedelta(days=i))

    # Add monthly dates (first of each month)
    if monthly_since:
        try:
            start = datetime.strptime(monthly_since, "%Y-%m-%d").date()
            cutoff = today - timedelta(days=30)  # Don't add monthly dates for last 30 days

            current = start.replace(day=1)
            while current < cutoff:
                target_dates.add(current)
                # Move to first of next month
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)

        except ValueError as e:
            logger.error(f"Invalid date format for --monthly-since: {monthly_since} (use YYYY-MM-DD)")
            sys.exit(1)

    # Sort oldest first
    return sorted(target_dates)


async def main():
    parser = argparse.ArgumentParser(
        description='Backfill historical metrics from git history',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --days 30
  %(prog)s --monthly-since 2024-01-01
  %(prog)s --days 30 --monthly-since 2024-01-01
  %(prog)s --days 7 --dry-run
        """
    )
    parser.add_argument('--days', type=int, default=0,
                       help='Backfill last N days (default: 0)')
    parser.add_argument('--monthly-since', type=str,
                       help='Add monthly snapshots from YYYY-MM-DD to 30 days ago')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be collected without writing to database')

    args = parser.parse_args()

    # Validate arguments
    if args.days == 0 and not args.monthly_since:
        parser.error('Must specify --days or --monthly-since (or both)')

    # Generate target dates
    target_dates = generate_target_dates(args.days, args.monthly_since)

    if not target_dates:
        logger.error("No target dates generated")
        sys.exit(1)

    # Print header
    print("\nMetrics Historical Backfill")
    print("=" * 50)

    daily_count = args.days if args.days > 0 else 0
    monthly_count = len(target_dates) - daily_count

    if args.dry_run:
        print("[DRY RUN MODE - No database writes]")

    print(f"Target dates: {daily_count} daily + {monthly_count} monthly = {len(target_dates)} total")
    print(f"Date range: {target_dates[0]} to {target_dates[-1]}")
    print()

    # Configure git to trust codebase directory (needed in container)
    configure_git_safe_directory()

    # Load critical paths
    critical_paths = await load_critical_paths()
    logger.info(f"Loaded {len(critical_paths)} critical paths")

    # Create database connection pool
    pool = None
    if not args.dry_run:
        try:
            pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=2)
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            sys.exit(1)

    # Process each date
    start_time = datetime.now()
    results = []

    try:
        for i, target_date in enumerate(target_dates, 1):
            print(f"\nProcessing {target_date} ({i}/{len(target_dates)})...")

            result = await process_date(
                target_date,
                critical_paths,
                pool,
                args.dry_run
            )
            results.append(result)

            if result['success']:
                print(f"  Status: SUCCESS")
            else:
                error_msg = result['error'] or 'unknown'
                print(f"  Status: FAILED ({error_msg})")

    finally:
        # Close database pool
        if pool:
            await pool.close()

    # Print summary
    duration = datetime.now() - start_time
    success_count = sum(1 for r in results if r['success'])
    error_counts = {}
    for r in results:
        if not r['success'] and r['error']:
            error_counts[r['error']] = error_counts.get(r['error'], 0) + 1

    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"Processed: {len(results)} dates")
    print(f"Success: {success_count}")
    print(f"Failed: {len(results) - success_count}")

    if error_counts:
        print("\nFailure breakdown:")
        for error, count in sorted(error_counts.items()):
            print(f"  {error}: {count}")

    print(f"\nDuration: {duration.total_seconds() / 60:.1f} minutes")

    if args.dry_run:
        print("\nThis was a dry run. No data was written to the database.")
    else:
        print(f"\nBackfill complete! Database contains {success_count} historical snapshots.")

    # Exit with error code if any failures
    sys.exit(0 if success_count == len(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Metrics Collection Script

Collects codebase metrics (LOC, complexity, test results) and stores in database.
Run daily at 02:00 UTC via scheduler.py
"""

import asyncio
import asyncpg
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Configuration
POSTGRES_DSN = os.getenv('POSTGRES_DSN', 'postgresql://lt_user:${POSTGRES_PASSWORD}@postgres:5432/livetranslator')
CODEBASE_PATH = os.getenv('CODEBASE_PATH', '/opt/stack/livetranslator')
CRITICAL_PATHS_FILE = os.getenv('CRITICAL_PATHS_FILE', '/opt/stack/livetranslator/api/config/critical_paths.json')


async def load_critical_paths() -> List[str]:
    """Load critical paths from JSON config"""
    try:
        with open(CRITICAL_PATHS_FILE, 'r') as f:
            config = json.load(f)
            return config.get('critical_paths', [])
    except Exception as e:
        logger.error(f"Failed to load critical paths: {e}")
        return []


async def collect_cloc_metrics() -> Dict[str, Any]:
    """
    Run cloc on codebase and parse output.
    Returns LOC counts by directory.
    """
    logger.info("Running cloc for LOC metrics...")

    try:
        # Run cloc with JSON output (remove --quiet, it causes multi-line JSON issues)
        result = subprocess.run(
            ['cloc', 'api/', 'web/src/', 'tests/', '--json'],
            cwd=CODEBASE_PATH,
            capture_output=True,
            text=True,
            timeout=120  # 2-minute timeout
        )

        if result.returncode != 0:
            logger.error(f"cloc failed: {result.stderr}")
            return {}

        # Extract JSON from output (cloc sometimes adds text before/after JSON)
        stdout = result.stdout.strip()

        # Find the JSON object (starts with { and ends with })
        json_start = stdout.find('{')
        json_end = stdout.rfind('}') + 1

        if json_start == -1 or json_end == 0:
            logger.error("No JSON found in cloc output")
            return {}

        json_str = stdout[json_start:json_end]
        data = json.loads(json_str)

        # Extract totals
        total_loc = data.get('SUM', {}).get('code', 0)

        # Parse per-directory (approximate from cloc output structure)
        api_loc = 0
        web_loc = 0
        test_loc = 0

        # Run cloc again per directory for accurate counts
        for directory, var_name in [('api/', 'api_loc'), ('web/src/', 'web_loc'), ('tests/', 'test_loc')]:
            dir_result = subprocess.run(
                ['cloc', directory, '--json'],
                cwd=CODEBASE_PATH,
                capture_output=True,
                text=True,
                timeout=60
            )
            if dir_result.returncode == 0:
                # Extract JSON from output
                dir_stdout = dir_result.stdout.strip()
                dir_json_start = dir_stdout.find('{')
                dir_json_end = dir_stdout.rfind('}') + 1
                if dir_json_start != -1 and dir_json_end > 0:
                    dir_json_str = dir_stdout[dir_json_start:dir_json_end]
                    dir_data = json.loads(dir_json_str)
                    if var_name == 'api_loc':
                        api_loc = dir_data.get('SUM', {}).get('code', 0)
                    elif var_name == 'web_loc':
                        web_loc = dir_data.get('SUM', {}).get('code', 0)
                    elif var_name == 'test_loc':
                        test_loc = dir_data.get('SUM', {}).get('code', 0)

        logger.info(f"LOC: Total={total_loc}, API={api_loc}, Web={web_loc}, Test={test_loc}")

        return {
            'total_loc': total_loc,
            'api_loc': api_loc,
            'web_loc': web_loc,
            'test_loc': test_loc
        }

    except subprocess.TimeoutExpired:
        logger.error("cloc timed out after 2 minutes")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"cloc output invalid JSON: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in cloc collection: {e}", exc_info=True)
        return {}


async def collect_complexity_metrics(critical_paths: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Run lizard on codebase and parse complexity metrics.
    Returns per-file complexity data.
    """
    logger.info("Running lizard for complexity metrics...")

    try:
        # Run lizard with CSV output (easier to parse)
        result = subprocess.run(
            ['lizard', '-l', 'python', '-l', 'javascript', '--csv', 'api/', 'web/src/'],
            cwd=CODEBASE_PATH,
            capture_output=True,
            text=True,
            timeout=300  # 5-minute timeout
        )

        if result.returncode != 0:
            logger.error(f"lizard failed: {result.stderr}")
            return {}

        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:  # Header + at least 1 data row
            logger.warning("lizard returned no data")
            return {}

        # Parse CSV (format: NLOC, CCN, token, PARAM, length, location, file, function, long_name, start, end)
        header = lines[0].split(',')

        file_metrics = {}  # file_path -> {functions: [...], metrics: {...}}

        for line in lines[1:]:
            if not line.strip():
                continue

            parts = line.split(',')
            if len(parts) < 7:
                continue

            try:
                nloc = int(parts[0])
                ccn = int(parts[1])
                param_count = int(parts[3]) if len(parts) > 3 else 0
                file_path = parts[6].strip()
                function_name = parts[7].strip() if len(parts) > 7 else '<unknown>'

                # Normalize file path (remove codebase prefix)
                if file_path.startswith(CODEBASE_PATH):
                    file_path = file_path[len(CODEBASE_PATH):].lstrip('/')

                if file_path not in file_metrics:
                    file_metrics[file_path] = {
                        'functions': [],
                        'total_loc': 0,
                        'function_count': 0,
                        'avg_ccn': 0,
                        'max_ccn': 0,
                        'is_critical_path': file_path in critical_paths
                    }

                file_metrics[file_path]['functions'].append({
                    'name': function_name,
                    'ccn': ccn,
                    'loc': nloc,
                    'parameter_count': param_count
                })

                file_metrics[file_path]['total_loc'] += nloc
                file_metrics[file_path]['function_count'] += 1
                file_metrics[file_path]['max_ccn'] = max(file_metrics[file_path]['max_ccn'], ccn)

            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to parse lizard line: {line[:100]} - {e}")
                continue

        # Calculate average CCN per file
        for file_path, metrics in file_metrics.items():
            if metrics['function_count'] > 0:
                total_ccn = sum(f['ccn'] for f in metrics['functions'])
                metrics['avg_ccn'] = round(total_ccn / metrics['function_count'], 2)

        logger.info(f"Analyzed {len(file_metrics)} files")

        return file_metrics

    except subprocess.TimeoutExpired:
        logger.error("lizard timed out after 5 minutes")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in lizard collection: {e}", exc_info=True)
        return {}


async def collect_test_metrics() -> Dict[str, Any]:
    """
    Collect test pass rate and count.
    NOTE: For MVP, we'll return mock data since running pytest in collector is expensive.
    In production, parse pytest JSON output from CI/CD.
    """
    logger.info("Collecting test metrics (mock data for MVP)...")

    # TODO: In Phase 2, parse actual pytest output or query CI/CD
    return {
        'test_pass_rate': 98.5,
        'test_count': 733
    }


def calculate_health_score(
    test_pass_rate: float,
    avg_complexity: float,
    test_ratio: float
) -> int:
    """
    Calculate health score (0-100) from sub-metrics.

    Formula:
    - Test pass rate: 40% weight
    - Complexity: 30% weight (lower is better, inverted scale)
    - Test ratio: 30% weight (test_loc / total_loc, 1:1 is ideal)
    """
    # Test pass rate score (already 0-100)
    test_score = test_pass_rate * 0.4

    # Complexity score (inverted: lower complexity = higher score)
    # Assume 0 complexity = 100 score, 15+ complexity = 0 score
    complexity_score = max(0, 100 - (avg_complexity / 15 * 100)) * 0.3

    # Test ratio score (1:1 ratio = 100, <0.5 = 0)
    ratio_score = min(100, test_ratio * 100) * 0.3

    health_score = test_score + complexity_score + ratio_score

    return int(round(health_score))


async def save_metrics_to_db(
    snapshot_date: date,
    loc_metrics: Dict[str, Any],
    complexity_metrics: Dict[str, List[Dict[str, Any]]],
    test_metrics: Dict[str, Any]
):
    """Save collected metrics to database (idempotent)"""
    logger.info("Saving metrics to database...")

    try:
        conn = await asyncpg.connect(POSTGRES_DSN)

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

            logger.info(f"Saved metrics snapshot: health_score={health_score}")

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

                logger.info(f"Saved {len(complexity_rows)} complexity snapshots")

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
                        # Delete old function records (cascade will handle this, but explicit is better)
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

                logger.info(f"Saved function-level complexity data")

        finally:
            await conn.close()

    except Exception as e:
        logger.error(f"Failed to save metrics to database: {e}", exc_info=True)
        raise


async def run_collection():
    """Main collection workflow"""
    logger.info("=== Starting metrics collection ===")
    start_time = datetime.now()

    try:
        snapshot_date = date.today()

        # Load critical paths
        critical_paths = await load_critical_paths()
        logger.info(f"Loaded {len(critical_paths)} critical paths")

        # Collect metrics (parallel where possible)
        loc_metrics = await collect_cloc_metrics()
        complexity_metrics = await collect_complexity_metrics(critical_paths)
        test_metrics = await collect_test_metrics()

        # Save to database
        if loc_metrics and complexity_metrics:
            await save_metrics_to_db(
                snapshot_date,
                loc_metrics,
                complexity_metrics,
                test_metrics
            )

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"=== Metrics collection completed in {duration:.1f}s ===")
        else:
            logger.error("Metrics collection incomplete, skipping database save")

    except Exception as e:
        logger.error(f"Metrics collection failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_collection())

#!/usr/bin/env python3
"""
Metrics Collection Scheduler

Runs metrics collection daily at 02:00 UTC using event loop (NOT cron).
Includes lock mechanism to prevent concurrent runs.
"""

import asyncio
import logging
import os
import sys
import redis
from datetime import datetime, timedelta
from collect_metrics import run_collection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/5')
COLLECTION_HOUR = int(os.getenv('COLLECTION_HOUR', '2'))  # UTC hour (default 02:00)
LOCK_TTL = 600  # 10 minutes (max collection time)


def get_redis_client():
    """Create Redis client"""
    return redis.from_url(REDIS_URL, decode_responses=True)


async def run_with_lock():
    """Run collection with distributed lock to prevent concurrent runs"""
    redis_client = get_redis_client()
    lock_key = "metrics:collection:lock"

    logger.info("Attempting to acquire collection lock...")

    # Try to acquire lock (NX = only set if not exists, EX = expiry in seconds)
    acquired = redis_client.set(lock_key, "locked", nx=True, ex=LOCK_TTL)

    if not acquired:
        logger.warning("Metrics collection already running (lock held), skipping")
        return

    logger.info("Lock acquired, starting collection")

    try:
        await run_collection()
    except Exception as e:
        logger.error(f"Collection failed: {e}", exc_info=True)
    finally:
        # Always release lock
        redis_client.delete(lock_key)
        logger.info("Lock released")


async def schedule_daily_collection(target_hour: int = 2):
    """
    Run collection daily at target_hour (UTC) using event loop.

    This approach is superior to cron in Docker:
    - Proper logging to Docker logs
    - Environment variables work correctly
    - Graceful shutdown handling
    - No cron dependency
    """
    logger.info(f"Scheduler started, will run daily at {target_hour:02d}:00 UTC")

    # Run immediately on startup (for testing)
    logger.info("Running initial collection on startup...")
    await run_with_lock()

    while True:
        now = datetime.utcnow()
        target_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)

        # If past today's target, schedule for tomorrow
        if now >= target_time:
            target_time = target_time + timedelta(days=1)

        # Calculate sleep duration
        sleep_seconds = (target_time - now).total_seconds()
        logger.info(f"Next collection in {sleep_seconds/3600:.1f} hours at {target_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        # Sleep until target time
        await asyncio.sleep(sleep_seconds)

        # Run collection
        await run_with_lock()

        # Sleep 5 minutes to avoid double-run (in case of clock drift)
        await asyncio.sleep(300)


if __name__ == "__main__":
    try:
        asyncio.run(schedule_daily_collection(target_hour=COLLECTION_HOUR))
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler crashed: {e}", exc_info=True)
        sys.exit(1)

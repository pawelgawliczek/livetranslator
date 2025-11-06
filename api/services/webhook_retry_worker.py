"""
Webhook Retry Worker - US-011

Processes failed webhook events with exponential backoff:
- Retry schedule: 1min, 5min, 30min, 2hr, 24hr
- Give up after: 7 days (payments) or 27 hours (others)
- Alert admin after 4 failures
"""
import asyncio
import os
import logging
import json
from datetime import datetime, timedelta
import asyncpg

logger = logging.getLogger(__name__)

# Retry schedule (exponential backoff)
RETRY_DELAYS = [
    timedelta(minutes=1),   # Retry 1
    timedelta(minutes=5),   # Retry 2
    timedelta(minutes=30),  # Retry 3
    timedelta(hours=2),     # Retry 4
    timedelta(hours=24),    # Retry 5
]

# Critical events that need longer retry window
CRITICAL_EVENTS = {
    'checkout.session.completed',
    'customer.subscription.created',
    'invoice.payment_succeeded'
}

CRITICAL_MAX_AGE = timedelta(days=7)  # 7 days for critical events
NORMAL_MAX_AGE = timedelta(hours=27)  # 27 hours for others


async def get_db_pool():
    """Get async database pool."""
    dsn = os.getenv('POSTGRES_DSN')
    if not dsn:
        user = os.getenv('POSTGRES_USER', 'lt_user')
        password = os.getenv('POSTGRES_PASSWORD', '')
        host = os.getenv('POSTGRES_HOST', 'postgres')
        port = os.getenv('POSTGRES_PORT', '5432')
        db = os.getenv('POSTGRES_DB', 'livetranslator')
        dsn = f'postgresql://{user}:{password}@{host}:{port}/{db}'

    return await asyncpg.create_pool(dsn, min_size=2, max_size=5)


async def send_failure_alert(webhook_id: int, event_id: str, event_type: str, error: str):
    """
    Send alert to admin about persistent webhook failure.

    TODO: Implement email notification (US-012)
    For now, just log prominently.
    """
    logger.error(
        f"🚨 WEBHOOK RETRY EXHAUSTED 🚨\n"
        f"  Webhook ID: {webhook_id}\n"
        f"  Event ID: {event_id}\n"
        f"  Event Type: {event_type}\n"
        f"  Error: {error[:200]}\n"
        f"  Action Required: Manual intervention needed"
    )

    # TODO US-012: Send email to admin
    # await send_email(
    #     to=ADMIN_EMAIL,
    #     subject=f"Webhook Retry Failed: {event_type}",
    #     body=f"Event {event_id} failed after 5 retries. Manual review required."
    # )


async def process_webhook_event(pool, webhook_id: int, payload: dict):
    """
    Replay webhook event processing.

    This is the same logic as the main webhook handler, but:
    - Skips signature verification (already verified)
    - Uses stored payload instead of request body
    """
    from api.routers.payments import (
        handle_checkout_completed,
        handle_subscription_updated,
        handle_payment_failed,
        handle_subscription_deleted
    )
    from api.db import SessionLocal

    event_type = payload.get('type')
    event_data = payload.get('data', {}).get('object', {})

    db = SessionLocal()
    try:
        if event_type == 'checkout.session.completed':
            await handle_checkout_completed(event_data, db)
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(event_data, db)
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(event_data, db)
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_deleted(event_data, db)
        else:
            logger.warning(f"Unknown event type for retry: {event_type}")

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Webhook replay failed: {e}")
        raise
    finally:
        db.close()


async def retry_worker_loop():
    """
    Main retry worker loop.

    Runs every 30 seconds to check for webhooks needing retry.
    """
    pool = await get_db_pool()
    logger.info("Webhook retry worker started")

    while True:
        try:
            async with pool.acquire() as conn:
                # Find webhooks ready for retry
                webhooks = await conn.fetch("""
                    SELECT id, event_id, event_type, payload, retry_count, created_at, error_message
                    FROM webhook_events
                    WHERE status = 'failed'
                      AND next_retry_at <= NOW()
                    ORDER BY next_retry_at ASC
                    LIMIT 20
                """)

                for webhook in webhooks:
                    webhook_id = webhook['id']
                    event_id = webhook['event_id']
                    event_type = webhook['event_type']
                    payload = webhook['payload']
                    retry_count = webhook['retry_count']
                    created_at = webhook['created_at']

                    # Check if webhook is too old
                    age = datetime.utcnow() - created_at
                    is_critical = event_type in CRITICAL_EVENTS
                    max_age = CRITICAL_MAX_AGE if is_critical else NORMAL_MAX_AGE

                    if age > max_age:
                        # Give up - too old
                        await conn.execute("""
                            UPDATE webhook_events
                            SET status = 'abandoned',
                                error_message = CONCAT(error_message, ' [Abandoned: max age exceeded]')
                            WHERE id = $1
                        """, webhook_id)

                        await send_failure_alert(
                            webhook_id, event_id, event_type,
                            f"Abandoned after {age.days} days (max: {max_age.days})"
                        )
                        continue

                    # Check if max retries exceeded
                    if retry_count >= len(RETRY_DELAYS):
                        # Give up - too many retries
                        await conn.execute("""
                            UPDATE webhook_events
                            SET status = 'abandoned',
                                error_message = CONCAT(error_message, ' [Abandoned: max retries exceeded]')
                            WHERE id = $1
                        """, webhook_id)

                        await send_failure_alert(
                            webhook_id, event_id, event_type,
                            f"Failed after {retry_count} retries"
                        )
                        continue

                    # Attempt retry
                    logger.info(f"Retrying webhook {event_id} (attempt {retry_count + 1})")

                    try:
                        # Mark as processing
                        await conn.execute("""
                            UPDATE webhook_events
                            SET status = 'processing',
                                last_retry_at = NOW()
                            WHERE id = $1
                        """, webhook_id)

                        # Process webhook
                        await process_webhook_event(pool, webhook_id, payload)

                        # Success - mark completed
                        await conn.execute("""
                            UPDATE webhook_events
                            SET status = 'completed',
                                completed_at = NOW()
                            WHERE id = $1
                        """, webhook_id)

                        logger.info(f"Webhook retry succeeded: {event_id}")

                    except Exception as e:
                        # Failure - schedule next retry
                        next_delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
                        next_retry = datetime.utcnow() + next_delay

                        await conn.execute("""
                            UPDATE webhook_events
                            SET status = 'failed',
                                retry_count = retry_count + 1,
                                next_retry_at = $1,
                                error_message = $2
                            WHERE id = $3
                        """, next_retry, str(e)[:500], webhook_id)

                        logger.warning(
                            f"Webhook retry failed: {event_id}, "
                            f"retry {retry_count + 1}, next attempt in {next_delay}"
                        )

                        # Alert after 4 failures
                        if retry_count >= 3:
                            await send_failure_alert(webhook_id, event_id, event_type, str(e))

        except Exception as e:
            logger.error(f"Retry worker error: {e}")

        # Sleep 30 seconds before next check
        await asyncio.sleep(30)


async def cleanup_old_webhooks():
    """
    Clean up completed webhooks older than 90 days (GDPR compliance).
    Runs daily at 2am.
    """
    pool = await get_db_pool()

    while True:
        try:
            # Wait until 2am
            now = datetime.utcnow()
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)

            sleep_seconds = (next_run - now).total_seconds()
            await asyncio.sleep(sleep_seconds)

            # Delete completed webhooks older than 90 days
            async with pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM webhook_events
                    WHERE status = 'completed'
                      AND completed_at < NOW() - INTERVAL '90 days'
                """)

                logger.info(f"Cleaned up {result.split()[1]} old webhook events")

        except Exception as e:
            logger.error(f"Webhook cleanup error: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour


async def main():
    """Run retry worker and cleanup task."""
    await asyncio.gather(
        retry_worker_loop(),
        cleanup_old_webhooks()
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

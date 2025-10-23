#!/usr/bin/env python3
"""
Room cleanup service - removes rooms where admin has been absent for 30+ minutes
Archives room metadata before deletion to preserve history
"""
import asyncio
import os
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, Table, Column, Integer, String, DateTime, Boolean, ForeignKey, MetaData, text, Numeric, BigInteger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Configuration
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator")
CLEANUP_INTERVAL_SECONDS = int(os.getenv("ROOM_CLEANUP_INTERVAL", "300"))  # Default: 5 minutes
ADMIN_ABSENT_THRESHOLD_MINUTES = int(os.getenv("ADMIN_ABSENT_THRESHOLD", "30"))  # Default: 30 minutes

print(f"[Room Cleanup] Starting...")
print(f"  Interval: {CLEANUP_INTERVAL_SECONDS}s")
print(f"  Threshold: {ADMIN_ABSENT_THRESHOLD_MINUTES} minutes")
print(f"  Database: {POSTGRES_DSN.split('@')[1] if '@' in POSTGRES_DSN else POSTGRES_DSN}")

engine = create_async_engine(POSTGRES_DSN, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Define table metadata (without importing full models)
metadata = MetaData()
rooms_table = Table(
    'rooms',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('code', String(16)),
    Column('owner_id', Integer),
    Column('created_at', DateTime),
    Column('recording', Boolean),
    Column('is_public', Boolean),
    Column('requires_login', Boolean),
    Column('max_participants', Integer),
    Column('admin_left_at', DateTime, nullable=True),
)

room_archive_table = Table(
    'room_archive',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('room_code', String(12)),
    Column('owner_id', Integer),
    Column('created_at', DateTime),
    Column('archived_at', DateTime),
    Column('recording', Boolean),
    Column('is_public', Boolean),
    Column('requires_login', Boolean),
    Column('max_participants', Integer),
    Column('total_participants', Integer),
    Column('total_messages', Integer),
    Column('duration_minutes', Numeric(10, 2)),
    Column('stt_minutes', Numeric(10, 2)),
    Column('stt_cost_usd', Numeric(12, 6)),
    Column('mt_cost_usd', Numeric(12, 6)),
    Column('total_cost_usd', Numeric(12, 6)),
    Column('archive_reason', String(50)),
)

async def archive_room(session, room_id: int, room_code: str, owner_id: int, created_at: datetime,
                       recording: bool, is_public: bool, requires_login: bool, max_participants: int):
    """Archive room metadata before deletion"""
    try:
        # Get aggregated metrics
        # 1. Count participants
        participants_result = await session.execute(
            text("SELECT COUNT(DISTINCT user_id) FROM room_participants WHERE room_id = :room_id AND user_id IS NOT NULL"),
            {"room_id": room_id}
        )
        total_participants = participants_result.scalar() or 0

        # 2. Count messages
        messages_result = await session.execute(
            text("SELECT COUNT(*) FROM segments WHERE room_id = :room_id AND final = true"),
            {"room_id": room_id}
        )
        total_messages = messages_result.scalar() or 0

        # 3. Calculate duration (time from created_at to now)
        duration = datetime.utcnow() - created_at
        duration_minutes = Decimal(duration.total_seconds() / 60)

        # 4. Get cost metrics from room_costs table
        costs_result = await session.execute(
            text("""
                SELECT
                    SUM(CASE WHEN pipeline = 'stt_final' THEN units ELSE 0 END) / 60.0 as stt_minutes,
                    SUM(CASE WHEN pipeline = 'stt_final' THEN amount_usd ELSE 0 END) as stt_cost,
                    SUM(CASE WHEN pipeline = 'mt' THEN amount_usd ELSE 0 END) as mt_cost
                FROM room_costs
                WHERE room_id = :room_code
            """),
            {"room_code": room_code}
        )
        cost_data = costs_result.first()
        stt_minutes = Decimal(cost_data[0] or 0)
        stt_cost = Decimal(cost_data[1] or 0)
        mt_cost = Decimal(cost_data[2] or 0)
        total_cost = stt_cost + mt_cost

        # Insert into room_archive
        from sqlalchemy import insert
        archive_stmt = insert(room_archive_table).values(
            room_code=room_code,
            owner_id=owner_id,
            created_at=created_at,
            archived_at=datetime.utcnow(),
            recording=recording,
            is_public=is_public,
            requires_login=requires_login,
            max_participants=max_participants,
            total_participants=total_participants,
            total_messages=total_messages,
            duration_minutes=duration_minutes,
            stt_minutes=stt_minutes,
            stt_cost_usd=stt_cost,
            mt_cost_usd=mt_cost,
            total_cost_usd=total_cost,
            archive_reason="cleanup"
        )
        await session.execute(archive_stmt)

        print(f"[Room Cleanup]   Archived: {total_participants} participants, {total_messages} messages, "
              f"{float(stt_minutes):.1f} STT min, ${float(total_cost):.4f}")

        return True
    except Exception as e:
        print(f"[Room Cleanup]   ✗ Archive failed: {e}")
        return False

async def mark_stale_zombie_rooms():
    """
    Mark zombie rooms as abandoned by setting admin_left_at to NOW().

    Zombie rooms are rooms where WebSocket disconnect never fired (browser crash, network drop, etc.)
    so admin_left_at was never set. After 24 hours with no activity, we assume the admin has left
    and set admin_left_at = NOW(), giving a 30-minute grace period before deletion.

    Why set admin_left_at to NOW() instead of created_at:
    - Provides 30-minute grace period in case we made a mistake marking the room as abandoned
    - Allows time for admin to rejoin if they return
    - Gives operators time to review/cancel if needed

    This approach:
    1. Uses the same cleanup logic for all rooms (consistent behavior)
    2. Follows the same archive/delete flow (data safety)
    3. Provides safety buffer against false positives (grace period)

    Total time until deletion: 24 hours (detection threshold) + 30 minutes (grace period) = 24.5 hours
    """
    async with AsyncSessionLocal() as session:
        try:
            # Find rooms created > 24 hours ago with no admin_left_at set
            zombie_cutoff = datetime.utcnow() - timedelta(hours=24)

            # Query for zombie rooms
            zombie_stmt = select(
                rooms_table.c.id,
                rooms_table.c.code,
                rooms_table.c.created_at
            ).where(
                rooms_table.c.admin_left_at.is_(None),  # No admin_left_at set
                rooms_table.c.created_at < zombie_cutoff  # Older than 24 hours
            )
            result = await session.execute(zombie_stmt)
            zombie_rooms = result.all()

            if zombie_rooms:
                print(f"[Room Cleanup] Found {len(zombie_rooms)} zombie rooms (no disconnect event, > 24h old)")

                for room in zombie_rooms:
                    age = datetime.utcnow() - room.created_at
                    age_hours = int(age.total_seconds() / 3600)

                    print(f"[Room Cleanup] Marking zombie room {room.code} as abandoned (created {age_hours} hours ago)")

                    # Set admin_left_at to NOW() - gives 30 minute grace period before deletion
                    # This allows time to recover if we made a mistake in marking the room as abandoned
                    from sqlalchemy import update
                    update_stmt = update(rooms_table).where(
                        rooms_table.c.id == room.id
                    ).values(
                        admin_left_at=datetime.utcnow()
                    )
                    await session.execute(update_stmt)
                    print(f"[Room Cleanup]   ✓ Set admin_left_at for {room.code} (will be deleted in 30 minutes)")

                await session.commit()
                print(f"[Room Cleanup] ✓ Marked {len(zombie_rooms)} zombie rooms for cleanup")
            # Removed the "else" to reduce log noise - only log when action is taken

        except Exception as e:
            print(f"[Room Cleanup] ✗ Error during zombie room marking: {e}")
            await session.rollback()


async def cleanup_abandoned_rooms():
    """Archive and delete rooms where admin has been absent for more than the threshold"""
    async with AsyncSessionLocal() as session:
        try:
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(minutes=ADMIN_ABSENT_THRESHOLD_MINUTES)

            # Find rooms where admin left before cutoff time
            stmt = select(
                rooms_table.c.id,
                rooms_table.c.code,
                rooms_table.c.owner_id,
                rooms_table.c.created_at,
                rooms_table.c.recording,
                rooms_table.c.is_public,
                rooms_table.c.requires_login,
                rooms_table.c.max_participants,
                rooms_table.c.admin_left_at
            ).where(
                rooms_table.c.admin_left_at.isnot(None),
                rooms_table.c.admin_left_at < cutoff_time
            )
            result = await session.execute(stmt)
            abandoned_rooms = result.all()

            if abandoned_rooms:
                print(f"[Room Cleanup] Found {len(abandoned_rooms)} abandoned rooms to archive and delete")

                for room in abandoned_rooms:
                    elapsed = datetime.utcnow() - room.admin_left_at
                    elapsed_minutes = int(elapsed.total_seconds() / 60)

                    print(f"[Room Cleanup] Processing room {room.code} (admin absent for {elapsed_minutes} minutes)")

                    # Archive room data before deletion
                    archived = await archive_room(
                        session,
                        room.id,
                        room.code,
                        room.owner_id,
                        room.created_at,
                        room.recording,
                        room.is_public,
                        room.requires_login,
                        room.max_participants
                    )

                    if archived:
                        # Delete the room (CASCADE will handle related records)
                        from sqlalchemy import delete
                        delete_stmt = delete(rooms_table).where(rooms_table.c.id == room.id)
                        await session.execute(delete_stmt)
                        print(f"[Room Cleanup]   ✓ Deleted room {room.code}")
                    else:
                        print(f"[Room Cleanup]   ⚠ Skipped deletion due to archive failure")

                await session.commit()
                print(f"[Room Cleanup] ✓ Completed cleanup of {len(abandoned_rooms)} rooms")
            else:
                print(f"[Room Cleanup] No abandoned rooms found")

        except Exception as e:
            print(f"[Room Cleanup] ✗ Error during cleanup: {e}")
            await session.rollback()

async def cleanup_loop():
    """Run cleanup periodically"""
    while True:
        try:
            # First, mark zombie rooms as abandoned (set admin_left_at)
            # Zombie rooms are > 24h old with no disconnect event
            await mark_stale_zombie_rooms()

            # Then, clean up all abandoned rooms (admin_left_at > 30 minutes ago)
            # This includes both properly disconnected rooms and marked zombies
            await cleanup_abandoned_rooms()
        except Exception as e:
            print(f"[Room Cleanup] ✗ Unexpected error: {e}")

        # Wait for next interval
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(cleanup_loop())

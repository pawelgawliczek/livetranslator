#!/usr/bin/env python3
"""
Room cleanup service - removes rooms where admin has been absent for 30+ minutes
"""
import asyncio
import os
from datetime import datetime, timedelta

from sqlalchemy import select, Table, Column, Integer, String, DateTime, Boolean, ForeignKey, MetaData
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

# Define rooms table metadata (without importing full models)
metadata = MetaData()
rooms_table = Table(
    'rooms',
    metadata,
    Column('id', Integer, primary_key=True),
    Column('code', String(16)),
    Column('owner_id', Integer),
    Column('created_at', DateTime),
    Column('recording', Boolean),
    Column('admin_left_at', DateTime, nullable=True),
)

async def cleanup_abandoned_rooms():
    """Delete rooms where admin has been absent for more than the threshold"""
    async with AsyncSessionLocal() as session:
        try:
            # Calculate cutoff time
            cutoff_time = datetime.utcnow() - timedelta(minutes=ADMIN_ABSENT_THRESHOLD_MINUTES)

            # Find rooms where admin left before cutoff time
            stmt = select(rooms_table.c.id, rooms_table.c.code, rooms_table.c.admin_left_at).where(
                rooms_table.c.admin_left_at.isnot(None),
                rooms_table.c.admin_left_at < cutoff_time
            )
            result = await session.execute(stmt)
            abandoned_rooms = result.all()

            if abandoned_rooms:
                print(f"[Room Cleanup] Found {len(abandoned_rooms)} abandoned rooms to delete")

                for room in abandoned_rooms:
                    elapsed = datetime.utcnow() - room.admin_left_at
                    elapsed_minutes = int(elapsed.total_seconds() / 60)

                    print(f"[Room Cleanup] Deleting room {room.code} (admin absent for {elapsed_minutes} minutes)")

                    # Delete the room (CASCADE will handle related records)
                    from sqlalchemy import delete
                    delete_stmt = delete(rooms_table).where(rooms_table.c.id == room.id)
                    await session.execute(delete_stmt)

                await session.commit()
                print(f"[Room Cleanup] ✓ Deleted {len(abandoned_rooms)} abandoned rooms")
            else:
                print(f"[Room Cleanup] No abandoned rooms found")

        except Exception as e:
            print(f"[Room Cleanup] ✗ Error during cleanup: {e}")
            await session.rollback()

async def cleanup_loop():
    """Run cleanup periodically"""
    while True:
        try:
            await cleanup_abandoned_rooms()
        except Exception as e:
            print(f"[Room Cleanup] ✗ Unexpected error: {e}")

        # Wait for next interval
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)

if __name__ == "__main__":
    asyncio.run(cleanup_loop())

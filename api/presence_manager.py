"""
Presence Manager - Debounced user presence tracking for UI/notifications.

This module handles user presence state with packet-loss resistance and debouncing.
It is SEPARATE from translation routing (which uses active_lang Redis keys).

Key Features:
- 15-second grace period before marking user as "left"
- Automatic reconnection handling (silent if within grace period)
- Broadcasts presence_snapshot events (idempotent, includes full participant list)
- Background cleanup task for expired disconnect timers
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
import structlog
import redis.asyncio as redis

# Configurable constant for grace period before user is marked as "left"
PRESENCE_GRACE_PERIOD_SECONDS = 15


class PresenceManager:
    """
    Manages user presence state with debouncing for packet-loss resistance.

    Redis Data Structures:
    - room:{room_id}:presence_state - Hash mapping user:{user_id} to user data JSON
    - room:{room_id}:disconnect_timer:{user_id} - Timer key with TTL for disconnect grace period

    Event Types Broadcast:
    - presence_snapshot: Complete participant list (sent on connection/initial state)
    - user_joined: New user joined (after confirming they stayed past grace period)
    - user_left: User left (after grace period expired)
    - language_changed: User changed their language preference
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Initialize PresenceManager.

        Args:
            redis_client: Async Redis client instance
        """
        self.redis = redis_client
        self.log = structlog.get_logger("presence")

    async def user_connected(
        self,
        room_id: str,
        user_id: str,
        display_name: str,
        language: str,
        is_guest: bool = False
    ) -> dict:
        """
        Mark user as active in the room.

        If user reconnects within grace period, this cancels the disconnect timer
        and prevents "user left" notification from being sent.

        Args:
            room_id: Room identifier
            user_id: User identifier
            display_name: User's display name
            language: User's preferred language code
            is_guest: Whether user is a guest

        Returns:
            Dict containing presence_snapshot event to broadcast
        """
        presence_key = f"room:{room_id}:presence_state"
        user_key = f"user:{user_id}"

        # Check if user was already in room (reconnection scenario)
        existing_data = await self.redis.hget(presence_key, user_key)
        is_reconnection = False

        if existing_data:
            existing = json.loads(existing_data)
            if existing.get("state") == "disconnecting":
                is_reconnection = True
                self.log.info(
                    "user_reconnected_within_grace_period",
                    room=room_id,
                    user=user_id,
                    display_name=display_name
                )

        # Update or create presence state
        user_data = {
            "display_name": display_name,
            "language": language,
            "is_guest": is_guest,
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat(),
            "state": "active"
        }

        await self.redis.hset(presence_key, user_key, json.dumps(user_data))

        # Cancel any pending disconnect timer
        timer_key = f"room:{room_id}:disconnect_timer:{user_id}"
        await self.redis.delete(timer_key)

        # Build and return presence snapshot
        event_type = "presence_snapshot" if is_reconnection else "user_joined"

        self.log.info(
            "user_connected",
            room=room_id,
            user=user_id,
            display_name=display_name,
            language=language,
            is_reconnection=is_reconnection
        )

        return await self._build_presence_snapshot(room_id, event_type, user_id)

    async def user_disconnected(self, room_id: str, user_id: str) -> None:
        """
        Start disconnect grace period.

        User is marked as "disconnecting" but not removed immediately.
        Actual removal and "user_left" broadcast happens after grace period expires.

        Args:
            room_id: Room identifier
            user_id: User identifier
        """
        presence_key = f"room:{room_id}:presence_state"
        user_key = f"user:{user_id}"

        # Get current user data
        user_data_str = await self.redis.hget(presence_key, user_key)
        if not user_data_str:
            # User not in presence state, nothing to do
            return

        # Mark as disconnecting
        user_data = json.loads(user_data_str)
        user_data["state"] = "disconnecting"
        user_data["disconnect_started"] = datetime.utcnow().isoformat()
        await self.redis.hset(presence_key, user_key, json.dumps(user_data))

        # Schedule removal after grace period
        timer_key = f"room:{room_id}:disconnect_timer:{user_id}"
        await self.redis.setex(timer_key, PRESENCE_GRACE_PERIOD_SECONDS, "1")

        self.log.info(
            "user_disconnect_started",
            room=room_id,
            user=user_id,
            grace_period=PRESENCE_GRACE_PERIOD_SECONDS
        )

    async def user_changed_language(
        self,
        room_id: str,
        user_id: str,
        new_language: str
    ) -> Optional[dict]:
        """
        Update user's language preference.

        Args:
            room_id: Room identifier
            user_id: User identifier
            new_language: New language code

        Returns:
            Dict containing presence_snapshot event with language_changed type,
            or None if user not found
        """
        presence_key = f"room:{room_id}:presence_state"
        user_key = f"user:{user_id}"

        user_data_str = await self.redis.hget(presence_key, user_key)
        if not user_data_str:
            self.log.warning(
                "language_change_user_not_found",
                room=room_id,
                user=user_id
            )
            return None

        user_data = json.loads(user_data_str)
        old_language = user_data.get("language")

        # Update language and last_seen
        user_data["language"] = new_language
        user_data["last_seen"] = datetime.utcnow().isoformat()
        await self.redis.hset(presence_key, user_key, json.dumps(user_data))

        self.log.info(
            "user_language_changed",
            room=room_id,
            user=user_id,
            old_lang=old_language,
            new_lang=new_language
        )

        return await self._build_presence_snapshot(
            room_id,
            "language_changed",
            user_id,
            extra={"old_language": old_language, "new_language": new_language}
        )

    async def get_presence_snapshot(self, room_id: str) -> dict:
        """
        Get current presence state for a room.

        Args:
            room_id: Room identifier

        Returns:
            Dict containing presence_snapshot event
        """
        return await self._build_presence_snapshot(room_id, "presence_snapshot")

    async def _build_presence_snapshot(
        self,
        room_id: str,
        event_type: str,
        triggered_by_user_id: Optional[str] = None,
        extra: Optional[dict] = None
    ) -> dict:
        """
        Build presence snapshot with all active participants.

        Args:
            room_id: Room identifier
            event_type: Type of event (presence_snapshot, user_joined, user_left, language_changed)
            triggered_by_user_id: User ID that triggered this event
            extra: Extra data to include in event

        Returns:
            Dict containing complete presence snapshot event
        """
        presence_key = f"room:{room_id}:presence_state"
        all_users = await self.redis.hgetall(presence_key)

        participants = []
        language_counts = {}

        for user_key, user_data_str in all_users.items():
            try:
                user_data = json.loads(user_data_str)

                # Only include active users (not disconnecting)
                if user_data.get("state") == "active":
                    user_id = user_key.replace("user:", "") if isinstance(user_key, str) else user_key.decode().replace("user:", "")

                    participant = {
                        "user_id": user_id,
                        "display_name": user_data["display_name"],
                        "language": user_data["language"],
                        "is_guest": user_data.get("is_guest", False),
                        "joined_at": user_data["joined_at"]
                    }
                    participants.append(participant)

                    # Count languages
                    lang = user_data["language"]
                    language_counts[lang] = language_counts.get(lang, 0) + 1
            except (json.JSONDecodeError, KeyError) as e:
                self.log.error(
                    "invalid_presence_data",
                    room=room_id,
                    user_key=user_key,
                    error=str(e)
                )
                continue

        # Build event
        event = {
            "type": event_type,
            "room_id": room_id,
            "participants": participants,
            "language_counts": language_counts,
            "timestamp": datetime.utcnow().isoformat()
        }

        if triggered_by_user_id:
            event["triggered_by_user_id"] = triggered_by_user_id

        if extra:
            event.update(extra)

        return event

    async def cleanup_stale_disconnects(self):
        """
        Background task: Check disconnect timers and finalize user removals.

        This task runs every 5 seconds and:
        1. Scans all presence states for disconnecting users
        2. Checks if grace period has elapsed
        3. Removes users and broadcasts "user_left" events

        Should be started as an asyncio task on application startup.
        """
        self.log.info("cleanup_task_started", grace_period=PRESENCE_GRACE_PERIOD_SECONDS)

        while True:
            try:
                await asyncio.sleep(5)

                # Scan for all presence_state hashes
                pattern = "room:*:presence_state"

                async for presence_key in self.redis.scan_iter(match=pattern, count=100):
                    presence_key_str = presence_key if isinstance(presence_key, str) else presence_key.decode()

                    # Get all users in this room
                    all_users = await self.redis.hgetall(presence_key_str)
                    current_time = datetime.utcnow()

                    for user_key, user_data_str in all_users.items():
                        try:
                            user_key_str = user_key if isinstance(user_key, str) else user_key.decode()
                            user_data_bytes = user_data_str if isinstance(user_data_str, bytes) else user_data_str.encode()
                            user_data = json.loads(user_data_bytes)

                            # Only process users in disconnecting state
                            if user_data.get("state") != "disconnecting":
                                continue

                            # Check if grace period has elapsed
                            disconnect_started_str = user_data.get("disconnect_started")
                            if not disconnect_started_str:
                                continue

                            disconnect_started = datetime.fromisoformat(disconnect_started_str)
                            elapsed = (current_time - disconnect_started).total_seconds()

                            if elapsed >= PRESENCE_GRACE_PERIOD_SECONDS:
                                # Grace period expired, remove user
                                # Extract room_id and user_id from keys
                                room_id = presence_key_str.split(":")[1]
                                user_id = user_key_str.replace("user:", "")

                                # Remove from presence state
                                await self.redis.hdel(presence_key_str, user_key_str)

                                # Remove disconnect timer if it still exists
                                timer_key = f"room:{room_id}:disconnect_timer:{user_id}"
                                await self.redis.delete(timer_key)

                                # Broadcast user_left event
                                event = await self._build_presence_snapshot(room_id, "user_left", user_id)
                                await self.redis.publish("presence_events", json.dumps(event))

                                self.log.info(
                                    "user_left_after_grace_period",
                                    room=room_id,
                                    user=user_id,
                                    display_name=user_data.get("display_name", "Unknown"),
                                    elapsed_seconds=int(elapsed)
                                )

                        except (json.JSONDecodeError, ValueError, IndexError) as e:
                            self.log.error(
                                "cleanup_parse_error",
                                user_key=user_key_str if 'user_key_str' in locals() else str(user_key),
                                error=str(e)
                            )
                            continue

                # Legacy: Also check for orphaned disconnect timers (old approach)
                # This ensures cleanup of any timers that exist without corresponding presence state
                keys_to_process = []
                pattern = "room:*:disconnect_timer:*"

                async for key in self.redis.scan_iter(match=pattern, count=100):
                    key_str = key if isinstance(key, str) else key.decode()
                    # Check if corresponding presence state exists
                    parts = key_str.split(":")
                    if len(parts) >= 4:
                        room_id = parts[1]
                        user_id = ":".join(parts[3:])  # Handle user IDs with colons (e.g., guest:name:timestamp)
                        presence_key = f"room:{room_id}:presence_state"
                        user_key = f"user:{user_id}"

                        # If user not in presence state, timer is orphaned - remove it
                        user_exists = await self.redis.hexists(presence_key, user_key)
                        if not user_exists:
                            await self.redis.delete(key_str)
                            self.log.info("orphaned_timer_removed", timer_key=key_str)

            except Exception as e:
                self.log.error("cleanup_task_error", error=str(e))
                # Continue running despite errors
                await asyncio.sleep(5)

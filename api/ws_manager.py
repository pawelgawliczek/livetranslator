# /opt/stack/livetranslator/api/ws_manager.py
import asyncio
import time
from datetime import datetime
from typing import Dict, Set, Tuple

import httpx
import orjson
import redis.asyncio as redis
import structlog
from fastapi import WebSocket
from sqlalchemy.orm import Session

from .persistence import save_stt_event, upsert_final_translation
from .metrics import MET_STT_EVENTS, MET_MT_REQ, MET_MT_ERR, MET_MT_LAT, E2E_LAT
from .models import Room
from .db import SessionLocal


class WSManager:
    def __init__(self, redis_url: str, mt_base_url: str, default_tgt: str = "en"):
        self.redis: redis.Redis = redis.from_url(redis_url, decode_responses=True)
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.default_tgt = default_tgt
        self.log = structlog.get_logger("wsman")
        self._pending_admin_checks: Dict[str, asyncio.Task] = {}  # Debounce admin checks

    async def get_room_languages(self, room_id: str) -> set:
        """Get all unique languages needed in a room"""
        languages = set()
        for ws in self.rooms.get(room_id, []):
            lang = getattr(ws.state, 'preferred_lang', 'en')
            languages.add(lang)
        return languages

    async def run_pubsub(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("stt_events", "mt_events")
        self.log.info("subscribed", channel="stt_events,mt_events")

        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue

            channel = msg.get("channel")
            raw = msg.get("data")
            
            try:
                payload = raw if isinstance(raw, (bytes, bytearray)) else raw.encode("utf-8")
                data = orjson.loads(payload)
            except Exception as e:
                self.log.error("bad_message", err=str(e))
                continue

            room = data.get("room_id") or data.get("roomId")
            if not room:
                continue

            # Route based on channel
            if channel == "stt_events":
                await self._handle_stt_event(data, room)
            elif channel == "mt_events":
                await self._handle_mt_event(data, room)

    async def _handle_stt_event(self, data: dict, room: str):
        seg_id = int(data.get("segment_id") or 0)
        rev = int(data.get("revision") or 0)
        is_final = bool(data.get("final"))
        src_lang = data.get("lang") or "auto"
        text = (data.get("text") or "").strip()
        kind = "final" if is_final else "partial"
        speaker = data.get("speaker", "system")

        MET_STT_EVENTS.labels(kind=kind).inc()
        self.log.info("stt_event", kind=kind, room=room, segment=seg_id, revision=rev, speaker=speaker)

        # broadcast raw STT to all participants
        await self.broadcast(room, data)

        # Get all target languages needed in this room
        target_languages = await self.get_room_languages(room)

        # Store target languages in Redis for MT router to use
        if target_languages:
            key = f"room:{room}:target_languages"
            await self.redis.sadd(key, *target_languages)
            await self.redis.expire(key, 3600)  # Expire after 1 hour

            self.log.info("room_languages", room=room, languages=list(target_languages))

        # persist STT
        try:
            save_stt_event(room, seg_id, rev, is_final, src_lang, text)
        except Exception as e:
            self.log.error("persist_stt_error", room=room, segment=seg_id, err=str(e))

    async def _handle_mt_event(self, data: dict, room: str):
        seg_id = int(data.get("segment_id") or 0)
        is_final = bool(data.get("is_final") or data.get("final"))
        src_lang = data.get("src_lang") or data.get("src") or "auto"
        tgt_lang = data.get("tgt_lang") or data.get("tgt") or self.default_tgt
        text = (data.get("text") or "").strip()
        kind = "final" if is_final else "partial"

        self.log.info("mt_event", kind=kind, room=room, segment=seg_id, tgt=tgt_lang)

        # Targeted broadcast: only send translation to users who need this target language
        out = {
            "type": f"translation_{kind}",
            "room_id": room,
            "segment_id": seg_id,
            "src": src_lang,
            "tgt": tgt_lang,
            "text": text,
            "final": is_final,
        }

        # Send to participants who have this language as their preference
        sent_count = 0
        for ws in list(self.rooms.get(room, [])):
            try:
                user_lang = getattr(ws.state, 'preferred_lang', 'en')
                # Send translation if it matches user's language preference
                if user_lang == tgt_lang:
                    await ws.send_json(out)
                    sent_count += 1
            except Exception as e:
                self.log.error("broadcast_failed", room=room, err=str(e))
                self.disconnect(room, ws)

        self.log.info("targeted_broadcast", room=room, type=out.get("type"),
                     segment=seg_id, tgt=tgt_lang, sent=sent_count)

        # persist final translations
        if is_final and text:
            try:
                src_text = data.get("src_text", "")
                upsert_final_translation(room, seg_id, src_lang, src_text, text)
            except Exception as e:
                self.log.error("persist_mt_error", room=room, segment=seg_id, err=str(e))

    async def _do_admin_check(self, room_id: str):
        """
        Internal method that actually performs the admin presence check.
        This is called after debouncing.
        """
        try:
            db: Session = SessionLocal()
            try:
                room = db.query(Room).filter(Room.code == room_id).first()
                if not room:
                    return

                # Check if admin is currently connected
                admin_present = False
                connected_users = []
                for ws in self.rooms.get(room_id, []):
                    user_id = getattr(ws.state, 'user', None)
                    connected_users.append(user_id)
                    # Check if this user is the admin (not a guest)
                    if user_id and not str(user_id).startswith('guest:'):
                        try:
                            # Convert to int for comparison with owner_id
                            if int(user_id) == room.owner_id:
                                admin_present = True
                                break
                        except (ValueError, TypeError):
                            # Skip if user_id can't be converted to int
                            continue

                self.log.info("admin_check_complete", room=room_id, admin_present=admin_present, owner_id=room.owner_id, connected_users=connected_users)

                # Update database based on admin presence
                if admin_present and room.admin_left_at:
                    # Admin rejoined - clear the timestamp
                    room.admin_left_at = None
                    db.commit()
                    self.log.info("admin_rejoined", room=room_id, owner_id=room.owner_id)
                elif not admin_present and not room.admin_left_at and len(connected_users) > 0:
                    # Admin left - set the timestamp
                    # Only mark as left if there are non-admin users still connected
                    has_non_admin_users = any(
                        user_id and str(user_id).startswith('guest:')
                        for user_id in connected_users
                    )
                    if has_non_admin_users:
                        room.admin_left_at = datetime.utcnow()
                        db.commit()
                        self.log.info("admin_left", room=room_id, owner_id=room.owner_id, timestamp=room.admin_left_at)
            finally:
                db.close()
        except Exception as e:
            self.log.error("admin_check_error", room=room_id, err=str(e))
        finally:
            # Clean up the pending task
            if room_id in self._pending_admin_checks:
                del self._pending_admin_checks[room_id]

    async def _check_admin_presence(self, room_id: str):
        """
        Check if the room admin is present with 3-second debouncing.
        Multiple rapid calls will only trigger one check after the delay.
        """
        # Cancel any pending check for this room
        if room_id in self._pending_admin_checks:
            self._pending_admin_checks[room_id].cancel()

        # Schedule a new check after 3 seconds
        async def delayed_check():
            await asyncio.sleep(3)
            await self._do_admin_check(room_id)

        self._pending_admin_checks[room_id] = asyncio.create_task(delayed_check())

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, set()).add(ws)

        # Check if admin rejoined
        await self._check_admin_presence(room_id)

        self.log.info("ws_join", room=room_id, conns=len(self.rooms.get(room_id, [])))

    async def disconnect(self, room_id: str, ws: WebSocket):
        conns = self.rooms.get(room_id)
        if conns and ws in conns:
            conns.remove(ws)
            if not conns:
                self.rooms.pop(room_id, None)

        # Check if admin left
        await self._check_admin_presence(room_id)

        self.log.info("ws_leave", room=room_id, conns=len(self.rooms.get(room_id, [])))

    async def broadcast(self, room_id: str, payload: dict):
        ok = 0
        total = len(self.rooms.get(room_id, []))
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(payload)
                ok += 1
            except Exception as e:
                self.log.error("broadcast_failed", room=room_id, err=str(e))
                self.disconnect(room_id, ws)
        self.log.info("broadcast", room=room_id, type=payload.get("type"), segment=payload.get("segment_id"), sent=ok, total=total)
        return ok

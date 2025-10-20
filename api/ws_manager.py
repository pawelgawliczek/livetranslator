# /opt/stack/livetranslator/api/ws_manager.py
import asyncio
import time
from typing import Dict, Set, Tuple

import httpx
import orjson
import redis.asyncio as redis
import structlog
from fastapi import WebSocket

from .persistence import save_stt_event, upsert_final_translation
from .metrics import MET_STT_EVENTS, MET_MT_REQ, MET_MT_ERR, MET_MT_LAT, E2E_LAT


class WSManager:
    def __init__(self, redis_url: str, mt_base_url: str, default_tgt: str = "en"):
        self.redis: redis.Redis = redis.from_url(redis_url, decode_responses=True)
        self.rooms: Dict[str, Set[WebSocket]] = {}
        self.default_tgt = default_tgt
        self.log = structlog.get_logger("wsman")

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

        MET_STT_EVENTS.labels(kind=kind).inc()
        self.log.info("stt_event", kind=kind, room=room, segment=seg_id, revision=rev)

        # broadcast raw STT
        await self.broadcast(room, data)

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

        self.log.info("mt_event", kind=kind, room=room, segment=seg_id)

        # broadcast translation to WebSocket
        out = {
            "type": f"translation_{kind}",
            "room_id": room,
            "segment_id": seg_id,
            "src": src_lang,
            "tgt": tgt_lang,
            "text": text,
            "final": is_final,
        }
        await self.broadcast(room, out)

        # persist final translations
        if is_final and text:
            try:
                src_text = data.get("src_text", "")
                upsert_final_translation(room, seg_id, src_lang, src_text, text)
            except Exception as e:
                self.log.error("persist_mt_error", room=room, segment=seg_id, err=str(e))

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, set()).add(ws)
        self.log.info("ws_join", room=room_id, conns=len(self.rooms.get(room_id, [])))

    def disconnect(self, room_id: str, ws: WebSocket):
        conns = self.rooms.get(room_id)
        if conns and ws in conns:
            conns.remove(ws)
            if not conns:
                self.rooms.pop(room_id, None)
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

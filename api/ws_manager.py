# /opt/stack/livetranslator/api/ws_manager.py
import asyncio
from typing import Dict, Set

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
        self.mt_url_final = mt_base_url.rstrip("/") + "/translate/final"
        self.default_tgt = default_tgt
        self.log = structlog.get_logger("wsman")

    async def run_pubsub(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("stt_events")
        self.log.info("subscribed", channel="stt_events")

        async with httpx.AsyncClient(timeout=30) as cli:
            async for msg in pubsub.listen():
                if not msg or msg.get("type") != "message":
                    continue

                raw = msg.get("data")
                try:
                    data = orjson.loads(raw if isinstance(raw, (bytes, bytearray)) else raw.encode("utf-8"))
                except Exception as e:
                    self.log.error("bad_message", err=str(e))
                    continue

                room = data.get("room_id")
                if not room:
                    continue

                seg_id = int(data.get("segment_id") or 0)
                rev = int(data.get("revision") or 0)
                is_final = bool(data.get("final"))
                src_lang = data.get("lang") or "auto"
                text = data.get("text") or ""
                kind = "final" if is_final else "partial"

                MET_STT_EVENTS.labels(kind=kind).inc()
                self.log.info("stt_event", kind=kind, room=room, segment=seg_id, revision=rev)

                # broadcast STT to clients
                await self.broadcast(room, data)

                # persist STT
                try:
                    save_stt_event(room, seg_id, rev, is_final, src_lang, text)
                except Exception as e:
                    self.log.error("persist_error", room=room, segment=seg_id, err=str(e))

                # on final, request MT and broadcast
                if is_final and text:
                    try:
                        e2e_start = asyncio.get_event_loop().time()
                        self.log.info("mt_request", room=room, segment=seg_id, src=src_lang, tgt=self.default_tgt, bytes=len(text.encode()))
                        resp = await cli.post(self.mt_url_final, json={"src": src_lang, "tgt": self.default_tgt, "text": text})
                        resp.raise_for_status()
                        ttext = resp.json().get("text", "")
                        MET_MT_REQ.inc()
                        MET_MT_LAT.observe(asyncio.get_event_loop().time() - e2e_start)

                        out = {
                            "type": "translation_final",
                            "room_id": room,
                            "device": data.get("device"),
                            "segment_id": seg_id,
                            "ts_iso": data.get("ts_iso"),
                            "src": src_lang,
                            "tgt": self.default_tgt,
                            "text": ttext,
                            "final": True,
                        }

                        try:
                            upsert_final_translation(room, seg_id, src_lang, text, ttext)
                        except Exception as e:
                            self.log.error("persist_mt_error", room=room, segment=seg_id, err=str(e))

                        await self.broadcast(room, out)
                        E2E_LAT.observe(asyncio.get_event_loop().time() - e2e_start)
                    except Exception as e:
                        MET_MT_ERR.inc()
                        self.log.error("mt_error", room=room, segment=seg_id, err=str(e))

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, set()).add(ws)

    def disconnect(self, room_id: str, ws: WebSocket):
        conns = self.rooms.get(room_id)
        if conns and ws in conns:
            conns.remove(ws)
            if not conns:
                self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: str, payload: dict):
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(room_id, ws)

import asyncio
from typing import Dict, Set
from fastapi import WebSocket
import redis.asyncio as redis
import orjson

class WSManager:
    def __init__(self, redis_url):
        self.redis: redis.Redis = redis.from_url(str(redis_url), decode_responses=True)
        self.rooms: Dict[str, Set[WebSocket]] = {}

    async def run_pubsub(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("stt_events")
        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue
            try:
                data = orjson.loads(msg["data"])
                room = data.get("room_id")
                if room:
                    await self.broadcast(room, data)
            except Exception:
                continue

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

import asyncio
import re
import orjson
import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .settings import settings
from .db import migrate
from .ws_manager import WSManager
from .stt_client import STTClient
from .mt_client import MTClient
from . import auth

app = FastAPI(title="LiveTranslator API")
app.include_router(auth.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.LT_DOMAIN}", f"http://{settings.LT_DOMAIN}"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

wsman = WSManager(str(settings.LT_REDIS_URL))
stt = STTClient(str(settings.LT_REDIS_URL))
mt = MTClient(str(settings.LT_MT_BASE_URL))

@app.on_event("startup")
async def _startup():
    migrate()
    asyncio.create_task(wsman.run_pubsub())

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.websocket("/ws/rooms/{room_id}")
async def ws_room(ws: WebSocket, room_id: str):
    await wsman.connect(room_id, ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "audio_chunk":
                continue
            device = msg.get("deviceId", "dev")
            await stt.push_chunk(room_id, device, msg.get("seq", 0), msg.get("pcm16_base64", ""))
    except WebSocketDisconnect:
        wsman.disconnect(room_id, ws)

# ---------- REST translate ----------
class TReq(BaseModel):
    src: str
    tgt: str
    text: str

MT_FAST = str(settings.LT_MT_BASE_URL).rstrip("/") + "/translate/fast"

@app.post("/translate")
async def translate(r: TReq):
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            resp = await cli.post(MT_FAST, json=r.model_dump())
            resp.raise_for_status()
            return {"text": resp.json().get("text")}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MT worker error: {e}")

# ---------- SSE streaming ----------
@app.get("/translate/stream")
async def translate_stream(q: str, src: str = "auto", tgt: str = "en"):
    parts = [p for p in re.split(r"([.!?]+\s+)", q) if p]

    async def gen():
        buf = ""
        async with httpx.AsyncClient(timeout=30) as cli:
            for p in parts:
                buf += p
                r = await cli.post(MT_FAST, json={"src": src, "tgt": tgt, "text": buf})
                r.raise_for_status()
                yield f"data: {orjson.dumps({'text': r.json()['text']}).decode()}\n\n"
                await asyncio.sleep(0.02)

    return StreamingResponse(gen(), media_type="text/event-stream")

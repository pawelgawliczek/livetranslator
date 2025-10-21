import asyncio, re, httpx, orjson, structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel
from .metrics import MET_WS_CONNS, MET_STT_EVENTS, MET_MT_REQ, MET_MT_ERR, MET_MT_LAT, generate_latest, CONTENT_TYPE_LATEST

from .settings import settings
from .db import migrate
from .ws_manager import WSManager
from .stt_client import STTClient
from .mt_client import MTClient
from .jwt_tools import verify_token
from .events import router as events_router
from .auth import router as auth_router
from .costs_api import router as costs_router
from .history_api import router as history_router
from .invites_api import router as invites_router
from .rooms_api import router as rooms_router
from .guest_api import router as guest_router

app = FastAPI(title="LiveTranslator API")
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(costs_router)
app.include_router(history_router)
app.include_router(invites_router)
app.include_router(rooms_router)
app.include_router(guest_router)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger("api")

import logging
class _MuteHealthMetrics(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return (" GET /metrics " not in msg) and (" GET /healthz " not in msg)
logging.getLogger("uvicorn.access").addFilter(_MuteHealthMetrics())

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.LT_DOMAIN}", f"http://{settings.LT_DOMAIN}"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

wsman = WSManager(str(settings.LT_REDIS_URL), str(settings.LT_MT_BASE_URL), "en")
stt = STTClient(str(settings.LT_REDIS_URL))
mt = MTClient(str(settings.LT_MT_BASE_URL))

# Store wsman in app state so other endpoints can access it
app.state.wsman = wsman

@app.on_event("startup")
async def _startup():
    migrate()
    asyncio.create_task(wsman.run_pubsub())

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.websocket("/ws/rooms/{room_id}")
async def ws_room(ws: WebSocket, room_id: str):
    qtok = getattr(ws, "query_params", {}).get("token") if hasattr(ws, "query_params") else None
    authv = ws.headers.get("authorization", "") if hasattr(ws, "headers") else ""
    htok = authv[7:] if authv.lower().startswith("bearer ") else ""
    token = qtok or htok
    try:
        claims = verify_token(token)
        user_id = claims.get("sub")
        user_email = claims.get("email", "unknown")
        user_lang = claims.get("preferred_lang", "en")  # Get language from token
        ws.state.user = user_id
        ws.state.email = user_email
        ws.state.preferred_lang = user_lang
    except Exception:
        await ws.accept()
        await ws.close(code=4401)
        return

    MET_WS_CONNS.inc()
    await wsman.connect(room_id, ws)

    # Broadcast participant joined event to notify other users in the room
    await wsman.broadcast(room_id, {
        "type": "participant_joined",
        "room_id": room_id,
        "user_email": user_email,
        "user_id": user_id,
        "preferred_lang": user_lang
    })

    try:
        while True:
            msg = await ws.receive_json()

            # Handle language preference update
            if msg.get("type") == "set_language":
                new_lang = msg.get("language", "en")
                ws.state.preferred_lang = new_lang
                # Notify room about language change
                await wsman.broadcast(room_id, {
                    "type": "participant_language_changed",
                    "room_id": room_id,
                    "user_email": user_email,
                    "preferred_lang": new_lang
                })
                continue

            # Always ensure room id and speaker
            if "room_id" not in msg:
                msg["room_id"] = room_id
            if "speaker" not in msg:
                msg["speaker"] = user_email

            if msg.get("type") in ["audio_chunk", "audio_chunk_partial"]:
                # Add speaker and their language to message before forwarding
                msg["speaker"] = user_email
                msg["speaker_lang"] = ws.state.preferred_lang
                await stt.push_raw(msg)
            else:
                # forward control events
                await stt.push_raw(msg)
    except WebSocketDisconnect:
        await wsman.disconnect(room_id, ws)
        MET_WS_CONNS.dec()

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

@app.get("/readyz")
async def readyz():
    async with httpx.AsyncClient(timeout=5) as cli:
        r1 = await cli.get(str(settings.LT_MT_BASE_URL).rstrip("/") + "/health")
        r1.raise_for_status()
    await wsman.redis.ping()
    return {"ok": True}

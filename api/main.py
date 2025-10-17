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

app = FastAPI(title="LiveTranslator API")
app.include_router(events_router)
app.include_router(auth_router)

# metrics

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger("api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.LT_DOMAIN}", f"http://{settings.LT_DOMAIN}"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

wsman = WSManager(str(settings.LT_REDIS_URL), str(settings.LT_MT_BASE_URL), "en")
stt = STTClient(str(settings.LT_REDIS_URL))
mt = MTClient(str(settings.LT_MT_BASE_URL))

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
        ws.state.user = claims.get("sub")
    except Exception:
        await ws.close(code=4401)
        return

    MET_WS_CONNS.inc()
    await wsman.connect(room_id, ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") != "audio_chunk":
                continue
            device = msg.get("deviceId","dev")
            await stt.push_chunk(room_id, device, msg.get("seq",0), msg.get("pcm16_base64",""))
    except WebSocketDisconnect:
        wsman.disconnect(room_id, ws)
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

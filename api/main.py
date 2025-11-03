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
from .presence_manager import PresenceManager
from .events import router as events_router
from .auth import router as auth_router
from .costs_api import router as costs_router
from .history_api import router as history_router
from .invites_api import router as invites_router
from .rooms_api import router as rooms_router
from .guest_api import router as guest_router
from .profile_api import router as profile_router
from .subscription_api import router as subscription_router
from .billing_api import router as billing_router
from .user_history_api import router as user_history_router
from .routers.admin_api import router as admin_router
from .routers.admin_costs import router as admin_costs_router
from .routers.quota import router as quota_router
from .routers.transcript import router as transcript_router

app = FastAPI(title="LiveTranslator API")
app.include_router(events_router)
app.include_router(auth_router)
app.include_router(costs_router)
app.include_router(history_router)
app.include_router(invites_router)
app.include_router(rooms_router)
app.include_router(guest_router)
app.include_router(profile_router)
app.include_router(subscription_router)
app.include_router(billing_router)
app.include_router(user_history_router)
app.include_router(admin_router)
app.include_router(admin_costs_router)
app.include_router(quota_router)
app.include_router(transcript_router)

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
presence_manager = PresenceManager(wsman.redis)

# Store managers in app state so other endpoints can access them
app.state.wsman = wsman
app.state.presence_manager = presence_manager

@app.on_event("startup")
async def _startup():
    migrate()
    asyncio.create_task(wsman.run_pubsub())
    asyncio.create_task(presence_manager.cleanup_stale_disconnects())

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def register_user_language(room_id: str, user_id: str, language: str):
    """Register user's language for translation routing"""
    redis = wsman.redis
    key = f"room:{room_id}:active_lang:{user_id}"
    await redis.setex(key, 3600, language)  # 1 hour TTL (expires when room inactive)
    log.info("registered_user_language", room=room_id, user=user_id, lang=language)

async def trigger_room_language_aggregation(room_id: str) -> list[str]:
    """Immediately aggregate languages for this room from active users"""
    redis = wsman.redis
    pattern = f"room:{room_id}:active_lang:*"
    languages = set()

    # Collect all active language keys
    async for key in redis.scan_iter(match=pattern, count=100):
        lang = await redis.get(key)
        if lang:
            lang_str = lang.decode() if isinstance(lang, bytes) else lang
            languages.add(lang_str)

    if languages:
        # Update target languages set with immediate effect
        target_key = f"room:{room_id}:target_languages"
        await redis.delete(target_key)
        await redis.sadd(target_key, *languages)
        await redis.expire(target_key, 30)  # 30s safety expiry
        log.info("aggregated_room_languages", room=room_id, languages=list(languages))
    else:
        # Clean up empty target set
        target_key = f"room:{room_id}:target_languages"
        await redis.delete(target_key)
        log.info("cleared_room_languages", room=room_id)

    return list(languages)

async def get_user_language_from_db(user_id: str, user_email: str, fallback: str = "en") -> str:
    """
    Get user's current preferred language from database.
    This ensures we always use the latest value, not stale JWT token data.

    Args:
        user_id: User ID from JWT token
        user_email: User email from JWT token
        fallback: Fallback language if user not found or is guest

    Returns:
        User's preferred language code
    """
    # Guests don't have database records, use fallback
    if str(user_id).startswith('guest:'):
        return fallback

    # Query database for current preferred_lang
    def query_db():
        from .db import SessionLocal
        from .models import User
        from sqlalchemy import select

        db = SessionLocal()
        try:
            user = db.scalar(select(User).where(User.email == user_email))
            if user and user.preferred_lang:
                # Normalize language from database (e.g., "en-GB" -> "en")
                db_lang = user.preferred_lang.split('-')[0] if user.preferred_lang else fallback
                return db_lang
            return fallback
        finally:
            db.close()

    # Run synchronous database query in thread pool
    try:
        return await asyncio.to_thread(query_db)
    except Exception as e:
        log.warning("failed_to_fetch_user_lang", error=str(e), fallback=fallback)
        return fallback

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
        # Normalize language code from JWT (e.g., "en-GB" -> "en") for Speechmatics compatibility
        jwt_lang = claims.get("preferred_lang", "en")
        normalized_jwt_lang = jwt_lang.split('-')[0] if jwt_lang else "en"
        # IMPORTANT: Get language from database, not JWT token (token can be stale)
        user_lang = await get_user_language_from_db(user_id, user_email, normalized_jwt_lang)
        ws.state.user = user_id
        ws.state.email = user_email
        ws.state.preferred_lang = user_lang
    except Exception:
        await ws.accept()
        await ws.close(code=4401)
        return

    MET_WS_CONNS.inc()
    await wsman.connect(room_id, ws)

    # IMPORTANT: Immediately register user's language in Redis for translation routing
    await register_user_language(room_id, str(user_id), user_lang)
    active_languages = await trigger_room_language_aggregation(room_id)

    # Add presence tracking (debounced, packet-loss resistant)
    is_guest = str(user_id).startswith('guest:')
    if is_guest:
        # For guests, user_id format is "guest:{name}:{timestamp}"
        parts = str(user_id).split(':', 2)
        display_name = parts[1] if len(parts) > 1 else 'Guest'
    else:
        display_name = user_email.split('@')[0] if '@' in user_email else user_email

    presence_event = await presence_manager.user_connected(
        room_id, str(user_id), display_name, user_lang, is_guest
    )
    await wsman.broadcast(room_id, presence_event)

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type", "unknown")
            if msg_type not in ["ping"]:  # Don't log pings
                print(f"[WebSocket] 📨 Received message type={msg_type} from room={room_id}")

            # Handle ping-pong for network monitoring
            if msg.get("type") == "ping":
                await ws.send_json({
                    "type": "pong",
                    "timestamp": msg.get("timestamp")
                })
                continue

            # Handle language preference update
            if msg.get("type") == "set_language":
                new_lang = msg.get("language", "en")
                # Normalize language code (e.g., "en-GB" -> "en") for Speechmatics compatibility
                normalized_lang = new_lang.split('-')[0] if new_lang else "en"
                ws.state.preferred_lang = normalized_lang

                # IMPORTANT: Immediately update Redis for translation routing
                await register_user_language(room_id, str(user_id), normalized_lang)
                active_languages = await trigger_room_language_aggregation(room_id)

                # Update presence with new language (debounced notifications)
                presence_event = await presence_manager.user_changed_language(
                    room_id, str(user_id), normalized_lang
                )
                if presence_event:
                    await wsman.broadcast(room_id, presence_event)
                continue

            # Handle speech_started event - allocate segment ID and broadcast to all room participants
            if msg.get("type") == "speech_started":
                # Allocate the next segment ID immediately
                r = wsman.redis
                segment_id_key = f"room:{room_id}:segment_counter"
                segment_id = await r.incr(segment_id_key)

                # Store the pre-allocated segment ID for this speaker
                # This will be used by the STT router when audio arrives
                pending_key = f"room:{room_id}:pending_segment:{user_email}"
                await r.setex(pending_key, 30, segment_id)  # Expire after 30 seconds

                await wsman.broadcast(room_id, {
                    "type": "speech_started",
                    "room_id": room_id,
                    "speaker": msg.get("speaker", user_email),
                    "timestamp": msg.get("timestamp", 0),
                    "segment_id": segment_id  # Include the segment ID
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
                # Note: speaker_id will be added by Speechmatics diarization in multi-speaker rooms
                await stt.push_raw(msg)
            else:
                # forward control events
                await stt.push_raw(msg)
    except WebSocketDisconnect:
        # Disconnect first (removes this WebSocket from the room)
        await wsman.disconnect(room_id, ws)
        MET_WS_CONNS.dec()

        # Clean up user's language from Redis immediately (for translation routing)
        lang_key = f"room:{room_id}:active_lang:{user_id}"
        await wsman.redis.delete(lang_key)

        # Re-aggregate languages to get updated list (for translation routing)
        active_languages = await trigger_room_language_aggregation(room_id)

        # Start grace period for presence (debounced - no immediate "left" notification)
        # Actual "user_left" broadcast happens after 15s grace period if user doesn't reconnect
        await presence_manager.user_disconnected(room_id, str(user_id))

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

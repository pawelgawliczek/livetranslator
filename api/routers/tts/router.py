"""
TTS Router - Text-to-Speech Event Processing
Subscribes to mt_events, generates audio, publishes via WebSocket

Architecture:
- Listens to mt_events Redis channel (translation_partial, translation_final)
- Checks room.tts_enabled flag
- Routes to TTS provider based on language (via language_router)
- Publishes tts_audio events to WebSocket via stt_events channel
- Tracks costs via cost_events channel

Event Flow:
1. MT Router publishes translation_final event
2. TTS Router receives event, checks if TTS enabled
3. Synthesizes audio using Google TTS
4. Publishes tts_audio event with base64 MP3
5. WebSocket manager broadcasts to room participants
6. Browser plays audio using Web Audio API
"""

import os
import asyncio
import time
import redis.asyncio as redis
from datetime import datetime

try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

# Import language router
from language_router import get_tts_provider_for_language, init_db_pool, clear_cache, CACHE_CLEAR_CHANNEL, update_provider_health

# Import TTS backends
try:
    from google_tts_backend import synthesize_speech as google_tts_synthesize
except ImportError:
    google_tts_synthesize = None
    print("[TTS Router] Google TTS backend not available")

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
MT_EVENTS_CHANNEL = os.getenv("MT_OUTPUT_CHANNEL", "mt_events")
STT_EVENTS_CHANNEL = os.getenv("STT_OUTPUT_EVENTS", "stt_events")  # TTS events go here for WebSocket broadcast
COST_TRACKING_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")
DEFAULT_QUALITY_TIER = os.getenv("TTS_QUALITY_TIER", "standard")
TTS_ENABLED = os.getenv("TTS_ENABLED", "true").lower() == "true"
TTS_FINAL_ONLY = os.getenv("TTS_FINAL_ONLY", "true").lower() == "true"  # Only synthesize final translations (saves costs)

# Database config
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "lt_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "livetranslator")

print(f"[TTS Router] Starting...")
print(f"  TTS Enabled:  {TTS_ENABLED}")
print(f"  Final Only:   {TTS_FINAL_ONLY} (skip partials to save costs)")
print(f"  Input:        {MT_EVENTS_CHANNEL}")
print(f"  Output:       {STT_EVENTS_CHANNEL}")
print(f"  Quality Tier: {DEFAULT_QUALITY_TIER}")

# Room TTS settings cache - stores room_code -> tts_enabled
room_tts_cache = {}
room_tts_cache_expiry = {}
ROOM_CACHE_TTL_SECONDS = 60  # Cache for 1 minute


async def check_room_tts_enabled(room_code: str) -> bool:
    """
    Check if TTS is enabled for a specific room.

    Returns:
        bool: True if TTS is enabled for this room
    """
    # Check cache first
    if room_code in room_tts_cache:
        cache_expiry = room_tts_cache_expiry.get(room_code)
        if cache_expiry and datetime.now() < cache_expiry:
            return room_tts_cache[room_code]

    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )

        # Query room TTS settings
        row = await conn.fetchrow("""
            SELECT tts_enabled
            FROM rooms
            WHERE code = $1
        """, room_code)

        await conn.close()

        if not row:
            # Room not found, default to disabled
            return False

        tts_enabled = row['tts_enabled']

        # Cache result
        room_tts_cache[room_code] = tts_enabled
        from datetime import timedelta
        room_tts_cache_expiry[room_code] = datetime.now() + timedelta(seconds=ROOM_CACHE_TTL_SECONDS)

        return tts_enabled

    except Exception as e:
        print(f"[TTS Router] Error checking room TTS settings for {room_code}: {e}")
        # Default to enabled on error (graceful degradation)
        return True


async def synthesize_with_provider(
    provider: str,
    text: str,
    language: str,
    config: dict
) -> dict:
    """
    Synthesize speech using the specified provider.

    Args:
        provider: Provider name (google_tts, azure_tts, etc.)
        text: Text to synthesize
        language: Language code (en, pl, ar, etc.)
        config: Provider-specific config (voice_id, pitch, rate, etc.)

    Returns:
        dict: Synthesis result with audio_base64, format, character_count, etc.
    """
    try:
        if provider == "google_tts" and google_tts_synthesize:
            result = await google_tts_synthesize(text, language, config)
        else:
            raise ValueError(f"Unknown or unavailable TTS provider: {provider}")

        return result

    except Exception as e:
        print(f"[TTS Router] Provider {provider} failed: {e}")
        raise


async def cache_invalidation_listener():
    """Listen for cache invalidation messages from Redis."""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(CACHE_CLEAR_CHANNEL)

    print(f"[TTS Router] Cache invalidation listener started on {CACHE_CLEAR_CHANNEL}")

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue

        try:
            data = jloads(msg["data"]) if isinstance(msg["data"], (str, bytes)) else msg["data"]
            service_type = data.get("service_type") if isinstance(data, dict) else None

            # Only clear TTS cache if service_type is 'tts' or None (clear all)
            if service_type in [None, 'tts']:
                language = data.get("language") if isinstance(data, dict) else None
                if language:
                    clear_cache(language=language)
                    print(f"[TTS Router] Cache cleared for language: {language}")
                else:
                    clear_cache()
                    print(f"[TTS Router] All TTS caches cleared")
        except Exception as e:
            print(f"[TTS Router] Cache clear error: {e}")


async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(MT_EVENTS_CHANNEL)

    # Initialize database pool for language router
    await init_db_pool()

    print(f"[TTS Router] Listening on {MT_EVENTS_CHANNEL}")

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue

        try:
            data = jloads(msg["data"])
            msg_type = data.get("type", "")

            # Only process translation events
            if msg_type not in ["translation_partial", "translation_final"]:
                continue

            # Skip partials if TTS_FINAL_ONLY is enabled (cost optimization)
            if TTS_FINAL_ONLY and msg_type == "translation_partial":
                continue

            room = data.get("room_id", "unknown")
            segment_id = data.get("segment_id", 0)
            tgt_lang = data.get("tgt", "en")
            translated_text = data.get("text", "").strip()
            is_final = data.get("final", False)
            speaker = data.get("speaker", "system")
            target_speaker_id = data.get("target_speaker_id")  # For multi-speaker mode

            if not translated_text:
                continue

            # Skip if text is too short (< 3 chars)
            if len(translated_text) < 3:
                continue

            # Check global TTS flag
            if not TTS_ENABLED:
                continue

            # Check room TTS enabled flag
            room_tts_enabled = await check_room_tts_enabled(room)
            if not room_tts_enabled:
                continue

            print(f"[TTS Router] Processing: room={room} seg={segment_id} tgt={tgt_lang} final={is_final} text={translated_text[:50]}...")

            try:
                # Get TTS provider for target language
                # TODO: Load user voice preferences from database
                provider_config = await get_tts_provider_for_language(
                    language=tgt_lang,
                    quality_tier=DEFAULT_QUALITY_TIER,
                    user_preferences=None  # TODO: Load from user settings
                )

                # Synthesize speech (measure latency)
                start_time = time.time()
                synthesis_result = await synthesize_with_provider(
                    provider=provider_config["provider"],
                    text=translated_text,
                    language=tgt_lang,
                    config=provider_config["config"]
                )
                latency_ms = int((time.time() - start_time) * 1000)

                # Update provider health
                await update_provider_health(
                    provider=provider_config["provider"],
                    success=True,
                    response_time_ms=latency_ms
                )

                # Publish TTS audio event via stt_events channel (for WebSocket broadcast)
                tts_event = {
                    "type": "tts_audio",
                    "room_id": room,
                    "segment_id": segment_id,
                    "language": tgt_lang,
                    "audio_base64": synthesis_result["audio_base64"],
                    "format": synthesis_result["format"],
                    "voice_id": synthesis_result["voice_id"],
                    "provider": synthesis_result["provider"],
                    "final": is_final,
                    "text": translated_text,  # Include text for debugging
                    "speaker": speaker,  # Original speaker
                    "ts_iso": datetime.utcnow().isoformat() + "Z"
                }

                # Add target_speaker_id for multi-speaker mode
                if target_speaker_id is not None:
                    tts_event["target_speaker_id"] = target_speaker_id

                await r.publish(STT_EVENTS_CHANNEL, jdumps(tts_event))
                print(f"[TTS Router] Sent TTS audio: seg={segment_id} lang={tgt_lang} chars={synthesis_result['character_count']} voice={synthesis_result['voice_id']} latency={latency_ms}ms")

                # Track cost
                cost_event = {
                    "room_id": room,
                    "pipeline": "tts",
                    "provider": synthesis_result["provider"],
                    "units": synthesis_result["character_count"],
                    "unit_type": "characters",
                    "segment_id": segment_id
                }

                # Add multi-speaker cost tracking fields
                if target_speaker_id is not None and speaker != "system":
                    try:
                        speaker_id = int(speaker) if isinstance(speaker, str) and speaker.isdigit() else None
                        if speaker_id is not None:
                            cost_event["speaker_id"] = speaker_id
                            cost_event["target_speaker_id"] = target_speaker_id
                    except (ValueError, TypeError):
                        pass

                await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                print(f"[TTS Router] Cost tracked: {synthesis_result['character_count']} chars ({synthesis_result['provider']}) seg={segment_id}")

            except Exception as e:
                print(f"[TTS Router] TTS synthesis failed for seg={segment_id}: {e}")

                # Update provider health on failure
                if 'provider_config' in locals():
                    await update_provider_health(
                        provider=provider_config["provider"],
                        success=False,
                        error=str(e)
                    )

        except Exception as e:
            print(f"[TTS Router] Error processing message: {e}")


async def main():
    """Run router loop and cache invalidation listener concurrently."""
    await asyncio.gather(
        router_loop(),
        cache_invalidation_listener()
    )


if __name__ == "__main__":
    asyncio.run(main())

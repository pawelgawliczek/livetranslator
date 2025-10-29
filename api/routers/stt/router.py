"""
STT Router v2 - Language-Based Multi-Provider Routing

This replaces the old router.py with intelligent language-aware provider selection.
Key improvements:
- Routes based on (language, mode, quality_tier) instead of per-room settings
- Supports 4 STT providers: Speechmatics, Google v2, Azure, Soniox
- Automatic fallback on provider health issues
- Diarization always enabled
- Cost tracking per provider

Migration from v1:
- Removed settings_fetcher dependency
- Added language_router for provider selection
- Integrated all provider backends
- Removed per-room STT mode configuration
"""

import os
import asyncio
import base64
import time
from datetime import datetime
import redis.asyncio as redis

try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

# Import language router
from language_router import get_stt_provider_for_language, init_db_pool, clear_cache, CACHE_CLEAR_CHANNEL

# Import streaming manager
from streaming_manager import get_streaming_manager
from language_router import normalize_language_code

# Import debug tracker
from debug_tracker import create_stt_debug_info

# Import all provider backends
from openai_backend import transcribe_audio_chunk as openai_transcribe
try:
    from speechmatics_backend import transcribe_audio_chunk as speechmatics_transcribe
except ImportError:
    speechmatics_transcribe = None
    print("[STT Router] Speechmatics backend not available")

try:
    from google_v2_backend import transcribe_audio_chunk as google_v2_transcribe
except ImportError:
    google_v2_transcribe = None
    print("[STT Router] Google v2 backend not available")

try:
    from azure_backend import transcribe_audio_chunk as azure_transcribe
except ImportError:
    azure_transcribe = None
    print("[STT Router] Azure backend not available")

try:
    from soniox_backend import transcribe_audio_chunk as soniox_transcribe
except ImportError:
    soniox_transcribe = None
    print("[STT Router] Soniox backend not available")

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
INPUT_CHANNEL = os.getenv("STT_INPUT_CHANNEL", "stt_input")
OUTPUT_CHANNEL = os.getenv("STT_OUTPUT_CHANNEL", "stt_local_in")  # For local worker fallback
STT_OUTPUT_EVENTS = os.getenv("STT_OUTPUT_EVENTS", "stt_events")
COST_TRACKING_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")
DEFAULT_QUALITY_TIER = os.getenv("STT_QUALITY_TIER", "standard")  # standard or budget

print(f"[STT Router v2] Starting with language-based routing...")
print(f"  Default Quality Tier: {DEFAULT_QUALITY_TIER}")
print(f"  Input:  {INPUT_CHANNEL}")
print(f"  Output: {STT_OUTPUT_EVENTS}")
print(f"  Providers: speechmatics, google_v2, azure, soniox, openai (fallback)")

# Streaming providers (require persistent websocket connections)
# Using native WebSocket protocol for Speechmatics (not SDK)
STREAMING_PROVIDERS = {"speechmatics", "google_v2", "azure", "soniox"}

# Get streaming manager singleton
streaming_manager = get_streaming_manager()

# Track current partial accumulation per room
partial_sessions = {}  # room -> {segment_id, accumulated_text, speaker, target_lang, provider, ...}


async def get_next_segment_id(r: redis.Redis, room: str) -> int:
    """Get and increment segment counter for a room, stored in Redis"""
    key = f"room:{room}:segment_counter"
    segment_id = await r.incr(key)
    return segment_id


async def transcribe_with_provider(
    audio_b64: str,
    provider: str,
    language: str,
    config: dict,
    context: str = None
) -> dict:
    """
    Transcribe audio using the specified provider.
    Falls back to OpenAI if provider fails or is unavailable.
    """
    try:
        if provider == "speechmatics" and speechmatics_transcribe:
            result = await speechmatics_transcribe(audio_b64, language, config)
        elif provider == "google_v2" and google_v2_transcribe:
            result = await google_v2_transcribe(audio_b64, language, config)
        elif provider == "azure" and azure_transcribe:
            result = await azure_transcribe(audio_b64, language, config)
        elif provider == "soniox" and soniox_transcribe:
            result = await soniox_transcribe(audio_b64, language, config)
        elif provider == "openai":
            # OpenAI backend doesn't use config dict, pass prompt for context
            result = await openai_transcribe(audio_b64, language, prompt=context)
        else:
            print(f"[STT Router] Provider {provider} not available, falling back to OpenAI")
            result = await openai_transcribe(audio_b64, language, prompt=context)

        return result

    except Exception as e:
        import traceback
        print(f"[STT Router] Provider {provider} failed: {e}, falling back to OpenAI")
        print(f"[STT Router] Traceback: {traceback.format_exc()}")
        # Fallback to OpenAI
        try:
            result = await openai_transcribe(audio_b64, language, prompt=context)
            return result
        except Exception as e2:
            print(f"[STT Router] OpenAI fallback also failed: {e2}")
            raise


async def cache_invalidation_listener():
    """Listen for cache invalidation messages from Redis."""
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(CACHE_CLEAR_CHANNEL)

    print(f"[STT Router] Cache invalidation listener started on {CACHE_CLEAR_CHANNEL}")

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue

        try:
            data = jloads(msg["data"]) if isinstance(msg["data"], (str, bytes)) else msg["data"]
            language = data.get("language") if isinstance(data, dict) else None

            if language:
                clear_cache(language=language, service_type="stt")
                print(f"[STT Router] 🔄 Cache cleared for language: {language}")
            else:
                clear_cache(service_type="stt")
                print(f"[STT Router] 🔄 All STT caches cleared")
        except Exception as e:
            print(f"[STT Router] Cache clear error: {e}")


async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(INPUT_CHANNEL)

    # Initialize database pool for language router
    await init_db_pool()

    print(f"[STT Router v2] Listening on {INPUT_CHANNEL}")

    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue

        try:
            data = jloads(msg["data"])
            msg_type = data.get("type", "")
            room = data.get("room_id", "unknown")
            speaker = data.get("speaker", "system")
            target_lang = data.get("target_lang", "en")
            quality_tier = data.get("quality_tier", DEFAULT_QUALITY_TIER)
            language_hint = data.get("language", "auto")

            # Filter out invalid language values from frontend
            if language_hint in [None, "undefined", "null", ""]:
                language_hint = "auto"

            # PARTIAL TRANSCRIPTION: audio_chunk_partial
            if msg_type == "audio_chunk_partial":
                audio_b64 = data.get("pcm16_base64", "")
                device = data.get("device", "web")

                audio_bytes = base64.b64decode(audio_b64)
                duration_sec = len(audio_bytes) / (16000 * 2)

                # Initialize or get existing partial session
                if room not in partial_sessions:
                    # Check if there's a pre-allocated segment ID from speech_started event
                    pending_key = f"room:{room}:pending_segment:{speaker}"
                    pending_segment_id = await r.get(pending_key)

                    if pending_segment_id:
                        # Use the pre-allocated segment ID and delete the pending key
                        segment_id = int(pending_segment_id)
                        await r.delete(pending_key)
                        print(f"[STT Router] ♻️  Reusing pre-allocated segment ID: {segment_id} for {speaker}")
                    else:
                        # No pre-allocated ID, create a new one (fallback)
                        segment_id = await get_next_segment_id(r, room)
                        print(f"[STT Router] 🆕 Creating new segment ID: {segment_id} for {speaker} (no pre-allocation)")

                    # Get provider for partial mode
                    provider_config = await get_stt_provider_for_language(
                        language=language_hint,
                        mode="partial",
                        quality_tier=quality_tier
                    )

                    # Check if there's an existing streaming connection we should reuse
                    existing_connection = streaming_manager.get_connection(room, provider_config["provider"])
                    print(f"[STT Router] DEBUG NEW SEGMENT: room={room}, provider={provider_config['provider']}, existing_connection={existing_connection}")
                    if existing_connection:
                        # Reset the connection for the new segment
                        print(f"[STT Router] ♻️  Reusing existing connection for new segment {segment_id}")
                        existing_connection.reset_for_new_segment(segment_id)
                    else:
                        print(f"[STT Router] 🆕 No existing connection found, will create new one")

                    partial_sessions[room] = {
                        "segment_id": segment_id,
                        "last_transcribed_length": 0,
                        "accumulated_audio": b"",
                        "accumulated_text": "",
                        "chunk_count": 0,
                        "speaker": speaker,
                        "target_lang": target_lang,
                        "language_hint": language_hint,
                        "quality_tier": quality_tier,
                        "provider": provider_config["provider"],
                        "provider_config": provider_config["config"],
                        "last_audio_end_time": 0.0,
                        "no_change_count": 0,
                        "last_new_text": "",
                        "conversation_history": [],
                        "streaming_connection": existing_connection  # Reuse existing connection
                    }

                session = partial_sessions[room]
                session["chunk_count"] += 1
                session["target_lang"] = target_lang
                session["language_hint"] = language_hint

                # Accumulate audio bytes
                # For streaming providers: Keep full audio for debugging (no trim)
                # For non-streaming providers: Cap at 30 seconds
                MAX_AUDIO_SECONDS = 30
                MAX_AUDIO_BYTES = MAX_AUDIO_SECONDS * 16000 * 2

                session["accumulated_audio"] += audio_bytes

                # Only trim for non-streaming providers (they need the buffer for batch transcription)
                # Streaming providers send audio in real-time, so we keep full audio for debugging
                if session["provider"] not in STREAMING_PROVIDERS:
                    if len(session["accumulated_audio"]) > MAX_AUDIO_BYTES:
                        trim_amount = len(session["accumulated_audio"]) - MAX_AUDIO_BYTES
                        session["accumulated_audio"] = session["accumulated_audio"][-MAX_AUDIO_BYTES:]
                        session["last_transcribed_length"] = max(0, session["last_transcribed_length"] - trim_amount)

                new_audio_len = len(session["accumulated_audio"])

                print(f"[STT Router] Processing PARTIAL: room={room} speaker={speaker} segment={session['segment_id']} "
                      f"chunk={session['chunk_count']} provider={session['provider']} lang={language_hint} "
                      f"audio={new_audio_len/32000:.1f}s tier={quality_tier}")

                try:
                    # Check if provider supports streaming
                    if session["provider"] in STREAMING_PROVIDERS:
                        # USE STREAMING WEBSOCKET
                        print(f"[STT Router] 🔌 Using streaming for {session['provider']}")

                        # Define callbacks for streaming events
                        async def on_partial(result):
                            """Handle partial results from streaming connection."""
                            # Check if session still exists (might be deleted after audio_end)
                            if room not in partial_sessions:
                                print(f"[STT Router] ⚠️  Ignoring late partial for {room} (session already cleared)")
                                return

                            text = result.get("text", "").strip()
                            if not text:
                                return

                            # Filter out meaningless partials (just punctuation)
                            if len(text) <= 3 and all(c in '.!?, ' for c in text):
                                print(f"[STT Router] ⏭️  Skipping meaningless partial: '{text}'")
                                return

                            # Speechmatics sends the FULL accumulated transcript in each partial
                            # So we just use it directly
                            session["accumulated_text"] = text
                            session["detected_lang"] = result.get("language", language_hint)
                            session["chunk_count"] += 1  # Increment revision for each partial update

                            # Publish partial event
                            stt_event = {
                                "type": "stt_partial",
                                "room_id": room,
                                "segment_id": session["segment_id"],
                                "revision": session["chunk_count"],
                                "text": text,  # Use the full transcript from Speechmatics
                                "lang": session["detected_lang"],
                                "final": False,
                                "speech_final": False,
                                "ts_iso": None,
                                "device": device,
                                "speaker": speaker,
                                "target_lang": target_lang,
                                "provider": session["provider"]
                            }

                            await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                            print(f"[STT Router] ✓ Stream partial {session['segment_id']}:{session['chunk_count']}: {text[:80]}...")

                        async def on_final(result):
                            """Handle final results from streaming connection."""
                            text = result.get("text", "").strip()
                            if text:
                                session["accumulated_text"] = text
                                print(f"[STT Router] ✓ Stream final: {text[:80]}...")

                        async def on_error(error):
                            """Handle streaming errors - fallback to OpenAI on quota/connection issues."""
                            error_str = str(error) if not isinstance(error, dict) else error.get('error', str(error))
                            print(f"[STT Router] ✗ Streaming error: {error_str}")

                            # Detect quota exceeded or connection errors that should trigger fallback
                            should_fallback = any(pattern in error_str.lower() for pattern in [
                                'quota_exceeded', 'quota exceeded', '4005',
                                'connection', 'timeout', 'unavailable'
                            ])

                            if should_fallback and room in partial_sessions:
                                print(f"[STT Router] 🔄 Fallback triggered: switching to OpenAI for {room}")

                                # Store fallback reason for debug tracking
                                original_provider = session["provider"]
                                session["fallback_error"] = error_str
                                session["fallback_from_provider"] = original_provider

                                # Close the failing streaming connection
                                await streaming_manager.close_connection(room, original_provider)

                                # Switch session to OpenAI batch mode
                                session["provider"] = "openai"
                                session["streaming_connection"] = None
                                print(f"[STT Router] ✓ Switched to OpenAI fallback for {room} (error: {error_str[:80]}...)")

                        # Get or create streaming connection
                        if session["streaming_connection"] is None:
                            # Speechmatics uses simple codes (pl, en, ar)
                            # Other providers use locale format (pl-PL, en-EN, ar-EG)
                            if session["provider"] == "speechmatics":
                                # Keep simple format for Speechmatics
                                provider_lang = language_hint.split('-')[0] if '-' in language_hint else language_hint
                            else:
                                # Normalize to locale format for Google/Azure
                                provider_lang = normalize_language_code(language_hint)

                            conn = await streaming_manager.get_or_create_connection(
                                room_id=room,
                                provider=session["provider"],
                                language=provider_lang,
                                config=session["provider_config"],
                                on_partial=on_partial,
                                on_final=on_final,
                                on_error=on_error
                            )
                            session["streaming_connection"] = conn

                        # Send audio to streaming connection
                        await session["streaming_connection"].send_audio(audio_b64)

                    else:
                        # USE BATCH API (OpenAI and fallback)
                        print(f"[STT Router] 📦 Using batch API for {session['provider']}")

                        # Only transcribe NEW audio (optimization)
                        new_audio_bytes = session["accumulated_audio"][session["last_transcribed_length"]:]
                        new_audio_b64 = base64.b64encode(new_audio_bytes).decode('utf-8')
                        new_audio_duration = len(new_audio_bytes) / (16000 * 2)

                        # Skip if too short (< 0.8s)
                        if new_audio_duration < 0.8:
                            print(f"[STT Router] Skipping - new audio too short ({new_audio_duration:.1f}s)")
                            continue

                        # Build context prompt from conversation history
                        context_prompt = None
                        if session.get("conversation_history"):
                            recent_context = " ".join(session["conversation_history"][-3:])[-200:]
                            context_prompt = recent_context
                            print(f"[STT Router] 📝 Using context: {context_prompt[:50]}...")

                        # Transcribe with provider
                        result = await transcribe_with_provider(
                            audio_b64=new_audio_b64,
                            provider=session["provider"],
                            language=language_hint,
                            config=session["provider_config"],
                            context=context_prompt
                        )

                        new_text = result["text"].strip()
                        detected_lang = result.get("language", "auto")
                        session["detected_lang"] = detected_lang

                        # Strip ending punctuation from partials
                        ending_punctuation = ['.', '?', '!', '。', '？', '！']
                        while new_text and new_text[-1] in ending_punctuation:
                            new_text = new_text[:-1].strip()

                        # Filter hallucinations
                        hallucinations = [
                            "Napisy stworzone przez społeczność Amara.org",
                            "Subtitles by the Amara.org community",
                            "Thank you for watching",
                            "Dziękuję za uwagę",
                            "Dziękujemy za uwagę"
                        ]

                        if any(h.lower() in new_text.lower() for h in hallucinations):
                            print(f"[STT Router] ⚠ Filtered hallucination: {new_text}")
                            session["last_transcribed_length"] = len(session["accumulated_audio"])
                            continue

                        # Smart deduplication (remove context overlap)
                        if new_text and context_prompt:
                            new_words = new_text.split()
                            context_words = context_prompt.split()
                            overlap_count = 0
                            for i in range(min(len(new_words), len(context_words))):
                                context_word = context_words[-(i+1)] if i < len(context_words) else None
                                new_word = new_words[i] if i < len(new_words) else None
                                if context_word and new_word and context_word.lower() == new_word.lower():
                                    overlap_count += 1
                                else:
                                    break
                            if overlap_count > 0:
                                new_text = " ".join(new_words[overlap_count:])
                                print(f"[STT Router] 🔍 Removed {overlap_count} duplicate words")

                        # Append new text
                        if new_text:
                            if session["accumulated_text"]:
                                session["accumulated_text"] += " " + new_text
                            else:
                                session["accumulated_text"] = new_text

                        # Detect repetition (noise)
                        last_new_text = session.get("last_new_text", "")
                        is_repetition = (new_text == last_new_text) and len(new_text) > 3

                        if is_repetition:
                            session["no_change_count"] += 1
                            print(f"[STT Router] ⚠ Repetition detected (count={session['no_change_count']})")
                            if session["no_change_count"] >= 2:
                                print(f"[STT Router] ⚠ Skipping repetitive noise")
                                session["last_transcribed_length"] = len(session["accumulated_audio"])
                                session["last_new_text"] = new_text
                                continue
                        else:
                            session["no_change_count"] = 0

                        session["last_new_text"] = new_text
                        session["last_transcribed_length"] = len(session["accumulated_audio"])

                        # Publish partial event
                        stt_event = {
                            "type": "stt_partial",
                            "room_id": room,
                            "segment_id": session["segment_id"],
                            "revision": session["chunk_count"],
                            "text": session["accumulated_text"],
                            "lang": detected_lang,
                            "final": False,
                            "speech_final": False,
                            "ts_iso": None,
                            "device": device,
                            "speaker": speaker,
                            "target_lang": target_lang,
                            "provider": session["provider"]
                        }

                        await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                        print(f"[STT Router] ✓ Partial {session['segment_id']}: {session['accumulated_text'][:80]}...")

                except Exception as e:
                    print(f"[STT Router] ✗ Partial transcription failed: {e}")

            # FINAL TRANSCRIPTION: audio_chunk (from VAD)
            elif msg_type == "audio_chunk":
                audio_b64 = data.get("pcm16_base64", "")
                device = data.get("device", "web")

                audio_bytes = base64.b64decode(audio_b64)
                duration_sec = len(audio_bytes) / (16000 * 2)

                # Use existing segment if we have partials, otherwise create new
                if room in partial_sessions:
                    session = partial_sessions[room]
                    segment_id = session["segment_id"]
                    stored_speaker = session["speaker"]
                    stored_target_lang = session["target_lang"]
                    stored_language_hint = session.get("language_hint", language_hint)
                    stored_quality_tier = session.get("quality_tier", quality_tier)
                    print(f"[STT Router] Processing FINAL (finalizing partial): room={room} segment={segment_id}")
                else:
                    segment_id = await get_next_segment_id(r, room)
                    stored_speaker = speaker
                    stored_target_lang = target_lang
                    stored_language_hint = language_hint
                    stored_quality_tier = quality_tier
                    print(f"[STT Router] Processing FINAL (no partials): room={room} segment={segment_id}")

                try:
                    # Get provider for final mode
                    provider_config = await get_stt_provider_for_language(
                        language=stored_language_hint,
                        mode="final",
                        quality_tier=stored_quality_tier
                    )

                    # Transcribe with final provider (measure latency)
                    start_time = time.time()
                    result = await transcribe_with_provider(
                        audio_b64=audio_b64,
                        provider=provider_config["provider"],
                        language=stored_language_hint,
                        config=provider_config["config"]
                    )
                    latency_ms = int((time.time() - start_time) * 1000)

                    stt_event = {
                        "type": "stt_final",
                        "room_id": room,
                        "segment_id": segment_id,
                        "revision": 1,
                        "text": result["text"],
                        "lang": result.get("language", "auto"),
                        "final": True,
                        "speech_final": True,
                        "ts_iso": None,
                        "device": device,
                        "speaker": stored_speaker,
                        "target_lang": stored_target_lang,
                        "provider": provider_config["provider"]
                    }

                    await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                    print(f"[STT Router] ✓ Final segment {segment_id}: {result['text'][:80]}...")

                    # Track cost
                    cost_event = {
                        "room_id": room,
                        "pipeline": "stt",
                        "mode": provider_config["provider"],
                        "units": duration_sec,
                        "unit_type": "seconds",
                        "segment_id": segment_id
                    }
                    await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                    print(f"[STT Router] 💰 Cost tracked: {duration_sec:.1f}s ({provider_config['provider']}) seg={segment_id}")

                    # Track debug info (fire-and-forget)
                    await create_stt_debug_info(
                        redis=r,
                        segment_id=segment_id,
                        room_code=room,
                        stt_data={
                            "provider": provider_config["provider"],
                            "language": stored_language_hint,
                            "mode": "final",
                            "latency_ms": latency_ms,
                            "audio_duration_sec": duration_sec,
                            "text": result["text"]
                        },
                        routing_info={
                            "routing_reason": f"{stored_language_hint}/final/{stored_quality_tier} → {provider_config['provider']} (primary)",
                            "fallback_triggered": provider_config.get("fallback", False)
                        }
                    )

                    # Clear partial session
                    if room in partial_sessions:
                        del partial_sessions[room]

                except Exception as e:
                    print(f"[STT Router] ✗ Final transcription failed: {e}")

            # AUDIO SESSION END: audio_end
            elif msg_type == "audio_end":
                import time
                timestamp = time.time()
                print(f"[STT Router] 🛑 [{timestamp:.3f}] audio_end received for room={room}")

                if room in partial_sessions:
                    session = partial_sessions[room]

                    # DON'T close streaming connection - keep it persistent per room!
                    # Only close on disconnect or long timeout
                    # if session.get("streaming_connection"):
                    #     print(f"[STT Router] 🔌 Closing streaming connection for room={room}")
                    #     await streaming_manager.close_connection(room, session["provider"])

                    # Check if we have a streaming connection with finalized text
                    streaming_conn = session.get("streaming_connection")
                    print(f"[STT Router] 🔍 [{timestamp:.3f}] streaming_conn exists: {streaming_conn is not None}")
                    if streaming_conn:
                        print(f"[STT Router] 🔍 [{timestamp:.3f}]   - segment_id: {streaming_conn.segment_id}")
                        print(f"[STT Router] 🔍 [{timestamp:.3f}]   - finalized_text: '{streaming_conn.finalized_text[:80] if streaming_conn.finalized_text else '(empty)'}'")
                        print(f"[STT Router] 🔍 [{timestamp:.3f}]   - accumulated_text: '{streaming_conn.accumulated_text[:80] if streaming_conn.accumulated_text else '(empty)'}'")

                    # For streaming providers, send a "finalization marker" event
                    # The last partial contains the complete text, we just mark it as finalized
                    if streaming_conn and hasattr(streaming_conn, 'finalized_text'):
                        # Get the last partial text (finalized + partial combined)
                        last_partial_text = streaming_conn.accumulated_text.strip()
                        print(f"[STT Router] 📊 [{timestamp:.3f}] Streaming session ended - sending finalization marker for: {last_partial_text[:80]}...")

                        # IMPORTANT: Send stt_final event with accumulated text to trigger final translation
                        # This ensures any remaining buffered text gets translated when user stops speaking
                        if last_partial_text:
                            final_event = {
                                "type": "stt_final",
                                "room_id": room,
                                "segment_id": session["segment_id"],
                                "revision": session["chunk_count"],
                                "text": last_partial_text,
                                "lang": session.get("detected_lang", session.get("language_hint", "auto")),
                                "speaker": session.get("speaker", "system"),
                                "target_lang": session.get("target_lang", "en"),
                                "device": data.get("device", "web"),
                                "provider": session.get("provider", "unknown"),
                                "final": True,
                                "speech_final": True,
                                "ts_iso": datetime.utcnow().isoformat() + "Z"
                            }
                            await r.publish(STT_OUTPUT_EVENTS, jdumps(final_event))
                            print(f"[STT Router] 🏁 [{timestamp:.3f}] Sent stt_final event to trigger final translation")

                        # Send finalization marker event (tells frontend the last partial is now final)
                        finalization_event = {
                            "type": "stt_finalize",
                            "room_id": room,
                            "segment_id": session["segment_id"],
                            "revision": session["chunk_count"],
                            "final": True,
                            "processing": False
                        }
                        await r.publish(STT_OUTPUT_EVENTS, jdumps(finalization_event))

                        # Track costs
                        audio_duration = len(session["accumulated_audio"]) / (16000 * 2)
                        cost_event = {
                            "room_id": room,
                            "pipeline": "stt",
                            "provider": session["provider"],
                            "mode": "final",
                            "units": audio_duration,
                            "unit_type": "seconds",
                            "segment_id": session["segment_id"]
                        }
                        await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                        print(f"[STT Router] 💰 [{timestamp:.3f}] Cost tracked: {audio_duration:.1f}s ({session['provider']}) seg={session['segment_id']}")

                        # Track debug info (fire-and-forget)
                        final_text = streaming_conn.finalized_text if streaming_conn and streaming_conn.finalized_text else last_partial_text

                        # Check if fallback was triggered for this session
                        fallback_triggered = "fallback_error" in session
                        routing_reason = f"{session.get('language_hint', 'auto')}/streaming/{session.get('quality_tier', 'standard')} → {session['provider']}"
                        if fallback_triggered:
                            routing_reason += f" (fallback from {session.get('fallback_from_provider', 'unknown')})"
                        else:
                            routing_reason += " (streaming)"

                        await create_stt_debug_info(
                            redis=r,
                            segment_id=session["segment_id"],
                            room_code=room,
                            stt_data={
                                "provider": session["provider"],
                                "language": session.get("detected_lang", session.get("language_hint", "auto")),
                                "mode": "streaming",
                                "latency_ms": 0,  # N/A for streaming mode (real-time)
                                "audio_duration_sec": audio_duration,
                                "text": final_text
                            },
                            routing_info={
                                "routing_reason": routing_reason,
                                "fallback_triggered": fallback_triggered,
                                "fallback_error": session.get("fallback_error"),
                                "fallback_from_provider": session.get("fallback_from_provider")
                            }
                        )

                        # Save accumulated text before resetting - use for content-based blocking of late finals
                        # Use accumulated_text (not finalized_text) because it includes partials that may arrive as late finals
                        # This will be used to block late AddTranscript events that arrive after the new segment starts
                        if streaming_conn.accumulated_text:
                            # Clear previous_segment_text from the PREVIOUS audio_end cycle
                            # Then save the current accumulated text as the new previous_segment_text
                            old_previous = streaming_conn.previous_segment_text
                            streaming_conn.previous_segment_text = streaming_conn.accumulated_text.strip()
                            print(f"[STT Router] 💾 [{timestamp:.3f}] Updated blocking text (from accumulated): '{streaming_conn.previous_segment_text[:80]}...'")
                            if old_previous:
                                print(f"[STT Router] 🗑️  [{timestamp:.3f}] Cleared old blocking text: '{old_previous[:50]}...'")
                        elif streaming_conn.finalized_text:
                            # Fallback to finalized_text if accumulated_text is empty
                            old_previous = streaming_conn.previous_segment_text
                            streaming_conn.previous_segment_text = streaming_conn.finalized_text.strip()
                            print(f"[STT Router] 💾 [{timestamp:.3f}] Updated blocking text (from finalized): '{streaming_conn.previous_segment_text[:80]}...'")
                            if old_previous:
                                print(f"[STT Router] 🗑️  [{timestamp:.3f}] Cleared old blocking text: '{old_previous[:50]}...'")
                        else:
                            print(f"[STT Router] ⚠️  [{timestamp:.3f}] No text to save for blocking (both accumulated and finalized empty)")

                        # Reset finalized text for next sentence (even within same segment)
                        print(f"[STT Router] 🔄 [{timestamp:.3f}] Resetting finalized text for next utterance")
                        print(f"[STT Router] 🔄 [{timestamp:.3f}]   - BEFORE: finalized='{streaming_conn.finalized_text[:50] if streaming_conn.finalized_text else '(empty)'}', accum='{streaming_conn.accumulated_text[:50] if streaming_conn.accumulated_text else '(empty)'}'")
                        streaming_conn.finalized_text = ""
                        streaming_conn.accumulated_text = ""
                        streaming_conn.revision = 0

                        # CRITICAL: Freeze last_audio_end_time at audio_end AND set flag
                        # Any AddTranscript that arrives after this point within 1.5s should be blocked
                        if hasattr(streaming_conn, 'last_audio_end_time') and streaming_conn.last_audio_end_time is not None:
                            streaming_conn.audio_has_ended = True  # Enable threshold blocking
                            print(f"[STT Router] 🔒 [{timestamp:.3f}] Audio ended - last_audio_end_time FROZEN at {streaming_conn.last_audio_end_time:.2f}s")
                            print(f"[STT Router] 🔒 [{timestamp:.3f}] Threshold blocking ENABLED - will block AddTranscript within 1.5s of cutoff")
                            print(f"[STT Router] 🔒 [{timestamp:.3f}] Any future AddTranscript with end_time <= {streaming_conn.last_audio_end_time + 1.5:.2f}s will be blocked")

                        print(f"[STT Router] 🔄 [{timestamp:.3f}]   - AFTER: finalized='{streaming_conn.finalized_text}', accum='{streaming_conn.accumulated_text}'")

                        # Skip batch refinement for streaming providers
                        # No separate final event needed - finalization marker is enough

                    elif session["accumulated_audio"] and len(session["accumulated_audio"]) > 0:
                        # Fallback: use batch API for non-streaming providers
                        audio_duration = len(session["accumulated_audio"]) / (16000 * 2)

                        # Send instant result
                        instant_text = session["accumulated_text"].strip()
                        if instant_text:
                            print(f"[STT Router] ⚡ Sending instant result: {instant_text[:80]}...")
                            instant_event = {
                                "type": "stt_final",
                                "room_id": room,
                                "segment_id": session["segment_id"],
                                "revision": session["chunk_count"],
                                "text": instant_text,
                                "lang": session.get("detected_lang", "auto"),
                                "final": True,
                                "processing": True,
                                "ts_iso": None,
                                "device": "web",
                                "speaker": session["speaker"],
                                "target_lang": session["target_lang"],
                                "provider": session["provider"]
                            }
                            await r.publish(STT_OUTPUT_EVENTS, jdumps(instant_event))

                        # Background quality refinement with final provider
                        print(f"[STT Router] 🎯 Background refinement with final provider...")

                        try:
                            full_audio_b64 = base64.b64encode(session["accumulated_audio"]).decode('utf-8')
                            language_hint = session.get("language_hint", "auto")
                            quality_tier = session.get("quality_tier", DEFAULT_QUALITY_TIER)

                            # Get final provider (may be different from partial provider)
                            provider_config = await get_stt_provider_for_language(
                                language=language_hint,
                                mode="final",
                                quality_tier=quality_tier
                            )

                            # Measure latency for quality refinement
                            refine_start_time = time.time()
                            result = await transcribe_with_provider(
                                audio_b64=full_audio_b64,
                                provider=provider_config["provider"],
                                language=language_hint,
                                config=provider_config["config"]
                            )
                            refine_latency_ms = int((time.time() - refine_start_time) * 1000)

                            final_text = result["text"].strip()
                            detected_lang = result.get("language", session.get("detected_lang", "auto"))

                            # Send update if different
                            if final_text != instant_text:
                                print(f"[STT Router] ✨ Quality improved: {final_text[:80]}...")
                                quality_event = {
                                    "type": "stt_final",
                                    "room_id": room,
                                    "segment_id": session["segment_id"],
                                    "revision": session["chunk_count"] + 1,
                                    "text": final_text,
                                    "lang": detected_lang,
                                    "final": True,
                                    "processing": False,
                                    "ts_iso": None,
                                    "device": "web",
                                    "speaker": session["speaker"],
                                    "target_lang": session["target_lang"],
                                    "provider": provider_config["provider"]
                                }
                                await r.publish(STT_OUTPUT_EVENTS, jdumps(quality_event))
                            else:
                                print(f"[STT Router] ✓ Quality version same - sending completion")
                                complete_event = {
                                    "type": "stt_final",
                                    "room_id": room,
                                    "segment_id": session["segment_id"],
                                    "revision": session["chunk_count"] + 1,
                                    "text": instant_text,
                                    "lang": detected_lang,
                                    "final": True,
                                    "processing": False,
                                    "ts_iso": None,
                                    "device": "web",
                                    "speaker": session["speaker"],
                                    "target_lang": session["target_lang"],
                                    "provider": provider_config["provider"]
                                }
                                await r.publish(STT_OUTPUT_EVENTS, jdumps(complete_event))
                                final_text = instant_text

                            # Track cost
                            cost_event = {
                                "room_id": room,
                                "pipeline": "stt",
                                "mode": provider_config["provider"],
                                "units": audio_duration,
                                "unit_type": "seconds",
                                "segment_id": session["segment_id"]
                            }
                            await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                            print(f"[STT Router] 💰 Cost tracked: {audio_duration:.1f}s ({provider_config['provider']}) seg={session['segment_id']}")

                            # Track debug info (fire-and-forget)
                            await create_stt_debug_info(
                                redis=r,
                                segment_id=session["segment_id"],
                                room_code=room,
                                stt_data={
                                    "provider": provider_config["provider"],
                                    "language": language_hint,
                                    "mode": "final",
                                    "latency_ms": refine_latency_ms,
                                    "audio_duration_sec": audio_duration,
                                    "text": final_text
                                },
                                routing_info={
                                    "routing_reason": f"{language_hint}/final/{quality_tier} → {provider_config['provider']} (quality refinement)",
                                    "fallback_triggered": provider_config.get("fallback", False)
                                }
                            )

                            # Add to conversation history
                            if final_text and len(final_text) > 10:
                                if "conversation_history" not in session:
                                    session["conversation_history"] = []
                                session["conversation_history"].append(final_text)
                                if len(session["conversation_history"]) > 5:
                                    session["conversation_history"] = session["conversation_history"][-5:]
                                print(f"[STT Router] 📚 Added to conversation history ({len(session['conversation_history'])} sentences)")

                        except Exception as e:
                            print(f"[STT Router] ✗ Quality refinement failed: {e}")

                    # Clear session
                    del partial_sessions[room]
                    print(f"[STT Router] Session cleared for room={room}")

        except Exception as e:
            print(f"[STT Router] Error processing message: {e}")


async def main():
    """Run router loop and cache invalidation listener concurrently."""
    await asyncio.gather(
        router_loop(),
        cache_invalidation_listener()
    )


if __name__ == "__main__":
    asyncio.run(main())

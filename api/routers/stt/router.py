import os
import asyncio
import base64
import redis.asyncio as redis
try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

from openai_backend import transcribe_audio_chunk
from settings_fetcher import get_room_stt_settings, init_db_pool, clear_cache, CACHE_CLEAR_CHANNEL

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
INPUT_CHANNEL = os.getenv("STT_INPUT_CHANNEL", "stt_input")
OUTPUT_CHANNEL = os.getenv("STT_OUTPUT_CHANNEL", "stt_local_in")
DEFAULT_STT_MODE = os.getenv("LT_STT_PARTIAL_MODE", "local")  # Renamed to DEFAULT
STT_OUTPUT_EVENTS = os.getenv("STT_OUTPUT_EVENTS", "stt_events")
COST_TRACKING_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")

print(f"[STT Router] Starting...")
print(f"  Default Mode: {DEFAULT_STT_MODE}")
print(f"  Input:  {INPUT_CHANNEL}")
print(f"  Output: {OUTPUT_CHANNEL if DEFAULT_STT_MODE == 'local' else STT_OUTPUT_EVENTS}")
print(f"  Settings: Room-specific settings will be fetched from database")

# Track current partial accumulation per room
partial_sessions = {}  # room -> {segment_id, accumulated_text, speaker, target_lang}

async def get_next_segment_id(r: redis.Redis, room: str) -> int:
    """Get and increment segment counter for a room, stored in Redis"""
    key = f"room:{room}:segment_counter"
    segment_id = await r.incr(key)
    return segment_id

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
            room_code = data.get("room_code") if isinstance(data, dict) else None

            if room_code:
                clear_cache(room_code)
                print(f"[STT Router] 🔄 Cache cleared for room: {room_code}")
            else:
                clear_cache()  # Clear all caches
                print(f"[STT Router] 🔄 All caches cleared (global settings updated)")
        except Exception as e:
            print(f"[STT Router] Cache clear error: {e}")

async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(INPUT_CHANNEL)

    # Initialize database pool for settings
    await init_db_pool()

    print(f"[STT Router] Listening on {INPUT_CHANNEL}")
    
    async for msg in pubsub.listen():
        if not msg or msg.get("type") != "message":
            continue

        try:
            data = jloads(msg["data"])
            msg_type = data.get("type", "")
            room = data.get("room_id", "unknown")
            speaker = data.get("speaker", "system")
            target_lang = data.get("target_lang", "en")

            # Fetch room-specific STT settings
            partial_mode, final_mode = await get_room_stt_settings(room)

            # LOCAL MODE: Forward all messages directly to local STT worker
            if partial_mode == "local":
                print(f"[STT Router] Forwarding {msg_type} to {OUTPUT_CHANNEL} for room={room} (mode=local)")
                await r.publish(OUTPUT_CHANNEL, jdumps(data))
                continue

            if msg_type == "audio_chunk_partial" and partial_mode == "openai_chunked":
                # Handle partial transcription - accumulate in same segment
                seq = data.get("seq", 0)
                audio_b64 = data.get("pcm16_base64", "")
                device = data.get("device", "web")
                language_hint = data.get("language", "auto")  # Get language preference from frontend

                # Filter out invalid language values from frontend
                if language_hint in [None, "undefined", "null", ""]:
                    language_hint = "auto"

                audio_bytes = base64.b64decode(audio_b64)
                duration_sec = len(audio_bytes) / (16000 * 2)

                # Initialize or get existing partial session
                if room not in partial_sessions:
                    segment_id = await get_next_segment_id(r, room)
                    partial_sessions[room] = {
                        "segment_id": segment_id,
                        "last_transcribed_length": 0,  # Track how much audio we've already transcribed
                        "accumulated_audio": b"",  # Accumulate audio bytes
                        "accumulated_text": "",
                        "chunk_count": 0,
                        "speaker": speaker,
                        "target_lang": target_lang,
                        "language_hint": language_hint,
                        "last_audio_end_time": 0.0,  # Track the timestamp where we last stopped (for deduplication)
                        "no_change_count": 0,  # Track how many times text hasn't changed
                        "last_new_text": "",  # Track the last new_text fragment to detect repetition
                        "conversation_history": []  # Track last few finalized sentences for context
                    }

                session = partial_sessions[room]
                session["chunk_count"] += 1
                session["target_lang"] = target_lang  # Update if changed
                session["language_hint"] = language_hint  # Update if changed

                # Accumulate audio bytes, but cap at 30 seconds to avoid OpenAI file size limit
                MAX_AUDIO_SECONDS = 30
                MAX_AUDIO_BYTES = MAX_AUDIO_SECONDS * 16000 * 2  # 30s at 16kHz mono 16-bit

                session["accumulated_audio"] += audio_bytes

                # Trim from the beginning if we exceed the max
                if len(session["accumulated_audio"]) > MAX_AUDIO_BYTES:
                    trim_amount = len(session["accumulated_audio"]) - MAX_AUDIO_BYTES
                    session["accumulated_audio"] = session["accumulated_audio"][-MAX_AUDIO_BYTES:]
                    # Adjust last_transcribed_length since we trimmed the beginning
                    session["last_transcribed_length"] = max(0, session["last_transcribed_length"] - trim_amount)

                new_audio_len = len(session["accumulated_audio"])

                print(f"[STT Router] Processing PARTIAL: room={room} speaker={speaker} segment={session['segment_id']} chunk={session['chunk_count']} lang_hint={language_hint} total_audio={new_audio_len/32000:.1f}s target={target_lang}")

                try:
                    # OPTIMIZATION: Only transcribe NEW audio since last transcription
                    # This is 10-20x faster than re-transcribing the entire buffer
                    new_audio_bytes = session["accumulated_audio"][session["last_transcribed_length"]:]
                    new_audio_b64 = base64.b64encode(new_audio_bytes).decode('utf-8')
                    new_audio_duration = len(new_audio_bytes) / (16000 * 2)

                    # Skip transcription if new audio is too short (< 0.8s) to avoid hallucinations
                    if new_audio_duration < 0.8:
                        print(f"[STT Router] Skipping transcription - new audio too short ({new_audio_duration:.1f}s)")
                        continue

                    # USE CONVERSATION CONTEXT for better accuracy
                    # Build prompt from last 2-3 finalized sentences
                    context_prompt = None
                    if session.get("conversation_history"):
                        # Use last 2-3 sentences (max 200 chars to stay under 224 token limit)
                        recent_context = " ".join(session["conversation_history"][-3:])[-200:]
                        context_prompt = recent_context
                        print(f"[STT Router] 📝 Using context: {context_prompt[:50]}...")

                    result = await transcribe_audio_chunk(new_audio_b64, language=language_hint, prompt=context_prompt)
                    new_text = result["text"].strip()

                    # Store detected language in session
                    detected_lang = result.get("language", "auto")
                    session["detected_lang"] = detected_lang

                    # STRIP ENDING PUNCTUATION from partials
                    # Whisper adds periods/question marks thinking each chunk is complete
                    # Only keep ending punctuation on the final transcription
                    ending_punctuation = ['.', '?', '!', '。', '？', '！']
                    while new_text and new_text[-1] in ending_punctuation:
                        new_text = new_text[:-1].strip()
                        print(f"[STT Router] 🔧 Removed ending punctuation from partial chunk")

                    # Filter out common Whisper hallucinations
                    hallucinations = [
                        "Napisy stworzone przez społeczność Amara.org",
                        "Subtitles by the Amara.org community",
                        "Thank you for watching",
                        "Dziękuję za uwagę",
                        "Dziękujemy za uwagę"
                    ]

                    is_hallucination = any(h.lower() in new_text.lower() for h in hallucinations)

                    if is_hallucination:
                        print(f"[STT Router] ⚠ Filtered hallucination: {new_text}")
                        # Don't append, but update position so we don't re-process this audio
                        session["last_transcribed_length"] = len(session["accumulated_audio"])
                        continue

                    # SMART DEDUPLICATION: Remove context words that leaked from prompt
                    if new_text and context_prompt:
                        # Check if new_text starts with words from the prompt context
                        new_words = new_text.split()
                        context_words = context_prompt.split()

                        # Find longest matching prefix (words from context appearing at start of new_text)
                        overlap_count = 0
                        for i in range(min(len(new_words), len(context_words))):
                            # Check from end of context
                            context_word = context_words[-(i+1)] if i < len(context_words) else None
                            new_word = new_words[i] if i < len(new_words) else None

                            if context_word and new_word and context_word.lower() == new_word.lower():
                                overlap_count += 1
                            else:
                                break

                        if overlap_count > 0:
                            new_text = " ".join(new_words[overlap_count:])
                            print(f"[STT Router] 🔍 Removed {overlap_count} duplicate words from context")

                    # Append new text to accumulated text
                    if new_text:
                        if session["accumulated_text"]:
                            session["accumulated_text"] += " " + new_text
                        else:
                            session["accumulated_text"] = new_text

                    # Detect if text stopped changing (noise/silence being transcribed)
                    # Check if new_text is the same as last iteration (indicates repeating noise)
                    last_new_text = session.get("last_new_text", "")
                    is_repetition = (new_text == last_new_text) and len(new_text) > 3

                    if is_repetition:
                        session["no_change_count"] += 1
                        print(f"[STT Router] ⚠ Repetition detected (count={session['no_change_count']}) - new_text='{new_text[:50]}'")
                        if session["no_change_count"] >= 2:  # Reduced from 3 to 2 - stop repetitions faster
                            print(f"[STT Router] ⚠ Text repeating for {session['no_change_count']} iterations, likely noise - skipping broadcast")
                            # Still update position to avoid re-processing
                            session["last_transcribed_length"] = len(session["accumulated_audio"])
                            session["last_new_text"] = new_text  # Update for next check
                            continue
                    else:
                        session["no_change_count"] = 0  # Reset counter when text changes

                    # Update last_new_text for next iteration
                    session["last_new_text"] = new_text

                    # Update the position for next iteration
                    session["last_transcribed_length"] = len(session["accumulated_audio"])

                    stt_event = {
                        "type": "stt_partial",
                        "room_id": room,
                        "segment_id": session["segment_id"],
                        "revision": session["chunk_count"],
                        "text": session["accumulated_text"],
                        "lang": detected_lang,
                        "final": False,
                        "ts_iso": None,
                        "device": device,
                        "speaker": speaker,
                        "target_lang": target_lang
                    }

                    await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                    print(f"[STT Router] ✓ Partial {session['segment_id']}: {session['accumulated_text'][:80]}...")

                    # Note: Cost tracking happens only on finalization (audio_end) to avoid double-counting

                except Exception as e:
                    print(f"[STT Router] ✗ Partial transcription failed: {e}")
                    
            elif msg_type == "audio_chunk":
                # Handle final transcription (from VAD) - uses final_mode
                # Check if final transcription is disabled
                if final_mode == "none":
                    print(f"[STT Router] Skipping final transcription (mode=none) for room={room}")
                    if room in partial_sessions:
                        del partial_sessions[room]
                    continue

                # If final mode is "local", forward to local worker
                if final_mode == "local":
                    print(f"[STT Router] Forwarding final to local worker for room={room}")
                    await r.publish(OUTPUT_CHANNEL, jdumps(data))
                    if room in partial_sessions:
                        del partial_sessions[room]
                    continue

                # Otherwise use OpenAI for finals (openai_chunked mode or openai final mode)
                seq = data.get("seq", 0)
                audio_b64 = data.get("pcm16_base64", "")
                device = data.get("device", "web")
                language_hint = data.get("language", "auto")  # Get language preference from frontend

                # Filter out invalid language values from frontend
                if language_hint in [None, "undefined", "null", ""]:
                    language_hint = "auto"

                audio_bytes = base64.b64decode(audio_b64)
                duration_sec = len(audio_bytes) / (16000 * 2)

                # Use existing segment if we have partials, otherwise create new
                if room in partial_sessions:
                    segment_id = partial_sessions[room]["segment_id"]
                    stored_speaker = partial_sessions[room]["speaker"]
                    stored_target_lang = partial_sessions[room]["target_lang"]
                    stored_language_hint = partial_sessions[room].get("language_hint", language_hint)
                    print(f"[STT Router] Processing FINAL with {final_mode} (finalizing partial): room={room} speaker={stored_speaker} segment={segment_id}")
                else:
                    segment_id = await get_next_segment_id(r, room)
                    stored_speaker = speaker
                    stored_target_lang = target_lang
                    stored_language_hint = language_hint
                    print(f"[STT Router] Processing FINAL with {final_mode} (no partials): room={room} speaker={speaker} segment={segment_id}")

                try:
                    result = await transcribe_audio_chunk(audio_b64, language=stored_language_hint)
                    
                    stt_event = {
                        "type": "stt_final",
                        "room_id": room,
                        "segment_id": segment_id,
                        "revision": 1,
                        "text": result["text"],
                        "lang": result.get("language", "auto"),
                        "final": True,
                        "ts_iso": None,
                        "device": device,
                        "speaker": stored_speaker,
                        "target_lang": stored_target_lang
                    }
                    
                    await r.publish(STT_OUTPUT_EVENTS, jdumps(stt_event))
                    print(f"[STT Router] ✓ Final segment {segment_id}: {result['text'][:80]}...")
                    
                    # Track cost (only for paid services)
                    if final_mode in ["openai", "openai_chunked", "elevenlabs"]:
                        cost_event = {
                            "room_id": room,
                            "pipeline": "stt",
                            "mode": final_mode,
                            "units": duration_sec,
                            "unit_type": "seconds"
                        }
                        await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                        print(f"[STT Router] 💰 Cost tracked: {duration_sec:.1f}s audio ({final_mode})")
                    
                    # Clear partial session
                    if room in partial_sessions:
                        del partial_sessions[room]
                    
                except Exception as e:
                    print(f"[STT Router] ✗ Final transcription failed: {e}")
                    
            elif msg_type == "audio_end":
                print(f"[STT Router] Audio session ended for room={room}")
                # Finalize any pending partial before clearing
                if room in partial_sessions:
                    session = partial_sessions[room]
                    if session["accumulated_audio"] and len(session["accumulated_audio"]) > 0:
                        audio_duration = len(session["accumulated_audio"]) / (16000 * 2)

                        # PARALLEL PROCESSING: Send partial immediately, then refine in background
                        # Step 1: Immediately send the accumulated partial text (INSTANT FEEDBACK)
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
                                "processing": True,  # Indicate background refinement in progress
                                "ts_iso": None,
                                "device": "web",
                                "speaker": session["speaker"],
                                "target_lang": session["target_lang"]
                            }
                            await r.publish(STT_OUTPUT_EVENTS, jdumps(instant_event))

                        # Step 2: Re-transcribe in background for quality (NON-BLOCKING)
                        # Check final_mode to decide which backend to use
                        if final_mode == "none":
                            print(f"[STT Router] ⏭ Skipping background refinement (mode=none)")
                            # Just send completion event
                            complete_event = {
                                "type": "stt_final",
                                "room_id": room,
                                "segment_id": session["segment_id"],
                                "revision": session["chunk_count"] + 1,
                                "text": instant_text,
                                "lang": session.get("detected_lang", "auto"),
                                "final": True,
                                "processing": False,
                                "ts_iso": None,
                                "device": "web",
                                "speaker": session["speaker"],
                                "target_lang": session["target_lang"]
                            }
                            await r.publish(STT_OUTPUT_EVENTS, jdumps(complete_event))
                            del partial_sessions[room]
                            continue

                        if final_mode == "local":
                            print(f"[STT Router] 🎯 Forwarding to local worker for background quality refinement...")
                            # Forward accumulated audio to local worker for processing
                            full_audio_b64 = base64.b64encode(session["accumulated_audio"]).decode('utf-8')
                            local_event = {
                                "type": "audio_chunk",
                                "room_id": room,
                                "seq": session["chunk_count"],
                                "pcm16_base64": full_audio_b64,
                                "speaker": session["speaker"],
                                "target_lang": session["target_lang"],
                                "device": "web",
                                "language": session.get("language_hint", "auto")
                            }
                            await r.publish(OUTPUT_CHANNEL, jdumps(local_event))
                            del partial_sessions[room]
                            continue

                        # Otherwise use OpenAI for background refinement
                        print(f"[STT Router] 🎯 Background re-transcribing with {final_mode} for quality...")

                        try:
                            full_audio_b64 = base64.b64encode(session["accumulated_audio"]).decode('utf-8')
                            language_hint = session.get("language_hint", "auto")

                            # Transcribe the FULL audio with NO prompt for clean result
                            result = await transcribe_audio_chunk(full_audio_b64, language=language_hint, prompt=None)
                            final_text = result["text"].strip()
                            detected_lang = result.get("language", session.get("detected_lang", "auto"))

                            # Only send update if quality version is different
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
                                    "processing": False,  # Processing complete
                                    "ts_iso": None,
                                    "device": "web",
                                    "speaker": session["speaker"],
                                    "target_lang": session["target_lang"]
                                }
                                await r.publish(STT_OUTPUT_EVENTS, jdumps(quality_event))
                            else:
                                print(f"[STT Router] ✓ Quality version same as instant - sending completion event")
                                # Send event to clear processing indicator even if text unchanged
                                complete_event = {
                                    "type": "stt_final",
                                    "room_id": room,
                                    "segment_id": session["segment_id"],
                                    "revision": session["chunk_count"] + 1,
                                    "text": instant_text,
                                    "lang": detected_lang,
                                    "final": True,
                                    "processing": False,  # Processing complete
                                    "ts_iso": None,
                                    "device": "web",
                                    "speaker": session["speaker"],
                                    "target_lang": session["target_lang"]
                                }
                                await r.publish(STT_OUTPUT_EVENTS, jdumps(complete_event))
                                final_text = instant_text  # Use instant for history

                            # Track cost for the accumulated audio (only for paid services)
                            if final_mode in ["openai", "openai_chunked", "elevenlabs"]:
                                cost_event = {
                                    "room_id": room,
                                    "pipeline": "stt",
                                    "mode": final_mode,
                                    "units": audio_duration,
                                    "unit_type": "seconds"
                                }
                                await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))
                                print(f"[STT Router] 💰 Cost tracked: {audio_duration:.1f}s audio ({final_mode})")

                            # ADD TO CONVERSATION HISTORY for context in next sentences
                            if final_text and len(final_text) > 10:  # Only meaningful sentences
                                # Keep last 5 sentences max
                                if "conversation_history" not in session:
                                    session["conversation_history"] = []
                                session["conversation_history"].append(final_text)
                                if len(session["conversation_history"]) > 5:
                                    session["conversation_history"] = session["conversation_history"][-5:]
                                print(f"[STT Router] 📚 Added to conversation history ({len(session['conversation_history'])} sentences)")

                        except Exception as e:
                            print(f"[STT Router] ✗ Quality re-transcription failed: {e}")
                            # Already sent instant result, so no fallback needed

                    # IMPORTANT: Delete the session to start fresh for next sentence
                    del partial_sessions[room]
                    print(f"[STT Router] Session cleared for room={room}, ready for next sentence")
                
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

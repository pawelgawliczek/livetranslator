import os
import asyncio
import httpx
import redis.asyncio as redis
from datetime import datetime, timedelta
try:
    import orjson
    def jdumps(x): return orjson.dumps(x).decode()
    def jloads(b): return orjson.loads(b)
except:
    import json
    def jdumps(x): return json.dumps(x)
    def jloads(b): return json.loads(b if isinstance(b, str) else b.decode())

from openai_backend import translate_text as openai_translate
import deepl_backend
import google_backend
import amazon_backend

# Import debug tracker
from debug_tracker import append_mt_debug_info, append_mt_skip_reason

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
STT_EVENTS = os.getenv("STT_EVENTS_CHANNEL", "stt_events")
MT_OUTPUT = os.getenv("MT_OUTPUT_CHANNEL", "mt_events")
MT_MODE_PARTIAL = os.getenv("LT_MT_MODE_PARTIAL", "local")
MT_MODE_FINAL = os.getenv("LT_MT_MODE_FINAL", "openai")
DEFAULT_TGT = os.getenv("LT_DEFAULT_TGT", "en")
COST_TRACKING_CHANNEL = os.getenv("COST_TRACKING_CHANNEL", "cost_events")
MT_WORKER_URL = os.getenv("LT_MT_BASE_URL", "http://mt_worker:8081")

# Database config
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "lt_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "livetranslator")

# Routing cache - stores (src, tgt, quality_tier) -> (primary, fallback)
routing_cache = {}
routing_cache_expiry = None
CACHE_TTL_SECONDS = 300  # 5 minutes

# Partial translation cache - stores (room, segment, src_lang, tgt_lang, text) -> translation_result
# This prevents translating the same partial text multiple times
partial_translation_cache = {}

# Arabic translation throttling - stores (room, segment, tgt_lang) -> last_translation_timestamp
# This prevents translating Arabic partials too frequently (GPT-4o is expensive)
arabic_translation_throttle = {}
ARABIC_THROTTLE_SECONDS = float(os.getenv("ARABIC_THROTTLE_SECONDS", "2.0"))  # Configurable throttle interval

print(f"[MT Router] Starting...")
print(f"  Partial Mode: {MT_MODE_PARTIAL}")
print(f"  Final Mode:   {MT_MODE_FINAL}")
print(f"  Input:        {STT_EVENTS}")
print(f"  Output:       {MT_OUTPUT}")
print(f"  Default Target: {DEFAULT_TGT}")
print(f"  MT Worker:    {MT_WORKER_URL}")
print(f"[MT Router] Database-driven routing enabled with {CACHE_TTL_SECONDS}s cache")
print(f"[MT Router] Partial translation caching enabled (saves costs on duplicate partials)")
print(f"[MT Router] Arabic translation throttling: {ARABIC_THROTTLE_SECONDS}s interval")

def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token"""
    return max(1, len(text) // 4)

def normalize_lang(lang: str) -> str:
    """Normalize language code to 2-letter format"""
    if not lang:
        return "auto"

    # Keep 'auto' as-is (don't default to 'en')
    if lang == "auto":
        return "auto"

    lang_lower = lang.lower()

    # Map common variations
    if "eng" in lang_lower or lang_lower == "en":
        return "en"
    elif "pol" in lang_lower or lang_lower == "pl":
        return "pl"
    elif "ara" in lang_lower or "arab" in lang_lower or lang_lower == "ar":
        return "ar"

    # Return first 2 chars as fallback
    return lang[:2].lower()

# Multi-speaker translation routing cache - stores room_code -> (is_multi_speaker, room_id, speakers_dict)
multi_speaker_cache = {}
multi_speaker_cache_expiry = {}
MULTI_SPEAKER_CACHE_TTL_SECONDS = 60  # Cache for 1 minute

async def check_multi_speaker_mode(room_code: str) -> tuple:
    """
    Check if a room is in multi-speaker mode and get speaker info.

    Returns:
        tuple: (is_multi_speaker: bool, room_id: int or None, speakers_dict: dict or None)
        speakers_dict format: {speaker_id: {"language": "en", "display_name": "Alice"}}
    """
    # Check cache first
    if room_code in multi_speaker_cache:
        cache_expiry = multi_speaker_cache_expiry.get(room_code)
        if cache_expiry and datetime.now() < cache_expiry:
            return multi_speaker_cache[room_code]

    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )

        # Query room to check if speakers are locked
        room_row = await conn.fetchrow("""
            SELECT id, speakers_locked
            FROM rooms
            WHERE code = $1
        """, room_code)

        if not room_row or not room_row['speakers_locked']:
            await conn.close()
            result = (False, None, None)
            # Cache negative result too
            multi_speaker_cache[room_code] = result
            multi_speaker_cache_expiry[room_code] = datetime.now() + timedelta(seconds=MULTI_SPEAKER_CACHE_TTL_SECONDS)
            return result

        room_id = room_row['id']

        # Get all speakers for this room
        speaker_rows = await conn.fetch("""
            SELECT speaker_id, language, display_name
            FROM room_speakers
            WHERE room_id = $1
            ORDER BY speaker_id
        """, room_id)

        await conn.close()

        # Build speakers dictionary
        speakers_dict = {}
        for row in speaker_rows:
            speakers_dict[row['speaker_id']] = {
                "language": row['language'],
                "display_name": row['display_name']
            }

        result = (True, room_id, speakers_dict)

        # Cache result
        multi_speaker_cache[room_code] = result
        multi_speaker_cache_expiry[room_code] = datetime.now() + timedelta(seconds=MULTI_SPEAKER_CACHE_TTL_SECONDS)

        return result

    except Exception as e:
        print(f"[MT Router] Error checking multi-speaker mode for room {room_code}: {e}")
        return (False, None, None)

def get_multi_speaker_translation_targets(speakers_dict: dict, current_speaker_id: int) -> list:
    """
    Get translation targets for multi-speaker mode.

    Args:
        speakers_dict: Dictionary of speakers {speaker_id: {"language": "en", "display_name": "Alice"}}
        current_speaker_id: Current speaker's ID

    Returns:
        list: List of dicts with keys: speaker_id, language, display_name (excluding current speaker)
    """
    targets = []
    for spk_id, spk_info in speakers_dict.items():
        if spk_id != current_speaker_id:
            targets.append({
                "speaker_id": spk_id,
                "language": spk_info["language"],
                "display_name": spk_info["display_name"]
            })
    return targets

async def load_routing_config_from_db():
    """Load all routing configuration from database into cache."""
    global routing_cache, routing_cache_expiry

    try:
        import asyncpg

        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database=POSTGRES_DB
        )

        # Query all enabled routing rules
        rows = await conn.fetch("""
            SELECT src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback
            FROM mt_routing_config
            WHERE enabled = true
            ORDER BY src_lang, tgt_lang, quality_tier
        """)

        await conn.close()

        # Build cache
        new_cache = {}
        for row in rows:
            key = (row['src_lang'], row['tgt_lang'], row['quality_tier'])
            new_cache[key] = (row['provider_primary'], row['provider_fallback'])

        routing_cache = new_cache
        routing_cache_expiry = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)

        print(f"[MT Router] Loaded {len(routing_cache)} routing rules from database")

    except Exception as e:
        print(f"[MT Router] Error loading routing config from DB: {e}")
        # Keep existing cache if load fails

async def get_provider_strategy(src_lang: str, tgt_lang: str, quality_tier: str = "standard") -> tuple:
    """
    Get MT provider strategy from database cache.

    Returns:
        tuple: (primary_provider, fallback_provider)
    """
    global routing_cache, routing_cache_expiry

    # Refresh cache if expired
    if routing_cache_expiry is None or datetime.now() > routing_cache_expiry:
        await load_routing_config_from_db()

    src = src_lang.lower()
    tgt = tgt_lang.lower()

    # Try exact match first
    key = (src, tgt, quality_tier)
    if key in routing_cache:
        return routing_cache[key]

    # Try wildcard matches: (*, tgt, tier), (src, *, tier), (*, *, tier)
    for fallback_key in [(src, "*", quality_tier), ("*", tgt, quality_tier), ("*", "*", quality_tier)]:
        if fallback_key in routing_cache:
            return routing_cache[fallback_key]

    # Default fallback if nothing found
    print(f"[MT Router] No routing rule found for {src}→{tgt} ({quality_tier}), using default")
    return ("google_translate", "amazon_translate")

async def translate_with_provider(provider: str, text: str, src: str, tgt: str) -> dict:
    """
    Translate text using the specified provider.

    Args:
        provider: Provider name (deepl, google_translate, amazon_translate, openai)
        text: Text to translate
        src: Source language code
        tgt: Target language code

    Returns:
        dict: Translation result with 'text' and metadata
    """
    try:
        if provider == "deepl":
            result = await deepl_backend.translate(text, src, tgt)
            return {
                "text": result["text"],
                "provider": "deepl",
                "char_count": len(text),
                "cost": await deepl_backend.get_cost(len(text))
            }
        elif provider in ["google_translate", "google"]:
            result = await google_backend.translate(text, src, tgt)
            return {
                "text": result["text"],
                "provider": "google_translate",
                "char_count": len(text),
                "cost": await google_backend.get_cost(len(text))
            }
        elif provider in ["amazon_translate", "amazon"]:
            result = await amazon_backend.translate(text, src, tgt)
            return {
                "text": result["text"],
                "provider": "amazon_translate",
                "char_count": len(text),
                "cost": await amazon_backend.get_cost(len(text))
            }
        elif provider == "openai":
            result = await openai_translate(text, src, tgt)
            translated = result["text"]
            model = result["model"]
            tokens = estimate_tokens(text) + estimate_tokens(translated)

            # Map model name to provider name for cost tracking
            provider_name = "openai_gpt4o" if model == "gpt-4o" else "openai_gpt4o_mini"

            return {
                "text": translated,
                "provider": provider_name,
                "tokens": tokens,
                "cost": tokens * 0.000001  # Rough estimate
            }
        else:
            raise ValueError(f"Unknown provider: {provider}")
    except Exception as e:
        print(f"[MT Router] Provider {provider} failed: {e}")
        raise

async def translate_with_fallback(text: str, src: str, tgt: str, quality_tier: str = "standard") -> dict:
    """
    Translate text using the optimal provider with automatic fallback.

    Args:
        text: Text to translate
        src: Source language code
        tgt: Target language code
        quality_tier: Quality tier (standard or budget)

    Returns:
        dict: Translation result with provider info
    """
    primary, fallback = await get_provider_strategy(src, tgt, quality_tier)

    print(f"[MT Router] Strategy: {src}→{tgt} ({quality_tier}) = {primary} (fallback: {fallback})")

    # Try primary provider
    try:
        result = await translate_with_provider(primary, text, src, tgt)
        print(f"[MT Router] ✓ {primary} succeeded")
        return result
    except Exception as e:
        print(f"[MT Router] ✗ {primary} failed: {e}")

    # Try fallback provider if exists
    if fallback:
        try:
            result = await translate_with_provider(fallback, text, src, tgt)
            print(f"[MT Router] ✓ {fallback} succeeded (fallback)")
            return result
        except Exception as e:
            print(f"[MT Router] ✗ {fallback} failed: {e}")

    raise Exception(f"All providers failed for {src}→{tgt}")

async def local_translate(client: httpx.AsyncClient, text: str, src: str, tgt: str, is_final: bool) -> str:
    """Call local mt_worker - only supports pl<->en (DEPRECATED - use translate_with_fallback)"""
    endpoint = "/translate/final" if is_final else "/translate/fast"
    url = f"{MT_WORKER_URL}{endpoint}"

    # mt_worker only supports pl and en
    src_normalized = normalize_lang(src)
    tgt_normalized = normalize_lang(tgt)

    # Map to mt_worker format (it expects "pl" or "en")
    if src_normalized not in ["pl", "en"]:
        src_normalized = "en"
    if tgt_normalized not in ["pl", "en"]:
        tgt_normalized = "en"

    response = await client.post(url, json={"src": src_normalized, "tgt": tgt_normalized, "text": text})
    response.raise_for_status()
    result = response.json()
    return result.get("text", "")

async def router_loop():
    r = redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(STT_EVENTS)

    # Preload routing configuration
    await load_routing_config_from_db()

    print(f"[MT Router] Listening on {STT_EVENTS}")
    print(f"[MT Router] Translation Matrix Mode: Translating to all room languages")

    timeout = httpx.Timeout(30.0, read=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue

            try:
                data = jloads(msg["data"])
                msg_type = data.get("type", "")

                # Translate both partials and finals
                if msg_type not in ["stt_partial", "stt_final"]:
                    continue

                room = data.get("room_id", "unknown")
                segment = data.get("segment_id", 0)
                detected_lang = data.get("lang", "auto")
                text = data.get("text", "").strip()
                is_final = data.get("final", False)
                speaker = data.get("speaker", "system")

                if not text:
                    continue

                # Normalize source language
                src_lang = normalize_lang(detected_lang)
                kind = "final" if is_final else "partial"

                # Determine quality tier - always use standard for streaming mode (no finals expected)
                quality_tier = "standard"

                # Check if room is in multi-speaker mode
                is_multi_speaker, room_id, speakers_dict = await check_multi_speaker_mode(room)

                # Determine translation targets based on mode
                translation_targets = []  # List of (tgt_lang, target_speaker_id) tuples

                if is_multi_speaker and speakers_dict and speaker is not None:
                    # Multi-speaker mode with speaker ID
                    try:
                        # speaker can be string or int from STT event
                        speaker_id = int(speaker) if isinstance(speaker, str) and speaker.isdigit() else None

                        if speaker_id is not None and speaker_id in speakers_dict:
                            # Get source language from speaker configuration
                            speaker_src_lang = normalize_lang(speakers_dict[speaker_id]["language"])

                            # Override detected language with speaker's configured language
                            if speaker_src_lang != src_lang:
                                print(f"[MT Router] 🎤 Multi-speaker: Overriding detected lang {src_lang} → {speaker_src_lang} (speaker {speaker_id} config)")
                                src_lang = speaker_src_lang

                            # Get other speakers as translation targets (N-1)
                            other_speakers = get_multi_speaker_translation_targets(speakers_dict, speaker_id)

                            for target_speaker in other_speakers:
                                target_lang = normalize_lang(target_speaker["language"])
                                translation_targets.append((target_lang, target_speaker["speaker_id"]))

                            print(f"[MT Router] 🎤 Multi-speaker mode: speaker {speaker_id} ({speaker_src_lang}) → {len(translation_targets)} targets")
                            print(f"[MT Router] 🎤 Translation matrix (N×N-1): {[(t[0], f'spk{t[1]}') for t in translation_targets]}")
                        else:
                            # Speaker ID not found in room speakers - fall back to single-speaker mode
                            print(f"[MT Router] ⚠ Speaker {speaker} not found in room speakers, using single-speaker mode")
                            is_multi_speaker = False
                    except (ValueError, TypeError) as e:
                        # Invalid speaker ID format - fall back to single-speaker mode
                        print(f"[MT Router] ⚠ Invalid speaker ID format '{speaker}', using single-speaker mode: {e}")
                        is_multi_speaker = False

                if not is_multi_speaker or not translation_targets:
                    # Single-speaker mode - translate to all room languages
                    target_langs_key = f"room:{room}:target_languages"
                    target_langs = await r.smembers(target_langs_key)

                    if not target_langs:
                        # Fallback to default if no languages registered
                        target_langs = {DEFAULT_TGT}
                        print(f"[MT Router] ⚠ No languages registered for room={room}, using default: {DEFAULT_TGT}")

                    # Convert to same format as multi-speaker (lang, None) - None means no specific target speaker
                    for tgt_lang in target_langs:
                        translation_targets.append((tgt_lang, None))

                    print(f"[MT Router] Processing {kind}: room={room} seg={segment} speaker={speaker} src={src_lang}")
                    print(f"[MT Router] Single-speaker translation matrix: {src_lang} → {[t[0] for t in translation_targets]}")

                # Clean up cache for final translations (no longer need partials for this segment)
                if is_final:
                    # Clean partial translation cache
                    keys_to_remove = [k for k in partial_translation_cache.keys() if k[0] == room and k[1] == segment]
                    for key in keys_to_remove:
                        del partial_translation_cache[key]

                    # Clean Arabic throttle cache
                    throttle_keys_to_remove = [k for k in arabic_translation_throttle.keys() if k[0] == room and k[1] == segment]
                    for key in throttle_keys_to_remove:
                        del arabic_translation_throttle[key]

                    if keys_to_remove or throttle_keys_to_remove:
                        print(f"[MT Router] 🧹 Cleaned {len(keys_to_remove)} cached partials and {len(throttle_keys_to_remove)} throttle entries for segment {segment}")

                # Translate to each target language
                for tgt_lang, target_speaker_id in translation_targets:
                    tgt_normalized = normalize_lang(tgt_lang)

                    # Skip translation if source language is unknown/auto
                    if src_lang == "auto":
                        target_info = f" (target speaker {target_speaker_id})" if target_speaker_id is not None else ""
                        print(f"[MT Router] ⊘ Skipping auto→{tgt_normalized}{target_info} (unknown source language)")
                        await append_mt_skip_reason(
                            redis=r,
                            room_code=room,
                            segment_id=segment,
                            src_lang=src_lang,
                            tgt_lang=tgt_normalized,
                            reason="Source language unknown (auto-detected as 'auto')"
                        )
                        continue

                    # Skip translation if source and target are the same
                    if src_lang == tgt_normalized:
                        target_info = f" (target speaker {target_speaker_id})" if target_speaker_id is not None else ""
                        print(f"[MT Router] ⊘ Skipping {src_lang}→{tgt_normalized}{target_info} (same language)")
                        await append_mt_skip_reason(
                            redis=r,
                            room_code=room,
                            segment_id=segment,
                            src_lang=src_lang,
                            tgt_lang=tgt_normalized,
                            reason=f"No translation needed - source and target are both '{src_lang}'"
                        )
                        continue

                    try:
                        # Check if this is an Arabic translation (to or from)
                        is_arabic_translation = (src_lang == "ar" or tgt_normalized == "ar")

                        # Throttle Arabic partial translations (GPT-4o is expensive)
                        if is_arabic_translation and not is_final:
                            throttle_key = (room, segment, tgt_normalized)
                            current_time = asyncio.get_event_loop().time()

                            if throttle_key in arabic_translation_throttle:
                                last_translation_time = arabic_translation_throttle[throttle_key]
                                time_since_last = current_time - last_translation_time

                                if time_since_last < ARABIC_THROTTLE_SECONDS:
                                    # Skip this partial - too soon since last translation
                                    print(f"[MT Router] ⏱ Throttled: {src_lang}→{tgt_normalized} ({time_since_last:.1f}s < {ARABIC_THROTTLE_SECONDS}s)")
                                    continue

                            # Update throttle timestamp
                            arabic_translation_throttle[throttle_key] = current_time

                        # Check cache for partials (not finals) to save costs
                        cache_key = None
                        from_cache = False

                        if not is_final:
                            cache_key = (room, segment, src_lang, tgt_normalized, text)
                            if cache_key in partial_translation_cache:
                                translation_result = partial_translation_cache[cache_key]
                                from_cache = True
                                print(f"[MT Router] 💾 Cache hit: {src_lang}→{tgt_normalized} ({len(text)} chars)")

                        # Measure latency and check if throttled
                        import time
                        was_throttled = is_arabic_translation and not is_final and (room, segment, tgt_normalized) in arabic_translation_throttle
                        throttle_delay_ms = 0

                        if not from_cache:
                            # Use database-driven routing with fallback (measure latency)
                            translate_start_time = time.time()
                            translation_result = await translate_with_fallback(text, src_lang, tgt_normalized, quality_tier)
                            latency_ms = int((time.time() - translate_start_time) * 1000)

                            # Cache partial translations for reuse
                            if not is_final and cache_key:
                                partial_translation_cache[cache_key] = translation_result
                        else:
                            latency_ms = 0  # Cached, no latency

                        translated = translation_result["text"]
                        backend_name = translation_result["provider"]

                        mt_event = {
                            "type": f"translation_{kind}",
                            "room_id": room,
                            "segment_id": segment,
                            "src": detected_lang,
                            "tgt": tgt_lang,
                            "text": translated,
                            "final": is_final,
                            "ts_iso": data.get("ts_iso"),
                            "backend": backend_name,
                            "speaker": speaker,
                            "src_text": text
                        }

                        # Add target_speaker_id for multi-speaker mode
                        if target_speaker_id is not None:
                            mt_event["target_speaker_id"] = target_speaker_id

                        await r.publish(MT_OUTPUT, jdumps(mt_event))

                        cache_indicator = " (cached)" if from_cache else ""
                        target_info = f" → speaker {target_speaker_id}" if target_speaker_id is not None else ""
                        print(f"[MT Router] ✓ {kind} ({backend_name}) {src_lang}→{tgt_normalized}{target_info}: {translated[:60]}...{cache_indicator}")

                        # Track cost only for non-cached translations
                        if not from_cache and "char_count" in translation_result:
                            # DeepL, Google, Amazon use character-based pricing
                            cost_event = {
                                "type": "cost_event",
                                "room_id": room,
                                "pipeline": "mt",
                                "mode": backend_name,
                                "units": translation_result["char_count"],
                                "unit_type": "characters",
                                "provider": backend_name,
                                "segment_id": segment
                            }

                            # Add multi-speaker cost tracking fields
                            if is_multi_speaker and speaker is not None:
                                try:
                                    speaker_id = int(speaker) if isinstance(speaker, str) and speaker.isdigit() else None
                                    if speaker_id is not None:
                                        cost_event["speaker_id"] = speaker_id
                                        if target_speaker_id is not None:
                                            cost_event["target_speaker_id"] = target_speaker_id
                                except (ValueError, TypeError):
                                    pass  # Skip if speaker_id can't be parsed

                            await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))

                            speaker_info = f" spk{speaker}→spk{target_speaker_id}" if (is_multi_speaker and target_speaker_id is not None) else ""
                            print(f"[MT Router] 💰 Cost tracked: {translation_result['char_count']} chars ({backend_name}) seg={segment}{speaker_info}")
                        elif not from_cache and "tokens" in translation_result:
                            # OpenAI uses token-based pricing
                            cost_event = {
                                "type": "cost_event",
                                "room_id": room,
                                "pipeline": "mt",
                                "mode": backend_name,
                                "units": translation_result["tokens"],
                                "unit_type": "tokens",
                                "provider": backend_name,
                                "segment_id": segment
                            }

                            # Add multi-speaker cost tracking fields
                            if is_multi_speaker and speaker is not None:
                                try:
                                    speaker_id = int(speaker) if isinstance(speaker, str) and speaker.isdigit() else None
                                    if speaker_id is not None:
                                        cost_event["speaker_id"] = speaker_id
                                        if target_speaker_id is not None:
                                            cost_event["target_speaker_id"] = target_speaker_id
                                except (ValueError, TypeError):
                                    pass  # Skip if speaker_id can't be parsed

                            await r.publish(COST_TRACKING_CHANNEL, jdumps(cost_event))

                            speaker_info = f" spk{speaker}→spk{target_speaker_id}" if (is_multi_speaker and target_speaker_id is not None) else ""
                            print(f"[MT Router] 💰 Cost tracked: {translation_result['tokens']} tokens ({backend_name}) seg={segment}{speaker_info}")

                        # Track debug info (fire-and-forget) - always track, even for cached
                        await append_mt_debug_info(
                            redis=r,
                            room_code=room,
                            segment_id=segment,
                            mt_data={
                                "src_lang": src_lang,
                                "tgt_lang": tgt_normalized,
                                "provider": backend_name,
                                "latency_ms": latency_ms if not from_cache else 0,  # Cache hits have no latency
                                "text": translated,
                                "char_count": translation_result.get("char_count"),
                                "input_tokens": translation_result.get("input_tokens"),
                                "output_tokens": translation_result.get("output_tokens")
                            },
                            routing_info={
                                "routing_reason": f"{src_lang}→{tgt_normalized}/{quality_tier} → {backend_name} ({'cached' if from_cache else 'fallback' if translation_result.get('fallback') else 'primary'})",
                                "fallback_triggered": translation_result.get("fallback", False),
                                "throttled": was_throttled,
                                "throttle_delay_ms": throttle_delay_ms,
                                "throttle_reason": f"Arabic {'partial' if not is_final else 'final'} throttling (max 1 req/{ARABIC_THROTTLE_SECONDS}s)" if was_throttled else None
                            }
                        )

                    except Exception as e:
                        print(f"[MT Router] ✗ Translation error {src_lang}→{tgt_normalized}: {e}")

            except Exception as e:
                print(f"[MT Router] Error: {e}")

if __name__ == "__main__":
    asyncio.run(router_loop())

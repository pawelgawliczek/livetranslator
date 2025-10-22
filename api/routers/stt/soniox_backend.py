"""
Soniox STT Backend (Budget Mode)

Provides cost-effective speech-to-text with speaker diarization using Soniox API.
- REST API for batch transcription
- Speaker identification
- 80-95% cheaper than competitors
- Good quality for budget-conscious applications
"""

import os
import base64
import asyncio
from typing import Optional, Dict, Any
import httpx

# Environment variables
SONIOX_API_KEY = os.getenv("SONIOX_API_KEY", "")
SONIOX_API_URL = os.getenv("SONIOX_API_URL", "https://api.soniox.com/transcribe")

# Pricing: ~$0.015 per hour (estimated, verify with Soniox)
SONIOX_PRICE_PER_HOUR = 0.015


def pcm16_to_bytes(pcm16_base64: str) -> bytes:
    """Convert PCM16 base64 to raw bytes"""
    return base64.b64decode(pcm16_base64)


async def transcribe_audio_chunk(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Soniox REST API.

    Args:
        audio_base64: Base64-encoded PCM16 audio
        language: Language code (pl, en, ar, auto)
        config: Optional config with diarization settings
            {
                "diarization": true,
                "enable_speaker_identification": true
            }

    Returns:
        {
            "text": "transcribed text",
            "language": "en",
            "speaker_labels": [
                {"speaker": "spk_1", "text": "Hello", "start": 0.0, "end": 1.5},
                {"speaker": "spk_2", "text": "Hi there", "start": 1.6, "end": 3.0}
            ],
            "is_final": true
        }
    """
    if not SONIOX_API_KEY:
        raise Exception("SONIOX_API_KEY not set")

    # Default config
    if config is None:
        config = {}

    diarization = config.get("diarization", True)
    speaker_identification = config.get("enable_speaker_identification", True)

    # Normalize language code
    lang_code = _normalize_language(language)

    # Convert PCM16 to bytes
    audio_bytes = pcm16_to_bytes(audio_base64)

    # Prepare request payload
    payload = {
        "audio": base64.b64encode(audio_bytes).decode("utf-8"),
        "model": "default",
        "language": lang_code if lang_code != "auto" else None,
        "enable_speaker_identification": speaker_identification if diarization else False,
        "enable_profanity_filter": False,
        "enable_punctuation": True
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SONIOX_API_URL,
                headers={
                    "Authorization": f"Bearer {SONIOX_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            response.raise_for_status()
            result_data = response.json()

        # Parse results
        result = _parse_soniox_result(result_data, diarization)

        print(f"[Soniox] Transcribed {len(result['text'])} chars, "
              f"lang={result['language']}, speakers={len(result.get('speaker_labels', []))}")

        return result

    except httpx.HTTPStatusError as e:
        print(f"[Soniox] HTTP error: {e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        print(f"[Soniox] Error: {e}")
        raise


async def transcribe_stream(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Soniox (for partials).

    Note: Soniox REST API doesn't support streaming in the same way.
    This uses the batch API for simplicity.

    Args:
        audio_base64: Base64-encoded PCM16 audio chunk
        language: Language code (pl, en, ar, auto)
        config: Optional config with diarization settings
        session_id: Optional session ID

    Returns:
        {
            "text": "partial transcription...",
            "language": "en",
            "is_final": false
        }
    """
    print(f"[Soniox] Using batch API for streaming (no dedicated streaming endpoint)")

    result = await transcribe_audio_chunk(audio_base64, language, config)
    result["is_final"] = False
    return result


def _normalize_language(language: str) -> str:
    """Convert language codes to Soniox format"""
    # Map common language codes to Soniox codes
    lang_map = {
        "pl": "pl",
        "pl-PL": "pl",
        "en": "en",
        "en-US": "en",
        "en-GB": "en",
        "ar": "ar",
        "ar-EG": "ar",
        "ar-SA": "ar",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "ru": "ru",
        "zh": "zh",
        "ja": "ja",
        "ko": "ko",
        "auto": "auto",  # Soniox supports auto-detect
        "*": "auto"
    }

    return lang_map.get(language, "auto")


def _parse_soniox_result(result_data: Dict[str, Any], diarization: bool) -> Dict[str, Any]:
    """
    Parse Soniox API response.

    Expected response format:
    {
        "text": "full transcription text",
        "words": [
            {
                "text": "word",
                "start_time": 0.5,
                "end_time": 1.2,
                "speaker": "spk_1",
                "confidence": 0.95
            }
        ],
        "language": "en"
    }
    """
    text = result_data.get("text", "")
    language = result_data.get("language", "auto")
    words = result_data.get("words", [])

    # Extract speaker labels if diarization enabled
    speaker_labels = []
    if diarization and words:
        current_speaker = None
        current_words = []
        current_start = None

        for word_data in words:
            speaker = word_data.get("speaker", "unknown")

            if speaker != current_speaker:
                # Save previous speaker segment
                if current_words:
                    speaker_labels.append({
                        "speaker": current_speaker,
                        "text": " ".join([w.get("text", "") for w in current_words]),
                        "start": current_start,
                        "end": current_words[-1].get("end_time", 0)
                    })

                # Start new speaker segment
                current_speaker = speaker
                current_words = [word_data]
                current_start = word_data.get("start_time", 0)
            else:
                current_words.append(word_data)

        # Add last segment
        if current_words:
            speaker_labels.append({
                "speaker": current_speaker,
                "text": " ".join([w.get("text", "") for w in current_words]),
                "start": current_start,
                "end": current_words[-1].get("end_time", 0)
            })

    return {
        "text": text,
        "language": language,
        "speaker_labels": speaker_labels,
        "is_final": True
    }


async def get_cost(audio_duration_seconds: float) -> float:
    """
    Calculate cost for Soniox transcription.

    Args:
        audio_duration_seconds: Duration of audio in seconds

    Returns:
        Cost in USD
    """
    hours = audio_duration_seconds / 3600.0
    return hours * SONIOX_PRICE_PER_HOUR

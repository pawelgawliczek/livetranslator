"""
Google Cloud Speech-to-Text v2 Backend

Provides real-time speech-to-text with speaker diarization using Google Cloud Speech API v2.
- Streaming recognition with interim results
- Speaker diarization (up to 6 speakers)
- Stability threshold for quality control
- Excellent Arabic dialect support
"""

import os
import base64
import asyncio
from typing import Optional, Dict, Any, List
from google.cloud import speech_v2 as speech
from google.api_core.client_options import ClientOptions

# Environment variables
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us")  # us, eu, asia

# Pricing: $0.024 per minute = $1.44 per hour
GOOGLE_STT_PRICE_PER_MINUTE = 0.024


def pcm16_to_bytes(pcm16_base64: str) -> bytes:
    """Convert PCM16 base64 to raw bytes"""
    return base64.b64decode(pcm16_base64)


async def transcribe_audio_chunk(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Google Cloud Speech v2 API.

    Args:
        audio_base64: Base64-encoded PCM16 audio
        language: Language code (pl-PL, ar-EG, en-US, auto)
        config: Optional config with diarization settings
            {
                "diarization": true,
                "stability_threshold": 0.8,
                "min_speaker_count": 2,
                "max_speaker_count": 6
            }

    Returns:
        {
            "text": "transcribed text",
            "language": "en-US",
            "speaker_labels": [
                {"speaker": 1, "text": "Hello", "start": 0.0, "end": 1.5},
                {"speaker": 2, "text": "Hi there", "start": 1.6, "end": 3.0}
            ],
            "is_final": true
        }
    """
    if not GOOGLE_APPLICATION_CREDENTIALS:
        raise Exception("GOOGLE_APPLICATION_CREDENTIALS not set")

    if not GOOGLE_CLOUD_PROJECT:
        raise Exception("GOOGLE_CLOUD_PROJECT not set")

    # Default config
    if config is None:
        config = {}

    diarization = config.get("diarization", True)
    min_speakers = config.get("min_speaker_count", 2)
    max_speakers = config.get("max_speaker_count", 6)

    # Normalize language code
    lang_code = _normalize_language(language)

    # Convert PCM16 to bytes
    audio_content = pcm16_to_bytes(audio_base64)

    # Create client with regional endpoint
    client_options = ClientOptions(
        api_endpoint=f"{GOOGLE_CLOUD_LOCATION}-speech.googleapis.com"
    )
    client = speech.SpeechClient(client_options=client_options)

    # Configure recognition
    recognition_config = speech.RecognitionConfig(
        auto_decoding_config=speech.AutoDetectDecodingConfig(),
        language_codes=[lang_code],
        model="long",  # Best for longer audio
        features=speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
        ),
    )

    # Enable diarization if requested
    if diarization:
        recognition_config.features.diarization_config = speech.SpeakerDiarizationConfig(
            min_speaker_count=min_speakers,
            max_speaker_count=max_speakers,
        )

    # Prepare request
    request = speech.RecognizeRequest(
        recognizer=f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}/recognizers/_",
        config=recognition_config,
        content=audio_content,
    )

    try:
        # Run recognition (synchronous, converted to async)
        response = await asyncio.to_thread(client.recognize, request=request)

        # Parse results
        result = _parse_google_result(response, diarization)

        print(f"[Google STT v2] Transcribed {len(result['text'])} chars, "
              f"lang={result['language']}, speakers={len(result.get('speaker_labels', []))}")

        return result

    except Exception as e:
        print(f"[Google STT v2] Error: {e}")
        raise


async def transcribe_stream(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Google Cloud Speech v2 streaming API (for partials).

    Note: This is a simplified implementation using batch API.
    For production, implement proper streaming with StreamingRecognizeRequest.

    Args:
        audio_base64: Base64-encoded PCM16 audio chunk
        language: Language code (pl-PL, ar-EG, en-US, auto)
        config: Optional config with diarization and stability settings
        session_id: Optional session ID for connection pooling

    Returns:
        {
            "text": "partial transcription...",
            "language": "en-US",
            "is_final": false,
            "stability": 0.85
        }
    """
    # TODO: Implement proper streaming with connection pooling
    print(f"[Google STT v2] Stream transcription using batch API (streaming not yet implemented)")

    result = await transcribe_audio_chunk(audio_base64, language, config)
    result["is_final"] = False
    result["stability"] = 0.9  # Placeholder
    return result


def _normalize_language(language: str) -> str:
    """Convert language codes to Google Cloud Speech format"""
    # Map common language codes to Google format (BCP-47)
    lang_map = {
        "pl": "pl-PL",
        "pl-PL": "pl-PL",
        "en": "en-US",
        "en-US": "en-US",
        "en-GB": "en-GB",
        "ar": "ar-EG",
        "ar-EG": "ar-EG",
        "ar-SA": "ar-SA",
        "es": "es-ES",
        "fr": "fr-FR",
        "de": "de-DE",
        "it": "it-IT",
        "pt": "pt-PT",
        "ru": "ru-RU",
        "zh": "zh-CN",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "auto": "en-US",  # Default to English for auto-detect
        "*": "en-US"
    }

    return lang_map.get(language, "en-US")


def _parse_google_result(response: Any, diarization: bool) -> Dict[str, Any]:
    """
    Parse Google Cloud Speech v2 API response.

    Response contains:
    - results[].alternatives[].transcript
    - results[].alternatives[].words[] with speaker_label
    """
    if not response.results:
        return {
            "text": "",
            "language": "auto",
            "speaker_labels": [],
            "is_final": True
        }

    # Get best alternative from first result
    result = response.results[0]
    alternative = result.alternatives[0] if result.alternatives else None

    if not alternative:
        return {
            "text": "",
            "language": "auto",
            "speaker_labels": [],
            "is_final": True
        }

    text = alternative.transcript
    language = result.language_code if hasattr(result, 'language_code') else "auto"

    # Extract speaker labels if diarization enabled
    speaker_labels = []
    if diarization and hasattr(alternative, 'words') and alternative.words:
        current_speaker = None
        current_words = []
        current_start = None

        for word_info in alternative.words:
            speaker = word_info.speaker_label if hasattr(word_info, 'speaker_label') else 0

            if speaker != current_speaker:
                # Save previous speaker segment
                if current_words:
                    speaker_labels.append({
                        "speaker": current_speaker,
                        "text": " ".join(current_words),
                        "start": current_start,
                        "end": word_info.start_offset.total_seconds() if hasattr(word_info, 'start_offset') else 0
                    })

                # Start new speaker segment
                current_speaker = speaker
                current_words = [word_info.word]
                current_start = word_info.start_offset.total_seconds() if hasattr(word_info, 'start_offset') else 0
            else:
                current_words.append(word_info.word)

        # Add last segment
        if current_words:
            last_word = alternative.words[-1]
            speaker_labels.append({
                "speaker": current_speaker,
                "text": " ".join(current_words),
                "start": current_start,
                "end": last_word.end_offset.total_seconds() if hasattr(last_word, 'end_offset') else 0
            })

    return {
        "text": text,
        "language": language,
        "speaker_labels": speaker_labels,
        "is_final": True
    }


async def get_cost(audio_duration_seconds: float) -> float:
    """
    Calculate cost for Google Cloud Speech v2 transcription.

    Args:
        audio_duration_seconds: Duration of audio in seconds

    Returns:
        Cost in USD
    """
    minutes = audio_duration_seconds / 60.0
    return minutes * GOOGLE_STT_PRICE_PER_MINUTE

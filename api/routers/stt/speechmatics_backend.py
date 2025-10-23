"""
Speechmatics STT Backend

Provides real-time speech-to-text with speaker diarization using Speechmatics API.
- WebSocket streaming for low latency
- Speaker diarization (real-time speaker labels)
- Configurable max_delay for latency control
- Support for Polish, English, and 30+ languages
"""

import os
import base64
import asyncio
import json
from typing import Optional, Dict, Any
from speechmatics.models import ConnectionSettings, AudioSettings, TranscriptionConfig
from speechmatics.batch_client import BatchClient
from speechmatics.client import WebsocketClient
import io

SPEECHMATICS_API_KEY = os.getenv("SPEECHMATICS_API_KEY", "")
SPEECHMATICS_REGION = os.getenv("SPEECHMATICS_REGION", "eu2")  # eu2, us2, etc.

# Pricing: $0.08 per hour of audio
SPEECHMATICS_PRICE_PER_HOUR = 0.08


def pcm16_to_wav(pcm16_base64: str, sample_rate=16000, channels=1) -> bytes:
    """Convert PCM16 base64 to WAV bytes"""
    import io
    import wave

    pcm_data = base64.b64decode(pcm16_base64)

    # Create WAV file in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

    return wav_buffer.getvalue()


async def transcribe_audio_chunk(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Speechmatics WebSocket streaming API.
    Fast, low-latency transcription with speaker diarization.

    Args:
        audio_base64: Base64-encoded PCM16 audio
        language: Language code (pl, en, auto)
        config: Optional config with diarization settings
            {
                "diarization": true,
                "max_delay": 1.5,  # seconds for ultra-fast response (0.7-1.5 range)
                "operating_point": "enhanced"  # standard, enhanced
            }

    Returns:
        {
            "text": "transcribed text",
            "language": "en",
            "speaker_labels": [
                {"speaker": "S1", "text": "Hello", "start": 0.0, "end": 1.5}
            ]
        }
    """
    if not SPEECHMATICS_API_KEY:
        raise Exception("SPEECHMATICS_API_KEY not set")

    # Default config
    if config is None:
        config = {}

    diarization = config.get("diarization", True)
    operating_point = config.get("operating_point", "enhanced")
    max_delay = config.get("max_delay", 2.0)

    # Convert language code to Speechmatics format
    lang_code = _normalize_language(language)

    # Convert PCM16 to raw audio bytes
    pcm_bytes = base64.b64decode(audio_base64)

    try:
        # Use WebSocket streaming API for low latency
        settings = ConnectionSettings(
            url=f"wss://{SPEECHMATICS_REGION}.rt.speechmatics.com/v2",
            auth_token=SPEECHMATICS_API_KEY,
        )

        # Configure audio settings (PCM16, 16kHz, mono)
        audio_settings = AudioSettings(
            encoding="pcm_s16le",
            sample_rate=16000,
            chunk_size=1024
        )

        # Configure transcription using TranscriptionConfig object
        transcription_config = TranscriptionConfig(
            language=lang_code,
            operating_point=operating_point,
            max_delay=max_delay,
            enable_partials=True,
            diarization="speaker" if diarization else "none",
            max_delay_mode=config.get("max_delay_mode", "flexible"),
            enable_entities=config.get("enable_entities", True)
        )

        # Add advanced features if provided
        if "punctuation_overrides" in config:
            punctuation_config = config["punctuation_overrides"]
            transcription_config.punctuation_overrides = punctuation_config

        if "speaker_diarization_config" in config:
            speaker_config = config["speaker_diarization_config"]
            transcription_config.speaker_diarization_config = speaker_config

        # Create WebSocket client
        ws_client = WebsocketClient(settings)

        # Collect transcription results
        transcripts = []
        speaker_labels = []
        detected_language = lang_code

        def on_transcript(msg):
            """Handle AddTranscript messages."""
            nonlocal transcripts, speaker_labels, detected_language

            if msg.get("message") == "AddTranscript":
                metadata = msg.get("metadata", {})
                results = msg.get("results", [])

                # Extract language
                if "transcript" in metadata:
                    detected_language = metadata.get("language", lang_code)

                # Collect words and speaker info
                for result in results:
                    if result.get("type") == "word":
                        alternatives = result.get("alternatives", [])
                        if alternatives:
                            word_data = alternatives[0]
                            content = word_data.get("content", "")
                            transcripts.append(content)

                            # Track speaker labels if diarization enabled
                            if diarization and "speaker" in word_data:
                                speaker_labels.append({
                                    "speaker": word_data.get("speaker"),
                                    "text": content,
                                    "start": word_data.get("start_time", 0),
                                    "end": word_data.get("end_time", 0)
                                })

        def on_error(msg):
            """Handle error messages."""
            print(f"[Speechmatics WS] Error: {msg}")

        # Register handlers
        ws_client.add_event_handler("AddTranscript", on_transcript)
        ws_client.add_event_handler("Error", on_error)

        # Create audio stream from PCM bytes
        audio_stream = io.BytesIO(pcm_bytes)

        # Run transcription in thread pool (Speechmatics SDK is synchronous)
        def run_transcription():
            # Start session
            ws_client.run_synchronously(
                audio_stream,
                transcription_config,
                audio_settings
            )

        await asyncio.to_thread(run_transcription)

        # Aggregate results
        full_text = " ".join(transcripts)

        # Group speaker labels by speaker
        grouped_speakers = {}
        for label in speaker_labels:
            speaker = label["speaker"]
            if speaker not in grouped_speakers:
                grouped_speakers[speaker] = []
            grouped_speakers[speaker].append(label)

        # Consolidate consecutive words from same speaker
        consolidated_labels = []
        for speaker, labels in grouped_speakers.items():
            if labels:
                speaker_text = " ".join([l["text"] for l in labels])
                consolidated_labels.append({
                    "speaker": speaker,
                    "text": speaker_text,
                    "start": labels[0]["start"],
                    "end": labels[-1]["end"]
                })

        result = {
            "text": full_text,
            "language": detected_language,
            "speaker_labels": consolidated_labels if diarization else []
        }

        print(f"[Speechmatics] Transcribed {len(result['text'])} chars, "
              f"lang={result['language']}, speakers={len(result.get('speaker_labels', []))}")

        return result

    except Exception as e:
        import traceback
        print(f"[Speechmatics] Error: {e}")
        print(f"[Speechmatics] Traceback: {traceback.format_exc()}")
        raise


async def transcribe_stream(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Speechmatics streaming API (for partials).

    Note: This is a simplified implementation. For production use,
    you should maintain persistent WebSocket connections per room/session.

    Args:
        audio_base64: Base64-encoded PCM16 audio chunk
        language: Language code (pl, en, auto)
        config: Optional config with diarization settings
        session_id: Optional session ID for connection pooling

    Returns:
        {
            "text": "partial transcription...",
            "language": "en",
            "is_final": false
        }
    """
    # For streaming, we would maintain WebSocket connections
    # This is a placeholder that uses the batch API
    # TODO: Implement proper WebSocket streaming with connection pooling

    print(f"[Speechmatics] Stream transcription not yet implemented, falling back to batch")
    result = await transcribe_audio_chunk(audio_base64, language, config)
    result["is_final"] = False  # Mark as partial
    return result


def _normalize_language(language: str) -> str:
    """Convert language codes to Speechmatics format"""
    # Map common language codes to Speechmatics codes
    lang_map = {
        "pl": "pl",
        "pl-PL": "pl",
        "en": "en",
        "en-EN": "en",
        "en-US": "en",
        "en-GB": "en",
        "ar": "ar",
        "ar-EG": "ar",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "it": "it",
        "pt": "pt",
        "ru": "ru",
        "zh": "zh",
        "ja": "ja",
        "ko": "ko",
        "auto": "en",  # Speechmatics doesn't support auto-detect, default to English
        "*": "en"
    }

    return lang_map.get(language, "en")


def _parse_speechmatics_result(transcript: Dict[str, Any], diarization: bool) -> Dict[str, Any]:
    """
    Parse Speechmatics API response.

    Response format (json-v2):
    {
        "results": [
            {
                "alternatives": [
                    {
                        "content": "word",
                        "confidence": 0.98,
                        "speaker": "S1",
                        "start_time": 0.5,
                        "end_time": 1.2
                    }
                ],
                "type": "word"
            }
        ],
        "metadata": {
            "language": "en"
        }
    }
    """
    # Extract full text
    words = []
    speaker_segments = {}

    for result in transcript.get("results", []):
        if result.get("type") == "word":
            alternatives = result.get("alternatives", [])
            if alternatives:
                word_data = alternatives[0]
                words.append(word_data.get("content", ""))

                # Group by speaker if diarization enabled
                if diarization and "speaker" in word_data:
                    speaker = word_data["speaker"]
                    if speaker not in speaker_segments:
                        speaker_segments[speaker] = []
                    speaker_segments[speaker].append(word_data)

    text = " ".join(words)

    # Build speaker labels if diarization enabled
    speaker_labels = []
    if diarization:
        for speaker, words_list in speaker_segments.items():
            if words_list:
                speaker_text = " ".join([w.get("content", "") for w in words_list])
                speaker_labels.append({
                    "speaker": speaker,
                    "text": speaker_text,
                    "start": words_list[0].get("start_time", 0),
                    "end": words_list[-1].get("end_time", 0)
                })

    return {
        "text": text,
        "language": transcript.get("metadata", {}).get("language", "auto"),
        "speaker_labels": speaker_labels if diarization else []
    }


async def get_cost(audio_duration_seconds: float) -> float:
    """
    Calculate cost for Speechmatics transcription.

    Args:
        audio_duration_seconds: Duration of audio in seconds

    Returns:
        Cost in USD
    """
    hours = audio_duration_seconds / 3600.0
    return hours * SPEECHMATICS_PRICE_PER_HOUR

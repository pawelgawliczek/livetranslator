"""
Azure Speech Service Backend

Provides real-time speech-to-text with speaker diarization using Azure Cognitive Services.
- Streaming recognition with conversation transcription mode
- Speaker diarization (real-time speaker identification)
- Stable partial result threshold
- Reliable global coverage
"""

import os
import base64
import asyncio
from typing import Optional, Dict, Any
import azure.cognitiveservices.speech as speechsdk

# Environment variables
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")

# Pricing: $1.00 per hour of audio
AZURE_SPEECH_PRICE_PER_HOUR = 1.00


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
    Transcribe audio using Azure Speech Service.

    Args:
        audio_base64: Base64-encoded PCM16 audio
        language: Language code (pl-PL, ar-EG, en-US, auto)
        config: Optional config with diarization settings
            {
                "diarization": true,
                "stable_partial_threshold": 0.8
            }

    Returns:
        {
            "text": "transcribed text",
            "language": "en-US",
            "speaker_labels": [
                {"speaker": "Guest-1", "text": "Hello", "start": 0.0, "end": 1.5},
                {"speaker": "Guest-2", "text": "Hi there", "start": 1.6, "end": 3.0}
            ],
            "is_final": true
        }
    """
    if not AZURE_SPEECH_KEY:
        raise Exception("AZURE_SPEECH_KEY not set")

    # Default config
    if config is None:
        config = {}

    diarization = config.get("diarization", True)
    stability_threshold = config.get("stable_partial_threshold", 0.8)

    # Normalize language code
    lang_code = _normalize_language(language)

    # Convert PCM16 to WAV
    wav_bytes = pcm16_to_wav(audio_base64)

    # Create speech config
    speech_config = speechsdk.SpeechConfig(
        subscription=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION
    )
    speech_config.speech_recognition_language = lang_code

    # Set stability threshold for partial results
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceResponse_StablePartialResultThreshold,
        str(stability_threshold)
    )

    # Create audio config from WAV bytes
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_file.write(wav_bytes)
        temp_file_path = temp_file.name

    try:
        audio_config = speechsdk.AudioConfig(filename=temp_file_path)

        # Use conversation transcriber for diarization
        if diarization:
            result = await _transcribe_with_diarization(speech_config, audio_config)
        else:
            result = await _transcribe_simple(speech_config, audio_config)

        print(f"[Azure Speech] Transcribed {len(result['text'])} chars, "
              f"lang={result['language']}, speakers={len(result.get('speaker_labels', []))}")

        return result

    finally:
        # Clean up temp file
        import os
        os.unlink(temp_file_path)


async def _transcribe_simple(
    speech_config: speechsdk.SpeechConfig,
    audio_config: speechsdk.AudioConfig
) -> Dict[str, Any]:
    """Simple transcription without diarization"""
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config
    )

    # Run recognition (synchronous, converted to async)
    result = await asyncio.to_thread(speech_recognizer.recognize_once)

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return {
            "text": result.text,
            "language": speech_config.speech_recognition_language,
            "speaker_labels": [],
            "is_final": True
        }
    elif result.reason == speechsdk.ResultReason.NoMatch:
        return {
            "text": "",
            "language": speech_config.speech_recognition_language,
            "speaker_labels": [],
            "is_final": True
        }
    else:
        raise Exception(f"Azure Speech recognition failed: {result.reason}")


async def _transcribe_with_diarization(
    speech_config: speechsdk.SpeechConfig,
    audio_config: speechsdk.AudioConfig
) -> Dict[str, Any]:
    """Transcription with speaker diarization using conversation transcriber"""

    # Create conversation transcriber
    transcriber = speechsdk.transcription.ConversationTranscriber(
        speech_config=speech_config,
        audio_config=audio_config
    )

    # Storage for results
    transcription_results = []
    done_event = asyncio.Event()

    def transcribing_cb(evt):
        """Handle interim results"""
        pass  # We only care about final results for batch mode

    def transcribed_cb(evt):
        """Handle final results"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcription_results.append({
                "speaker": evt.result.speaker_id,
                "text": evt.result.text,
                "offset": evt.result.offset,
                "duration": evt.result.duration
            })

    def canceled_cb(evt):
        """Handle cancellation"""
        print(f"[Azure Speech] Transcription canceled: {evt}")
        done_event.set()

    def session_stopped_cb(evt):
        """Handle session stop"""
        done_event.set()

    # Connect callbacks
    transcriber.transcribing.connect(transcribing_cb)
    transcriber.transcribed.connect(transcribed_cb)
    transcriber.canceled.connect(canceled_cb)
    transcriber.session_stopped.connect(session_stopped_cb)

    # Start transcription
    await asyncio.to_thread(transcriber.start_transcribing_async().get)

    # Wait for completion
    await done_event.wait()

    # Stop transcription
    await asyncio.to_thread(transcriber.stop_transcribing_async().get)

    # Build result
    full_text = " ".join([r["text"] for r in transcription_results])

    speaker_labels = []
    for r in transcription_results:
        speaker_labels.append({
            "speaker": r["speaker"],
            "text": r["text"],
            "start": r["offset"] / 10_000_000.0,  # Convert from 100ns ticks to seconds
            "end": (r["offset"] + r["duration"]) / 10_000_000.0
        })

    return {
        "text": full_text,
        "language": speech_config.speech_recognition_language,
        "speaker_labels": speaker_labels,
        "is_final": True
    }


async def transcribe_stream(
    audio_base64: str,
    language: str = "auto",
    config: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transcribe audio using Azure Speech streaming (for partials).

    Note: This is a simplified implementation using batch API.
    For production, implement proper streaming with PushAudioInputStream.

    Args:
        audio_base64: Base64-encoded PCM16 audio chunk
        language: Language code (pl-PL, ar-EG, en-US, auto)
        config: Optional config with diarization and stability settings
        session_id: Optional session ID for connection pooling

    Returns:
        {
            "text": "partial transcription...",
            "language": "en-US",
            "is_final": false
        }
    """
    # TODO: Implement proper streaming with PushAudioInputStream
    print(f"[Azure Speech] Stream transcription using batch API (streaming not yet implemented)")

    result = await transcribe_audio_chunk(audio_base64, language, config)
    result["is_final"] = False
    return result


def _normalize_language(language: str) -> str:
    """Convert language codes to Azure Speech format"""
    # Map common language codes to Azure format (BCP-47)
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


async def get_cost(audio_duration_seconds: float) -> float:
    """
    Calculate cost for Azure Speech transcription.

    Args:
        audio_duration_seconds: Duration of audio in seconds

    Returns:
        Cost in USD
    """
    hours = audio_duration_seconds / 3600.0
    return hours * AZURE_SPEECH_PRICE_PER_HOUR

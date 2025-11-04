"""
Google Cloud Text-to-Speech Backend
Synthesizes text to MP3 audio using Google Cloud TTS API
"""

import os
import base64
from typing import Dict, Any, Optional

try:
    from google.cloud import texttospeech
    GOOGLE_TTS_AVAILABLE = True
except ImportError:
    GOOGLE_TTS_AVAILABLE = False
    print("[Google TTS] google-cloud-texttospeech not installed")

# Google Cloud TTS client (lazy initialization)
_tts_client = None


def get_client():
    """Get or create Google TTS client (lazy initialization)."""
    global _tts_client
    if _tts_client is None and GOOGLE_TTS_AVAILABLE:
        _tts_client = texttospeech.TextToSpeechClient()
        print("[Google TTS] Client initialized")
    return _tts_client


async def synthesize_speech(
    text: str,
    language: str,
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Synthesize speech using Google Cloud TTS.

    Args:
        text: Text to synthesize
        language: Language code (en, pl, ar, etc.)
        config: TTS config from routing
            {
                'voice_id': 'en-US-Neural2-D',
                'pitch': 0.0,
                'speaking_rate': 1.0,
                'voice_gender': 'MALE' or 'FEMALE'
            }

    Returns:
    {
        'audio_base64': 'base64-encoded MP3 audio',
        'format': 'mp3',
        'character_count': 42,
        'voice_id': 'en-US-Neural2-D',
        'provider': 'google_tts'
    }
    """
    if not GOOGLE_TTS_AVAILABLE:
        raise RuntimeError("Google Cloud TTS library not installed")

    client = get_client()
    if client is None:
        raise RuntimeError("Failed to initialize Google TTS client")

    try:
        # Extract config parameters
        voice_id = config.get('voice_id', 'en-US-Neural2-D')
        pitch = config.get('pitch', 0.0)
        speaking_rate = config.get('speaking_rate', 1.0)
        voice_gender_str = config.get('voice_gender', 'MALE')

        # Map voice gender string to enum
        if voice_gender_str == 'FEMALE':
            voice_gender = texttospeech.SsmlVoiceGender.FEMALE
        elif voice_gender_str == 'MALE':
            voice_gender = texttospeech.SsmlVoiceGender.MALE
        elif voice_gender_str == 'NEUTRAL':
            voice_gender = texttospeech.SsmlVoiceGender.NEUTRAL
        else:
            voice_gender = texttospeech.SsmlVoiceGender.SSML_VOICE_GENDER_UNSPECIFIED

        # Build synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Build voice parameters
        # Extract language code from voice_id (e.g., 'en-US-Neural2-D' -> 'en-US')
        if '-' in voice_id:
            # Voice ID format: en-US-Neural2-D or pl-PL-Wavenet-A
            parts = voice_id.split('-')
            if len(parts) >= 2:
                language_code = f"{parts[0]}-{parts[1]}"
            else:
                language_code = f"{language}-{language.upper()}"
        else:
            # Fallback: construct from language parameter
            language_code = f"{language}-{language.upper()}"

        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_id,
            ssml_gender=voice_gender
        )

        # Build audio config
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch
        )

        # Perform TTS request
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Encode audio to base64
        audio_base64 = base64.b64encode(response.audio_content).decode('utf-8')

        # Calculate character count for cost tracking
        character_count = len(text)

        print(f"[Google TTS] Synthesized {character_count} chars with voice {voice_id}")

        return {
            'audio_base64': audio_base64,
            'format': 'mp3',
            'character_count': character_count,
            'voice_id': voice_id,
            'provider': 'google_tts'
        }

    except Exception as e:
        print(f"[Google TTS] Synthesis failed: {e}")
        raise


async def get_available_voices(language: Optional[str] = None) -> list:
    """
    Get list of available voices for a language.

    Args:
        language: Language code (en, pl, ar, etc.) or None for all voices

    Returns:
        List of voice dicts: [{'voice_id': 'en-US-Neural2-D', 'gender': 'MALE', ...}, ...]
    """
    if not GOOGLE_TTS_AVAILABLE:
        return []

    client = get_client()
    if client is None:
        return []

    try:
        # Fetch available voices
        response = client.list_voices()

        voices = []
        for voice in response.voices:
            # Filter by language if specified
            if language and not any(lc.startswith(language) for lc in voice.language_codes):
                continue

            # Extract voice info
            for language_code in voice.language_codes:
                voices.append({
                    'voice_id': voice.name,
                    'language': language_code,
                    'gender': texttospeech.SsmlVoiceGender(voice.ssml_gender).name,
                    'natural_sample_rate': voice.natural_sample_rate_hertz
                })

        print(f"[Google TTS] Found {len(voices)} voices for language: {language or 'all'}")
        return voices

    except Exception as e:
        print(f"[Google TTS] Failed to fetch available voices: {e}")
        return []


async def estimate_cost(character_count: int) -> float:
    """
    Estimate cost for Google TTS synthesis.

    Google Cloud TTS pricing (as of 2025):
    - Standard voices: $4 per 1M characters
    - WaveNet voices: $16 per 1M characters
    - Neural2 voices: $16 per 1M characters

    Args:
        character_count: Number of characters to synthesize

    Returns:
        Estimated cost in USD
    """
    # Using Neural2/WaveNet pricing ($16 per 1M chars)
    return character_count * 0.000016

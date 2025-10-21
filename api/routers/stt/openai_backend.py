import os
import base64
import io
import wave
import httpx
from datetime import datetime

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "whisper-1")

def pcm16_to_wav(pcm16_base64: str, sample_rate=16000, channels=1) -> bytes:
    """Convert PCM16 base64 to WAV bytes"""
    pcm_data = base64.b64decode(pcm16_base64)
    
    # Create WAV file in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    
    return wav_buffer.getvalue()

async def transcribe_audio_chunk(audio_base64: str, language: str = None, prompt: str = None) -> dict:
    """
    Send audio chunk to OpenAI Whisper API
    Returns: {"text": "...", "language": "en"}

    prompt: Optional context from previous transcription to improve continuity
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not set")

    # Convert PCM16 to WAV
    wav_bytes = pcm16_to_wav(audio_base64)

    # Prepare multipart form data
    files = {
        'file': ('audio.wav', wav_bytes, 'audio/wav'),
    }

    data = {
        'model': OPENAI_STT_MODEL,
        'response_format': 'verbose_json',  # Required to get detected language
    }

    if language and language != 'auto':
        data['language'] = language

    if prompt:
        # Provide context from previous transcription (max 224 tokens)
        data['prompt'] = prompt[-224:]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            'https://api.openai.com/v1/audio/transcriptions',
            headers={'Authorization': f'Bearer {OPENAI_API_KEY}'},
            files=files,
            data=data
        )
        response.raise_for_status()
        result = response.json()

        detected_lang = result.get("language", "auto")
        print(f"[OpenAI STT] Detected language: {detected_lang}, text: {result.get('text', '')[:50]}")

        return {
            "text": result.get("text", ""),
            "language": detected_lang
        }

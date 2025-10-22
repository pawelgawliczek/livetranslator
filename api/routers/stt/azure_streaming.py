"""
Azure Speech Service Real-Time Streaming Backend

Provides low-latency streaming with speaker diarization using Azure Cognitive Services.
- Maintains persistent push audio streams per session
- Real-time partial and final transcriptions
- Conversation transcription for speaker diarization
- Automatic reconnection and error handling
"""

import os
import base64
import asyncio
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import azure.cognitiveservices.speech as speechsdk

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")

# Pricing: $1.00 per hour of audio
AZURE_SPEECH_PRICE_PER_HOUR = 1.00


@dataclass
class StreamingSession:
    """Manages a single Azure Speech streaming session"""
    session_id: str
    language: str
    config: Dict[str, Any]
    push_stream: Optional[speechsdk.audio.PushAudioInputStream] = None
    transcriber: Optional[speechsdk.transcription.ConversationTranscriber] = None
    is_started: bool = False
    is_connected: bool = False
    audio_duration: float = 0.0
    done_event: Optional[asyncio.Event] = None

    # Callbacks
    on_partial: Optional[Callable] = None
    on_final: Optional[Callable] = None
    on_error: Optional[Callable] = None


class AzureStreamingClient:
    """Connection pool manager for Azure Speech streaming sessions"""

    def __init__(self):
        self.sessions: Dict[str, StreamingSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        session_id: str,
        language: str = "en-US",
        config: Optional[Dict[str, Any]] = None,
        on_partial: Optional[Callable] = None,
        on_final: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ) -> StreamingSession:
        """Create a new streaming session with push audio stream"""

        if not AZURE_SPEECH_KEY:
            raise Exception("AZURE_SPEECH_KEY not set")

        async with self._lock:
            # Close existing session if any
            if session_id in self.sessions:
                await self.close_session(session_id)

            # Create speech config
            speech_config = speechsdk.SpeechConfig(
                subscription=AZURE_SPEECH_KEY,
                region=AZURE_SPEECH_REGION
            )
            speech_config.speech_recognition_language = _normalize_language(language)

            # Set stability threshold for partial results
            if config and "stable_partial_threshold" in config:
                stability = config["stable_partial_threshold"]
                speech_config.set_property(
                    speechsdk.PropertyId.SpeechServiceResponse_StablePartialResultThreshold,
                    str(stability)
                )

            # Create push audio stream
            push_stream = speechsdk.audio.PushAudioInputStream(
                stream_format=speechsdk.audio.AudioStreamFormat(
                    samples_per_second=16000,
                    bits_per_sample=16,
                    channels=1
                )
            )

            # Create audio config from push stream
            audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

            # Create session
            session = StreamingSession(
                session_id=session_id,
                language=_normalize_language(language),
                config=config or {},
                push_stream=push_stream,
                done_event=asyncio.Event(),
                on_partial=on_partial,
                on_final=on_final,
                on_error=on_error
            )

            # Create transcriber or recognizer based on diarization
            use_diarization = config.get("diarization", True) if config else True

            if use_diarization:
                # Use conversation transcriber for diarization
                transcriber = speechsdk.transcription.ConversationTranscriber(
                    speech_config=speech_config,
                    audio_config=audio_config
                )

                # Connect event handlers
                transcriber.transcribing.connect(
                    lambda evt: self._on_transcribing(session, evt)
                )
                transcriber.transcribed.connect(
                    lambda evt: self._on_transcribed(session, evt)
                )
                transcriber.canceled.connect(
                    lambda evt: self._on_canceled(session, evt)
                )
                transcriber.session_stopped.connect(
                    lambda evt: self._on_stopped(session, evt)
                )

                session.transcriber = transcriber

            else:
                # Use simple recognizer without diarization
                recognizer = speechsdk.SpeechRecognizer(
                    speech_config=speech_config,
                    audio_config=audio_config
                )

                # Connect event handlers
                recognizer.recognizing.connect(
                    lambda evt: self._on_transcribing(session, evt)
                )
                recognizer.recognized.connect(
                    lambda evt: self._on_transcribed(session, evt)
                )
                recognizer.canceled.connect(
                    lambda evt: self._on_canceled(session, evt)
                )
                recognizer.session_stopped.connect(
                    lambda evt: self._on_stopped(session, evt)
                )

                session.transcriber = recognizer

            # Store session
            self.sessions[session_id] = session
            session.is_connected = True

            print(f"[Azure Stream] ✅ Created session {session_id}")

            return session

    async def start_recognition(self, session_id: str) -> None:
        """Start continuous recognition"""

        session = self.sessions.get(session_id)
        if not session or not session.transcriber:
            raise Exception(f"Session {session_id} not found")

        if session.is_started:
            print(f"[Azure Stream] ⚠️  Session {session_id} already started")
            return

        try:
            # Start transcription asynchronously
            if isinstance(session.transcriber, speechsdk.transcription.ConversationTranscriber):
                await asyncio.to_thread(
                    session.transcriber.start_transcribing_async().get
                )
            else:
                await asyncio.to_thread(
                    session.transcriber.start_continuous_recognition_async().get
                )

            session.is_started = True
            print(f"[Azure Stream] 🎤 Started recognition for session {session_id}")

        except Exception as e:
            print(f"[Azure Stream] ❌ Failed to start recognition: {e}")
            if session.on_error:
                await session.on_error(f"Failed to start: {e}")
            raise

    async def send_audio(self, session_id: str, audio_base64: str) -> None:
        """Send audio chunk to the streaming session"""

        session = self.sessions.get(session_id)
        if not session or not session.push_stream:
            raise Exception(f"Session {session_id} not found")

        # Start recognition if not started
        if not session.is_started:
            await self.start_recognition(session_id)

        try:
            # Decode base64 to raw bytes
            audio_bytes = base64.b64decode(audio_base64)

            # Track duration
            duration = len(audio_bytes) / (16000 * 2)
            session.audio_duration += duration

            # Push audio to stream (synchronous operation)
            await asyncio.to_thread(session.push_stream.write, audio_bytes)

            print(f"[Azure Stream] 📤 Pushed {len(audio_bytes)} bytes "
                  f"({duration:.2f}s) to session {session_id}")

        except Exception as e:
            print(f"[Azure Stream] ❌ Failed to send audio: {e}")
            if session.on_error:
                await session.on_error(f"Failed to send audio: {e}")
            raise

    def _on_transcribing(self, session: StreamingSession, evt):
        """Handle partial transcription event"""

        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            transcript = evt.result.text

            if not transcript.strip():
                return

            result = {
                "text": transcript,
                "is_final": False,
                "language": session.language,
                "session_id": session.session_id
            }

            print(f"[Azure Stream] 📝 Partial: {transcript[:50]}...")

            # Call callback (must be async-safe)
            if session.on_partial:
                asyncio.create_task(session.on_partial(result))

    def _on_transcribed(self, session: StreamingSession, evt):
        """Handle final transcription event"""

        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            transcript = evt.result.text

            if not transcript.strip():
                return

            # Extract speaker info if available
            speaker_id = None
            offset = 0
            duration = 0

            if hasattr(evt.result, 'speaker_id'):
                speaker_id = evt.result.speaker_id
            if hasattr(evt.result, 'offset'):
                offset = evt.result.offset / 10_000_000.0  # Convert from 100ns ticks
            if hasattr(evt.result, 'duration'):
                duration = evt.result.duration / 10_000_000.0

            # Build speaker labels
            speaker_labels = []
            if speaker_id:
                speaker_labels.append({
                    "speaker": speaker_id,
                    "text": transcript,
                    "start": offset,
                    "end": offset + duration
                })

            result = {
                "text": transcript,
                "is_final": True,
                "language": session.language,
                "speaker_labels": speaker_labels,
                "session_id": session.session_id
            }

            print(f"[Azure Stream] ✅ Final: {transcript[:50]}... "
                  f"(speaker: {speaker_id or 'none'})")

            # Call callback (must be async-safe)
            if session.on_final:
                asyncio.create_task(session.on_final(result))

    def _on_canceled(self, session: StreamingSession, evt):
        """Handle cancellation event"""

        print(f"[Azure Stream] ⚠️  Canceled for {session.session_id}: {evt}")

        if evt.reason == speechsdk.CancellationReason.Error:
            error_msg = f"Error: {evt.error_details}"
            print(f"[Azure Stream] ❌ {error_msg}")

            if session.on_error:
                asyncio.create_task(session.on_error(error_msg))

        session.done_event.set()

    def _on_stopped(self, session: StreamingSession, evt):
        """Handle session stopped event"""

        print(f"[Azure Stream] 🏁 Session stopped for {session.session_id}")
        session.done_event.set()

    async def end_of_stream(self, session_id: str) -> None:
        """Signal end of audio stream"""

        session = self.sessions.get(session_id)
        if not session or not session.push_stream:
            return

        try:
            # Close push stream
            await asyncio.to_thread(session.push_stream.close)
            print(f"[Azure Stream] 🏁 Closed push stream for {session_id}")

            # Wait for final results (with timeout)
            await asyncio.wait_for(session.done_event.wait(), timeout=5.0)

        except asyncio.TimeoutError:
            print(f"[Azure Stream] ⏱️  Timeout waiting for final results in {session_id}")
        except Exception as e:
            print(f"[Azure Stream] ⚠️  Error ending stream: {e}")

    async def close_session(self, session_id: str):
        """Close a streaming session"""

        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return

            # End stream if not already ended
            if session.is_started:
                try:
                    # Stop transcription
                    if isinstance(session.transcriber, speechsdk.transcription.ConversationTranscriber):
                        await asyncio.to_thread(
                            session.transcriber.stop_transcribing_async().get
                        )
                    else:
                        await asyncio.to_thread(
                            session.transcriber.stop_continuous_recognition_async().get
                        )

                    # Close push stream
                    if session.push_stream:
                        await asyncio.to_thread(session.push_stream.close)

                except Exception as e:
                    print(f"[Azure Stream] ⚠️  Error stopping transcription: {e}")

            # Remove from sessions
            del self.sessions[session_id]

            print(f"[Azure Stream] 🔌 Closed session {session_id} "
                  f"(duration: {session.audio_duration:.1f}s)")

    async def get_session_cost(self, session_id: str) -> float:
        """Get cost for a streaming session"""

        session = self.sessions.get(session_id)
        if not session:
            return 0.0

        hours = session.audio_duration / 3600.0
        return hours * AZURE_SPEECH_PRICE_PER_HOUR

    async def close_all(self):
        """Close all active sessions"""

        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)


def _normalize_language(language: str) -> str:
    """Convert language codes to Azure Speech format"""
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


# Global connection pool
_client_pool: Optional[AzureStreamingClient] = None


def get_streaming_client() -> AzureStreamingClient:
    """Get or create the global streaming client"""
    global _client_pool
    if _client_pool is None:
        _client_pool = AzureStreamingClient()
    return _client_pool


async def get_cost(audio_duration_seconds: float) -> float:
    """Calculate cost for Azure Speech transcription"""
    hours = audio_duration_seconds / 3600.0
    return hours * AZURE_SPEECH_PRICE_PER_HOUR

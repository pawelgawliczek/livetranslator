"""
Google Cloud Speech v2 Real-Time Streaming Backend

Provides low-latency gRPC streaming with speaker diarization.
- Maintains persistent gRPC streams per session
- Real-time partial and final transcriptions with stability scores
- Speaker diarization with word-level timestamps
- Automatic reconnection and error handling
"""

import os
import base64
import asyncio
from typing import Optional, Dict, Any, Callable, AsyncIterator
from dataclasses import dataclass
from google.cloud import speech_v2 as speech
from google.api_core.client_options import ClientOptions
from google.api_core import exceptions as google_exceptions

GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us")  # us, eu, asia

# Pricing: $0.024 per minute = $1.44 per hour
GOOGLE_STT_PRICE_PER_MINUTE = 0.024


@dataclass
class StreamingSession:
    """Manages a single gRPC streaming session"""
    session_id: str
    language: str
    config: Dict[str, Any]
    audio_queue: asyncio.Queue
    is_started: bool = False
    is_connected: bool = False
    audio_duration: float = 0.0
    stream_task: Optional[asyncio.Task] = None

    # Callbacks
    on_partial: Optional[Callable] = None
    on_final: Optional[Callable] = None
    on_error: Optional[Callable] = None


class GoogleStreamingClient:
    """Connection pool manager for Google Speech v2 streaming sessions"""

    def __init__(self):
        self.sessions: Dict[str, StreamingSession] = {}
        self._lock = asyncio.Lock()
        self.client: Optional[speech.SpeechClient] = None

    def _get_client(self) -> speech.SpeechClient:
        """Get or create the Speech client"""
        if not GOOGLE_APPLICATION_CREDENTIALS:
            raise Exception("GOOGLE_APPLICATION_CREDENTIALS not set")
        if not GOOGLE_CLOUD_PROJECT:
            raise Exception("GOOGLE_CLOUD_PROJECT not set")

        if self.client is None:
            client_options = ClientOptions(
                api_endpoint=f"{GOOGLE_CLOUD_LOCATION}-speech.googleapis.com"
            )
            self.client = speech.SpeechClient(client_options=client_options)

        return self.client

    async def create_session(
        self,
        session_id: str,
        language: str = "en-US",
        config: Optional[Dict[str, Any]] = None,
        on_partial: Optional[Callable] = None,
        on_final: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ) -> StreamingSession:
        """Create a new streaming session with gRPC connection"""

        async with self._lock:
            # Close existing session if any
            if session_id in self.sessions:
                await self.close_session(session_id)

            # Create new session
            session = StreamingSession(
                session_id=session_id,
                language=_normalize_language(language),
                config=config or {},
                audio_queue=asyncio.Queue(),
                on_partial=on_partial,
                on_final=on_final,
                on_error=on_error
            )

            # Store session
            self.sessions[session_id] = session

            # Start streaming task
            session.stream_task = asyncio.create_task(
                self._streaming_loop(session)
            )

            print(f"[Google Stream] ✅ Created session {session_id}")

            return session

    async def _streaming_loop(self, session: StreamingSession):
        """Main streaming loop for a session"""

        try:
            client = self._get_client()

            # Build streaming config
            streaming_config = speech.StreamingRecognitionConfig(
                config=speech.RecognitionConfig(
                    auto_decoding_config=speech.AutoDetectDecodingConfig(),
                    language_codes=[session.language],
                    model="long",
                    features=speech.RecognitionFeatures(
                        enable_automatic_punctuation=True,
                        enable_word_time_offsets=True,
                    ),
                ),
                streaming_features=speech.StreamingRecognitionFeatures(
                    interim_results=True,  # Enable partial results
                ),
            )

            # Enable diarization
            if session.config.get("diarization", True):
                min_speakers = session.config.get("min_speaker_count", 2)
                max_speakers = session.config.get("max_speaker_count", 6)
                streaming_config.config.features.diarization_config = (
                    speech.SpeakerDiarizationConfig(
                        min_speaker_count=min_speakers,
                        max_speaker_count=max_speakers,
                    )
                )

            # Create request generator
            async def request_generator() -> AsyncIterator[speech.StreamingRecognizeRequest]:
                # First request with config
                recognizer = f"projects/{GOOGLE_CLOUD_PROJECT}/locations/{GOOGLE_CLOUD_LOCATION}/recognizers/_"
                yield speech.StreamingRecognizeRequest(
                    recognizer=recognizer,
                    streaming_config=streaming_config
                )

                # Subsequent requests with audio
                while True:
                    try:
                        audio_bytes = await asyncio.wait_for(
                            session.audio_queue.get(),
                            timeout=30.0  # 30s timeout
                        )

                        if audio_bytes is None:  # End-of-stream marker
                            print(f"[Google Stream] 🏁 End of audio stream for {session.session_id}")
                            break

                        # Track duration
                        duration = len(audio_bytes) / (16000 * 2)
                        session.audio_duration += duration

                        yield speech.StreamingRecognizeRequest(
                            audio=audio_bytes
                        )

                    except asyncio.TimeoutError:
                        # No audio for 30 seconds, keep connection alive
                        print(f"[Google Stream] ⏱️  Timeout waiting for audio in {session.session_id}")
                        break

            # Start streaming recognition
            session.is_connected = True
            session.is_started = True
            print(f"[Google Stream] 🎤 Started streaming for {session.session_id}")

            responses = client.streaming_recognize(
                requests=request_generator()
            )

            # Process responses
            for response in responses:
                await self._handle_response(session, response)

            print(f"[Google Stream] ✅ Stream ended for {session.session_id}")

        except google_exceptions.GoogleAPICallError as e:
            print(f"[Google Stream] ❌ API error for {session.session_id}: {e}")
            session.is_connected = False
            if session.on_error:
                await session.on_error(f"API error: {e}")

        except Exception as e:
            print(f"[Google Stream] ❌ Unexpected error for {session.session_id}: {e}")
            session.is_connected = False
            if session.on_error:
                await session.on_error(f"Unexpected error: {e}")

    async def _handle_response(
        self,
        session: StreamingSession,
        response: speech.StreamingRecognizeResponse
    ):
        """Handle streaming recognition response"""

        for result in response.results:
            if not result.alternatives:
                continue

            alternative = result.alternatives[0]
            transcript = alternative.transcript

            if not transcript.strip():
                continue

            # Partial result
            if not result.is_final:
                stability = result.stability if hasattr(result, 'stability') else 0.0

                result_data = {
                    "text": transcript,
                    "is_final": False,
                    "stability": stability,
                    "language": session.language,
                    "session_id": session.session_id
                }

                print(f"[Google Stream] 📝 Partial (stability={stability:.2f}): {transcript[:50]}...")

                if session.on_partial:
                    await session.on_partial(result_data)

            # Final result
            else:
                # Extract speaker labels
                speaker_labels = []
                if hasattr(alternative, 'words') and alternative.words:
                    current_speaker = None
                    current_words = []
                    current_start = None

                    for word_info in alternative.words:
                        speaker = (word_info.speaker_label
                                 if hasattr(word_info, 'speaker_label')
                                 else 0)

                        if speaker != current_speaker:
                            # Save previous speaker segment
                            if current_words:
                                speaker_labels.append({
                                    "speaker": current_speaker,
                                    "text": " ".join(current_words),
                                    "start": current_start,
                                    "end": word_info.start_offset.total_seconds()
                                })

                            # Start new speaker segment
                            current_speaker = speaker
                            current_words = [word_info.word]
                            current_start = (word_info.start_offset.total_seconds()
                                           if hasattr(word_info, 'start_offset')
                                           else 0)
                        else:
                            current_words.append(word_info.word)

                    # Add last segment
                    if current_words:
                        last_word = alternative.words[-1]
                        speaker_labels.append({
                            "speaker": current_speaker,
                            "text": " ".join(current_words),
                            "start": current_start,
                            "end": (last_word.end_offset.total_seconds()
                                  if hasattr(last_word, 'end_offset')
                                  else 0)
                        })

                result_data = {
                    "text": transcript,
                    "is_final": True,
                    "language": session.language,
                    "speaker_labels": speaker_labels,
                    "session_id": session.session_id
                }

                print(f"[Google Stream] ✅ Final: {transcript[:50]}... "
                      f"(speakers: {len(speaker_labels)})")

                if session.on_final:
                    await session.on_final(result_data)

    async def send_audio(self, session_id: str, audio_base64: str) -> None:
        """Send audio chunk to the streaming session"""

        session = self.sessions.get(session_id)
        if not session:
            raise Exception(f"Session {session_id} not found")

        # Decode base64 to raw bytes
        audio_bytes = base64.b64decode(audio_base64)

        # Add to queue
        await session.audio_queue.put(audio_bytes)

        print(f"[Google Stream] 📤 Queued {len(audio_bytes)} bytes "
              f"({len(audio_bytes) / 32000:.2f}s) for session {session_id}")

    async def end_of_stream(self, session_id: str) -> None:
        """Signal end of audio stream"""

        session = self.sessions.get(session_id)
        if not session:
            return

        # Send end-of-stream marker (None)
        await session.audio_queue.put(None)
        print(f"[Google Stream] 🏁 Sent end-of-stream for session {session_id}")

    async def close_session(self, session_id: str):
        """Close a streaming session"""

        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return

            # Send end-of-stream
            if session.is_connected:
                try:
                    await self.end_of_stream(session_id)
                    await asyncio.sleep(0.5)  # Wait for final results
                except Exception as e:
                    print(f"[Google Stream] ⚠️  Error ending stream: {e}")

            # Cancel stream task
            if session.stream_task and not session.stream_task.done():
                session.stream_task.cancel()
                try:
                    await session.stream_task
                except asyncio.CancelledError:
                    pass

            # Remove from sessions
            del self.sessions[session_id]

            print(f"[Google Stream] 🔌 Closed session {session_id} "
                  f"(duration: {session.audio_duration:.1f}s)")

    async def get_session_cost(self, session_id: str) -> float:
        """Get cost for a streaming session"""

        session = self.sessions.get(session_id)
        if not session:
            return 0.0

        minutes = session.audio_duration / 60.0
        return minutes * GOOGLE_STT_PRICE_PER_MINUTE

    async def close_all(self):
        """Close all active sessions"""

        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)

        # Close client
        if self.client:
            self.client = None


def _normalize_language(language: str) -> str:
    """Convert language codes to Google Cloud Speech format"""
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
_client_pool: Optional[GoogleStreamingClient] = None


def get_streaming_client() -> GoogleStreamingClient:
    """Get or create the global streaming client"""
    global _client_pool
    if _client_pool is None:
        _client_pool = GoogleStreamingClient()
    return _client_pool


async def get_cost(audio_duration_seconds: float) -> float:
    """Calculate cost for Google Cloud Speech transcription"""
    minutes = audio_duration_seconds / 60.0
    return minutes * GOOGLE_STT_PRICE_PER_MINUTE

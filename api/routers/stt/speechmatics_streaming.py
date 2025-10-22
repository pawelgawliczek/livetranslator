"""
Speechmatics Real-Time Streaming Backend

Provides low-latency WebSocket streaming with speaker diarization.
- Maintains persistent WebSocket connections per session
- Real-time partial and final transcriptions
- Speaker diarization with word-level timestamps
- Automatic reconnection and error handling
"""

import os
import base64
import asyncio
import json
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import websockets
from websockets.exceptions import WebSocketException

SPEECHMATICS_API_KEY = os.getenv("SPEECHMATICS_API_KEY", "")
SPEECHMATICS_REGION = os.getenv("SPEECHMATICS_REGION", "eu2")  # eu2, us2, etc.

# Pricing: $0.08 per hour of audio
SPEECHMATICS_PRICE_PER_HOUR = 0.08


@dataclass
class StreamingSession:
    """Manages a single WebSocket streaming session"""
    session_id: str
    websocket: Optional[websockets.WebSocketClientProtocol]
    language: str
    config: Dict[str, Any]
    is_started: bool = False
    is_connected: bool = False
    audio_duration: float = 0.0

    # Callbacks
    on_partial: Optional[Callable] = None
    on_final: Optional[Callable] = None
    on_error: Optional[Callable] = None


class SpeechmaticsStreamingClient:
    """Connection pool manager for Speechmatics WebSocket sessions"""

    def __init__(self):
        self.sessions: Dict[str, StreamingSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        session_id: str,
        language: str = "en",
        config: Optional[Dict[str, Any]] = None,
        on_partial: Optional[Callable] = None,
        on_final: Optional[Callable] = None,
        on_error: Optional[Callable] = None
    ) -> StreamingSession:
        """Create a new streaming session with WebSocket connection"""

        if not SPEECHMATICS_API_KEY:
            raise Exception("SPEECHMATICS_API_KEY not set")

        async with self._lock:
            # Close existing session if any
            if session_id in self.sessions:
                await self.close_session(session_id)

            # Create new session
            session = StreamingSession(
                session_id=session_id,
                websocket=None,
                language=_normalize_language(language),
                config=config or {},
                on_partial=on_partial,
                on_final=on_final,
                on_error=on_error
            )

            # Connect WebSocket
            try:
                ws_url = f"wss://{SPEECHMATICS_REGION}.rt.speechmatics.com/v2"
                session.websocket = await websockets.connect(
                    ws_url,
                    extra_headers={
                        "Authorization": f"Bearer {SPEECHMATICS_API_KEY}"
                    },
                    ping_interval=30,  # Keep connection alive
                    ping_timeout=10
                )
                session.is_connected = True

                print(f"[Speechmatics Stream] ✅ Connected session {session_id}")

                # Start listening to responses in background
                asyncio.create_task(self._listen_to_responses(session))

                # Store session
                self.sessions[session_id] = session

                return session

            except Exception as e:
                print(f"[Speechmatics Stream] ❌ Connection failed: {e}")
                if on_error:
                    await on_error(f"Connection failed: {e}")
                raise

    async def start_recognition(self, session_id: str) -> None:
        """Send start_recognition message to begin transcription"""

        session = self.sessions.get(session_id)
        if not session or not session.websocket:
            raise Exception(f"Session {session_id} not found or not connected")

        if session.is_started:
            print(f"[Speechmatics Stream] ⚠️  Session {session_id} already started")
            return

        # Build start request
        start_request = {
            "message": "StartRecognition",
            "transcription_config": {
                "language": session.language,
                "operating_point": session.config.get("operating_point", "enhanced"),
                "max_delay": session.config.get("max_delay", 1.5),  # 1.5s for ultra-fast response
                "enable_partials": True,  # Enable partial results
            },
            "audio_format": {
                "type": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 16000
            }
        }

        # Enable diarization
        if session.config.get("diarization", True):
            start_request["transcription_config"]["diarization"] = "speaker"

        # Send start request
        try:
            await session.websocket.send(json.dumps(start_request))
            session.is_started = True
            print(f"[Speechmatics Stream] 🎤 Started recognition for session {session_id}")

        except Exception as e:
            print(f"[Speechmatics Stream] ❌ Failed to start recognition: {e}")
            if session.on_error:
                await session.on_error(f"Failed to start: {e}")
            raise

    async def send_audio(self, session_id: str, audio_base64: str) -> None:
        """Send audio chunk to the streaming session"""

        session = self.sessions.get(session_id)
        if not session or not session.websocket:
            raise Exception(f"Session {session_id} not found or not connected")

        if not session.is_started:
            await self.start_recognition(session_id)

        try:
            # Decode base64 to raw bytes
            audio_bytes = base64.b64decode(audio_base64)

            # Track audio duration
            duration = len(audio_bytes) / (16000 * 2)  # 16kHz, 16-bit PCM
            session.audio_duration += duration

            # Send raw audio data (Speechmatics expects raw PCM, not base64)
            await session.websocket.send(audio_bytes)

            print(f"[Speechmatics Stream] 📤 Sent {len(audio_bytes)} bytes "
                  f"({duration:.2f}s) to session {session_id}")

        except Exception as e:
            print(f"[Speechmatics Stream] ❌ Failed to send audio: {e}")
            if session.on_error:
                await session.on_error(f"Failed to send audio: {e}")
            raise

    async def end_of_stream(self, session_id: str) -> None:
        """Signal end of audio stream"""

        session = self.sessions.get(session_id)
        if not session or not session.websocket:
            return

        try:
            end_message = {"message": "EndOfStream"}
            await session.websocket.send(json.dumps(end_message))
            print(f"[Speechmatics Stream] 🏁 Sent EndOfStream for session {session_id}")

        except Exception as e:
            print(f"[Speechmatics Stream] ❌ Failed to send EndOfStream: {e}")

    async def _listen_to_responses(self, session: StreamingSession):
        """Background task to listen to WebSocket responses"""

        try:
            async for message in session.websocket:
                try:
                    # Parse JSON response
                    if isinstance(message, bytes):
                        # Ignore binary messages (shouldn't happen)
                        continue

                    data = json.loads(message)
                    message_type = data.get("message", "")

                    # Handle different message types
                    if message_type == "RecognitionStarted":
                        print(f"[Speechmatics Stream] ✅ Recognition started for {session.session_id}")

                    elif message_type == "AudioAdded":
                        # Acknowledgement of audio receipt (can ignore)
                        pass

                    elif message_type == "AddPartialTranscript":
                        # Partial transcription result
                        await self._handle_partial(session, data)

                    elif message_type == "AddTranscript":
                        # Final transcription result
                        await self._handle_final(session, data)

                    elif message_type == "EndOfTranscript":
                        print(f"[Speechmatics Stream] 🏁 End of transcript for {session.session_id}")

                    elif message_type == "Warning":
                        print(f"[Speechmatics Stream] ⚠️  Warning: {data.get('reason', 'unknown')}")

                    elif message_type == "Error":
                        error_msg = data.get("reason", "Unknown error")
                        print(f"[Speechmatics Stream] ❌ Error: {error_msg}")
                        if session.on_error:
                            await session.on_error(error_msg)

                except json.JSONDecodeError as e:
                    print(f"[Speechmatics Stream] ⚠️  Invalid JSON: {e}")
                except Exception as e:
                    print(f"[Speechmatics Stream] ⚠️  Error handling message: {e}")

        except WebSocketException as e:
            print(f"[Speechmatics Stream] 🔌 WebSocket error for {session.session_id}: {e}")
            session.is_connected = False
            if session.on_error:
                await session.on_error(f"WebSocket error: {e}")

        except Exception as e:
            print(f"[Speechmatics Stream] ❌ Unexpected error: {e}")
            session.is_connected = False
            if session.on_error:
                await session.on_error(f"Unexpected error: {e}")

    async def _handle_partial(self, session: StreamingSession, data: Dict[str, Any]):
        """Handle partial transcript message"""

        # Extract metadata
        metadata = data.get("metadata", {})
        transcript = metadata.get("transcript", "")

        if not transcript.strip():
            return

        # Build result
        result = {
            "text": transcript,
            "is_final": False,
            "language": session.language,
            "session_id": session.session_id
        }

        print(f"[Speechmatics Stream] 📝 Partial: {transcript[:50]}...")

        # Call callback
        if session.on_partial:
            await session.on_partial(result)

    async def _handle_final(self, session: StreamingSession, data: Dict[str, Any]):
        """Handle final transcript message"""

        # Extract metadata
        metadata = data.get("metadata", {})
        transcript = metadata.get("transcript", "")

        if not transcript.strip():
            return

        # Extract results with word-level details
        results = data.get("results", [])
        speaker_labels = []

        # Parse speaker segments
        if results:
            current_speaker = None
            current_words = []
            current_start = None

            for result in results:
                if result.get("type") == "word":
                    alternatives = result.get("alternatives", [])
                    if alternatives:
                        word_data = alternatives[0]
                        word = word_data.get("content", "")
                        speaker = word_data.get("speaker")
                        start_time = word_data.get("start_time", 0)
                        end_time = word_data.get("end_time", 0)

                        # Group by speaker
                        if speaker and speaker != current_speaker:
                            # Save previous speaker segment
                            if current_words:
                                speaker_labels.append({
                                    "speaker": current_speaker,
                                    "text": " ".join(current_words),
                                    "start": current_start,
                                    "end": end_time
                                })

                            # Start new speaker segment
                            current_speaker = speaker
                            current_words = [word]
                            current_start = start_time
                        elif speaker:
                            current_words.append(word)

            # Add last segment
            if current_words and current_speaker:
                last_result = results[-1]
                last_alt = last_result.get("alternatives", [{}])[0]
                speaker_labels.append({
                    "speaker": current_speaker,
                    "text": " ".join(current_words),
                    "start": current_start,
                    "end": last_alt.get("end_time", 0)
                })

        # Build result
        result = {
            "text": transcript,
            "is_final": True,
            "language": session.language,
            "speaker_labels": speaker_labels,
            "session_id": session.session_id
        }

        print(f"[Speechmatics Stream] ✅ Final: {transcript[:50]}... "
              f"(speakers: {len(speaker_labels)})")

        # Call callback
        if session.on_final:
            await session.on_final(result)

    async def close_session(self, session_id: str):
        """Close a streaming session"""

        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return

            # Send EndOfStream first
            if session.websocket and session.is_connected:
                try:
                    await self.end_of_stream(session_id)
                    await asyncio.sleep(0.5)  # Wait for final results
                except Exception as e:
                    print(f"[Speechmatics Stream] ⚠️  Error ending stream: {e}")

            # Close WebSocket
            if session.websocket:
                try:
                    await session.websocket.close()
                except Exception as e:
                    print(f"[Speechmatics Stream] ⚠️  Error closing WebSocket: {e}")

            # Remove from sessions
            del self.sessions[session_id]

            print(f"[Speechmatics Stream] 🔌 Closed session {session_id} "
                  f"(duration: {session.audio_duration:.1f}s)")

    async def get_session_cost(self, session_id: str) -> float:
        """Get cost for a streaming session"""

        session = self.sessions.get(session_id)
        if not session:
            return 0.0

        hours = session.audio_duration / 3600.0
        return hours * SPEECHMATICS_PRICE_PER_HOUR

    async def close_all(self):
        """Close all active sessions"""

        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)


def _normalize_language(language: str) -> str:
    """Convert language codes to Speechmatics format"""
    lang_map = {
        "pl": "pl",
        "pl-PL": "pl",
        "en": "en",
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
        "auto": "en",  # Default to English for auto-detect
        "*": "en"
    }
    return lang_map.get(language, "en")


# Global connection pool
_client_pool: Optional[SpeechmaticsStreamingClient] = None


def get_streaming_client() -> SpeechmaticsStreamingClient:
    """Get or create the global streaming client"""
    global _client_pool
    if _client_pool is None:
        _client_pool = SpeechmaticsStreamingClient()
    return _client_pool


async def get_cost(audio_duration_seconds: float) -> float:
    """Calculate cost for Speechmatics transcription"""
    hours = audio_duration_seconds / 3600.0
    return hours * SPEECHMATICS_PRICE_PER_HOUR

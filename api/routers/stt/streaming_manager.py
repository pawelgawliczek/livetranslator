"""
WebSocket Streaming Connection Manager

Manages persistent WebSocket connections for STT providers that require
streaming (Speechmatics, Google v2, Azure, Soniox).

Architecture:
- One websocket connection per (room, provider) tuple
- Connection lifecycle: created on first partial, closed on audio_end
- Automatic reconnection on connection failures
- Thread-safe connection pooling
"""

import os
import asyncio
import base64
from typing import Dict, Optional, Callable, Any
from datetime import datetime
from collections import defaultdict
import threading


class StreamingConnection:
    """
    Represents a single persistent streaming connection to an STT provider.
    """

    def __init__(
        self,
        room_id: str,
        provider: str,
        language: str,
        config: Dict[str, Any],
        on_partial: Callable,
        on_final: Callable,
        on_error: Callable
    ):
        self.room_id = room_id
        self.provider = provider
        self.language = language
        self.config = config
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error

        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        self.is_connected = False
        self.is_closing = False
        self.connection = None

        # Provider-specific connection objects
        self.ws_client = None  # For Speechmatics
        self.stream = None     # For other providers

        # Accumulated state for this session
        self.segment_id = None
        self.revision = 0
        self.accumulated_text = ""
        self.finalized_text = ""  # For Speechmatics: text confirmed by AddTranscript

        self._lock = threading.Lock()

    async def connect(self):
        """Initialize connection to the provider."""
        if self.is_connected:
            return

        print(f"[StreamingConnection] Connecting to {self.provider} for room={self.room_id}, lang={self.language}")

        try:
            if self.provider == "speechmatics":
                await self._connect_speechmatics()
            elif self.provider == "google_v2":
                await self._connect_google()
            elif self.provider == "azure":
                await self._connect_azure()
            elif self.provider == "soniox":
                await self._connect_soniox()
            else:
                raise ValueError(f"Provider {self.provider} does not support streaming")

            self.is_connected = True
            print(f"[StreamingConnection] ✓ Connected to {self.provider} for room={self.room_id}")

        except Exception as e:
            print(f"[StreamingConnection] ✗ Connection failed: {e}")
            await self.on_error({"error": str(e), "room_id": self.room_id, "provider": self.provider})
            raise

    async def send_audio(self, audio_b64: str):
        """Send audio chunk to the streaming connection."""
        if not self.is_connected or self.is_closing:
            print(f"[StreamingConnection] Cannot send audio - connection not ready")
            return

        self.last_activity = datetime.now()
        audio_bytes = base64.b64decode(audio_b64)

        try:
            if self.provider == "speechmatics":
                await self._send_speechmatics(audio_bytes)
            elif self.provider == "google_v2":
                await self._send_google(audio_bytes)
            elif self.provider == "azure":
                await self._send_azure(audio_bytes)
            elif self.provider == "soniox":
                await self._send_soniox(audio_bytes)
        except Exception as e:
            print(f"[StreamingConnection] Error sending audio: {e}")
            await self.on_error({"error": str(e), "room_id": self.room_id, "provider": self.provider})
            raise

    def reset_for_new_segment(self, segment_id: int):
        """Reset accumulated state for a new audio segment."""
        print(f"[StreamingConnection] 🔄 Resetting for new segment {segment_id}")
        self.segment_id = segment_id
        self.revision = 0
        self.accumulated_text = ""
        self.finalized_text = ""

    async def close(self):
        """Close the streaming connection."""
        if self.is_closing:
            return

        self.is_closing = True
        print(f"[StreamingConnection] Closing {self.provider} connection for room={self.room_id}")

        try:
            if self.provider == "speechmatics" and self.ws_client:
                # Speechmatics: send EndOfStream message
                import json
                end_of_stream = {"message": "EndOfStream", "last_seq_no": 0}
                await self.ws_client.send(json.dumps(end_of_stream))
                print(f"[StreamingConnection] Sent EndOfStream to Speechmatics")

                # Close the websocket
                await self.ws_client.close()
            elif self.stream:
                # Other providers: close stream
                if hasattr(self.stream, 'close'):
                    await self.stream.close()

            self.is_connected = False
            print(f"[StreamingConnection] ✓ Closed {self.provider} connection for room={self.room_id}")

        except Exception as e:
            print(f"[StreamingConnection] Error closing connection: {e}")

    # Provider-specific implementations

    async def _connect_speechmatics(self):
        """Connect to Speechmatics WebSocket API using native protocol."""
        import websockets
        import json

        SPEECHMATICS_API_KEY = os.getenv("SPEECHMATICS_API_KEY", "")
        SPEECHMATICS_REGION = os.getenv("SPEECHMATICS_REGION", "eu2")

        if not SPEECHMATICS_API_KEY:
            raise Exception("SPEECHMATICS_API_KEY not set")

        # Transcription config
        diarization = self.config.get("diarization", True)
        operating_point = self.config.get("operating_point", "enhanced")
        max_delay = self.config.get("max_delay", 1.5)

        # WebSocket URL
        url = f"wss://{SPEECHMATICS_REGION}.rt.speechmatics.com/v2"

        print(f"[StreamingConnection] Connecting to Speechmatics: {url}")

        # Connect to WebSocket
        # Use additional_headers instead of extra_headers for websockets library
        self.ws_client = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Bearer {SPEECHMATICS_API_KEY}"},
            ping_interval=20,
            ping_timeout=10
        )

        # Send StartRecognition message
        print(f"[StreamingConnection] Config: lang={self.language}, op={operating_point}, delay={max_delay}, diar={diarization}")

        start_recognition = {
            "message": "StartRecognition",
            "audio_format": {
                "type": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 16000
            },
            "transcription_config": {
                "language": self.language,
                "operating_point": operating_point,
                "max_delay": max_delay,
                "enable_partials": True,
                "diarization": "speaker" if diarization else "none"
            }
        }

        print(f"[StreamingConnection] Sending StartRecognition...")
        await self.ws_client.send(json.dumps(start_recognition))
        print(f"[StreamingConnection] ✓ Sent StartRecognition to Speechmatics")

        # Start listening for responses in background
        asyncio.create_task(self._speechmatics_listener())

    async def _speechmatics_listener(self):
        """Listen for messages from Speechmatics WebSocket."""
        import json

        try:
            async for message in self.ws_client:
                try:
                    msg = json.loads(message)
                    msg_type = msg.get("message")

                    if msg_type == "RecognitionStarted":
                        print(f"[StreamingConnection] Speechmatics recognition started for room={self.room_id}")

                    elif msg_type == "AddPartialTranscript":
                        # Speechmatics sends partial updates that may replace previous partials
                        # We need to keep finalized text and append new partials
                        metadata = msg.get("metadata", {})
                        partial_text = metadata.get("transcript", "").strip()

                        if partial_text:
                            # Combine finalized text + current partial
                            if self.finalized_text:
                                full_text = self.finalized_text + " " + partial_text
                            else:
                                full_text = partial_text

                            self.accumulated_text = full_text
                            self.revision += 1

                            print(f"[StreamingConnection] 📝 Partial: fin='{self.finalized_text[:30] if self.finalized_text else ''}' + part='{partial_text[:30]}'")

                            await self.on_partial({
                                "text": full_text,
                                "language": self.language,
                                "room_id": self.room_id,
                                "is_final": False
                            })

                    elif msg_type == "AddTranscript":
                        # Final result - this is confirmed text that won't change
                        metadata = msg.get("metadata", {})
                        final_text = metadata.get("transcript", "").strip()
                        if final_text:
                            # Add to finalized text
                            if self.finalized_text:
                                self.finalized_text += " " + final_text
                            else:
                                self.finalized_text = final_text

                            print(f"[StreamingConnection] ✓ Finalized: '{final_text[:50]}'")

                            await self.on_final({
                                "text": final_text,
                                "language": self.language,
                                "room_id": self.room_id,
                                "is_final": True
                            })

                    elif msg_type == "EndOfTranscript":
                        print(f"[StreamingConnection] Speechmatics end of transcript for room={self.room_id}")

                    elif msg_type == "Error":
                        error_msg = msg.get("reason", "Unknown error")
                        error_type = msg.get("type", "unknown")
                        print(f"[StreamingConnection] Speechmatics error: {error_type} - {error_msg}")
                        await self.on_error({
                            "error": f"{error_type}: {error_msg}",
                            "room_id": self.room_id,
                            "provider": "speechmatics"
                        })

                except json.JSONDecodeError as e:
                    print(f"[StreamingConnection] Failed to parse Speechmatics message: {e}")
                except Exception as e:
                    print(f"[StreamingConnection] Error processing Speechmatics message: {e}")

        except Exception as e:
            print(f"[StreamingConnection] Speechmatics listener error: {e}")
            await self.on_error({
                "error": str(e),
                "room_id": self.room_id,
                "provider": "speechmatics"
            })

    async def _send_speechmatics(self, audio_bytes: bytes):
        """Send audio chunk to Speechmatics WebSocket."""
        if self.ws_client and not self.is_closing:
            try:
                # Send binary audio data
                await self.ws_client.send(audio_bytes)
            except Exception as e:
                print(f"[StreamingConnection] Error sending audio to Speechmatics: {e}")
                raise

    async def _connect_google(self):
        """Connect to Google Speech-to-Text v2 streaming API."""
        # TODO: Implement Google v2 streaming
        raise NotImplementedError("Google v2 streaming not yet implemented")

    async def _send_google(self, audio_bytes: bytes):
        """Send audio to Google."""
        # TODO: Implement
        pass

    async def _connect_azure(self):
        """Connect to Azure Speech SDK streaming."""
        # TODO: Implement Azure streaming
        raise NotImplementedError("Azure streaming not yet implemented")

    async def _send_azure(self, audio_bytes: bytes):
        """Send audio to Azure."""
        # TODO: Implement
        pass

    async def _connect_soniox(self):
        """Connect to Soniox streaming API."""
        # TODO: Implement Soniox streaming
        raise NotImplementedError("Soniox streaming not yet implemented")

    async def _send_soniox(self, audio_bytes: bytes):
        """Send audio to Soniox."""
        # TODO: Implement
        pass


class StreamingManager:
    """
    Manages multiple streaming connections across rooms and providers.
    """

    def __init__(self):
        self.connections: Dict[str, StreamingConnection] = {}  # key: f"{room_id}:{provider}"
        self._lock = asyncio.Lock()

    def _get_key(self, room_id: str, provider: str) -> str:
        """Generate connection pool key."""
        return f"{room_id}:{provider}"

    async def get_or_create_connection(
        self,
        room_id: str,
        provider: str,
        language: str,
        config: Dict[str, Any],
        on_partial: Callable,
        on_final: Callable,
        on_error: Callable
    ) -> StreamingConnection:
        """
        Get existing connection or create a new one.
        """
        key = self._get_key(room_id, provider)

        async with self._lock:
            if key in self.connections:
                conn = self.connections[key]
                if conn.is_connected and not conn.is_closing:
                    print(f"[StreamingManager] Reusing connection for {key}")
                    return conn
                else:
                    # Connection is stale, remove it
                    print(f"[StreamingManager] Removing stale connection for {key}")
                    del self.connections[key]

            # Create new connection
            print(f"[StreamingManager] Creating new connection for {key}")
            conn = StreamingConnection(
                room_id=room_id,
                provider=provider,
                language=language,
                config=config,
                on_partial=on_partial,
                on_final=on_final,
                on_error=on_error
            )

            await conn.connect()
            self.connections[key] = conn
            return conn

    def get_connection(self, room_id: str, provider: str) -> Optional[StreamingConnection]:
        """Get existing connection without creating a new one."""
        key = self._get_key(room_id, provider)
        return self.connections.get(key)

    async def close_connection(self, room_id: str, provider: str):
        """Close and remove a connection."""
        key = self._get_key(room_id, provider)

        async with self._lock:
            if key in self.connections:
                conn = self.connections[key]
                await conn.close()
                del self.connections[key]
                print(f"[StreamingManager] Removed connection for {key}")

    async def close_all_for_room(self, room_id: str):
        """Close all connections for a room."""
        async with self._lock:
            keys_to_remove = [k for k in self.connections.keys() if k.startswith(f"{room_id}:")]
            for key in keys_to_remove:
                conn = self.connections[key]
                await conn.close()
                del self.connections[key]
            print(f"[StreamingManager] Closed {len(keys_to_remove)} connections for room={room_id}")

    async def cleanup_stale_connections(self, max_age_seconds: int = 300):
        """Remove connections that haven't been active recently."""
        now = datetime.now()
        async with self._lock:
            keys_to_remove = []
            for key, conn in self.connections.items():
                age = (now - conn.last_activity).total_seconds()
                if age > max_age_seconds:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                conn = self.connections[key]
                await conn.close()
                del self.connections[key]

            if keys_to_remove:
                print(f"[StreamingManager] Cleaned up {len(keys_to_remove)} stale connections")


# Global singleton
_streaming_manager = StreamingManager()


def get_streaming_manager() -> StreamingManager:
    """Get the global streaming manager instance."""
    return _streaming_manager

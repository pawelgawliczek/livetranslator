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

# Import Google streaming client
try:
    import google_streaming
except ImportError:
    google_streaming = None
    print("[StreamingManager] Warning: google_streaming module not available")


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
        self.ws_client = None     # For Speechmatics WebSocket
        self.google_session = None  # For Google streaming session
        self.stream = None        # For other providers

        # Accumulated state for this session
        self.segment_id = None
        self.revision = 0
        self.accumulated_text = ""
        self.finalized_text = ""  # For Speechmatics: text confirmed by AddTranscript
        self.previous_segment_text = ""  # Save finalized text from previous segment to detect late finals
        self.ended_segment_id = None  # Track which segment ended (to block its late finals)
        self.segment_start_time = None  # Track when segment started - for time-based blocking
        self.last_audio_end_time = None  # Track audio end_time from Speechmatics - for audio timing-based blocking
        self.audio_has_ended = False  # Track if audio_end has been called - ONLY apply threshold AFTER this

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
        import time
        timestamp = time.time()
        print(f"[StreamingConnection] 🔄 [{timestamp:.3f}] Resetting for new segment {segment_id} (prev segment: {self.segment_id})")

        # Save current accumulated/finalized text before resetting - ONLY if previous_segment_text is not already set
        # (audio_end may have already saved it before this reset is called)
        # Use accumulated_text because it includes partials that may arrive as late finals
        if not self.previous_segment_text:
            if self.accumulated_text:
                self.previous_segment_text = self.accumulated_text.strip()
                print(f"[StreamingConnection] 💾 [{timestamp:.3f}] Saved previous segment text (accumulated): '{self.previous_segment_text[:80]}...'")
            elif self.finalized_text:
                self.previous_segment_text = self.finalized_text.strip()
                print(f"[StreamingConnection] 💾 [{timestamp:.3f}] Saved previous segment text (finalized): '{self.previous_segment_text[:80]}...'")
            else:
                print(f"[StreamingConnection] ⚠️  [{timestamp:.3f}] No text to save (both accumulated and finalized empty)")
        else:
            print(f"[StreamingConnection] ✓ [{timestamp:.3f}] Previous segment text already saved: '{self.previous_segment_text[:80]}...'")

        # Track which segment ended
        if self.segment_id is not None and segment_id != self.segment_id:
            self.ended_segment_id = self.segment_id
            print(f"[StreamingConnection] 📌 [{timestamp:.3f}] Will block late finals from ended segment {self.segment_id}")
        else:
            print(f"[StreamingConnection] ℹ️  [{timestamp:.3f}] Same segment or first segment, no blocking needed")

        print(f"[StreamingConnection] 🧹 [{timestamp:.3f}] Clearing state: accumulated_text='{self.accumulated_text[:50] if self.accumulated_text else ''}', finalized_text='{self.finalized_text[:50] if self.finalized_text else ''}'")

        # IMPORTANT: FREEZE last_audio_end_time when starting new segment
        # Any AddTranscript with end_time <= this frozen value belongs to previous segment
        if self.last_audio_end_time is not None:
            print(f"[StreamingConnection] 🔒 [{timestamp:.3f}] FREEZING last_audio_end_time at {self.last_audio_end_time:.2f}s for blocking")
            print(f"[StreamingConnection] 🔒 [{timestamp:.3f}] Any audio ending <= {self.last_audio_end_time:.2f}s will be blocked as late")

        self.segment_id = segment_id
        self.revision = 0
        self.accumulated_text = ""
        self.finalized_text = ""
        self.segment_start_time = timestamp  # Record when this segment started
        # DON'T reset audio_has_ended here - keep it True until we see real new speech (time_diff > 1.5s)
        print(f"[StreamingConnection] ⏱️  [{timestamp:.3f}] Segment start time recorded for blocking window")
        print(f"[StreamingConnection] 🔒 [{timestamp:.3f}] audio_has_ended={self.audio_has_ended} - will remain True until new speech detected")
        # DON'T clear previous_segment_text or last_audio_end_time here - they're needed for blocking late finals!

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

            elif self.provider == "google_v2" and self.google_session:
                # Google: close the streaming session
                if hasattr(self, '_google_client') and self._google_client:
                    await self._google_client.close_session(self.google_session.session_id)
                    print(f"[StreamingConnection] Closed Google session")

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
                            # Block partials that are duplicates from previous segment
                            # This happens when late finals were blocked but partials slip through
                            if self.previous_segment_text and partial_text in self.previous_segment_text:
                                print(f"[StreamingConnection] 🚫 BLOCKED duplicate partial: '{partial_text[:80]}' (was in previous segment)")
                                continue

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
                        import time
                        timestamp = time.time()
                        metadata = msg.get("metadata", {})
                        final_text = metadata.get("transcript", "").strip()

                        # Strip leading punctuation - it's never correct at the start of a segment
                        # Speechmatics sometimes adds ". " at the beginning due to VAD/revision issues
                        original_text = final_text
                        final_text = final_text.lstrip('.,!?;: ')
                        if original_text != final_text:
                            print(f"[StreamingConnection] ✂️  [{timestamp:.3f}] Stripped leading punctuation: '{original_text}' → '{final_text}'")

                        # Extract Speechmatics sequence numbers for tracking
                        start_time = metadata.get("start_time", None)
                        end_time = metadata.get("end_time", None)

                        print(f"[StreamingConnection] 📨 [{timestamp:.3f}] AddTranscript received: '{final_text[:80] if final_text else '(empty)'}' for segment_id={self.segment_id}")
                        print(f"[StreamingConnection] 📨 [{timestamp:.3f}]   - Speechmatics timing: start={start_time}, end={end_time}")
                        print(f"[StreamingConnection] 📨 [{timestamp:.3f}]   - Full metadata: {metadata}")

                        if final_text:
                            # Audio timing-based blocking: Use Speechmatics end_time to determine if this belongs to previous segment
                            # This is more accurate than arrival time or content matching
                            should_block = False

                            if end_time is not None and self.last_audio_end_time is not None:
                                # Check for time going backwards - indicates late final from previous segment
                                if end_time <= self.last_audio_end_time:
                                    should_block = True
                                    print(f"[StreamingConnection] 🚫 [{timestamp:.3f}] BLOCKED - audio time going BACKWARDS: '{final_text[:80]}'")
                                    print(f"[StreamingConnection] 🚫 [{timestamp:.3f}]   - This end_time: {end_time:.2f}s <= last seen: {self.last_audio_end_time:.2f}s")
                                    print(f"[StreamingConnection] 🚫 [{timestamp:.3f}]   - This is a late final from a previous segment!")
                                elif self.audio_has_ended:
                                    # After audio_end, check if this transcript overlaps with already-seen audio
                                    # Use start_time to determine if this is NEW audio content
                                    if start_time is not None and start_time > self.last_audio_end_time:
                                        # start_time is AFTER the last seen audio - this is NEW content
                                        # Accept it as either continuation of current segment or start of new segment
                                        print(f"[StreamingConnection] ✅ [{timestamp:.3f}] New audio content: start_time {start_time:.2f}s > last_audio_end_time {self.last_audio_end_time:.2f}s")
                                        self.last_audio_end_time = end_time
                                        self.audio_has_ended = False  # Reset flag - we're in active speech now
                                        print(f"[StreamingConnection] 📍 [{timestamp:.3f}] Updated last_audio_end_time to {end_time:.2f}s")
                                        print(f"[StreamingConnection] 🎤 [{timestamp:.3f}] audio_has_ended=False - active speech mode")
                                    else:
                                        # start_time overlaps with or is missing - apply threshold check
                                        LATE_FINAL_THRESHOLD = 3.0  # seconds
                                        time_diff = end_time - self.last_audio_end_time

                                        if time_diff <= LATE_FINAL_THRESHOLD:
                                            # Too close to previous segment - likely a late final
                                            should_block = True
                                            print(f"[StreamingConnection] 🚫 [{timestamp:.3f}] BLOCKED - within threshold after audio_end: '{final_text[:80]}'")
                                            print(f"[StreamingConnection] 🚫 [{timestamp:.3f}]   - start_time: {start_time}, end_time: {end_time:.2f}s, last_audio_end_time: {self.last_audio_end_time:.2f}s")
                                            print(f"[StreamingConnection] 🚫 [{timestamp:.3f}]   - time_diff: {time_diff:.2f}s <= threshold: {LATE_FINAL_THRESHOLD}s")
                                            print(f"[StreamingConnection] 🚫 [{timestamp:.3f}]   - This is likely a late final from previous segment!")
                                        else:
                                            # Sufficient gap - this is genuine new speech
                                            print(f"[StreamingConnection] ✅ [{timestamp:.3f}] New speech detected: time_diff {time_diff:.2f}s > {LATE_FINAL_THRESHOLD}s")
                                            self.last_audio_end_time = end_time
                                            self.audio_has_ended = False  # Reset flag - we're in active speech now
                                            print(f"[StreamingConnection] 📍 [{timestamp:.3f}] Updated last_audio_end_time to {end_time:.2f}s")
                                            print(f"[StreamingConnection] 🎤 [{timestamp:.3f}] audio_has_ended=False - active speech mode")
                                else:
                                    # Active speech mode - accept and update continuously
                                    print(f"[StreamingConnection] ✅ [{timestamp:.3f}] Active speech, time progressing: {self.last_audio_end_time:.2f}s → {end_time:.2f}s")
                                    self.last_audio_end_time = end_time
                            elif end_time is not None:
                                # First AddTranscript - initialize tracking
                                print(f"[StreamingConnection] 📍 [{timestamp:.3f}] First AddTranscript, initializing last_audio_end_time to {end_time:.2f}s")
                                self.last_audio_end_time = end_time

                            if should_block:
                                continue

                            # Detect punctuation-only finals (sentence boundaries from Speechmatics)
                            is_punctuation_only = final_text in ['.', '!', '?', ',', ';', ':']

                            if is_punctuation_only:
                                # Append punctuation to both finalized_text AND accumulated_text
                                # Then send it as a final event so frontend displays it
                                old_finalized = self.finalized_text
                                old_accumulated = self.accumulated_text

                                if self.finalized_text:
                                    self.finalized_text += final_text  # No space before punctuation
                                else:
                                    self.finalized_text = final_text

                                # Also update accumulated_text (so partials include punctuation)
                                if self.accumulated_text:
                                    self.accumulated_text += final_text  # No space before punctuation
                                else:
                                    self.accumulated_text = final_text

                                print(f"[StreamingConnection] 📍 [{timestamp:.3f}] Punctuation detected: '{final_text}' - appending and sending as final")
                                print(f"[StreamingConnection] 📍 [{timestamp:.3f}]   - updated finalized_text: '{self.finalized_text[:80]}'")
                                print(f"[StreamingConnection] 📍 [{timestamp:.3f}]   - updated accumulated_text: '{self.accumulated_text[:80]}'")

                                # Send the punctuation as a final event so frontend appends it
                                await self.on_final({
                                    "text": final_text,
                                    "language": self.language,
                                    "room_id": self.room_id,
                                    "is_final": True
                                })
                                continue

                            # Add to finalized text (normal words)
                            old_finalized = self.finalized_text
                            if self.finalized_text:
                                self.finalized_text += " " + final_text
                            else:
                                self.finalized_text = final_text

                            print(f"[StreamingConnection] ✓ [{timestamp:.3f}] Finalized (segment {self.segment_id}): '{final_text[:80]}'")
                            print(f"[StreamingConnection] ✓ [{timestamp:.3f}]   - old finalized_text: '{old_finalized[:50] if old_finalized else '(empty)'}'")
                            print(f"[StreamingConnection] ✓ [{timestamp:.3f}]   - new finalized_text: '{self.finalized_text[:80]}'")

                            await self.on_final({
                                "text": final_text,
                                "language": self.language,
                                "room_id": self.room_id,
                                "is_final": True
                            })

                    elif msg_type == "EndOfTranscript":
                        import time
                        finalize_timestamp = time.time()
                        print(f"[StreamingConnection] 🏁 [{finalize_timestamp:.3f}] Speechmatics EndOfTranscript received (after {self.config.get('end_of_utterance_silence_trigger', 0.6)}s silence) for room={self.room_id}")
                        print(f"[StreamingConnection] 📤 [{finalize_timestamp:.3f}] Sending stt_finalize to frontend for segment_id={self.segment_id}")
                        # This event fires after end_of_utterance_silence_trigger timeout
                        # Send finalize event to frontend to switch partial → final display
                        await self.on_final({
                            "type": "stt_finalize",
                            "segment_id": self.segment_id,
                            "room_id": self.room_id,
                            "language": self.language,
                            "backend_timestamp": finalize_timestamp  # For measuring sync delay
                        })

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
        if not google_streaming:
            raise NotImplementedError("google_streaming module not available")

        # Get or create the global Google client
        if not hasattr(self, '_google_client'):
            self._google_client = google_streaming.get_streaming_client()

        # Create a new Google streaming session
        session_id = self.room_id

        # Create session with callbacks
        self.google_session = await self._google_client.create_session(
            session_id=session_id,
            language=self.language,
            config=self.config,
            on_partial=self._handle_google_partial,
            on_final=self._handle_google_final,
            on_error=self._handle_google_error
        )

        print(f"[StreamingConnection] ✓ Google session created for room={self.room_id}")

    async def _handle_google_partial(self, result: Dict[str, Any]):
        """Handle partial results from Google."""
        # Update accumulated_text from partial (for audio_end handling)
        text = result.get("text", "").strip()
        if text:
            self.accumulated_text = text
            self.revision += 1

        # Forward to the common partial handler
        await self.on_partial(result)

    async def _handle_google_final(self, result: Dict[str, Any]):
        """Handle final results from Google."""
        # Update finalized_text from final
        text = result.get("text", "").strip()
        if text:
            self.finalized_text = text
            self.accumulated_text = text  # Also update accumulated for consistency

        # Forward to the common final handler
        await self.on_final(result)

    async def _handle_google_error(self, error: str):
        """Handle errors from Google."""
        await self.on_error({"error": error, "room_id": self.room_id, "provider": "google_v2"})

    async def _send_google(self, audio_bytes: bytes):
        """Send audio to Google streaming session."""
        if not self.google_session:
            print(f"[StreamingConnection] ⚠️  No Google session for room={self.room_id}")
            return

        # Convert bytes to base64 (Google client expects base64)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        # Send to Google client
        await self._google_client.send_audio(self.google_session.session_id, audio_b64)

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

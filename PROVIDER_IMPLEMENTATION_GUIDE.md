# STT Provider Implementation Guide

This guide explains how to add new streaming STT providers to the system.

## Architecture Overview

The system uses **persistent WebSocket connections** for real-time STT streaming:

```
Audio Chunks → Router → Streaming Manager → Provider WebSocket → Partials Back
                             ↓
                   Connection Pool (one per room)
```

## Adding a New Provider

### 1. Implement Provider in streaming_manager.py

Add two methods to the `StreamingConnection` class:

```python
async def _connect_YOUR_PROVIDER(self):
    """Connect to provider's WebSocket API."""
    import websockets

    API_KEY = os.getenv("YOUR_PROVIDER_API_KEY")
    url = "wss://your-provider.com/v1/stream"

    # Connect
    self.ws_client = await websockets.connect(
        url,
        additional_headers={"Authorization": f"Bearer {API_KEY}"}
    )

    # Send initialization message
    init_msg = {
        "language": self.language,
        "config": self.config
    }
    await self.ws_client.send(json.dumps(init_msg))

    # Start listener
    asyncio.create_task(self._your_provider_listener())

async def _your_provider_listener(self):
    """Listen for responses from provider."""
    async for message in self.ws_client:
        msg = json.loads(message)

        if msg["type"] == "partial":
            await self.on_partial({
                "text": msg["transcript"],
                "language": self.language,
                "room_id": self.room_id,
                "is_final": False
            })
        elif msg["type"] == "final":
            await self.on_final({
                "text": msg["transcript"],
                "language": self.language,
                "room_id": self.room_id,
                "is_final": True
            })

async def _send_YOUR_PROVIDER(self, audio_bytes: bytes):
    """Send audio chunk to provider."""
    await self.ws_client.send(audio_bytes)
```

### 2. Update router.py

Add your provider to `STREAMING_PROVIDERS`:

```python
STREAMING_PROVIDERS = {"speechmatics", "google_v2", "azure", "soniox", "your_provider"}
```

### 3. Add to Database

Insert routing configuration:

```sql
INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config, enabled)
VALUES
  ('en-US', 'partial', 'standard', 'your_provider', 'openai', '{"diarization": true}', true),
  ('en-US', 'final', 'standard', 'your_provider', 'openai', '{"diarization": true}', true);
```

### 4. Add API Keys

Add to `.env`:

```
YOUR_PROVIDER_API_KEY=your_api_key_here
```

Add to `docker-compose.yml`:

```yaml
stt_router:
  environment:
    YOUR_PROVIDER_API_KEY: ${YOUR_PROVIDER_API_KEY}
```

## Provider-Specific Notes

### Speechmatics (Implemented ✅)

- **WebSocket Protocol**: Native WebSocket (not SDK)
- **Partials**: Sends word-by-word updates (accumulate on our side)
- **Quality**: `operating_point: "enhanced"` for best accuracy
- **Latency Control**: `max_delay` (0.7s - 4.0s, recommended: 1.5s for ultra-fast, 2.0s for balanced)

### Google Cloud Speech v2 (TODO)

- Uses gRPC streaming
- Sends accumulated transcripts in partials
- Excellent accuracy for English

### Azure Speech SDK (TODO)

- Native SDK with callbacks
- Real-time continuous recognition
- Good multilingual support

### Soniox (TODO)

- WebSocket protocol
- Low latency, good for conversations
- Focus on English

## Testing Your Provider

1. **Set provider in database**:
   ```sql
   UPDATE stt_routing_config
   SET provider_primary = 'your_provider'
   WHERE language = 'en-US' AND mode = 'partial';
   ```

2. **Clear cache**:
   ```bash
   redis-cli PUBLISH routing_cache_clear '{"language":"en-US","service_type":"stt"}'
   ```

3. **Watch logs**:
   ```bash
   docker compose logs -f stt_router
   ```

4. **Test via web interface** - speak in the target language

Look for:
- `🔌 Using streaming for your_provider`
- `[StreamingConnection] Connected to your_provider`
- `✓ Stream partial: [transcribed text]`

## Troubleshooting

**No partials appearing:**
- Check WebSocket connection logs
- Verify API key is set
- Check provider is in `STREAMING_PROVIDERS`

**Partials overwriting each other:**
- Provider sends word-by-word → accumulate on our side
- Provider sends full transcript → use directly

**Connection errors:**
- Check `additional_headers` vs `extra_headers` for websockets library
- Verify WebSocket URL format
- Check authentication method

## File Locations

- **Streaming Manager**: `api/routers/stt/streaming_manager.py`
- **Router**: `api/routers/stt/router.py`
- **Database Config**: `stt_routing_config` table
- **Docker Compose**: `docker-compose.yml`

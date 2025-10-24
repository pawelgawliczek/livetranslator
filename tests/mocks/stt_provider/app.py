"""
Mock STT Provider for Testing
Simulates Speechmatics, Google, Azure, etc.
"""
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
import asyncio
import json

app = FastAPI(title="Mock STT Provider")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock_stt_provider"}


@app.post("/v2/transcribe")
async def transcribe_audio(audio_data: bytes):
    """Mock synchronous transcription (like OpenAI Whisper)."""
    # Simulate processing delay
    await asyncio.sleep(0.1)

    return {
        "text": "This is a mock transcription",
        "language": "en",
        "confidence": 0.95,
        "duration": 2.5
    }


@app.websocket("/ws")
async def websocket_transcription(websocket: WebSocket):
    """Mock WebSocket transcription (like Speechmatics)."""
    await websocket.accept()

    try:
        # Send mock transcription results
        async for message in websocket.iter_text():
            data = json.loads(message)

            if data.get("type") == "audio":
                # Send partial result
                await websocket.send_json({
                    "type": "partial",
                    "text": "Mock partial transcription",
                    "confidence": 0.85
                })

                # Wait a bit, then send final
                await asyncio.sleep(0.2)
                await websocket.send_json({
                    "type": "final",
                    "text": "Mock final transcription.",
                    "confidence": 0.95
                })

            elif data.get("type") == "end_of_stream":
                await websocket.send_json({
                    "type": "end_of_transcript"
                })
                break

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

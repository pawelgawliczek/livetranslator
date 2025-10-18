import orjson
import redis.asyncio as redis

class STTClient:
    def __init__(self, redis_url):
        self.redis: redis.Redis = redis.from_url(str(redis_url), decode_responses=True)

    async def push_chunk(self, room_id: str, device: str, seq: int, pcm16_base64: str):
        payload = {
            "type": "audio_chunk",
            "room_id": room_id,
            "device": device,
            "seq": seq,
            "pcm16_base64": pcm16_base64,
        }
        await self.redis.publish("stt_input", orjson.dumps(payload).decode())

    async def push_raw(self, payload: dict):
        await self.redis.publish("stt_input", orjson.dumps(payload).decode())


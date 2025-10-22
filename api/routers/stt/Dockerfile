FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir redis orjson httpx asyncpg \
    deepgram-sdk>=5.0.0 \
    speechmatics-python \
    google-cloud-speech \
    azure-cognitiveservices-speech \
    soniox \
    websockets

COPY . .

CMD ["python", "router.py"]

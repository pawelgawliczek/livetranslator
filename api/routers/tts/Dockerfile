FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir redis orjson asyncpg \
    google-cloud-texttospeech \
    azure-cognitiveservices-speech

COPY . .

CMD ["python", "router.py"]

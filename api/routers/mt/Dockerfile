FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir redis orjson httpx

COPY . .

CMD ["python", "router.py"]

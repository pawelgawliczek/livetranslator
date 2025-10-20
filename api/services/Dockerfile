FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir redis orjson asyncpg

COPY cost_tracker_service.py .

CMD ["python", "cost_tracker_service.py"]

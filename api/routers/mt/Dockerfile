FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir redis orjson

COPY router.py .

CMD ["python", "router.py"]

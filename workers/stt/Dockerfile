FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 988 docker && adduser --system --uid 1001 --ingroup docker app

ENV HF_HOME=/tmp/hf_home TRANSFORMERS_CACHE=/tmp/hf_cache
RUN mkdir -p /tmp/hf_home /tmp/hf_cache && chmod -R 777 /tmp/hf_home /tmp/hf_cache

WORKDIR /srv
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R app:docker /srv
USER app

EXPOSE 8080
CMD ["python","worker.py"]

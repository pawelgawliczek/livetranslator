FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_ONLY_BINARY=:all:

RUN addgroup --system --gid 988 docker && adduser --system --uid 1001 --ingroup docker app
WORKDIR /srv
COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt
COPY . .
RUN chown -R app:docker /srv
USER app

CMD ["python","worker.py"]

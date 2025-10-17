FROM python:3.11-slim

RUN addgroup --system --gid 988 docker && adduser --system --uid 1001 --ingroup docker app
# build deps for webrtcvad + runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ make \
    ffmpeg libsndfile1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .
RUN chown -R app:docker /srv
USER app

CMD ["python","worker.py"]

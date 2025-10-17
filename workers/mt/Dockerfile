FROM python:3.11-bookworm

# minimal system deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

# avoid exec-stack issue: pin to CTranslate2 4.2.x
RUN pip install --no-cache-dir \
    "fastapi==0.115.0" "uvicorn[standard]==0.30.6" \
    "ctranslate2==4.2.1" "transformers==4.43.3" \
    "sentencepiece==0.2.0" "sacremoses==0.0.53" "huggingface_hub==0.24.6" "langdetect==1.0.9"

WORKDIR /app
# after WORKDIR /app
ENV HF_HOME=/tmp/hf_home TRANSFORMERS_CACHE=/tmp/hf_cache
RUN mkdir -p /tmp/hf_home /tmp/hf_cache && chmod -R 777 /tmp/hf_home /tmp/hf_cache
COPY app.py /app/app.py

ENV MODELS_DIR=/models PORT=8081 PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/tmp/hf_cache
USER 65532:65532
EXPOSE 8081
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8081"]

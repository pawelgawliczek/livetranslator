FROM python:3.11-slim
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN addgroup --system --gid 988 docker && adduser --system --uid 1001 --ingroup docker app \
 && apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app/api
USER app
EXPOSE 8000
CMD ["uvicorn","api.main:app","--host","0.0.0.0","--port","8000","--proxy-headers"]

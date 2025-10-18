# /usr/local/bin/livetranslator-restart.sh
#!/usr/bin/env bash
set -euo pipefail

cd /opt/stack/livetranslator

echo "[1/4] Ensure Redis is up"
docker compose up -d redis

echo "[2/4] Clear Redis DB (queues/state)"
docker compose exec redis sh -lc 'redis-cli -n 0 FLUSHDB ASYNC && echo "FLUSHED"'

echo "[3/4] Restart all stack services"
docker compose up -d --force-recreate --build

echo "[4/4] Reload Caddy"
if command -v caddy-reload >/dev/null 2>&1; then
  caddy-reload
else
  docker exec caddy caddy reload --config /etc/caddy/Caddyfile || true
fi

echo "Health:"
docker compose exec api curl -sS http://localhost:8000/healthz || true
docker compose exec mt_worker curl -sS http://localhost:8081/health || true
docker compose ps

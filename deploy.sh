#!/bin/bash
set -e

echo "=== AI Avatar Content OS — Server Deploy ==="
cd "$(dirname "$0")"

# ── 1. Verify .env exists (NEVER generate secrets in this script) ──
if [ ! -f .env ]; then
  echo "[ERROR] .env file not found."
  echo "  Copy .env.example to .env and fill in production secrets before deploying."
  echo "  NEVER hardcode secrets in deploy scripts."
  exit 1
fi

source .env

# Validate critical env vars are set and not defaults
if [ -z "$API_SECRET_KEY" ] || echo "$API_SECRET_KEY" | grep -qi "changeme"; then
  echo "[ERROR] API_SECRET_KEY is missing or contains 'changeme'. Set a strong random key in .env."
  exit 1
fi
if [ -z "$POSTGRES_PASSWORD" ] || echo "$POSTGRES_PASSWORD" | grep -qi "changeme"; then
  echo "[ERROR] POSTGRES_PASSWORD is missing or contains 'changeme'. Set a strong password in .env."
  exit 1
fi

echo "[1/6] .env validated."

# ── 2. Tag current images for rollback ──
echo "[2/6] Tagging current images for rollback ..."
docker compose images --quiet 2>/dev/null | while read img; do
  docker tag "$img" "${img}:rollback" 2>/dev/null || true
done

# ── 3. Build images ──
echo "[3/6] Building images ..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# ── 4. Start postgres+redis, then sync schema directly ──
echo "[4/6] Starting database and syncing schema ..."
docker compose up -d postgres redis

echo "    Waiting for postgres ..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-avataros}" -d "${POSTGRES_DB:-avatar_revenue_os}" > /dev/null 2>&1; then
    echo "    Postgres ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[ERROR] Postgres did not become ready in 60s. Aborting."
    exit 1
  fi
  sleep 2
done

echo "    Running schema sync ..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps api python scripts/ensure_schema.py

# ── 5. Rolling restart (start new before stopping old) ──
echo "[5/6] Starting all services ..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api web worker scheduler caddy

# ── 6. Health verification ──
echo "[6/6] Verifying health ..."
MAX_RETRIES=15
for i in $(seq 1 $MAX_RETRIES); do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/healthz 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" = "200" ]; then
    echo "    API healthy (HTTP 200)."
    break
  fi
  if [ "$i" -eq "$MAX_RETRIES" ]; then
    echo "[WARNING] API health check failed after ${MAX_RETRIES} attempts (HTTP $HTTP_CODE)."
    echo "  Check logs: docker compose logs api"
    echo "  To rollback: docker compose down && docker compose up -d (with rollback images)"
  fi
  sleep 3
done

docker compose ps

echo ""
echo "=== Deploy complete ==="
echo "Frontend: https://app.nvironments.com"
echo "API:      https://api.nvironments.com"
echo ""
echo "Check logs:  docker compose logs -f"
echo "Check API:   curl http://localhost:8001/healthz"

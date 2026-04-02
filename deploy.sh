#!/bin/bash
set -e

echo "=== AI Avatar Content OS — Server Deploy ==="
cd "$(dirname "$0")"

# ── 1. Create .env if missing ──
if [ ! -f .env ]; then
  echo "[1/5] Creating production .env ..."
  cat > .env << 'DOTENV'
COMPOSE_PROJECT_NAME=avatar-revenue-os

POSTGRES_USER=avataros
POSTGRES_PASSWORD=avataros_dev_2026
POSTGRES_DB=avatar_revenue_os
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os
DATABASE_URL_SYNC=postgresql://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

API_HOST=0.0.0.0
API_PORT=8000
API_SECRET_KEY=avataros-prod-8f3a9c2d7e1b4056a3f9d8c2e71b0456
API_CORS_ORIGINS=["https://app.nvironments.com","http://web:3000"]
API_ENV=production

NEXT_PUBLIC_API_URL=https://api.nvironments.com

S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_BUCKET_NAME=avatar-revenue-os
S3_REGION=us-east-1

OPENAI_API_KEY=
ELEVENLABS_API_KEY=
TAVUS_API_KEY=
HEYGEN_API_KEY=

SENTRY_DSN=
LOG_LEVEL=info
DOTENV
  echo "    .env created."
else
  echo "[1/5] .env already exists, keeping it."
fi

# ── 2. Stop everything ──
echo "[2/5] Stopping existing containers ..."
docker compose down --remove-orphans 2>/dev/null || true

# ── 3. Build images ──
echo "[3/5] Building images ..."
docker compose build

# ── 4. Start postgres+redis, then sync schema directly ──
echo "[4/5] Starting database and syncing schema ..."
docker compose up -d postgres redis

echo "    Waiting for postgres ..."
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U avataros -d avatar_revenue_os > /dev/null 2>&1; then
    echo "    Postgres ready."
    break
  fi
  sleep 2
done

echo "    Running schema sync (bypassing Alembic) ..."
docker compose run --rm -e DATABASE_URL_SYNC="${DATABASE_URL_SYNC:-postgresql://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os}" --no-deps api python scripts/ensure_schema.py

# ── 5. Start all services (skip migrate since we already synced) ──
echo "[5/5] Starting all services ..."
docker compose up -d --no-deps api web worker scheduler

echo ""
echo "    Waiting for services ..."
sleep 15

docker compose ps

echo ""
echo "=== Deploy complete ==="
echo "Frontend: https://app.nvironments.com"
echo "API:      https://api.nvironments.com"
echo ""
echo "Check logs:  docker compose logs -f"
echo "Check API:   curl http://localhost:8001/healthz"

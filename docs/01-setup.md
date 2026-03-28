# Setup Guide — AI Avatar Revenue OS

## Prerequisites

- Docker Desktop (with Docker Compose v2)
- Node.js 20+ (for local frontend dev without Docker)
- Python 3.11+ (for local backend dev without Docker)

## Quick Start (Docker)

```bash
cd "AI AVATAR CONTENT OS OPS NEW"

# Build all images (first time takes ~5-10 minutes)
docker compose build

# Start all services
docker compose up -d

# Verify all containers are running
docker ps --filter "name=aro"
```

## Ports

| Service    | Port  | URL                        |
|-----------|-------|----------------------------|
| Web UI    | 3001  | http://localhost:3001      |
| API       | 8001  | http://localhost:8001      |
| API Docs  | 8001  | http://localhost:8001/docs |
| PostgreSQL| 5433  | localhost:5433             |
| Redis     | 6380  | localhost:6380             |

These ports are intentionally offset from 3000/8000/5432/6379 to avoid conflicts with other projects.

## Database Migrations

Migrations run automatically on `docker compose up`. To run manually:

```bash
docker exec aro-api alembic -c packages/db/alembic.ini upgrade head
```

To generate a new migration after model changes:

```bash
docker exec aro-api alembic -c packages/db/alembic.ini revision --autogenerate -m "description"
```

## Seed Data

Populate the database with realistic development data:

```bash
docker exec aro-api python scripts/seed.py
```

This creates:
- 1 organization (RevenueLab)
- 3 users: admin/operator/viewer (passwords: admin123, operator123, viewer123)
- 2 brands with avatars and provider profiles
- 4 offers across both brands
- 4 creator accounts across YouTube, TikTok, Instagram
- Provider usage cost records
- Audit log entries

Login: `admin@revenuelab.ai` / `admin123`

## Environment Variables

Copy `.env.example` to `.env` and configure:

- `POSTGRES_*` — Database credentials
- `REDIS_*` — Cache/queue connection
- `API_SECRET_KEY` — JWT signing key (change in production)
- `OPENAI_API_KEY` — For script generation (Phase 2+)
- `ELEVENLABS_API_KEY` — For voice synthesis
- `TAVUS_API_KEY` — For avatar video generation
- `HEYGEN_API_KEY` — For live avatar streaming

## Running Tests

```bash
# Create test database first
docker exec aro-postgres createdb -U avataros avatar_revenue_os_test

# Run tests
docker exec aro-api pytest tests/ -v
```

## Container Management

```bash
docker compose logs -f aro-api    # Follow API logs
docker compose logs -f aro-worker # Follow worker logs
docker compose restart aro-api    # Restart API
docker compose down               # Stop all
docker compose down -v            # Stop and remove volumes
```

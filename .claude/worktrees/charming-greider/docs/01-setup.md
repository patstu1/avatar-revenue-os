# Setup Guide — AI Avatar Revenue OS

## Prerequisites

- Docker Desktop (with Docker Compose v2)
- Node.js 20+ (for local frontend dev without Docker)
- Python 3.11+ (for local backend dev without Docker)

## Quick Start (Docker)

```bash
cd "AI AVATAR CONTENT OS OPS NEW"

# Copy environment config
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD to a real password

# Build all images (first time takes ~5-10 minutes)
docker compose build

# Start all services (migrations run automatically)
docker compose up -d

# Verify all containers are healthy
docker compose ps

# Seed the database with dev data (all dashboards populated)
docker exec aro-api python scripts/seed.py
```

## Ports

| Service    | Port  | URL                        |
|-----------|-------|----------------------------|
| Web UI    | 3001  | http://localhost:3001      |
| API       | 8001  | http://localhost:8001      |
| API Docs  | 8001  | http://localhost:8001/docs |
| PostgreSQL| 5433  | localhost:5433             |
| Redis     | 6380  | localhost:6380             |

These ports are intentionally offset from 3000/8000/5432/6379 to avoid conflicts.

## Health Checks

```bash
# API liveness
curl http://localhost:8001/healthz

# API readiness (checks Postgres + Redis)
curl http://localhost:8001/readyz

# Docker-level health (all containers should show "healthy")
docker compose ps
```

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

Populate the database with realistic data across **all** dashboards:

```bash
docker exec aro-api python scripts/seed.py
```

This creates:
- 1 organization (RevenueLab) with 3 users (admin/operator/viewer)
- 2 brands with avatars, provider profiles, 4 offers, 4 creator accounts
- Scale Alerts: alerts, launch candidates, blockers, readiness reports, notifications
- Revenue Ceiling A: offer ladders, audience assets, funnel metrics, leak fixes
- Revenue Ceiling B: high-ticket, product opportunities, density reports, upsell recs
- Revenue Ceiling C: recurring revenue, sponsor inventory, trust, mix, paid promotion
- Expansion Pack 2 A: leads, closer actions, qualification reports, owned offer recs
- Expansion Pack 2 B: pricing, bundles, retention, reactivation campaigns
- Expansion Pack 2 C: referral programs, competitive gaps, sponsor targets, profit guardrails

**Login**: `admin@revenuelab.ai` / `admin123`

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Purpose |
|---|---|
| `POSTGRES_*` | Database credentials |
| `REDIS_*` | Cache/queue connection |
| `API_SECRET_KEY` | JWT signing key (change in production!) |
| `OPENAI_API_KEY` | Script generation (optional) |
| `ELEVENLABS_API_KEY` | Voice synthesis (optional) |
| `TAVUS_API_KEY` | Avatar video generation (optional) |
| `HEYGEN_API_KEY` | Live avatar streaming (optional) |
| `SMTP_HOST/PORT/USER/PASS` | Email notifications (optional) |
| `SLACK_WEBHOOK_URL` | Slack notifications (optional) |
| `SMS_API_KEY` | SMS notifications (optional) |
| `SENTRY_DSN` | Error monitoring (optional) |

## Running Tests

### Local (against Docker Postgres)

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Create test database
docker exec aro-postgres createdb -U avataros avatar_revenue_os_test 2>/dev/null || true

# Apply migrations to test DB
export DATABASE_URL_SYNC="postgresql://avataros:changeme_in_production@127.0.0.1:5433/avatar_revenue_os_test"
alembic -c packages/db/alembic.ini upgrade head

# Unit tests (no Postgres required)
python -m pytest tests/unit/ -v

# Integration tests (requires test DB)
export TEST_DATABASE_URL="postgresql+asyncpg://avataros:changeme_in_production@127.0.0.1:5433/avatar_revenue_os_test"
python -m pytest tests/integration/ -v
```

### Inside Docker

```bash
# All tests inside API container
docker exec aro-api pytest tests/ -v

# Just unit tests
docker exec aro-api pytest tests/unit/ -v
```

## Queue Architecture

The system uses 15 isolated Celery queues:

| Queue | Tasks |
|---|---|
| `default` | General tasks |
| `generation` | Content generation |
| `publishing` | Content publishing |
| `analytics` | Performance tracking, trend scanning |
| `qa` | Quality assurance |
| `learning` | Memory consolidation |
| `portfolio` | Portfolio rebalancing |
| `scale_alerts` | Alert/blocker/readiness recomputes |
| `notifications` | Email/Slack/SMS delivery |
| `growth_pack` | Growth commander + pack recomputes |
| `revenue_ceiling_a` | Offer ladders, audiences, sequences, funnels |
| `revenue_ceiling_b` | High-ticket, product, density, upsell |
| `revenue_ceiling_c` | Recurring, sponsors, trust, mix, promotions |
| `expansion_pack2` | Lead qual, offers, pricing, bundles, retention, referral, guardrails |
| `mxp` | Maximum-strength pack: experiments, contribution, capacity, lifecycle, recovery, deal desk, audience, reputation, timing, kill ledger |

## Container Management

```bash
docker compose logs -f aro-api        # Follow API logs
docker compose logs -f aro-worker     # Follow worker logs
docker compose logs -f aro-scheduler  # Follow Celery beat scheduler logs
docker compose restart aro-api        # Restart API
docker compose restart aro-scheduler  # Restart beat scheduler (picks up schedule changes)
docker compose down                   # Stop all
docker compose down -v                # Stop and remove volumes (reset DB)
```

## Development Tools

```bash
# Install pre-commit hooks (one-time setup)
pip install pre-commit
pre-commit install

# Available make targets (run `make help` for full list)
make up            # Start all services
make test-unit     # Run unit tests
make test-integration  # Run integration tests (creates test DB)
make lint          # Ruff linter
make format        # Auto-format
make typecheck     # Mypy type checking
make seed          # Seed dev data
make health        # Check API health
```

## Production Deployment

Use the production compose override for resource limits, multi-worker uvicorn, and `next start`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Observability

- **Request IDs**: Every API request gets an `X-Request-ID` header (auto-generated or pass your own)
- **Structured logging**: JSON logs in production, console in development
- **Health checks**: `/healthz` (liveness), `/readyz` (readiness with DB+Redis checks)
- **Sentry**: Set `SENTRY_DSN` for error tracking (FastAPI + SQLAlchemy + Celery integrations)
- **Rate limiting**: Auth endpoints (10/min), recompute endpoints (5/min) per client IP
- **CI**: GitHub Actions runs lint, type check, unit tests, integration tests, and frontend build on every push/PR

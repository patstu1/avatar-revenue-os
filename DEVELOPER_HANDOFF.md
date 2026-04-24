# AI Avatar Revenue OS — Developer Handoff

**Repo:** `github.com/patstu1/avatar-revenue-os` (branch `main`, many `claude/*` feature branches)
**Production:** `https://app.nvironments.com` (being migrated to `proofhook.com`)
**Prod host:** single Hetzner VPS at `root@5.78.187.31`, `/opt/avatar-revenue-os`
**Analysis date:** 2026-04-22

---

## 1. What this is in one paragraph

A self-hosted, multi-tenant, autonomous content-to-revenue platform. It ingests a brief, generates AI content (text + image + video + avatar + voice) through a tiered provider stack with fallback, runs it through a QA → approval → publish lifecycle, ingests analytics, writes every revenue event to a canonical `RevenueLedgerEntry` table, then runs 17 revenue engines + an autonomous action dispatcher on top of that ledger to decide what to do next. Everything is observable via ~180 Next.js dashboard pages and driven by a Celery Beat scheduler running 187 recurring tasks across 25 queues. All of it runs inside one Docker Compose stack behind Caddy.

## 2. Tech stack

**Backend** (Python 3.11, `pyproject.toml`):
- FastAPI 0.115.6 + uvicorn 0.34.0
- SQLAlchemy 2.0.36 async + asyncpg 0.30.0 + Alembic 1.14.1
- Pydantic 2.10.4 + pydantic-settings
- Celery 5.4.0 + redis-py 5.2.1
- JWT via python-jose HS256, bcrypt via passlib
- structlog (JSON in prod, console in dev) + sentry-sdk
- openai 1.58.1 + anthropic ≥0.39 + google-api-python-client
- stripe ≥8.0 + weasyprint + boto3 + aiosmtplib

**Frontend** (`apps/web`):
- Next.js 14+ App Router, TypeScript, Tailwind
- React Query + Zustand
- 322 `.ts`/`.tsx` files, ~180 dashboard pages

**Infra**:
- Docker Compose (dev + prod override)
- Caddy 2-alpine auto-HTTPS via Let's Encrypt
- Postgres 16-alpine (`max_connections=500`)
- Redis 7-alpine (256MB LRU) as broker + result backend
- Terraform dir exists, placeholder only

## 3. Repo layout

```
avatar-revenue-os/
├── apps/
│   ├── api/              FastAPI backend
│   │   ├── main.py       ~320 lines; mounts 113 routers
│   │   ├── routers/      113 routers, one per domain surface
│   │   ├── services/     132 service files (business logic)
│   │   ├── schemas/      Pydantic request/response
│   │   └── middleware/   RequestID, SecurityHeaders, RedirectHostFix
│   └── web/              Next.js frontend
│       └── src/app/
│           ├── dashboard/   ~180 operator pages
│           ├── offers/      Static offer pages (3 brands × 6–8)
│           ├── lp/[pageId]/ Dynamic landing pages
│           ├── login/
│           └── page.tsx
├── workers/              68 Celery worker packages
│   ├── celery_app.py     993 lines; 25 queues, 187 beat tasks
│   ├── base_task.py      TrackedTask base (emits SystemJob + SystemEvent)
│   └── <worker>/tasks.py One dir per worker
├── packages/
│   ├── db/
│   │   ├── models/       92 SQLAlchemy model files (one per domain)
│   │   ├── alembic/      Migrations + versions_backup/
│   │   └── session.py    async_session_factory
│   ├── scoring/          107 scoring engine files (+ growth_pack/)
│   ├── clients/          External API clients (Buffer, SMTP, Twilio, etc.)
│   ├── provider_clients/ AI SDK wrappers (Anthropic, OpenAI, HeyGen, …)
│   ├── executors/        Action execution
│   ├── guardrails/       Pre-action policy checks
│   ├── notifications/    Email/SMS
│   ├── media/            S3-or-local storage helpers
│   └── utils/, forecasting/, policy-rules/, prompt-templates/
├── infrastructure/
│   ├── caddy/Caddyfile   Reverse proxy config
│   ├── docker/           Dockerfile.api + Dockerfile.web
│   └── terraform/        Placeholder
├── tests/                170 test files (unit + integration + e2e)
├── scripts/              ~20 ops scripts (proofs, seeds, verify)
├── docs/                 107 numbered markdown docs (01–85)
├── Makefile              up/down/migrate/seed/test/lint/typecheck
├── deploy.sh             6-step prod deploy with rollback tagging
├── docker-compose.yml    Dev stack
├── docker-compose.prod.yml
└── .env / .env.example   150+ env vars
```

## 4. Getting a dev environment running

### 4.1 Prereqs
- Docker Desktop with Compose v2
- Make
- Python 3.11 (for running tests/scripts locally if desired)
- Node 18+ (for frontend-only local dev)

### 4.2 First boot
```bash
git clone git@github.com:patstu1/avatar-revenue-os.git
cd avatar-revenue-os
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY, OPENAI_API_KEY, STRIPE_API_KEY (test mode)
make up
```

`make up` runs `docker compose up -d`. The `aro-migrate` container runs `scripts/ensure_schema.py` and exits 0 before anything else starts (enforced via `depends_on: condition: service_completed_successfully`).

### 4.3 Host-exposed dev ports

| Service | Container | Host | Container |
|---|---|---|---|
| Postgres | aro-postgres | 5433 | 5432 |
| Redis | aro-redis | 6380 | 6379 |
| API | aro-api | 8001 | 8000 |
| Web | aro-web | 3001 | 3000 |

Frontend: `http://localhost:3001`. API docs (dev only): `http://localhost:8001/docs`.

### 4.4 Common Make targets
```bash
make up          # Start the stack
make down        # Stop it
make migrate     # Run Alembic upgrade head
make seed        # Seed dev data
make test        # Run pytest inside aro-api
make lint        # ruff
make typecheck   # mypy
make health      # Hit /healthz
make reset       # Nuke volumes and rebuild
```

### 4.5 Running a single worker locally
```bash
docker compose up -d postgres redis api
docker exec -it aro-worker-default celery -A workers.celery_app worker --loglevel=info -Q default
```

### 4.6 Running Beat standalone
```bash
docker exec -it aro-scheduler celery -A workers.celery_app beat --loglevel=info
```

## 5. Runtime topology

```
                       Let's Encrypt (ACME via Caddy)
                                ▲
                                │ :80 / :443
                    ┌───────────┴───────────┐
                    │    Caddy (aro-caddy)   │
                    │  Path routing:          │
                    │   /api/*     → api:8000 │
                    │   /health*   → api:8000 │
                    │   /docs      → api:8000 │
                    │   /ws/*      → api:8000 │
                    │   /media/*   → api:8000 │
                    │   else       → web:3000 │
                    └──┬───────────────────┬──┘
                       │                   │
                   aro-api             aro-web (Next.js)
                   FastAPI :8000       :3000
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    aro-postgres   aro-redis     (shared volumes)
    (asyncpg)    (broker+backend)
                       ▲
     ┌─────────────────┼─────────────────────┐
     │      │          │          │          │
  worker- worker-  worker-    worker-   worker-
 generation publish analytics outreach  default
   (c=4)   (c=8)    (c=4)      (c=4)     (c=8)
                       ▲
                 aro-scheduler
                 (Celery Beat, 187 tasks)
```

Queue-to-worker mapping (`docker-compose.yml`):

| Container | Concurrency | Queues |
|---|---|---|
| worker-generation | 4 | generation, pipeline, cinema_studio |
| worker-publishing | 8 | publishing, buffer |
| worker-analytics | 4 | analytics, learning, portfolio, qa |
| worker-outreach | 4 | outreach |
| worker-default | 8 | default, brain, mxp, scale_alerts, notifications, monetization, repurposing, autonomous_phase_d, growth_pack, revenue_ceiling_a/b/c, expansion_pack2, creator_revenue |

`express_publishing` queue uses priority with `x-max-priority: 10`.

## 6. FastAPI app shape

`apps/api/main.py` is a single-mount-point app:

1. CORS middleware (origins from `API_CORS_ORIGINS`)
2. Custom middleware: `RequestIDMiddleware`, `SecurityHeadersMiddleware`, `RedirectHostFixMiddleware`
3. Global exception handlers
4. Conditional Sentry init (fastapi + sqlalchemy + celery integrations, 10% trace sample)
5. `lifespan` hook: seeds provider registry via `provider_registry_service.audit_providers()` per org on startup
6. Local `/media` static mount (dropped when `S3_BUCKET_NAME` is set)
7. ~113 `app.include_router(...)` calls

Router families (prefix → purpose):
- `/api/v1/auth` — JWT register/login, bcrypt
- `/api/v1/organizations|brands|avatars|offers|accounts` — tenant CRUD
- `/api/v1/oauth` + `/api/v1/oauth/microsoft` — platform connections
- `/api/v1/content|pipeline` — content lifecycle
- `/api/v1/analytics` — attribution + reporting
- `/api/v1/brands/{id}/*` — 40+ per-brand engine routers mounted under this prefix (growth, revenue_ceiling, expansion_pack2, mxp, autonomous, brain, ai_command, …)
- `/api/v1/monetization` — credits, plans, ledger
- `/api/v1/webhooks` — Stripe, Shopify, media provider callbacks
- `/api/v1/email/drafts` + `/email_pipeline` — inbox classification + reply drafts
- `/api/v1/ws/*` — websocket live stream
- `/api/v1/gm_ai` + `/gm_chat` — the strategic "General Manager" agent
- `/health`, `/healthz`, `/readyz` — probes
- `/docs`, `/redoc` — only when `API_ENV=development`

### 6.1 Service layer pattern

```
Router (thin)  →  Service (logic)  →  Model (persistence)
     │                │                     │
  validation    business rules       SQLAlchemy ORM
  auth / RBAC   audit logging        PostgreSQL
  HTTP codes    error handling
```

No business logic in routers. All logic in `apps/api/services/*.py` (132 files).

### 6.2 RBAC
Three roles: `ADMIN` (3) > `OPERATOR` (2) > `VIEWER` (1). Enforced via `RequireRole` dependency with aliases: `CurrentUser`, `ViewerUser`, `OperatorUser`, `AdminUser`. Read is viewer+, write is operator+, settings/org is admin.

## 7. Data layer

### 7.1 Models (`packages/db/models/`, 92 files)

One file per domain slice. All use UUID PKs, TZ-aware `created_at`/`updated_at`, JSONB for flexible fields. Key groups:

- **Tenancy**: `accounts.py` (Organization, User), brand/creator structures
- **Content**: `content.py`, `content_form.py`, `content_routing.py`, `publishing.py`, `media_jobs.py`, `landing_pages.py`
- **Monetization**: `revenue_ledger.py` (the canonical 34-col `RevenueLedgerEntry` table), `offers.py`, `monetization.py`, `saas_metrics.py`
- **Autonomy**: `autonomous_execution.py`, `autonomous_farm.py`, `autonomous_phase_{a,b,c,d}.py`
- **Brain**: `brain_architecture.py`, `brain_phase_{b,c,d}.py`, `ai_personality.py`
- **MXP** (Maximum-Pack experiment layer): `experiments.py`, `experiment_decisions.py`, `capacity.py`, `contribution.py`, `creative_memory.py`, `audience_state.py`, `deal_desk.py`, `market_timing.py`, `reputation.py`, `offer_lifecycle.py`, `kill_ledger.py`, `recovery.py`
- **Revenue ceiling & expansion**: `revenue_ceiling_phase_{a,b,c}.py`, `expansion_pack2_phase_{a,b,c}.py`
- **Intelligence**: `pattern_memory.py`, `failure_family.py`, `objection_mining.py`, `opportunity_cost.py`, `capital_allocator.py`, `causal_attribution.py`, `trend_viral.py`, `executive_intel.py`
- **Governance**: `operator_permission_matrix.py`, `enterprise_security.py`, `brand_governance.py`, `quality_governor.py`, `gatekeeper.py`, `gm.py`
- **Integrations**: `integration_registry.py`, `provider_registry.py`, `provider_secrets.py`
- **Instrumentation**: `system.py`, `system_events.py`

`packages/db/models/__init__.py` is intentionally thin (no star exports) — import models directly from their module.

### 7.2 Migrations

Alembic in `packages/db/alembic/`:
```
001_consolidated_schema.py                     (squashed baseline)
002_cinema_studio_tables.py
003_provider_secrets.py
004_add_monetization_and_saas_models.py
005_expand_media_jobs_table.py
006_create_gm_and_alert_tables.py
007_publish_policy_rules.py
b6587e9c03b5_create_all_missing_tables_and_columns.py  (catch-up autogen)
```

`versions_backup/` has the pre-squash history.

**Important**: boot doesn't run `alembic upgrade head`. It runs `scripts/ensure_schema.py` via the one-shot `aro-migrate` container. This is intentional (audit flags it) — the schema has drifted past Alembic tracking. If you modify models, you need to (a) add an Alembic migration AND (b) make sure `ensure_schema.py` handles it idempotently.

### 7.3 The ledger

`RevenueLedgerEntry` is the canonical table for every dollar. 34 columns. Write path:
- Stripe webhooks → `monetization_bridge.py::record_stripe_event()`
- Shopify webhooks → `monetization_bridge.py::record_shopify_order()`
- Affiliate webhooks → `monetization_bridge.py::record_affiliate_commission()`
- Sponsor payments, service fees, product sales, refunds → same bridge

Idempotency via unique `webhook_ref` column. Duplicate-detection at insert.

All 17 revenue engines read from this table. Break the ledger and the whole engine stack goes blind.

### 7.4 Event bus

Two tables: `SystemEvent` (lifecycle audit) and `OperatorAction` (human-actionable items). Helpers in `apps/api/services/event_bus.py`.

Every meaningful state transition calls:
```python
db.add(SystemEvent(event_type=..., entity_id=..., metadata=...))
```

And when the system wants a human to decide:
```python
db.add(OperatorAction(
    action_type="approve_content",
    entity_id=content.id,
    confidence=0.72,
    suggested_action=...,
))
```

Actions with `confidence >= 0.6` are picked up by the autonomous dispatcher and executed without human intervention.

## 8. Celery worker layout (`workers/`)

68 worker packages, one sub-dir each. Every task inherits from `base_task.TrackedTask` which writes `SystemJob` and `SystemEvent` rows automatically.

Partial roster (alphabetical):
```
account_state_intel, action_executor, affiliate_intel,
analytics_ingestion, analytics, autonomous_generation,
autonomous_phase_{a,b,c,d}, brain, brand_governance, buffer,
campaign, capital_allocator, causal_attribution, cinema_studio,
competitor, content_form, content_ideation, content_routing,
creator_revenue, data_pruning, digital_twin, email_campaign,
engagement, enterprise_security, executive_intel, failure_family,
fleet_manager, generation, growth_pack, health_monitor, hyperscale,
integrations_listening, intelligence_report, landing_page, learning,
live_execution, monetization, monster_ops, mxp, niche_research,
objection_mining, offer_{discovery,lab,rotation}, opportunity_cost,
outreach, pattern_memory, pipeline, portfolio, promote_winner,
publishing, qa, quality_governor, recovery_engine, repurposing,
revenue_ceiling, revenue_leak, scale_alerts, strategy_adjustment,
trend_viral, warmup
```

### 8.1 Celery Beat (`workers/celery_app.py`)

993 lines, 187 periodic tasks. Sample cadences:

| Every | Task |
|---|---|
| 30 min | `analytics_worker.tasks.ingest_performance` |
| 1 h | `analytics_worker.tasks.scan_trends` |
| 4 h | `scale_alerts_worker.tasks.recompute_all_alerts` |
| 4 h | `monetization_worker.tasks.run_revenue_cycle` (per docs; not runtime-proven) |
| 6 h | `analytics_worker.tasks.check_saturation` |
| daily 06:00 | `portfolio_worker.tasks.rebalance_portfolios` |
| varied | 180+ per-engine recomputes |

A 14MB `celerybeat-schedule` shelve file sits at the repo root. It's Beat's state on last run — ephemeral, should be in `.gitignore` and isn't. One of the cleanup tasks.

### 8.2 Queue routing

Task-to-queue mapping is partially in `celery_app.py::task_routes` and partially via `@celery_app.task(queue=...)` decorators. The monolithic `revenue_ceiling_worker.tasks.*` functions are hard-routed by name pattern into `revenue_ceiling_a|b|c` + `expansion_pack2`.

## 9. The revenue-maximization loop (the business logic)

1. **Discover** — signals/trends/niches → `discovery_service.py`, `niche_research_worker`. **Status:** manual seed only; no trend APIs wired.
2. **Ideate** — `content_form_service.py`, `content_ideation_worker`.
3. **Route** — tiered provider selection → `content_routing_service.py`, `integration_manager.py` (new subsystem in `NEXT_SESSION_SPEC.md`).
4. **Generate** — `content_generation_service.py`, `generation_worker`, `cinema_studio_worker` (long-form).
5. **QA** — `quality_governor_service.py`, `content_pipeline_service.run_qa()`. **Status:** scores are hardcoded (`originality_score=0.7`, `compliance_score=0.85`). High priority to replace.
6. **Approve** — human-in-loop via `OperatorAction`.
7. **Publish** — `publishing_worker`. Buffer wired (real HTTP). Publer + Ayrshare clients exist, unused.
8. **Ingest analytics** — `analytics_ingestion_worker`. Models exist. Clients **don't**. High priority.
9. **Attribute** — `attribution_builder.py` + `causal_attribution_service.py`.
10. **Ledger write** — `monetization_bridge.py`.
11. **Compute** — 17 engines E1–E17 (see §9.1).
12. **Act** — autonomous dispatcher executes `OperatorAction` rows with confidence ≥0.6.

### 9.1 The 17 revenue engines

| # | Engine | File |
|---|---|---|
| E1 | Creator fit scoring (10 paths per account) | `packages/scoring/revenue_maximizer.py` |
| E2 | Opportunity detection | same |
| E3 | Revenue allocation | same |
| E4 | Suppression targets | same |
| E5 | Revenue memory (what worked) | same |
| E6 | Monetization mix (current vs optimal) | same |
| E7 | Next-best actions (top 10 by value) | same |
| E8 | What-if simulation | `revenue_engines_extended.py` |
| E9 | Margin rankings | same |
| E10 | Creator archetypes (11 types) | same |
| E11 | Offer packaging (entry / core / upsell) | same |
| E12 | Experiment opportunities | same |
| E13 | Payout speed (days-to-cash) | same |
| E14 | Leak detection | same |
| E15 | Portfolio allocation | same |
| E16 | Cross-platform compounding | same |
| E17 | Durability scoring | same |

All engines are read-only computations that return recommendations. The dispatcher is what turns recommendations into state changes.

### 9.2 Autonomy layers

Two parallel stacks:

**Autonomous Phases A→D** (content-side):
- A: signal scan / warmup
- B: policies / distribution / suppression
- C: funnel / paid / sponsor / retention / recovery
- D: agents / pressure / overrides / blockers / escalations

Each phase has router + service + worker + model.

**Brain Phases A→D** (cognition-side):
- A: memory + state (fully real)
- B: decisions + policies + confidence + arbitration (fully real)
- C: agent mesh / workflows / context bus (not auditable at 2026-04-04)
- D: meta-monitoring / self-correction / escalation (not auditable)

### 9.3 Bridges

Cross-layer coordinators in `apps/api/services/*_bridge.py`:

- `event_bus.py` — SystemEvent + OperatorAction emission
- `governance_bridge.py` — permission check + AuditLog + MemoryEntry. **NB:** returns a dict, does NOT enforce; callers must respect voluntarily. Audit flagged this.
- `intelligence_bridge.py` — converts `BrainDecision`, `PatternDecayReport`, `PWExperimentWinner`, `FailureFamilyReport` → `OperatorAction` rows
- `monetization_bridge.py` — ledger writers + revenue-state readers
- `orchestration_bridge.py` — job/worker/provider visibility, auto-creates OperatorActions for stuck jobs

## 10. Frontend shape

`apps/web/src/app/` (App Router):

- `/` — marketing root
- `/login` — login
- `/lp/[pageId]` — dynamic landing page renderer
- `/offers/{brand}/{slug}` — static offer pages (3 brands × 6–8 offers)
- `/dashboard/...` — ~180 operator pages

Brand themes live under `/offers/`:
- `aesthetic-theory` (beauty/skincare) — 3 fully custom pages + 5 `PackagePage` templates
- `body-theory` (fitness/wellness) — 6 template pages
- `tool-signal` (B2B SaaS) — 6 template pages

Dashboard groupings (representative, not exhaustive):
- Observability: `content`, `jobs`, `analytics`, `decisions`, `library`, `calendar`, `live-events`
- Autonomy: `autonomous-execution`, `brain-decisions`, `brain-ops`, `meta-monitoring`, `agent-mesh`
- MXP: `experiments`, `capacity`, `contribution`, `deal-desk`, `kill-ledger`, `recovery`
- Revenue ceiling A/B/C + Expansion Pack 2 A/B/C
- Growth / Gatekeeper / Copilot
- Ops: `command-center`, `cockpit`, `workflows`, `integrations`, `settings`
- Creator revenue: `creator-revenue-hub`, `ugc-services`, `consulting`, `premium-access`, `merch`, `licensing`, `data-products`
- Buffer/distribution: `buffer-publish`, `buffer-profiles`, `buffer-retry`, `buffer-status`
- Cinema Studio: `studio`, `studio/{characters,projects,scenes,styles,generations}`
- Landing pages, campaigns, paid-operator, syndication
- Misc: trend-scanner, capital-allocation, pattern-memory, failure-families, knowledge-graph, roadmap

**Important**: per `REALITY_AUDIT.md`, at audit time only 3 pages had operational action buttons (`dashboard`, `content`, `orchestration`). The rest are read-only reporting surfaces. When a user asks "can I click this to do X", the answer is usually no — today.

## 11. Configuration (`.env.example`, 150+ vars)

Grouped:

- **Identity**: `COMPOSE_PROJECT_NAME`, `DOMAIN`
- **Postgres**: `POSTGRES_*`, `DATABASE_URL` (async), `DATABASE_URL_SYNC` (for Alembic)
- **Redis**: `REDIS_URL`, `CELERY_BROKER_URL` (db 1), `CELERY_RESULT_BACKEND` (db 2)
- **API**: `API_HOST/PORT/SECRET_KEY/CORS_ORIGINS/ENV`, `LOG_LEVEL`
- **Web**: `NEXT_PUBLIC_API_URL`, `FRONTEND_URL`, `WEBHOOK_BASE_URL`
- **S3**: `S3_*` (falls back to local `/media` if unset)
- **AI text**: `ANTHROPIC_API_KEY`, `GOOGLE_AI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, `XAI_API_KEY`
- **AI image**: `FAL_API_KEY`, `REPLICATE_API_TOKEN`, `STABILITY_*`
- **AI video**: `RUNWAY_API_KEY`, `KLING_*`, `HIGGSFIELD_*`
- **AI avatar**: `HEYGEN_API_KEY`, `DID_API_KEY`, `TAVUS_API_KEY`, `SYNTHESIA_*`
- **AI voice**: `ELEVENLABS_API_KEY`, `FISH_AUDIO_API_KEY`
- **AI music**: `MUBERT_API_KEY`, `SUNO_*`
- **Publishing**: `BUFFER_API_KEY` (via dashboard Settings; not in .env), `PUBLER_API_KEY`, `AYRSHARE_API_KEY`
- **Platform analytics**: `YOUTUBE_API_KEY`, `YOUTUBE_OAUTH_TOKEN`, `TIKTOK_ACCESS_TOKEN`, `INSTAGRAM_ACCESS_TOKEN`
- **Trends**: `SERPAPI_KEY`
- **Payments**: `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*` (6 IDs)
- **Commerce**: `SHOPIFY_DOMAIN/ACCESS_TOKEN/WEBHOOK_SECRET`, `CLICKBANK_API_KEY`
- **Affiliate**: `IMPACT_*`, `SHAREASALE_*`
- **Email**: `SMTP_*` (Brevo), `IMAP_*` (Outlook)
- **Observability**: `SENTRY_DSN`

docker-compose intentionally sets `env_file: .env` PLUS explicit `environment:` overrides for Docker-internal hostnames. This is to prevent stray shell env vars from nulling out real values — don't "clean it up."

## 12. Deployment (`deploy.sh`)

Six steps with rollback tagging:

1. Verify `.env` exists; hard-fail if `API_SECRET_KEY` or `POSTGRES_PASSWORD` contain `changeme`
2. Tag current images `:rollback`
3. Build using `docker-compose.yml` + `docker-compose.prod.yml`
4. Start postgres + redis, wait ≤60s for `pg_isready`, run `scripts/ensure_schema.py` in a one-shot `--rm --no-deps api` container
5. Rolling restart: api, web, worker, scheduler, caddy
6. Health verify: 15 × 3s hits to `http://localhost:8001/healthz`. Warns on timeout; doesn't fail.

Prints `docker compose ps` and public URLs at the end.

## 13. Testing

- `tests/unit/` — services, models, pure logic
- `tests/integration/` — runs inside `aro-api` container against `avatar_revenue_os_test` DB (created on demand via `make create-test-db`). `pytest-asyncio` in `asyncio_mode = "auto"`.
- `tests/e2e/` — full flows
- `pyproject.toml`: `testpaths = ["tests"]`, deprecation warnings silenced

Run:
```bash
make test                                              # inside container
docker exec aro-api pytest tests/unit/test_x.py -v     # specific file
```

### 13.1 The "proof" scripts

`scripts/*_proof.py` — the project's in-house integration tests for high-level behavior. Not pytest. Run imperatively:
```bash
docker exec aro-api python scripts/compounding_proof.py       # 28/28
docker exec aro-api python scripts/monetization_proof.py      # 54/54
docker exec aro-api python scripts/revenue_maximizer_proof.py # 38/38 + 43/43
docker exec aro-api python scripts/runtime_proof.py           # 60/60
docker exec aro-api python scripts/static_proof.py            # 101/101
docker exec aro-api python scripts/last_mile_proof.py
docker exec aro-api python scripts/e2e_publish_proof.py
```

These are the ground-truth regression suite. If any drops below its claimed pass count, that's a real regression. Every PR should run these.

## 14. Reality check — what's real vs stub

`REALITY_AUDIT.md` (28KB, dated 2026-04-04, commit `6540a3e`) is authoritative. Every feature classified: **Fully real** / **Partially real** / **Surface-only** / **Not real**. Read it before making any architectural change — it will save you from reimplementing something that's stubbed by design.

### Fully real (runtime-verified)
- Event bus + OperatorAction pattern (60/60 proof)
- Control layer dashboard (cross-layer SQL aggregation)
- `RevenueLedgerEntry` + all ledger writers with idempotent `webhook_ref`
- All 17 revenue engines E1–E17 as read-only computations
- Execution engine + autonomous dispatcher, confidence gating ≥0.6
- AI text generation (when creds configured) — tiered routing + template fallback
- Media generation (when creds) — HeyGen, D-ID, Runway, Kling
- Buffer publishing (real HTTP POSTs)
- Email via aiosmtplib, SMS via Twilio (when creds)
- Webhook signature verification (Stripe HMAC-SHA256, Shopify SHA256, 300s tolerance)
- JWT HS256, bcrypt, 24h expiry
- Brain Phase A + B (computational)

### Known gaps (HIGH severity)
1. **QA scoring hardcoded** — `content_pipeline_service.run_qa()` passes `originality_score=0.7, compliance_score=0.85`. No actual content analysis.
2. **No performance data collection** — `PerformanceMetric` model exists; no platform-analytics API clients. YouTube, TikTok, Instagram clients missing.

### Known gaps (MEDIUM severity)
3. **Discovery is manual-only** — no Google Trends, YouTube Research, social trend APIs. `SERPAPI_KEY` empty.
4. **Brain decisions don't auto-execute** — `BrainDecision` rows created but no worker dispatches them. Wire via `intelligence_bridge.py`.
5. **Autonomous execution loop doesn't orchestrate** — `autonomous_execution_service.py` evaluates policy gates but doesn't dispatch. Revenue execution engine + action dispatcher partially replaces.

### Known gaps (LOW severity)
6. Provider audit is credential-check only (presence of env var, not connectivity). Recommended rename: "credential registry."
7. CRM sync not implemented — `CrmContact`/`CrmSync` models but no API clients. Hide the dashboard page until real.
8. Publer/Ayrshare clients exist but unused — `publishing_worker` uses Buffer only.
9. Scheduled revenue cycle not runtime-proven — Beat entry exists, task is importable, never observed firing.
10. Brain Phase C+D not auditable at audit time. Workers reference but implementation unclear.
11. ~204 of 207 frontend pages are read-only. Only `dashboard`, `content-pipeline`, `orchestration` have operational action buttons.

Audit items 1–5 are the direct multipliers on revenue-engine effectiveness. Tackle in order.

## 15. Integration Manager (new subsystem, WIP)

Per `NEXT_SESSION_SPEC.md`, there's an in-progress unified provider catalog + credential broker:

- **Models**: `IntegrationProvider` (26 cols, encrypted creds, health tracking, tier routing), `CreatorPlatformAccount` (22 cols)
- **Service**: `integration_manager.py` with `seed_provider_catalog()`, `set_credential()` (encrypts), `get_credential()` (decrypts), `list_providers()` (masks), `get_provider_for_task(category, quality_tier)` (tier-aware with fallback)
- **Seeded providers**: 24 across LLM (claude/gemini/deepseek/groq), Image (openai/imagen4/flux), Video (kling/runway), Avatar (heygen/did), Voice (elevenlabs/fish_audio/voxtral), Publishing (buffer/publer/ayrshare), Analytics (youtube/tiktok/instagram), Trends (serpapi), Email (smtp), Inbox (imap), Payment (stripe)
- **Router**: `integrations_dashboard.py` — `POST /integrations/seed`, `GET /integrations/providers`, `POST /integrations/providers/{key}/credential`, `GET /integrations/route`, `POST /integrations/providers/{key}/{enable|disable}`

Content + publishing pipelines still read env vars directly. Wiring them to consume `integration_manager.get_provider_for_task()` is the open work. When done, manual env-var babysitting goes away and tier routing + fallback becomes automatic.

## 16. Working conventions

### 16.1 Branches
- `main` — prod-deployable
- `claude/<codename>` — feature branches (many active)
- Never force-push `main`

### 16.2 Commits
- Conventional commits preferred (`feat:`, `fix:`, `chore:`, `refactor:`)
- Reference audit items as `audit: HIGH-2 performance data collection`
- `.pre-commit-config.yaml` is enforced — ruff + mypy + basic hooks

### 16.3 Adding a new model
1. Create the file in `packages/db/models/<domain>.py`
2. UUID PK, TZ-aware timestamps, JSONB for flexible fields
3. Never add to `__init__.py` — import directly
4. Write an Alembic migration: `docker exec aro-api alembic revision --autogenerate -m "<desc>"`
5. **Also update `scripts/ensure_schema.py`** to handle the new table idempotently (boot uses this, not Alembic)
6. Add model-level tests in `tests/unit/models/`

### 16.4 Adding a new router
1. File in `apps/api/routers/<domain>.py`
2. `router = APIRouter(prefix="/api/v1/<domain>", tags=["<domain>"])`
3. Thin handlers — delegate to service
4. Use `CurrentUser`, `OperatorUser`, `AdminUser` dependencies for RBAC
5. `app.include_router(router)` in `apps/api/main.py`
6. Schema files in `apps/api/schemas/<domain>.py`
7. Integration test in `tests/integration/routers/test_<domain>.py`

### 16.5 Adding a new Celery task
1. Function in `workers/<worker>/tasks.py`
2. Inherit `TrackedTask` for SystemJob/SystemEvent instrumentation:
```python
from workers.base_task import TrackedTask
@celery_app.task(base=TrackedTask, queue="<queue>", bind=True)
def my_task(self, *args, **kwargs):
    ...
```
3. Register queue in `docker-compose.yml` worker container if not already
4. Add Beat schedule entry in `workers/celery_app.py` if periodic
5. Smoke: `docker exec aro-api celery -A workers.celery_app call workers.<worker>.tasks.my_task`

### 16.6 Adding a new frontend dashboard page
1. Dir: `apps/web/src/app/dashboard/<domain>/page.tsx`
2. Use existing `components/` for cards, tables, filters
3. Data via React Query hooks in `hooks/use<Domain>.ts`
4. Types in `types/<domain>.ts`
5. Link from a parent page or sidebar component if discoverable

### 16.7 Adding a new revenue source type
1. New string value in `revenue_source_type` comment in `packages/db/models/revenue_ledger.py` (column is `String(60)`, no enum)
2. Writer function in `monetization_bridge.py`: `record_<source>_event(...)` with idempotency via unique `webhook_ref`
3. Webhook handler in `apps/api/routers/webhooks.py` if external trigger
4. All 17 engines already read by `revenue_source_type` — no changes needed on the read side

## 17. Things that are easy to break

- **`scripts/ensure_schema.py` vs Alembic**: model changes must go in BOTH. Forget and boot fails on one envs but not others.
- **Duplicate `RevenueLedgerEntry` on webhook retry**: `webhook_ref` must be unique and set by the writer, not the DB default.
- **Beat schedule from the host**: `celerybeat-schedule` at repo root is shelve state from running Beat on the host, not in Docker. Never run Beat both places simultaneously — tasks duplicate.
- **CORS origins**: `API_CORS_ORIGINS` is a JSON array in the env. A raw comma-separated string silently fails.
- **Redis as broker AND result backend** but in different DBs (1 vs 2). Don't put both on db 0.
- **OperatorAction confidence threshold**: changing the default 0.6 cutoff changes what auto-executes vs what waits for human approval. Test impact before adjusting.

## 18. Where to start if you want to help

Top candidates by `$ / hour of dev work` (these close HIGH-severity audit gaps):

1. **YouTube analytics client** — `packages/clients/youtube_analytics.py`. Wire into `workers/analytics_ingestion_worker/tasks.py::ingest_performance`. Unlocks engines E14, E15, E16, E17 against real data.
2. **TikTok + Instagram analytics clients** — same pattern. Parallel work.
3. **Real QA scoring** — `apps/api/services/content_pipeline_service.py::run_qa()`. Replace hardcoded scores with OpenAI embeddings (originality) + Claude API calls (compliance, hook strength).
4. **Brain decision dispatcher** — `workers/brain_worker/tasks.py::dispatch_brain_decisions`. Select confidence ≥0.7 unexecuted, convert to `OperatorAction` via `intelligence_bridge.py`, mark executed. Add Beat entry every 15 min.
5. **SerpAPI trend discovery** — env key + wrapper in `packages/clients/serpapi_client.py`, wire into `workers/niche_research_worker`.
6. **Publer + Ayrshare publishing fallback** — add priority-ordered routing in `workers/publishing_worker/tasks.py`.
7. **Integration Manager wiring** — finish per `NEXT_SESSION_SPEC.md`. Content + publishing pipelines read from `integration_manager.get_provider_for_task()` instead of env vars directly.

Smaller cleanup wins:
- `.gitignore` `celerybeat-schedule`, `.pytest_cache/`, `.backups/`
- Hide dashboard pages for unimplemented features (per audit item 11)
- Consolidate the `NEW` vs `NEW2` sibling confusion (see `SYSTEM_ANALYSIS.md` §0)
- Rotate secrets in `.env` (dev password is still the default-ish value)
- Fix apps/web `node_modules` + `.next` stale state (both 0 bytes via `du`)

## 19. Docs tree

107 numbered markdown docs in `docs/` covering every engine, phase, and module. Entry points:

- `docs/01-setup.md` — setup
- `docs/02-architecture.md` — authoritative architecture
- `docs/33-mxp-*.md` → `docs/43-mxp-*.md` — MXP modules
- `docs/50-revenue-ceiling-*.md` → `docs/60-*.md` — revenue ceiling phases
- `docs/70-expansion-pack-*.md` → `docs/85-trend-viral-engine.md` — expansion packs

Repo-root companions:
- `REALITY_AUDIT.md` — what's real vs stub (read this first)
- `NEXT_SESSION_SPEC.md` — forward-looking work queue
- `SYSTEM_ANALYSIS.md` — structural analysis (this document's predecessor)
- `REVENUE_PLAYBOOK.md` — business-side playbook

## 20. Fast-start checklist

```
[ ] Clone repo, cp .env.example → .env, fill in AI provider keys (Anthropic minimum)
[ ] make up
[ ] Visit http://localhost:3001 — Next.js root loads
[ ] Visit http://localhost:8001/docs — FastAPI Swagger loads
[ ] Visit http://localhost:8001/healthz — returns 200
[ ] docker exec aro-api python scripts/compounding_proof.py — 28/28 passes
[ ] docker exec aro-api python scripts/monetization_proof.py — 54/54 passes
[ ] Read REALITY_AUDIT.md top-to-bottom
[ ] Pick one HIGH-severity audit gap from §18
[ ] Open a claude/<feature> branch, wire it, PR
```

---

*End of handoff document.*

# System Analysis — AI Avatar Revenue OS (folder "AI AVATAR CONTENT OS OPS NEW2")

**Analysis date:** 2026-04-22
**Analyst:** Claude (Cowork mode)
**Target folder:** `/Users/pstuart/Desktop/AI AVATAR CONTENT OS OPS NEW2/`
**Git:** `https://github.com/patstu1/avatar-revenue-os.git` — branch `main`, many `claude/*` feature branches

---

## 0. Clarification vs. the sibling "NEW" folder

The sibling folder `~/Desktop/AI AVATAR CONTENT OS OPS NEW/` is nearly empty — just a `.claude/settings.local.json` allow-list and empty scaffolding. **This** folder (`…NEW2`) is the **actual** working copy of the system: 380 KB of source, 380+ Python files, 322 TypeScript/TSX files, 107 markdown docs, full Docker Compose, full Git history. Everything described below is ground-truth from the code itself.

---

## 1. One-paragraph summary

**AI Avatar Revenue OS** ("ARO", internal name `avatar-revenue-os`, production domain `app.nvironments.com`) is a self-described "production-grade SaaS for autonomous content monetization." It is a multi-tenant (Organization → Brand → CreatorAccount) platform that ingests AI-generated content across multiple providers (text, image, video, avatar, voice), routes it through a tiered provider stack (hero / standard / bulk with fallback), runs it through a content lifecycle (brief → generate → QA → approve → publish), distributes it via Buffer / Publer / Ayrshare, ingests analytics, writes all revenue events to a canonical `RevenueLedgerEntry` table, and then runs 17 revenue engines + an autonomous action dispatcher on top of that ledger to compute what to do next — with everything observable via 180+ Next.js dashboard pages and executable via a Celery Beat scheduler running 187 recurring tasks across 25 queues.

---

## 2. Tech stack (ground-truth from `pyproject.toml`, `requirements.txt`, `docker-compose.yml`, `package.json`)

### Backend (Python 3.11, requires ≥3.9)

| Layer | Choice | Version pin |
|---|---|---|
| Web framework | FastAPI | 0.115.6 |
| ASGI server | uvicorn[standard] | 0.34.0 |
| ORM (async) | SQLAlchemy | 2.0.36 |
| Postgres driver (async) | asyncpg | 0.30.0 |
| Postgres driver (sync, migrations) | psycopg2-binary | 2.9.10 |
| Migrations | Alembic | 1.14.1 |
| Validation / config | Pydantic + pydantic-settings | 2.10.4 / 2.7.1 |
| Task queue | Celery[redis] | 5.4.0 |
| Redis client | redis-py | 5.2.1 |
| Auth | python-jose (JWT HS256) + passlib[bcrypt] | 3.3.0 / 1.7.4 |
| HTTP client | httpx | 0.28.1 |
| Logging | structlog (JSON in prod, console in dev) | 24.4.0 |
| Errors/tracing | sentry-sdk[fastapi,celery,sqlalchemy] | 2.19.2 |
| LLM SDKs | openai 1.58.1, anthropic ≥0.39 | — |
| Email | aiosmtplib ≥3.0 | — |
| Storage | boto3 | 1.36.2 |
| Payments | stripe | ≥8.0 |
| PDFs | weasyprint | ≥62.0 |
| Google APIs | google-api-python-client, google-auth, google-auth-oauthlib | — |
| Utilities | orjson 3.10.13, tenacity 9.0.0, python-dateutil 2.9.0 | — |
| Dev | pytest 8.x + pytest-asyncio + pytest-cov + ruff + mypy + pre-commit | — |

### Frontend (`apps/web`)

- **Next.js 14+ App Router** (`apps/web/src/app/…`, 322 `.tsx`/`.ts` files)
- TypeScript + Tailwind + React Query (per `docs/02-architecture.md`) + Zustand
- Dev command: `npm run dev`, port 3000 (host-exposed 3001 via `docker-compose.yml`)
- Directories under `apps/web/src/`: `app/`, `components/`, `hooks/`, `lib/`, `types/`
- `.next/` build cache is present at analysis time (compiled artifacts exist)

### Infrastructure (`docker-compose.yml` + `docker-compose.prod.yml` + `infrastructure/`)

- **Docker Compose** project `avatar-revenue-os`, network `aro-network` (bridge)
- **Reverse proxy**: Caddy 2-alpine, auto-HTTPS via Let's Encrypt, routes based on path
- **Dockerfiles** at `infrastructure/docker/Dockerfile.api` and `Dockerfile.web`
- **Terraform** directory present but not inspected (IaC in progress)
- **Volumes**: `aro_pgdata`, `aro_redisdata`, `aro_web_node_modules`, `aro_caddy_data`, `aro_caddy_config`
- **Host-exposed dev ports**: postgres 5433 → 5432, redis 6380 → 6379, api 8001 → 8000, web 3001 → 3000

---

## 3. Repository layout

```
avatar-revenue-os/
├── apps/
│   ├── api/                        FastAPI backend
│   │   ├── main.py                 ~320 lines; mounts all 113 routers
│   │   ├── middleware/             RequestID, SecurityHeaders, RedirectHostFix, exception handlers
│   │   ├── routers/                113 routers (one per domain surface)
│   │   ├── services/               132 services (business logic, service-layer architecture)
│   │   └── schemas/                Pydantic request/response models
│   └── web/                        Next.js App Router frontend
│       └── src/
│           ├── app/                180+ dashboard pages + 3 public route groups
│           │   ├── dashboard/      180+ operational pages (see §8)
│           │   ├── lp/[pageId]/    Dynamic landing-page renderer
│           │   ├── offers/{brand}/{slug}/  Static offer pages (3 brand themes × 6–8 packages)
│           │   ├── login/
│           │   └── page.tsx        Root
│           ├── components/
│           ├── hooks/
│           ├── lib/
│           └── types/
├── workers/                        68 Celery worker packages (§6)
│   ├── celery_app.py               993 lines: 25 queues, 187 beat-scheduled tasks
│   ├── base_task.py                Shared TrackedTask base (emits SystemJob rows)
│   └── <worker_name>/tasks.py      One folder per worker
├── packages/
│   ├── db/
│   │   ├── models/                 92 SQLAlchemy model files (one per domain slice)
│   │   ├── alembic/
│   │   │   ├── alembic.ini
│   │   │   └── versions/           8 migrations (§7.3)
│   │   └── session.py              async_session_factory
│   ├── scoring/                    107 scoring engine files (+ growth_pack/)
│   ├── clients/                    External API clients (SMTP, Twilio, Buffer, Publer, Ayrshare, etc.)
│   ├── provider_clients/           Provider-SDK wrappers (Anthropic, OpenAI, Gemini, HeyGen, …)
│   ├── executors/                  Action execution wrappers
│   ├── guardrails/                 Pre-action policy checks
│   ├── media/                      Storage + media helpers (S3-or-local)
│   ├── notifications/              Email/SMS delivery
│   ├── forecasting/
│   ├── policy-rules/
│   ├── prompt-templates/
│   ├── shared-types/               Cross-language type definitions
│   ├── ui/                         Shared UI tokens/utilities
│   └── utils/
├── infrastructure/
│   ├── caddy/Caddyfile             Reverse-proxy routes (§4)
│   ├── docker/                     Dockerfile.api, Dockerfile.web
│   └── terraform/                  (placeholder for IaC)
├── tests/                          170 test files
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/                        ~20 operational scripts (§7.4)
├── docs/                           107 markdown docs numbered 01–85 with letter suffixes
├── media/                          Runtime-written media (gitignored mostly)
├── Makefile                        up/down/migrate/seed/test/lint/typecheck/health/reset
├── deploy.sh                       6-step production deploy with rollback tagging
├── docker-compose.yml              Dev stack
├── docker-compose.prod.yml         Prod overrides
├── pyproject.toml
├── requirements.txt + requirements.lock
├── .env / .env.example             ~150+ env vars covering every provider
├── REALITY_AUDIT.md                28 KB internal honesty audit (§9)
├── NEXT_SESSION_SPEC.md            Forward-looking work-in-progress list
└── celerybeat-schedule             14 MB shelve file (last Beat state; was running on host)
```

---

## 4. Runtime topology

```
                   Let's Encrypt (Caddy ACME)
                            ▲
                            │ 80 / 443 (TCP+UDP)
┌───────────────────────────┴────────────────────────────┐
│                  Caddy (aro-caddy)                      │
│  Path routing (from infrastructure/caddy/Caddyfile):    │
│   /api/* /health /healthz /readyz /docs /openapi.json  ─┼──► api:8000
│   /ws/*  /media/*                                       │
│   everything else  ─────────────────────────────────────┼──► web:3000
└────┬────────────────────────┬────────────────────────┬──┘
     │                        │                        │
┌────▼──────┐       ┌─────────▼──────────┐   ┌─────────▼──────────┐
│  aro-api  │       │  aro-web (Next.js) │   │  (shared volumes)  │
│  FastAPI  │       │  App Router, 322   │   │   aro_pgdata       │
│  uvicorn  │       │  TS/TSX files      │   │   aro_redisdata    │
│  :8000    │       │  :3000             │   │   aro_caddy_*      │
└───┬───────┘       └────────────────────┘   └────────────────────┘
    │
    ├── asyncpg ──► aro-postgres (postgres:16-alpine, max_connections=500)
    │                                   ↑
    │                                   │ sync psycopg2
    │                               aro-migrate (one-shot, scripts/ensure_schema.py)
    │
    └── redis ──► aro-redis (redis:7-alpine, 256 MB LRU)
                        ▲
                        │ broker + result backend
     ┌──────────────────┼────────────────────────────────────┐
     │                  │                                    │
┌────▼──────────┐  ┌────▼──────────┐   ┌────▼──────────┐  ┌──▼────────────┐
│ worker-       │  │ worker-       │   │ worker-       │  │ worker-       │
│ generation    │  │ publishing    │   │ analytics     │  │ outreach      │
│ (concurrency  │  │ (concurrency  │   │ (concurrency  │  │ (concurrency  │
│  4)           │  │  8)           │   │  4)           │  │  4)           │
│ queues:       │  │ queues:       │   │ queues:       │  │ queues:       │
│  generation,  │  │  publishing,  │   │  analytics,   │  │  outreach     │
│  pipeline,    │  │  buffer       │   │  learning,    │  │               │
│  cinema_      │  │               │   │  portfolio,   │  │               │
│  studio       │  │               │   │  qa           │  │               │
└───────────────┘  └───────────────┘   └───────────────┘  └───────────────┘
                        ┌───────────────┐      ┌───────────────┐
                        │ worker-default│      │ aro-scheduler │
                        │ concurrency 8 │      │ Celery Beat   │
                        │ 14 queues     │      │ 187 periodic  │
                        │  (brain, mxp, │      │ tasks         │
                        │  monetization,│      └───────────────┘
                        │  repurposing, │
                        │  autonomous_d,│
                        │  growth_pack, │
                        │  revenue_     │
                        │  ceiling_a/b/ │
                        │  c, expansion │
                        │  _pack2,      │
                        │  creator_     │
                        │  revenue, …)  │
                        └───────────────┘
```

Service-to-service dependencies enforced via `healthcheck` + `depends_on` with `condition: service_healthy` / `service_completed_successfully` — a migrate container runs `scripts/ensure_schema.py` on every boot, and nothing else starts until that succeeds.

---

## 5. FastAPI backend shape

`apps/api/main.py` is the single mount point. It creates one `FastAPI(...)` app with:

- CORS (origins from `API_CORS_ORIGINS` env), custom middleware stack (`RequestIDMiddleware`, `SecurityHeadersMiddleware`, `RedirectHostFixMiddleware`), global exception handlers.
- Conditional Sentry init (FastAPI + SQLAlchemy + Celery integrations, 10% traces sample rate).
- A startup `lifespan` hook that seeds the provider registry for every Organization by calling `provider_registry_service.audit_providers()`.
- A local-media static mount at `/media` if `S3_BUCKET` env is unset.

Then 100+ `app.include_router(...)` calls. Router prefixes cluster into these families:

| Prefix | Example routers | Purpose |
|---|---|---|
| `/api/v1/auth` | auth | JWT register/login |
| `/api/v1/organizations`, `/brands`, `/avatars`, `/offers`, `/accounts` | CRUD core | Tenant + resources |
| `/api/v1/oauth`, `/api/v1/oauth/…/microsoft` | oauth, microsoft_inbox_oauth | Platform connections (YouTube, TikTok, IG, X, Microsoft) |
| `/api/v1/content`, `/pipeline` | content, pipeline, content_form, content_routing | Content lifecycle |
| `/api/v1/decisions`, `/jobs`, `/providers`, `/provider-registry`, `/dashboard`, `/settings` | CRUD meta | System visibility |
| `/api/v1/analytics` | analytics | Attribution + reporting |
| `/api/v1/brands` (**bulk prefix**, ~40 routers mounted here) | growth_*, revenue_ceiling_*, expansion_pack2_*, mxp_*, autonomous_*, brain_*, ai_command, … | All per-brand engines |
| `/api/v1/monetization` | monetization, revenue_machine | Credits, plans, packs, telemetry |
| `/api/v1/onboarding` | onboarding | New-user setup |
| `/api/v1/webhooks` | webhooks | Stripe + Shopify + media-provider callbacks |
| `/api/v1/email/drafts`, `/email_pipeline` | email_pipeline | Inbound email classification + reply drafts |
| `/api/v1/ops`, `/brain_ops` | ops, brain_ops | Operational surfaces |
| `/api/v1/ws/*` | ws_live | WebSocket live-revenue stream |
| `/api/v1/gm_ai`, `/gm_chat` | gm_ai, gm_chat | GM — the strategic operating brain (conversational) |
| (root) `/health`, `/healthz`, `/readyz` | health | Kubernetes-style probes |

`/docs` and `/redoc` are mounted only when `API_ENV == "development"`.

### Service layer

All business logic lives in `apps/api/services/*.py` (132 files). The pattern, restated from `docs/02-architecture.md`:

```
Router (thin) → Service (logic) → Model (persistence)
     ↓              ↓                    ↓
  Validation    Business rules      SQLAlchemy ORM
  Auth/RBAC     Audit logging       PostgreSQL
  HTTP codes    Error handling
```

### RBAC

Three roles: `ADMIN` (3) > `OPERATOR` (2) > `VIEWER` (1). Enforced by `RequireRole` dependency with aliases `CurrentUser`, `ViewerUser`, `OperatorUser`, `AdminUser`. Create/update/delete requires Operator+. Settings and org config require Admin.

---

## 6. Celery worker topology (68 workers, 25 queues, 187 beat tasks)

The `workers/` directory contains one sub-package per business capability. Each has `tasks.py` and inherits from `base_task.TrackedTask` which emits `SystemJob` and `SystemEvent` rows on every run — the audit writes cited in `REALITY_AUDIT.md` come from here.

Worker packages present (alphabetical):

```
account_state_intel_worker        ▸ Account-state intelligence
action_executor_worker            ▸ Executes autonomous OperatorAction rows
affiliate_intel_worker            ▸ Affiliate performance scoring
analytics_ingestion_worker        ▸ Platform analytics ingestion
analytics_worker                  ▸ Trend scan, performance ingest, saturation
autonomous_generation_worker      ▸ Auto content generation
autonomous_phase_{a,b,c,d}_worker ▸ Four-phase autonomy (see docs 34–38)
brain_worker                      ▸ Brain phase A/B/C/D tasks
brand_governance_worker           ▸ Brand OS enforcement
buffer_worker                     ▸ Buffer sync + retry
campaign_worker
capital_allocator_worker          ▸ Spend routing by tier
causal_attribution_worker
cinema_studio_worker              ▸ Long-form avatar cinema pipeline
competitor_worker
content_form_worker               ▸ Form/format selection engine
content_ideation_worker
content_routing_worker            ▸ Tiered provider routing
creator_revenue_worker            ▸ UGC, consulting, premium access
data_pruning_worker
digital_twin_worker               ▸ What-if simulation
email_campaign_worker
engagement_worker
enterprise_security_worker
executive_intel_worker
failure_family_worker             ▸ Suppress failed pattern families
fleet_manager_worker
generation_worker                 ▸ HeyGen / D-ID / Runway / Kling calls
growth_pack_worker
health_monitor_worker
hyperscale_worker
integrations_listening_worker
intelligence_report_worker
landing_page_worker
learning_worker
live_execution_{_,_phase2_}worker
monetization_worker               ▸ Revenue cycle (runs every 4 h)
monster_ops_worker
mxp_worker                        ▸ MaXimum-Pack: experiments/capacity/etc.
niche_research_worker
objection_mining_worker
offer_{discovery,lab,rotation}_worker
opportunity_cost_worker
outreach_worker
pattern_memory_worker             ▸ Winning-pattern memory
pipeline_worker
portfolio_worker                  ▸ Portfolio rebalance daily
promote_winner_worker
publishing_worker                 ▸ Buffer (wired), Publer/Ayrshare (exist)
qa_worker
quality_governor_worker
recovery_engine_worker
repurposing_worker
revenue_ceiling_worker            ▸ A/B/C + Expansion Pack 2 recomputes
revenue_leak_worker
scale_alerts_worker
strategy_adjustment_worker
trend_viral_worker
warmup_worker                     ▸ Account warmup on new platforms
```

Queues are consolidated into five worker containers. From `docker-compose.yml`:

| Container | Concurrency | Queues |
|---|---|---|
| worker-generation | 4 | generation, pipeline, cinema_studio |
| worker-publishing | 8 | publishing, buffer |
| worker-analytics | 4 | analytics, learning, portfolio, qa |
| worker-outreach | 4 | outreach |
| worker-default | 8 | default, brain, mxp, scale_alerts, notifications, monetization, repurposing, autonomous_phase_d, growth_pack, revenue_ceiling_a/b/c, expansion_pack2, creator_revenue |

The `express_publishing` queue uses RabbitMQ-style `x-max-priority: 10` for priority handling.

---

## 7. Data layer

### 7.1 SQLAlchemy models (92 files in `packages/db/models/`)

The model layer is split one file per domain slice. All files use UUID primary keys, timezone-aware `created_at/updated_at`, and JSONB for flexible fields. Highlights:

- **Core tenancy**: `accounts.py` (Organization, User), brand/creator structures.
- **Content**: `content.py`, `content_form.py`, `content_routing.py`, `publishing.py`, `media_jobs.py`, `landing_pages.py`.
- **Monetization ledger**: `revenue_ledger.py` (the canonical 34-column RevenueLedgerEntry table per REALITY_AUDIT), `offers.py`, `monetization.py`, `saas_metrics.py`.
- **Autonomy stack**: `autonomous_execution.py`, `autonomous_farm.py`, `autonomous_phase_{a,b,c,d}.py`.
- **Brain**: `brain_architecture.py`, `brain_phase_{b,c,d}.py`, `ai_personality.py`.
- **MXP**: `experiments.py`, `experiment_decisions.py`, `capacity.py`, `contribution.py`, `creative_memory.py`, `audience_state.py`, `deal_desk.py`, `market_timing.py`, `reputation.py`, `offer_lifecycle.py`, `kill_ledger.py`, `recovery.py`.
- **Revenue ceiling & expansion**: `revenue_ceiling_phase_{a,b,c}.py`, `expansion_pack2_phase_{a,b,c}.py`.
- **Intelligence**: `pattern_memory.py`, `failure_family.py`, `objection_mining.py`, `opportunity_cost.py`, `capital_allocator.py`, `causal_attribution.py`, `trend_viral.py`, `executive_intel.py`.
- **Governance & control**: `operator_permission_matrix.py`, `enterprise_security.py`, `brand_governance.py`, `quality_governor.py`, `gatekeeper.py`, `gm.py`, `alert_routing.py`, `decisions.py`, `scoring.py`.
- **Integrations**: `integration_registry.py`, `provider_registry.py`, `provider_secrets.py`, `integrations_listening.py`.
- **System instrumentation**: `system.py`, `system_events.py`, `cinema_studio.py`, `hyperscale.py`, `email_pipeline.py`.

`packages/db/models/__init__.py` is intentionally thin (no star exports) — consumers import models directly.

### 7.2 Alembic migrations (`packages/db/alembic/versions/`)

Only 8 active migrations:

```
001_consolidated_schema.py
002_cinema_studio_tables.py
003_provider_secrets.py
004_add_monetization_and_saas_models.py
005_expand_media_jobs_table.py
006_create_gm_and_alert_tables.py
007_publish_policy_rules.py
b6587e9c03b5_create_all_missing_tables_and_columns.py
```

`001` is a *consolidated* baseline — the repo was squashed once. Additionally, `packages/db/alembic/versions_backup/` exists (pre-squash history). The terminal autogen migration `b6587…` is a `create_all_missing_tables_and_columns` catch-up that suggests schema has drifted past what Alembic tracks.

In practice, boot uses `scripts/ensure_schema.py` (run by the one-shot `aro-migrate` container) rather than Alembic `upgrade head`. This is called out in `REALITY_AUDIT.md` as an intentional choice.

### 7.3 Event bus

A system-wide audit trail implemented via two tables (`SystemEvent`, `OperatorAction`) and the helper `apps/api/services/event_bus.py`. Every lifecycle transition calls `db.add(SystemEvent(...))` and, when human action is needed, `db.add(OperatorAction(...))`. These drive:

- The `control_layer_service.py` dashboard aggregate (cross-layer SQL).
- The autonomous action dispatcher (reads pending `OperatorAction`s with confidence ≥0.6).
- The Next.js activity feed.

### 7.4 Operational scripts (`scripts/`)

```
activate_live.py                  Flip org/brand to live mode
audit_migrations.py               Schema vs. model drift detector
brand_cleanup.py                  Bulk brand housekeeping
compounding_proof.py              Reality-proof: 28/28 compounding test
e2e_publish_proof.py              End-to-end publish proof
ensure_schema.py                  Primary first-boot schema sync
import_apollo_contacts.py         Cold-outreach contact import
last_mile_proof.py                Final-mile closure proof
monetization_proof.py             54/54 ledger proof
revenue_maximizer_proof.py        38/38 + 43/43 engine proofs
runtime_proof.py                  60/60 runtime proof (event bus)
seed.py / seed_packages.py /      Dev-data seeders
  seed_phase{2,3,4}.py
static_proof.py                   101/101 static code-path proof
sync_buffer_profiles.py           One-off Buffer account sync
verify_production.py              Deploy smoke test
deploy_verify.sh                  Shell verifier
brand_cleanup.py
```

The `*_proof.py` scripts implement what `REALITY_AUDIT.md` calls "runtime proofs" — each asserts a set of end-to-end invariants (e.g. "27/28 compounding wins reduce unmonetized count"). They are the project's in-house alternative to integration tests for high-level behavior.

---

## 8. Frontend (Next.js `apps/web`)

322 TS/TSX files. The App-Router tree under `src/app/` has four top-level segments:

- **`/`** — marketing root.
- **`/login`** — login.
- **`/lp/[pageId]`** — dynamic landing page renderer driven by the `landing_pages` router.
- **`/offers/{brand}/{slug}`** — static offer pages organized by brand theme.
- **`/dashboard/…`** — the operator console (≈180 distinct pages).

### Public offer pages (`/offers/`)

Three brand themes, each with up to 8 productized offers:

| Brand theme | Packages |
|---|---|
| `aesthetic-theory` | ai-ugc-starter, beauty-content-pack, creative-strategy-funnel-upgrade, full-creative-retainer, growth-content-pack, launch-sprint, performance-creative-pack, ugc-starter-pack |
| `body-theory` | creative-strategy-funnel-upgrade, full-creative-retainer, growth-content-pack, launch-sprint, performance-creative-pack, ugc-starter-pack |
| `tool-signal` | creative-strategy-funnel-upgrade, full-creative-retainer, growth-content-pack, launch-sprint, performance-creative-pack, ugc-starter-pack |

Each is a page that ties to Stripe via the same mechanism proved out in `/scripts/monetization_proof.py`.

### Dashboard surfaces (`/dashboard/`, representative)

The dashboard is intentionally wide — one page per engine/view. Rough groupings:

- **Observability**: `content`, `jobs`, `analytics`, `decisions`, `avatars`, `library`, `calendar`, `live-events`.
- **Autonomy & brain**: `autonomous-execution`, `brain-decisions`, `brain-escalations`, `brain-memory`, `brain-ops`, `meta-monitoring`, `self-corrections`, `readiness-brain`, `agent-memory`, `agent-mesh`, `agent-orchestration`.
- **MXP**: `experiments`, `experiment-decisions`, `experiment-truth`, `capacity`, `contribution`, `creative-memory`, `audience-state`, `audience-states-v2`, `deal-desk`, `market-timing`, `reputation-monitor`, `offer-lifecycle`, `kill-ledger`, `recovery`, `recovery-autonomy`.
- **Revenue ceiling**: `revenue-ceiling/{funnel-leaks,offer-ladders,owned-audience,sequences}`, `revenue-ceiling-b/{high-ticket,productization,revenue-density,upsell}`, `revenue-ceiling-c/{mix,promotion,recurring,sponsors,trust}`.
- **Expansion Pack 2**: `expansion-pack2-a/{leads,closer,offers}`, `expansion-pack2-b/{bundling,pricing,retention}`, `expansion-pack2-c/{competitive-gap,profit-guardrails,referral,sponsor-sales}`.
- **Growth / Gatekeeper / Copilot**: `growth`, `growth-commander`, `growth-command-center`, `gatekeeper` plus 10 sub-pages (`alerts`, `closure`, `commands`, `completion`, `contradictions`, `dependencies`, `expansion`, `ledger`, `tests`, `truth`), `copilot` plus 5 sub-pages.
- **Ops**: `command-center`, `cockpit`, `ai-command-center`, `workflows`, `workflow-coordination`, `permissions`, `jobs`, `webhook-ingestion`, `integrations`, `setup`, `settings`, `onboarding`.
- **Creator revenue**: `creator-revenue-hub`, `creator-revenue-events`, `creator-revenue-blockers`, `creator-revenue-truth`, `ugc-services`, `service-consulting`, `premium-access`, `merch`, `licensing`, `data-products`.
- **Buffer/distribution**: `buffer-publish`, `buffer-profiles`, `buffer-retry`, `buffer-status`, `buffer-readiness`, `buffer-blockers`, `buffer-truth`.
- **Cinema Studio**: `studio`, `studio/characters`, `studio/projects`, `studio/scenes`, `studio/styles`, `studio/generations`.
- **Email/SMS/CRM**: `email-sms-execution`, `messaging-blockers`, `crm-sync`, `sequence-triggers`, `comment-cash`.
- **Landing pages / campaigns**: `landing-pages`, `campaigns`, `ad-reporting`, `paid-operator`, `syndication`.
- **Portfolio / scale**: `portfolio`, `scale`, `scale-alerts`, `max-output`, `hyperscale`.
- **Misc**: `signal-scanner`, `trend-scanner`, `trend-viral`, `capital`, `capital-allocation`, `objection-mining`, `opportunity-cost`, `opportunity-states`, `pattern-memory`, `failure-families`, `override-policies`, `execution-policies`, `policy-evaluations`, `platform-warmup-policies`, `quality-governor`, `qa`, `enterprise-security`, `brand-governance`, `affiliate-intel`, `affiliate-governance`, `owned-affiliate-program`, `payment-connectors`, `analytics-sync`, `analytics-truth`, `revenue`, `revenue-pressure`, `revenue-machine`, `revenue-intel`, `revenue-intelligence`, `revenue-avenues`, `revenue-leaks`, `monetization`, `monetization-router`, `sponsors`, `sponsor-autonomy`, `retention-autonomy`, `distribution-plans`, `knowledge-graph`, `shared-context`, `roadmap`.

Per `REALITY_AUDIT.md` the majority of these pages are read-only reporting surfaces; only three (`dashboard`, `content`, `orchestration`) had operational action buttons at audit time.

---

## 9. Domain model — what the platform actually *does*

Synthesizing from `docs/02…85` + `REALITY_AUDIT.md` + router/service/model names:

### 9.1 The revenue-maximization loop

1. **Discover** signals/trends/niches → `discovery_service.py`, `niche_research_worker`.
   *Currently "manual seed only" per REALITY_AUDIT; trend APIs not wired.*
2. **Ideate** content forms and formats → `content_form_service.py`, `content_ideation_worker`.
3. **Route** to the best provider tier (hero / standard / bulk) → `content_routing_service.py`, `integration_manager.py` (new, per `NEXT_SESSION_SPEC.md`).
4. **Generate** script + media + avatar + voice → `content_generation_service.py`, `generation_worker`, `cinema_studio_worker` for long-form.
5. **QA** via `quality_governor_service.py` and `content_pipeline_service.run_qa()` (QA inputs currently hardcoded — flagged in audit).
6. **Approve** via human-in-the-loop `approval` page / `OperatorAction` rows.
7. **Publish** via `publishing_worker` using Buffer (wired) or Publer/Ayrshare (clients exist, not used).
8. **Ingest analytics** via `analytics_ingestion_worker` (YouTube/TikTok/Instagram analytics — stub; models exist, clients don't).
9. **Attribute revenue** via `attribution_builder.py` + `causal_attribution_service.py`.
10. **Write to ledger** via `monetization_bridge.py` — Stripe webhooks, Shopify webhooks, affiliate commissions, sponsor payments, service payments, product sales, and refunds all route here; duplicate detection via unique `webhook_ref` column.
11. **Compute** all 17 revenue engines over the ledger.
12. **Act** — the autonomous action dispatcher executes state changes: `attach_offer_to_content`, `suppress_losing_offer`, `promote_winning_offer`, `deprioritize_low_margin`, `reduce_dead_channel`, `repair_broken_attribution`, `recover_failed_webhook`.

### 9.2 The 17 revenue engines (E1–E17)

| # | Engine | File |
|---|---|---|
| E1 | Creator fit scoring (10 paths per account) | `revenue_maximizer.py` |
| E2 | Opportunity detection | `revenue_maximizer.py` |
| E3 | Revenue allocation | `revenue_maximizer.py` |
| E4 | Suppression targets | `revenue_maximizer.py` |
| E5 | Revenue memory (what worked) | `revenue_maximizer.py` |
| E6 | Monetization mix (current vs optimal) | `revenue_maximizer.py` |
| E7 | Next-best actions (top 10 by value) | `revenue_maximizer.py` |
| E8 | What-if simulation | `revenue_engines_extended.py` |
| E9 | Margin rankings | `revenue_engines_extended.py` |
| E10 | Creator archetypes (11 types) | `revenue_engines_extended.py` |
| E11 | Offer packaging (entry / core / upsell) | `revenue_engines_extended.py` |
| E12 | Experiment opportunities | `revenue_engines_extended.py` |
| E13 | Payout speed (days-to-cash) | `revenue_engines_extended.py` |
| E14 | Leak detection | `revenue_engines_extended.py` |
| E15 | Portfolio allocation (hero/growth/maintain/pause) | `revenue_engines_extended.py` |
| E16 | Cross-platform compounding | `revenue_engines_extended.py` |
| E17 | Durability scoring (short-term vs lasting) | `revenue_engines_extended.py` |

### 9.3 Autonomy layers

Two parallel but coordinated autonomy stacks:

1. **Autonomous Phases A→D** (content-side): signal scan / warmup → policies / distribution / suppression → funnel / paid / sponsor / retention / recovery → agents / pressure / overrides / blockers / escalations. Each phase has a router, service, worker, and model file, and a set of dashboard pages.
2. **Brain Phases A→D** (cognition-side): memory + state → decisions + policies + confidence + arbitration → agent mesh / workflows / context bus → meta-monitoring / self-correction / escalation. Audit classifies Brain A–B as fully real (computation) but Brain C–D as "not auditable" at the time of the 2026-04-04 audit.

### 9.4 Bridges

Four "bridge" services coordinate cross-layer state (`apps/api/services/*_bridge.py`):

- **`event_bus.py`** — SystemEvent + OperatorAction emission.
- **`governance_bridge.py`** — permission check + AuditLog + MemoryEntry (but audit notes: the check returns a dict and does *not* enforce; callers must respect voluntarily).
- **`intelligence_bridge.py`** — converts `BrainDecision`, `PatternDecayReport`, `PWExperimentWinner`, `FailureFamilyReport` into `OperatorAction` rows.
- **`monetization_bridge.py`** — ledger writers + revenue-state readers.
- **`orchestration_bridge.py`** — job/worker/provider visibility, auto-creates OperatorActions for stuck jobs.

### 9.5 MXP ("Maximum-Pack") modules

Per docs 33–43, this is the experiment/measurement/capacity layer: `mxp_experiment_decisions`, `mxp_contribution`, `mxp_capacity`, `mxp_offer_lifecycle`, `mxp_creative_memory`, `mxp_recovery`, `mxp_deal_desk`, `mxp_audience_state`, `mxp_reputation`, `mxp_market_timing`, `mxp_kill_ledger`. Each is a router + service + model trio, backed by a single MXP worker.

### 9.6 GM ("General Manager") — the strategic brain

`gm_ai.router` and `gm_chat.router` expose the "strategic operating brain" as both a programmatic API and a conversational chat. `services/gm_ai.py`, `services/gm_startup.py`, `services/gm_system_prompt.py` configure an Anthropic-backed agent that reads across the whole ledger + engines + brain decisions and answers operator questions or prescribes plays. This is the thing the older `NEW/` folder's allow-list was talking to via `/api/v1/gm/write/*` endpoints (those endpoints are under `gm_ai.router`).

### 9.7 Integration Manager (new subsystem, per `NEXT_SESSION_SPEC.md`)

A unified provider catalog + credential broker:

- Models: `IntegrationProvider` (26 cols, encrypted credentials, health tracking, tier routing), `CreatorPlatformAccount` (22 cols).
- Service: `integration_manager.seed_provider_catalog()`, `set_credential()` (encrypts), `get_credential()` (decrypts), `list_providers()` (masks), `get_provider_for_task(category, quality_tier)` (tier-aware with fallback).
- 24 pre-seeded providers across categories **LLM** (claude/gemini/deepseek/groq), **Image** (openai/imagen4/flux), **Video** (kling/runway), **Avatar** (heygen/did), **Voice** (elevenlabs/fish_audio/voxtral), **Publishing** (buffer/publer/ayrshare), **Analytics** (youtube/tiktok/instagram analytics), **Trends** (serpapi), **Email** (smtp), **Inbox** (imap), **Payment** (stripe).
- Router: `integrations_dashboard.py` — `POST /integrations/seed`, `GET /integrations/providers`, `POST /integrations/providers/{key}/credential`, `GET /integrations/route`, `POST /integrations/providers/{key}/{enable|disable}`.
- Spec notes that content/publishing pipelines still need to be rewired to use this instead of reading env vars directly — work-in-progress.

---

## 10. Celery Beat schedule (187 entries, 993-line file)

Notable periodic tasks sampled from `workers/celery_app.py`:

| Every | Task | Purpose |
|---|---|---|
| 30 min | `analytics_worker.tasks.ingest_performance` | Pull platform analytics |
| 1 h | `analytics_worker.tasks.scan_trends` | Trend intake |
| 4 h | `scale_alerts_worker.tasks.recompute_all_alerts` | Scale-alert recomputes |
| 4 h | (implied) `monetization_worker.tasks.run_revenue_cycle` | Full revenue cycle — per docs |
| 6 h | `analytics_worker.tasks.check_saturation` | Saturation detection |
| daily 06:00 | `portfolio_worker.tasks.rebalance_portfolios` | Portfolio rebalance |
| … | 180+ others | Per-engine recomputes (offer ladders, owned audience, message sequences, funnel leaks, high-ticket, productization, revenue density, upsells, recurring, sponsor inventory, trust conversion, monetization mix, paid promotion candidates, lead qualification, owned offer recommendations, pricing, bundle, retention, reactivation, referral program, competitive gap, sponsor targets, sponsor outreach, profit guardrails, etc.) |

Celery queue-routing rules also hard-code many task paths so that the monolithic `revenue_ceiling_worker.tasks.*` functions are dispatched into the correct `revenue_ceiling_a/b/c` or `expansion_pack2` queue.

A 14 MB `celerybeat-schedule` shelve file at the repo root confirms Beat has been running from the host at some point (this file is not in `.gitignore` but should be — it's ephemeral state).

---

## 11. Testing (`tests/`, 170 files)

- **Unit tests** (`tests/unit/`) — cover services/models/pure logic.
- **Integration tests** (`tests/integration/`) — run inside the `aro-api` container against the `avatar_revenue_os_test` Postgres database (created on demand via `make create-test-db`). `pytest-asyncio` in `asyncio_mode = "auto"`.
- **E2E** (`tests/e2e/`) — end-to-end flows.
- Config in `pyproject.toml`: `testpaths = ["tests"]`, deprecation warnings silenced.
- The `scripts/*_proof.py` family acts as an outside-in reality suite (runtime proofs cited in `REALITY_AUDIT.md`).

---

## 12. Configuration surface (`.env.example`, 150+ variables)

Grouped by concern:

- **Identity**: `COMPOSE_PROJECT_NAME`, `DOMAIN`.
- **Postgres**: `POSTGRES_USER/PASSWORD/DB/HOST/PORT`, `DATABASE_URL` (async), `DATABASE_URL_SYNC` (sync for Alembic).
- **Redis**: `REDIS_URL`, `CELERY_BROKER_URL` (db 1), `CELERY_RESULT_BACKEND` (db 2).
- **API**: `API_HOST/PORT/SECRET_KEY/CORS_ORIGINS/ENV`, `LOG_LEVEL`.
- **Web**: `NEXT_PUBLIC_API_URL`, `FRONTEND_URL`, `WEBHOOK_BASE_URL`.
- **S3**: `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION` (falls back to local disk at `/media` if unset).
- **AI providers** (each category with tiered hero/standard/bulk):
  - Text: ANTHROPIC / GOOGLE_AI / DEEPSEEK / OPENAI / GROQ / XAI / MISTRAL
  - Image: FAL / REPLICATE / STABILITY
  - Video: RUNWAY / KLING / HIGGSFIELD
  - Avatar: HEYGEN / DID / TAVUS / SYNTHESIA
  - Voice: ELEVENLABS / FISH_AUDIO
  - Music: SUNO / MUBERT
- **Publishing**: BUFFER / PUBLER / AYRSHARE (+ platform OAuth for YouTube, TikTok, Instagram, X).
- **Analytics trends**: SERPAPI.
- **Payments & commerce**: STRIPE (6 price IDs), SHOPIFY (domain + access token + webhook secret), CLICKBANK.
- **Affiliate networks**: IMPACT, SHAREASALE, …
- **Sentry**: `SENTRY_DSN`.

The docker-compose `api` service uses `env_file: .env` plus explicit `environment:` overrides for the Docker-internal hostnames so that stray shell env vars don't null out real values (comment in compose file explicitly calls this out).

---

## 13. Deployment (`deploy.sh`)

Six-step production deploy with rollback tagging:

1. Verify `.env` exists and contains no `changeme` defaults for `API_SECRET_KEY` or `POSTGRES_PASSWORD` (hard fail if either).
2. Tag current Docker images with `:rollback` so a fast revert is possible.
3. Build images using `docker-compose.yml` + `docker-compose.prod.yml`.
4. Start postgres + redis, wait up to 60 s for `pg_isready`, then run `scripts/ensure_schema.py` in a one-shot `--rm --no-deps api` container.
5. Rolling restart: `docker compose up -d api web worker scheduler caddy`.
6. Health verification: up to 15 × 3 s retries against `http://localhost:8001/healthz`; warns (does not fail) on timeout.

Prints `docker compose ps` and the two public URLs (`app.nvironments.com`, `api.nvironments.com`) at the end.

---

## 14. `REALITY_AUDIT.md` — what's real vs. surface-only

The repo ships an internal 28 KB audit (dated 2026-04-04, commit `6540a3e`) with per-feature classifications: **Fully real**, **Partially real**, **Surface-only**, **Not real**. The honest picture:

### Fully real (runtime-verified)

- Event bus + OperatorAction pattern (60/60 proof)
- Control layer dashboard (cross-layer SQL aggregation)
- Canonical `RevenueLedgerEntry` table with 34 columns; affiliate, sponsor, service, product, refund writers; idempotent via `webhook_ref`
- All 17 revenue engines (E1–E17) as read-only computations (38/38 + 28/28 proof) — note caveats on E10/E13/E17 using some hardcoded weights/estimates
- Execution engine + autonomous action dispatcher with confidence gating ≥0.6; state-changing actions compounding-proven (28/28)
- AI content generation (when creds configured) — Claude/Gemini/DeepSeek tiered routing + template fallback
- Media generation (when creds) — HeyGen/D-ID/Runway/Kling
- Publishing via Buffer (real HTTP POSTs)
- Email via aiosmtplib, SMS via Twilio (when creds)
- Webhook signature verification (Stripe HMAC-SHA256, Shopify SHA256, 300s tolerance)
- Auth (JWT HS256, bcrypt, 24 h expiry)
- Onboarding, Brain Phase A + B (computational)

### Partially real / surface-only / not real

- **QA scoring uses hardcoded inputs** — `run_qa()` passes `originality_score=0.7, compliance_score=0.85` etc. No actual content analysis. **High** severity.
- **No performance data collection** — `PerformanceMetric` model exists; no platform-analytics API clients. **High** severity.
- **Discovery is manual-only** — no Google Trends, YouTube Research, or social-trend API integration. **Medium**.
- **Brain decisions don't auto-execute** — `BrainDecision` rows created but no worker dispatches based on them. **Medium**.
- **Provider audit is credential-check only** — checks env var presence, not connectivity. **Low** (recommended rename: "credential registry").
- **Autonomous execution loop doesn't orchestrate** — the revenue execution engine + action dispatcher partially replaces it; remaining phases un-wired. **Medium**.
- **CRM sync not implemented** — `CrmContact` / `CrmSync` models but no API clients. **Low** (hide page until real).
- **Publer / Ayrshare clients exist but unused** in `publishing_worker` (Buffer only). **Low**.
- **Scheduled revenue cycle not runtime-proven** — Celery Beat entry exists; task is importable; never observed firing in a running system. **Low**.
- **Brain Phase C–D not auditable** — referenced by workers but implementation not in scope at audit time.
- **~204 of 207 frontend pages are read-only** — only `dashboard`, `content-pipeline`, `orchestration` have operational action buttons.

This audit is the authoritative map of where claims meet reality. Work after commit `6540a3e` may have closed some of these (`NEXT_SESSION_SPEC.md` documents the Integration-Manager subsystem that directly addresses the "provider audit is cred-check only" gap).

---

## 15. Top-of-file notes the repo keeps for itself

- `REALITY_AUDIT.md` — the honesty audit above.
- `NEXT_SESSION_SPEC.md` — 6 KB of forward-looking work the operator wants done next (integration manager wiring, creator-accounts UI, provider health testing, credential encryption upgrade, etc.).
- `docs/` — 107 numbered markdown documents describing every engine, phase, and module from Phase 1 (`docs/01-setup.md`) to Phase 8 + all the expansion packs (`docs/85-trend-viral-engine.md`). `docs/02-architecture.md` is the authoritative architecture diagram source.

---

## 16. State as of 2026-04-22

- Primary branch: `main` (many active `claude/<codename>` feature branches).
- Origin: `github.com/patstu1/avatar-revenue-os`.
- `.pre-commit-config.yaml` + `ruff` + `mypy` enforced.
- `.github/` directory present (CI/CD config).
- Stale artifacts at root: `celerybeat-schedule` (14 MB Beat shelve), `.pytest_cache/`, `.backups/` — candidates for `.gitignore`.
- `apps/web/node_modules` and `apps/web/.next` present locally; both are `0` bytes via `du` (stale symlinks? build artifacts cleared?).
- Production: single Hetzner VPS at `root@5.78.187.31`, repo checked out at `/opt/avatar-revenue-os`, served at `https://app.nvironments.com`.

---

## 17. What this system is, in one line

**A self-hosted, single-tenant-per-org, vertically integrated autonomous content-monetization operating system**: content ingest → AI generation → tiered provider routing → QA → publishing → analytics → canonical revenue ledger → 17 computing engines → autonomous dispatcher → human approval surface across ~180 dashboard pages — all on one Hetzner box running a 10-service Docker Compose stack behind Caddy, scheduled by Celery Beat with 187 recurring tasks, and governed by an explicit internal honesty audit that flags what is real versus what is still a stub.

---

*End of analysis.*

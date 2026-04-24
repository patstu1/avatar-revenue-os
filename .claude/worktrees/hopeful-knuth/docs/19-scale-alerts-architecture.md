# Scale Alerts & Launch Candidate Upgrade

This document describes the Scale Alerts engine, launch candidate generation, launch readiness scoring, scale blocker diagnostics, notification delivery model, AI Scale Command Center workflow, tuning thresholds, and how live channels relate to adapter-ready stubs.

## Architecture

- **Engine (`packages/scoring/scale_alerts_engine.py`)** — Pure functions: `generate_scale_alerts`, `generate_launch_candidates`, `diagnose_scale_blockers`, `compute_launch_readiness`, plus `dedupe_alerts_by_type` for recompute idempotency.
- **Service (`apps/api/services/scale_alerts_service.py`)** — Async SQLAlchemy persistence, org-scoped acknowledge/resolve, filtered list queries, linking expansion-class alerts to the top `LaunchCandidate` by urgency after insert.
- **API** — Under `/api/v1/brands/...` for brand-scoped resources; **alternate** acknowledge/resolve paths at `/api/v1/alerts/{id}/...` for clients that prefer root-level routes.
- **Workers (`workers/scale_alerts_worker/tasks.py`)** — Celery tasks call the same service via `asyncio.run` + `async_session_factory` per brand. Notification worker processes `notification_deliveries` rows with adapters and retry semantics.

### Tables

| Table | Role |
| --- | --- |
| `operator_alerts` | Typed alerts with metrics, optional links to scale recommendation and launch candidate |
| `launch_candidates` | Typed expansion candidates with economics and blockers |
| `scale_blocker_reports` | Diagnostic blockers with severity and thresholds |
| `launch_readiness_reports` | Composite score, gating factors, component breakdown |
| `notification_deliveries` | Per-channel delivery attempts (in-app, email, Slack, SMS) |

## Launch candidate generation

- **Primary mapping** — `REC_KEY_TO_CANDIDATE` maps `scale.py` recommendation keys to candidate types (e.g. `scale_current_winners_harder` → `flagship_expansion`).
- **Suppression** — If `cannibalization_risk >= 0.75`, **no** candidates are emitted (high cannibalization suppresses launch candidates).
- **Extras** — Optional `platform_specialist_account` when the portfolio is single-platform and readiness is favorable; `feeder_account` when the recommendation is `monitor` but readiness is healthy; `high_ticket_conversion_account` when incremental profit is very high and risk is moderate.

## Launch readiness scoring

- Combines **ScaleReadinessScore**, **ExpansionConfidence**, audience separation, saturation/opportunity blend, monetization depth (offer count proxy), funnel conversion, trust, posting capacity, and cannibalization inverse.
- **Actions**: `launch_now`, `prepare_but_wait`, `monitor`, `do_not_launch_yet` (gating factors such as low trust, high cannibalization, near-zero funnel CVR force `do_not_launch_yet`).

## Blocker diagnostics

- Portfolio and per-account signals produce blocker rows: readiness, CTR/CVR, fatigue, saturation, originality, trust, cannibalization, audience separation, leaks, offer depth, monetization depth, posting capacity, repeatability, expansion confidence, retention pressure.
- Duplicate `blocker_type` entries are merged keeping the higher severity.

## Notification delivery model

- Each alert creates an **in_app** delivery (marked delivered immediately) and, for **urgency ≥ 55**, pending **email** and **slack** rows (SMS uses the same adapter pattern when wired).
- **Adapters** (`packages/notifications/adapters.py`): `EmailAdapter`, `SlackWebhookAdapter`, `SMSAdapter` — return failure with a clear message when credentials are missing; suitable for production extension.
- **Worker** — Increments `attempts`, calls the right adapter, sets `delivered_at` on success, keeps `pending` for retry until `MAX_DELIVERY_ATTEMPTS`, then `failed` with `last_error`.

### Live channels vs adapter-ready

- **In-app**: Always recorded as delivered in the API path for immediate UI feed consistency.
- **Email / Slack / SMS**: Persisted as `pending`; without `SMTP_*`, `SLACK_WEBHOOK_URL`, or `SMS_API_KEY`, adapters fail and retries exhaust — **not blocked by missing credentials for development**, but **live delivery requires env configuration**.

## AI Scale Command Center alert workflow

1. Operator selects a brand and runs **Recompute alerts & launch intel** (`POST /api/v1/brands/{id}/scale-intel/recompute-all`), which orders: launch candidates → alerts (links) → blockers → readiness.
2. Alerts appear in the **Scale alerts feed** with severity, urgency, time-to-signal, and cost/upside hints.
3. **Acknowledge** / **Resolve** mutate state and write audit log entries (`alert.acknowledged`, `alert.resolved`).

## Thresholds and tuning

| Knob | Default behavior |
| --- | --- |
| Cannibalization warning alert | Risk > 0.5 |
| Cannibalization candidate suppression | Risk ≥ 0.75 |
| Niche shift alert | Average saturation > 0.72 |
| Outbound email/Slack queue | Alert urgency ≥ 55 |
| Weak portfolio CTR blocker | Average CTR < 0.015 |
| Posting capacity blocker | Total capacity < 3/day |

Adjust constants in `scale_alerts_engine.py` and `_outbound_channels_for_alert` in the service as needed.

## Celery Beat (recurring jobs)

Configured in `workers/celery_app.py` on the `scale_alerts` queue:

| Schedule | Task |
| --- | --- |
| Every 4h :30 | `recompute_all_alerts` |
| Every 4h :40 | `recompute_all_launch_candidates` |
| Every 4h :50 | `recompute_all_blockers` |
| Every 4h :55 | `recompute_all_readiness` |
| Every 15m | `process_notification_deliveries` |

Staggered minutes reduce concurrent DB load across tasks.

## API access control

- **Acknowledge / resolve / get launch candidate by id**: If the alert or candidate does not exist → **404**. If it belongs to another organization → **403** (does not leak existence across tenants).
- **Brand-scoped GETs**: Brand must belong to the caller’s organization (existing `_require_brand` checks).
- **FastAPI dependencies**: `RequireRole` uses `current_user: User = Depends(get_current_user)` internally (not the `CurrentUser` alias) so nested `Annotated` types resolve correctly under FastAPI 0.115+.

## Referential integrity

- `operator_alerts.linked_launch_candidate_id` references `launch_candidates.id` with `ON DELETE SET NULL` (Alembic revision `o6c7d8e9f0a1`).

## Integration tests

Run against a live Postgres (set `TEST_DATABASE_URL` for `asyncpg`, e.g. Docker Compose service or localhost). Tests in `tests/integration/test_scale_alerts_flow.py` cover recompute, list, acknowledge, resolve, filters, and bundle recompute.

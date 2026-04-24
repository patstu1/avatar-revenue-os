# Recovery incident and action model (MXP Phase C)

## Purpose

The Autonomous Recovery Engine turns operational telemetry into **open incidents** and **prescribed actions** with severity, escalation state, and expected mitigation effects—without hiding behind opaque “AI” scoring.

## Tables

### `recovery_incidents`

| Column | Role |
|--------|------|
| `incident_type` | Failure family (e.g. `publishing_failure_spike`, `conversion_decline`, `email_deliverability_issue`). |
| `severity` | `critical` \| `high` \| `medium` \| `low` from threshold rules in `recovery_engine`. |
| `escalation_state` | `escalated`, `pending_operator`, `monitoring`, or `open` derived from severity. |
| `recommended_recovery_action` | Primary action type from the first ranked recommendation (e.g. `replace_offer`). |
| `automatic_action_taken` | Nullable. Reserved for when a real automated executor records a completed action (default pipeline keeps this null). |
| `explanation_json` | `{ "explanation", "confidence", "failure_type" }` plus any service context. |
| `detected_at` | When the incident row was materialized during recompute. |

### `recovery_actions`

Each incident may fan out to multiple rows (reroute, notify operator, etc.).

| Column | Role |
|--------|------|
| `action_type` | One of `ACTION_TYPES` in `recovery_engine` (e.g. `force_guarded_review`, `reduce_paid_spend`). |
| `action_mode` | `automatic`, `manual`, or `escalate` from severity (automatic modes are **not** executed without an executor integration). |
| `expected_effect_json` | Structured effect estimate (hours to recover, savings %, etc.). |
| `executed` | Boolean; `false` until an external actor confirms execution. |

## Engine rules

- **Detection**: `detect_recovery_incidents(system_state, thresholds)` — pure function in `packages/scoring/recovery_engine.py`.
- **Actions**: `recommend_recovery_actions(incidents, available_actions)` maps incident type → ordered actions.
- **Service**: `recompute_recovery_incidents` in `apps/api/services/recovery_service.py` builds `system_state` from SQL aggregates (jobs, metrics, LTV, sponsors, costs, optional `email_bounce_rate` in `performance_metrics.raw_data`), replaces prior rows for the brand, and logs audit events from the API router.

## API

- `GET /api/v1/brands/{brand_id}/recovery-incidents` — incidents with nested `actions` (read-only).
- `POST /api/v1/brands/{brand_id}/recovery-incidents/recompute` — operator-only recompute (audit-logged).

## Worker

`workers.mxp_worker.tasks.recompute_all_recovery_incidents` on the `mxp` queue; beat schedule in `workers/celery_app.py` (every 4 hours).

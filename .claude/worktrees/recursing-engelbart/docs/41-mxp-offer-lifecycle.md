# MXP: Offer Lifecycle

## Purpose

The Offer Lifecycle module tracks each monetization offer through its lifecycle (launch → active → declining → sunset) and recommends actions (promote, optimize, replace, kill) based on health signals.

## Table

**`offer_lifecycle_reports`**

| Column | Type | Description |
|--------|------|-------------|
| brand_id | UUID FK | Parent brand |
| offer_id | UUID FK | Linked offer |
| lifecycle_state | String | launch, active, declining, sunset |
| health_score | Float | 0–1 composite health |
| dependency_risk_score | Float | Revenue concentration risk |
| decay_score | Float | Performance decay rate |
| recommended_next_action | String | monitor, optimize, replace, kill |
| confidence_score | Float | 0–1 |
| explanation_json | JSONB | State reasoning |

## Engine Logic (`packages/scoring/mxp/offer_lifecycle.py`)

- Evaluates each active offer's conversion rate, EPC, and revenue trends.
- Computes a composite health score from CVR trend, EPC stability, and dependency concentration.
- Assigns lifecycle state based on health thresholds.
- Recommends next action: monitor (healthy), optimize (slight decline), replace (significant decline), kill (terminal).

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brands/{id}/offer-lifecycle-reports` | List lifecycle reports |
| GET | `/api/v1/brands/{id}/offer-lifecycle-summary` | Aggregated summary |
| POST | `/api/v1/brands/{id}/offer-lifecycle-reports/recompute` | Recompute lifecycle |

## Worker

`workers/learning_worker/tasks.py` — `recompute_offer_lifecycle` runs on a 6-hour schedule via Celery beat.

## Dashboard

`/dashboard/offer-lifecycle/` — displays per-offer lifecycle state, health, and recommended actions.

## Execution vs Recommendation Boundary

- **Recommends only**: lifecycle recommendations feed into the kill ledger and monetization router but do not directly deactivate offers.

## Data Provenance

Derived from persisted offer conversion and revenue data. Scores are **proxy** when only seed or limited data is available.

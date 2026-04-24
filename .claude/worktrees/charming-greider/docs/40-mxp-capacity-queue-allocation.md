# MXP: Capacity & Queue Allocation

## Purpose

The Capacity module determines how much content the brand can sustainably produce, identifies bottlenecks, and allocates queue capacity across accounts and platforms to prevent overproduction, fatigue, and quality degradation.

## Tables

**`capacity_reports`**

| Column | Type | Description |
|--------|------|-------------|
| brand_id | UUID FK | Parent brand |
| capacity_type | String | content_generation, publishing, monetization |
| current_capacity | Float | Current throughput capacity |
| used_capacity | Float | Currently consumed capacity |
| recommended_volume | Float | Optimal volume recommendation |
| recommended_throttle | Float | 0–1 throttle factor |
| expected_profit_impact | Float | Estimated $ impact of throttle |
| confidence_score | Float | 0–1 |
| explanation_json | JSONB | Bottleneck details |

**`queue_allocation_decisions`**

| Column | Type | Description |
|--------|------|-------------|
| brand_id | UUID FK | Parent brand |
| queue_name | String | generation, publishing, monetization |
| priority_score | Float | Queue priority ranking |
| allocated_capacity | Float | Units allocated |
| deferred_capacity | Float | Units deferred |
| reason_json | JSONB | Allocation rationale |

## Engine Logic (`packages/scoring/mxp/capacity.py`)

- Calculates total production capacity from account posting limits and provider availability.
- Compares used vs available capacity to determine throttle recommendations.
- Allocates queue slots by priority: flagship accounts first, experimental accounts second.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brands/{id}/capacity-reports` | List capacity reports |
| GET | `/api/v1/brands/{id}/queue-allocations` | List queue allocations |
| POST | `/api/v1/brands/{id}/capacity-reports/recompute` | Recompute capacity |

## Worker

`workers/learning_worker/tasks.py` — `recompute_capacity` runs on a 4-hour schedule via Celery beat.

## Dashboard

`/dashboard/capacity/` — displays capacity reports and queue allocation decisions.

## Execution vs Recommendation Boundary

- **Recommends only**: capacity throttle recommendations inform the content runner and suppression engine but do not directly pause publishing.

## Data Provenance

Derived from persisted account and provider data. Capacity numbers are **live** when accounts are connected; otherwise **proxy/synthetic**.

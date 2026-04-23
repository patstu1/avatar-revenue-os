# MXP: Contribution & Attribution

## Purpose

The Contribution module measures the estimated value each content piece, account, platform, and monetization path contributes to overall brand revenue. It uses proxy attribution models (first-touch, last-touch, linear) to assign revenue credit when full multi-touch tracking is not yet available.

## Table

**`contribution_reports`**

| Column | Type | Description |
|--------|------|-------------|
| brand_id | UUID FK | Parent brand |
| attribution_model | String | first_touch, last_touch, linear |
| scope_type | String | content, account, platform, offer |
| estimated_contribution_value | Float | Estimated $ contribution |
| contribution_score | Float | 0–1 normalized score |
| confidence_score | Float | 0–1 |
| explanation_json | JSONB | Model rationale and window |

## Engine Logic (`packages/scoring/mxp/contribution.py`)

- Retrieves all active accounts and published content for the brand.
- Applies selected attribution model to assign revenue credit proportionally.
- Scores contribution relative to total revenue to produce a normalized 0–1 `contribution_score`.
- Confidence degrades when data is sparse or synthetic.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brands/{id}/contribution-reports` | List contribution reports |
| POST | `/api/v1/brands/{id}/contribution-reports/recompute` | Recompute attribution |

## Worker

`workers/learning_worker/tasks.py` — `recompute_contribution` runs on a 6-hour schedule via Celery beat.

## Dashboard

`/dashboard/contribution/` — displays contribution reports with attribution model, scope, value, and confidence.

## Execution vs Recommendation Boundary

- **Recommends only**: contribution scores inform downstream modules (capacity, offer lifecycle, audience state) but do not execute any action on their own.
- Data is **proxy-based** until real multi-touch tracking is connected.

## Data Provenance

All outputs are currently **synthetic/proxy** — derived from available engagement and revenue metrics without external analytics integration.

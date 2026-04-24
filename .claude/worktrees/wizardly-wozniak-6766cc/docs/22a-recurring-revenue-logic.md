# Recurring Revenue Engine — Phase C

## Overview

Scores each brand's potential for subscription-style income and projects monthly and annual recurring value against audience size, engagement, and niche affinity. One row per brand is written to `recurring_revenue_models`. Recompute replaces the existing row.

## API

| Method | Path | Role |
|---|---|---|
| `GET` | `/api/v1/brands/{brand_id}/recurring-revenue` | Any authenticated user |
| `POST` | `/api/v1/brands/{brand_id}/recurring-revenue/recompute` | OPERATOR |

## Inputs

- **`niche`** — brand niche string (e.g. `tech`, `finance`, `health`, `saas`, `fitness`).
- **Active offers** — each offer's `monetization_method`, `payout_amount`, and any existing recurring product flags.
- **`audience_size`** — aggregated follower count summed across all `creator_accounts` linked to the brand (minimum 1).
- **`avg_content_engagement_rate`** — mean engagement rate across recent content items; falls back to `0.03` if no content exists.
- **`existing_recurring_products`** — boolean list of already-active recurring offer types used to avoid recommending duplicates.

## Outputs

| Field | Type | Description |
|---|---|---|
| `recurring_potential_score` | float 0–1 | Blend of audience signal, engagement rate, and niche affinity. |
| `best_recurring_offer_type` | enum | One of: `newsletter`, `membership`, `saas_tool`, `coaching_retainer`, `community`. |
| `audience_fit` | float 0–1 | How well the absolute audience size supports a recurring model (log-scaled). |
| `churn_risk_proxy` | float 0–1 | Inverse engagement proxy; high engagement → low churn. |
| `expected_monthly_value` | float | `potential_score × audience_size × 0.002 × avg_payout`. |
| `expected_annual_value` | float | `monthly × 12 × (1 − churn_risk × 0.5)`. |
| `confidence` | float 0–1 | Overall model confidence; penalised when audience_size < 500 or no content. |

## Logic

- **Niche affinity boost**: brands in `tech`, `finance`, `health`, or `saas` receive a flat `+0.1` added to `recurring_potential_score` before clamping to `[0.0, 1.0]`.
- **`churn_risk_proxy`**: computed as `1 − min(1, engagement_rate × 10)`, then clamped to `[0.1, 0.9]`.
- **`best_recurring_offer_type`** selection: `saas_tool` preferred for `tech`/`saas` niches; `coaching_retainer` preferred for `health`/`fitness`; `membership` for `finance`; `newsletter` as the universal fallback. Already-active types are excluded from consideration before selection.
- **`audience_fit`**: `log10(audience_size) / 6.0`, clamped `[0.0, 1.0]`.
- **`expected_monthly_value`** uses `avg_payout` from the highest-payout active offer; falls back to `50.0` when no offers exist.

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_recurring_revenue` | Every 8 h (minute :05) | `revenue_ceiling` |

## Scoring Engine

Pure function: `score_recurring_revenue()` in `packages/scoring/revenue_ceiling_phase_c_engines.py`.

## Persistence

- Table: `recurring_revenue_models`
- Unique constraint: one row per brand (`uq_recurring_revenue_brand`)
- Recompute deletes existing row before inserting new one

# Organic-to-Paid Promotion Gate — Phase C

## Overview

Applies a strict four-condition gate to each content item and certifies only organic winners as safe to amplify with paid spend. One row per content item is written to `paid_promotion_candidates`. The refresh operation deletes and rebuilds all rows for the brand.

## API

| Method | Path | Role |
|---|---|---|
| `GET` | `/api/v1/brands/{brand_id}/paid-promotion-candidates` | Any authenticated user |
| `POST` | `/api/v1/brands/{brand_id}/paid-promotion-candidates/recompute` | OPERATOR |

## Inputs (per content item)

- **`content_item_id`**, **`title`** — item identity.
- **`organic_impressions`** — total organic impression count.
- **`organic_engagement_rate`** — organic engagement rate (clicks + likes + shares / impressions).
- **`organic_revenue`** — attributed organic revenue; `0` if none recorded.
- **`organic_roi`** — `organic_revenue / max(cost, 1)` where cost is sourced from `performance_metrics.total_cost`; `0.0` when no cost or revenue data exists.
- **`content_age_days`** — days since `published_at`; computed at evaluation time.

## Outputs

| Field | Type | Description |
|---|---|---|
| `organic_winner_evidence` | JSON object | All four signal values with `pass: bool` per signal. |
| `is_eligible` | bool | `true` only when **all** four gate conditions pass. |
| `gate_reason` | string | Brief plain-English explanation of the gate result. |
| `confidence` | float 0–1 | Penalised when `organic_revenue == 0` or cost data is absent. |

## Gate Logic

All four conditions must pass simultaneously for `is_eligible = true`:

1. **`organic_impressions >= 5,000`** — minimum organic reach threshold.
2. **`organic_engagement_rate >= 0.04`** (4 %) — minimum engagement quality.
3. **`organic_revenue > 0`** — content must have generated at least one dollar of attributable organic revenue.
4. **`organic_roi >= 1.5` OR `content_age_days >= 14`** — the ROI condition is waived for content that has been live at least 14 days, allowing time for delayed attribution.

Thresholds are configurable per-brand via operator-supplied overrides stored in brand metadata; the defaults above apply when no override is present.

## Rationale

Paid promotion should only amplify proven organic winners. Promoting content that has not validated organic engagement risks wasting ad budget on unproven creative. The 14-day age bypass prevents penalising evergreen content where delayed revenue attribution is common (e.g. SEO-driven articles, long-form YouTube).

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `refresh_all_paid_promotion_candidates` | Every 6 h (minute :58) | `revenue_ceiling` |

## Scoring Engine

Pure function: `evaluate_paid_promotion_candidate()` in `packages/scoring/revenue_ceiling_phase_c_engines.py`.

## Persistence

- Table: `paid_promotion_candidates`
- Unique constraint: one row per brand + content item (`uq_paid_promo_brand_content`)
- Refresh deletes all existing rows for the brand before inserting new ones

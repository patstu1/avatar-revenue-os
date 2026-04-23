# Competitive Gap Hunter

## Overview

The Competitive Gap Hunter compares a brand's offers against competitor offerings and market feedback to identify pricing, feature, and satisfaction gaps — each with severity, estimated impact, and a monetization opportunity.

## Inputs

| Source | Fields Used |
|--------|------------|
| `Offer` | `id`, `name`, `audience_fit_tags` (features), `payout_amount` (pricing) |
| Competitor offers (static) | `competitor_name`, `offer_id`, `name`, `features`, `pricing` |
| Market feedback (static) | `feedback_id`, `offer_id`, `sentiment`, `comment` |

## Scoring Logic (`packages/scoring/expansion_pack2_phase_c_engines.py`)

`analyze_competitive_gaps(brand_id, own_offers, competitor_offers, market_feedback)`

1. **No offers guard** — returns `no_own_offers` gap with medium severity.
2. **Pricing gap** — if own price > competitor price by ≥ 10%, produces `pricing_disadvantage` with `estimated_impact = (own - competitor) × 100`.
3. **Feature gap** — if competitor has ≥ 2 more features, produces `feature_disadvantage` with estimated impact 5000.
4. **Satisfaction gap** — if ≥ 5 negative feedback items, produces `customer_satisfaction_gap` with impact 15000.
5. **Fallback** — `no_significant_gap` with severity low.

### Derived Fields

Each report includes `niche` (keyword-matched from offer name), `sub_niche`, `monetization_opportunity`, `expected_difficulty`, and `expected_upside` (impact × multiplier).

## API Endpoints

- **GET** `/api/v1/brands/{id}/competitive-gaps` — list gap reports
- **POST** `/api/v1/brands/{id}/competitive-gaps/recompute` — trigger recomputation (operator only)

## Worker

`recompute_all_competitive_gap_reports` — runs every 12 hours via Celery beat.

## Frontend

`/dashboard/expansion-pack2-c/competitive-gap` — table showing gap type, severity, impact, and recommendations.

## DB Table

`competitive_gap_reports` — unique constraint on `(brand_id, competitor_name, offer_id)`.

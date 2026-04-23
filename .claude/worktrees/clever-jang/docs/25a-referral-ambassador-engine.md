# Referral & Ambassador Engine

## Overview

The Referral & Ambassador Engine identifies high-value customer segments and recommends optimal referral program parameters — incentive type, bonus amounts, estimated conversion rate, and projected revenue impact.

## Inputs

| Source | Fields Used |
|--------|------------|
| `AudienceSegment` | `name`, `estimated_size`, `revenue_contribution`, `conversion_rate` (loyalty proxy), `avg_ltv` (purchase value proxy) |
| Historical referral data (static) | `program_type`, `referral_bonus`, `referred_bonus`, `conversion_rate` |

## Scoring Logic (`packages/scoring/expansion_pack2_phase_c_engines.py`)

`recommend_referral_program(brand_id, customer_segment_data, historical_referral_data)`

1. **Segment selection** — picks the segment with the highest `loyalty_score` (derived from conversion_rate).
2. **Program matching** — selects the historical program type with the highest conversion rate.
3. **Revenue impact** — `estimated_conversion_rate × estimated_size × avg_purchase_value`.
4. **Confidence** — base 0.6 + bonuses for high loyalty (≥ 0.7 → +0.15) and historical conversion ≥ 0.1 (→ +0.1).
5. **Fallback** — when no segment data is available, returns a `standard_cash_bonus` recommendation with 0.5 confidence.

### Recommendation Types

| Loyalty Score | Program Type |
|--------------|-------------|
| ≥ 0.7 | `tiered_cash_bonus` |
| 0.3 – 0.7 | `discount_for_next_purchase` |
| < 0.3 | `standard_cash_bonus` |

## Outputs

| Field | Type | Description |
|-------|------|-------------|
| `customer_segment` | string | Selected segment name |
| `recommendation_type` | string | Incentive program type |
| `referral_bonus` | float | Referrer bonus amount |
| `referred_bonus` | float | Referred customer bonus |
| `estimated_conversion_rate` | float | Expected conversion rate |
| `estimated_revenue_impact` | float | Projected revenue |
| `confidence` | float | 0-1 confidence score |
| `explanation` | string | Detailed reasoning |

## API Endpoints

- **GET** `/api/v1/brands/{id}/referral-programs` — list active recommendations
- **POST** `/api/v1/brands/{id}/referral-programs/recompute` — trigger recomputation (operator only)

## Worker

`recompute_all_referral_program_recommendations` — runs every 8 hours via Celery beat.

## Frontend

`/dashboard/expansion-pack2-c/referral` — table view with recompute button.

## DB Table

`referral_program_recommendations` — unique constraint on `(brand_id, customer_segment)`.

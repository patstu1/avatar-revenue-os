# Pricing Intelligence Engine

Part of **Expansion Pack 2 — Phase B**. Evaluates price elasticity, competitor positioning, and willingness-to-pay to recommend optimal price points for every active offer.

---

## Overview

The Pricing Intelligence Engine scores each active offer's current price against three signal sources — historical sales volume changes, competitor market data, and customer segment willingness-to-pay — then produces a recommendation type (`price_increase`, `price_decrease`, `anchor_reprice`, or `hold`), a recommended price, and a confidence score. One row is written to `pricing_recommendations` per active offer per brand.

---

## Inputs

| Input | Source | Description |
|---|---|---|
| `offer_id` | `offers.id` | The active offer being evaluated. |
| `current_price` | `offers.payout_amount` | Current price of the offer (minimum $1.00). |
| `historical_sales_data` | Analytics pipeline | List of `{price, quantity_sold, date}` dicts from recent sales history. |
| `market_data` | External / manual | List of `{competitor_price, competitor_features, demand_level}` dicts. |
| `customer_segment_data` | `AudienceSegment` | List of `{segment_name, price_sensitivity, willingness_to_pay}` dicts. |

---

## Scoring Logic

### 1. Price Elasticity Signal

When ≥ 2 historical data points exist, the engine computes percentage change in price and quantity between the earliest and most recent records:

```
dp = (last_price - first_price) / max(|first_price|, 1.0)
dq = (last_qty - first_qty) / max(|first_qty|, 1.0)
elasticity = |dq / dp|   (clamped to [0.05, 2.0])
```

When < 2 data points, elasticity defaults to `0.50`.

### 2. Market Signal

- **Competitor average**: mean of `competitor_price` values from `market_data`.
- **Demand level**: mean of `demand_level` values (0–1 scale).
- **Market ratio**: `avg_competitor_price / current_price`.

### 3. Willingness-to-Pay Signal

- **Average WTP**: mean of `willingness_to_pay` values from customer segments.
- **Average sensitivity**: mean of `price_sensitivity` values (0–1 scale).

### 4. Composite Recommended Price

```
market_pull = current_price × (0.40 × market_ratio + 0.30 × (avg_wtp / current_price) + 0.30 × (1.0 + demand × 0.20))
sensitivity_dampener = 1.0 - avg_sensitivity × 0.30
recommended_price = max(1.0, market_pull × sensitivity_dampener)
```

### 5. Recommendation Type

| Condition | Type |
|---|---|
| `delta_pct > 5%` | `price_increase` |
| `delta_pct < -5%` | `price_decrease` |
| `|delta_pct| ≤ 5%` and competitor data exists | `anchor_reprice` |
| Otherwise | `hold` |

### 6. Revenue Impact Estimate

```
volume_proxy = avg quantity_sold from last 3 historical records (default 10)
estimated_revenue_impact = (recommended_price - current_price) × volume_proxy
```

### 7. Confidence Score

```
confidence = clamp(0.25 + data_depth + market_depth + segment_depth)
```

Where:
- `data_depth` = `min(len(historical) / 12, 0.30)`
- `market_depth` = `min(len(market) / 5, 0.25)`
- `segment_depth` = `min(len(segments) / 4, 0.20)`

---

## Outputs — `pricing_recommendations` Table

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier. |
| `brand_id` | UUID FK | References `brands.id`. |
| `offer_id` | UUID FK | References `offers.id`. |
| `recommendation_type` | String | `price_increase` \| `price_decrease` \| `anchor_reprice` \| `hold`. |
| `current_price` | Float | Price at time of evaluation. |
| `recommended_price` | Float | Engine-recommended price point. |
| `price_elasticity` | Float | Computed elasticity (0.05–2.0). |
| `estimated_revenue_impact` | Float | Monthly revenue impact estimate. |
| `confidence` | Float | Model confidence (0–1). |
| `explanation` | Text | Human-readable rationale. |
| `is_active` | Bool | Soft-delete flag. |
| `created_at` | Timestamp | Row creation time. |
| `updated_at` | Timestamp | Last recompute time. |

Unique constraint: `(brand_id, offer_id)`.

---

## API Endpoints

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/brands/{id}/pricing-recommendations` | Any | All pricing recommendations for the brand, ordered by `estimated_revenue_impact` desc. |
| `POST` | `/brands/{id}/pricing-recommendations/recompute` | OPERATOR | Delete and rebuild all pricing recommendations for the brand. |

---

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_pricing_recommendations` | Every 8 h (`:12`) | `revenue_ceiling` |

Iterates all active brands, deletes existing `pricing_recommendations`, and rebuilds one row per active offer.

---

## Frontend

Mounted at `/dashboard/expansion-pack2-b/pricing`. Displays a table with columns: Offer ID, Type, Current Price, Recommended Price, Elasticity, Revenue Impact, Confidence (progress bar), and Explanation. Recompute button (OPERATOR only) triggers the recompute endpoint and refreshes the table after 5 seconds.

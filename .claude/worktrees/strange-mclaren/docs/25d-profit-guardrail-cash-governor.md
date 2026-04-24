# Profit Guardrail & Cash Governor

## Overview

The Profit Guardrail & Cash Governor monitors key financial health metrics against configurable thresholds. When a metric crosses into warning or violation territory, the engine recommends throttle actions to protect profitability.

## Inputs

| Source | Fields Used |
|--------|------------|
| `Offer` | `payout_amount`, `conversion_rate` |
| `AudienceSegment` | `estimated_size`, `revenue_contribution`, `avg_ltv` |
| Defined guardrails (default or custom) | `metric_name`, `threshold`, `direction`, `warning_buffer`, `action` |

### Derived Financial Metrics

The service layer computes these from real DB data:

| Metric | Derivation |
|--------|-----------|
| `profit_margin` | `(total_revenue - estimated_cac × audience × 0.01) / total_revenue` |
| `customer_acquisition_cost` | `avg_payout / max(avg_cvr, 0.001)` |
| `monthly_burn_rate` | `estimated_cac × total_audience × 0.005` |
| `refund_rate` | Default 0.04 (no refund data yet) |
| `ltv_to_cac_ratio` | `avg_ltv / estimated_cac` |

## Scoring Logic (`packages/scoring/expansion_pack2_phase_c_engines.py`)

`analyze_profit_guardrails(brand_id, financial_metrics, defined_guardrails)`

### Default Guardrails

| Metric | Direction | Threshold | Warning Buffer | Action |
|--------|-----------|-----------|---------------|--------|
| `profit_margin` | min | 0.20 | 0.05 | `throttle_ad_spend` |
| `customer_acquisition_cost` | max | 150.0 | 25.0 | `reduce_paid_acquisition` |
| `monthly_burn_rate` | max | 10,000 | 2,000 | `cut_discretionary_spend` |
| `refund_rate` | max | 0.08 | 0.03 | `review_offer_quality` |
| `ltv_to_cac_ratio` | min | 3.0 | 0.5 | `rebalance_acquisition_channels` |

### Status Determination

For `min` direction: violation if `value < threshold`, warning if `value < threshold + buffer`, else ok.
For `max` direction: violation if `value > threshold`, warning if `value > threshold - buffer`, else ok.

### Impact & Confidence

- **Violation** — impact = `|gap| × 1000`, confidence = `min(1.0, 0.85 + |gap| × 0.5)`
- **Warning** — impact = `|gap| × 500`, confidence = 0.70
- **OK** — impact = 0, confidence = 0.95

### Action Recommendation

- Violation → guardrail's configured action
- Warning → `monitor_{metric_name}`
- OK → None

## Outputs

Returns a **list** of report dicts, one per evaluated guardrail:

| Field | Type | Description |
|-------|------|-------------|
| `metric_name` | string | Financial metric name |
| `current_value` | float | Current computed value |
| `threshold_value` | float | Guardrail threshold |
| `status` | string | `ok`, `warning`, or `violation` |
| `action_recommended` | string? | Throttle action or monitor instruction |
| `estimated_impact` | float | Revenue at risk |
| `confidence` | float | 0-1 confidence score |

## API Endpoints

- **GET** `/api/v1/brands/{id}/profit-guardrails` — list guardrail reports
- **POST** `/api/v1/brands/{id}/profit-guardrails/recompute` — trigger recomputation (operator only)

## Worker

`recompute_all_profit_guardrail_reports` — runs every 6 hours via Celery beat.

## Frontend

`/dashboard/expansion-pack2-c/profit-guardrails` — shows metric status, threshold bars, and recommended actions.

## DB Table

`profit_guardrail_reports` — unique constraint on `(brand_id, metric_name)`.

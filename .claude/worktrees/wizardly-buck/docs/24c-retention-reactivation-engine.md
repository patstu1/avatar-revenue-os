# Retention & Reactivation Engine

Part of **Expansion Pack 2 — Phase B**. Scores churn risk per customer segment, recommends retention strategies, and designs reactivation campaigns for lapsed customers.

---

## Overview

The Retention & Reactivation Engine operates in two modes:

1. **Retention mode** — evaluates churn risk across three synthetic customer segments (high-value at risk, declining engagement, healthy) and produces a targeted retention recommendation per segment. Results are persisted to `retention_recommendations`.
2. **Reactivation mode** — designs time-bound reactivation campaigns for lapsed customer segments, selecting the optimal campaign type from historical performance data. Results are persisted to `reactivation_campaigns`.

Both modes delete and rebuild all rows for the brand on each recompute cycle.

---

## Retention Engine

### Inputs

| Input | Source | Description |
|---|---|---|
| `customer_id` | Synthetic UUID | Placeholder customer identifier. |
| `customer_behavior_data` | Analytics pipeline | List of `{activity_level}` dicts (`"high"`, `"medium"`, `"low"`). |
| `churn_risk_score` | Derived | Float 0–1 representing churn likelihood. |
| `available_retention_offers` | `offers` table | Up to 3 active offers formatted as `{offer_id, type, discount}`. |

### Segment Classification

| Churn Score | Segment |
|---|---|
| ≥ 0.75 | `critical_churn_risk` |
| ≥ 0.50 | `high_churn_risk` |
| ≥ 0.25 | `moderate_churn_risk` |
| < 0.25 | `low_churn_risk` |

### Strategy Selection

| Churn Range | Strategy | Action Details |
|---|---|---|
| ≥ 0.75 + offers available | `win_back_discount` | `{offer_id, discount, urgency: "immediate"}` |
| ≥ 0.75 + no offers | `personal_outreach` | `{channel: "email", urgency: "immediate"}` |
| ≥ 0.50 | `personalized_offer` | `{offer_id, urgency: "48h"}` |
| ≥ 0.25 | `engagement_campaign` | `{campaign_type: "content_drip", duration_days: 14}` |
| < 0.25 | `loyalty_reward` | `{reward_type: "early_access", duration_days: 30}` |

### Retention Lift Estimate

```
base_lift = strategy-specific base (e.g. win_back_discount = 0.18, loyalty_reward = 0.08)
offer_bonus = 0.05 if retention offers available, else 0.0
recency_bonus = (1.0 - avg_recency_risk) × 0.05
estimated_lift = clamp(base_lift + offer_bonus + recency_bonus, 0.0, 0.50)
```

Activity-level recency risk mapping: `high → 0.1`, `medium → 0.3`, `low → 0.6`.

### Confidence Score

```
confidence = clamp(0.35 + data_signal + offer_signal + (1.0 - churn) × 0.15)
```

Where:
- `data_signal` = `min(len(behavior_data) / 10, 0.25)`
- `offer_signal` = `min(len(retention_offers) / 3, 0.15)`

---

## Reactivation Engine

### Inputs

| Input | Source | Description |
|---|---|---|
| `lapsed_customer_segment` | Analytics pipeline | List of `{segment_name, last_activity_days_ago, segment_size}` dicts. |
| `historical_campaign_performance` | Campaign history | List of `{campaign_type, reactivation_rate}` dicts. |
| `available_campaign_types` | Configuration | List of campaign type strings (e.g. `"email_series"`, `"discount_offer"`). |

### Campaign Type Selection

1. If historical data exists, select the campaign type with the highest `reactivation_rate` that is also in `available_campaign_types`.
2. Otherwise, select the first available type.
3. Fallback: `"email_series"`.

### Reactivation Rate Estimate

```
base_rate = campaign-type-specific (email_series: 0.05, discount_offer: 0.08, content_drip: 0.04, 
            social_retarget: 0.06, personal_outreach: 0.10, limited_time_access: 0.07)
lapse_penalty = clamp(avg_lapse_days / 365, 0.0, 0.50) × 0.5
hist_bonus = min(best_historical_rate × 0.30, 0.05)
estimated_rate = clamp(base_rate - lapse_penalty + hist_bonus, 0.01, 0.30)
```

### Revenue Impact Estimate

```
estimated_revenue = segment_size × estimated_rate × avg_aov ($75)
```

### Campaign Duration

- 30 days if `avg_lapse < 120 days`
- 45 days otherwise

### Confidence Score

```
confidence = clamp(0.35 + hist_depth + seg_depth + min(0.15, best_rate × 2.0))
```

Where:
- `hist_depth` = `min(len(historical) / 5, 0.25)`
- `seg_depth` = `min(len(segments) / 3, 0.20)`

---

## Output Tables

### `retention_recommendations`

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier. |
| `brand_id` | UUID FK | References `brands.id`. |
| `customer_segment` | String | Segment name (e.g. `high_value_at_risk`). |
| `recommendation_type` | String | Strategy type (e.g. `win_back_discount`). |
| `action_details` | JSONB | Action parameters (offer_id, discount, urgency, etc.). |
| `estimated_retention_lift` | Float | Projected retention improvement (0–0.50). |
| `confidence` | Float | Model confidence (0–1). |
| `explanation` | Text | Human-readable rationale. |
| `is_active` | Bool | Soft-delete flag. |
| `created_at` | Timestamp | Row creation time. |
| `updated_at` | Timestamp | Last recompute time. |

Unique constraint: `(brand_id, customer_segment)`.

### `reactivation_campaigns`

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier. |
| `brand_id` | UUID FK | References `brands.id`. |
| `campaign_name` | String | Human-readable campaign name. |
| `target_segment` | String | Target lapsed segment name. |
| `campaign_type` | String | Campaign channel type. |
| `start_date` | Timestamp | Campaign start date. |
| `end_date` | Timestamp | Campaign end date. |
| `estimated_reactivation_rate` | Float | Projected reactivation rate (0.01–0.30). |
| `estimated_revenue_impact` | Float | Projected revenue from reactivated customers. |
| `confidence` | Float | Model confidence (0–1). |
| `explanation` | Text | Human-readable rationale. |
| `is_active` | Bool | Soft-delete flag. |
| `created_at` | Timestamp | Row creation time. |
| `updated_at` | Timestamp | Last recompute time. |

Unique constraint: `(brand_id, campaign_name)`.

---

## API Endpoints

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/brands/{id}/retention-recommendations` | Any | All retention recommendations, ordered by `estimated_retention_lift` desc. |
| `POST` | `/brands/{id}/retention-recommendations/recompute` | OPERATOR | Delete and rebuild all retention recommendations. |
| `GET` | `/brands/{id}/reactivation-campaigns` | Any | All reactivation campaigns, ordered by `estimated_revenue_impact` desc. |
| `POST` | `/brands/{id}/reactivation-campaigns/recompute` | OPERATOR | Delete and rebuild all reactivation campaigns. |

---

## Workers

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_retention_recommendations` | Every 6 h (`:22`) | `revenue_ceiling` |
| `recompute_all_reactivation_campaigns` | Every 12 h (`:35`) | `revenue_ceiling` |

---

## Frontend

Mounted at `/dashboard/expansion-pack2-b/retention`. Displays two sections:

1. **Retention Recommendations** — table with Segment, Type, Action Details (JSON), Retention Lift, Confidence, Explanation. Recompute button triggers retention recompute.
2. **Reactivation Campaigns** — table with Campaign Name, Target Segment, Type, Start/End Date, Reactivation Rate, Revenue Impact, Confidence, Explanation. Recompute button triggers reactivation recompute.

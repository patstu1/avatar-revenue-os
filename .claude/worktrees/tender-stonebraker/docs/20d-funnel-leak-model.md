# Funnel Leak Model

## Funnel Stages Tracked

Metrics are computed as a synthetic conversion chain per content family:

1. click
2. landing
3. opt_in
4. lead_confirmation
5. email_open
6. email_click
7. sales_page_view
8. checkout_start
9. purchase
10. upsell
11. retention_event
12. repeat_purchase

**Content families** are derived from `content_items.tags` (same rules as owned audience), capped at 12 families. With no content, a single **general** family is used.

## Leak Detection

Heuristic rules compare stage values to thresholds and emit leak rows. Detected leak types:

| Leak Type | Trigger | Stage |
|---|---|---|
| `weak_above_fold_clarity` | landing < 0.5 | landing |
| `poor_form_conversion` | opt_in < 0.2 | opt_in |
| `checkout_abandonment` | purchase / checkout_start < 0.35 | purchase |
| `weak_trust_proof` | email_open < 0.25 | email_open |
| `low_repeat_conversion` | repeat_purchase < 0.08 | repeat_purchase |
| `weak_offer_positioning` | fallback (no other leaks) | sales_page_view |

Additional defined leak types (for future expansion):

- `weak_landing_headline`
- `cta_mismatch`
- `too_much_friction`
- `weak_upsell_order`
- `wrong_audience_wrong_funnel`

## Persistence

### Table: `funnel_stage_metrics`

| Column | Type | Notes |
|---|---|---|
| `brand_id` | UUID FK → brands | indexed |
| `content_family` | String(120) | indexed |
| `stage` | String(80) | indexed |
| `metric_value` | Float | 0..1 conversion rate |
| `sample_size` | Integer | synthetic |
| `period_start` | String(40) | ISO date |
| `period_end` | String(40) | ISO date |

### Table: `funnel_leak_fixes`

| Column | Type | Notes |
|---|---|---|
| `brand_id` | UUID FK → brands | indexed |
| `leak_type` | String(120) | indexed |
| `severity` | String(20) | low / medium / high |
| `affected_funnel_stage` | String(80) | |
| `affected_content_family` | String(120) | nullable |
| `suspected_cause` | Text | |
| `recommended_fix` | Text | |
| `expected_upside` | Float | dollar value |
| `confidence` | Float | 0..1 |
| `urgency` | Float | 0..100 scale |
| `is_active` | Boolean | default true |

## API

- `GET /api/v1/brands/{brand_id}/funnel-stage-metrics` — list all stage metrics
- `GET /api/v1/brands/{brand_id}/funnel-leaks` — list active leaks
- `POST /api/v1/brands/{brand_id}/funnel-leaks/recompute` — delete + rebuild metrics and leaks

## Engine

`packages/scoring/revenue_ceiling_phase_a_engines.py`:

- `compute_funnel_stage_metrics()` — synthetic conversion chain per content family
- `detect_funnel_leaks()` — heuristic leak detection from stage drop-offs

If no rule fires, a low-severity `weak_offer_positioning` leak is added so the dashboard is never empty.

## Worker

Celery beat task `recompute_all_funnel_leaks` runs every 6 hours on the `revenue_ceiling` queue.

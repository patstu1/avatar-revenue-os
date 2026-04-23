# Monetization Mix Optimizer — Phase C

## Overview

Measures concentration risk across active revenue methods using an HHI-style dependency metric, identifies underused monetization paths, and recommends a diversified allocation. One row per brand is written to `monetization_mix_reports`.

## API

| Method | Path | Role |
|---|---|---|
| `GET` | `/api/v1/brands/{brand_id}/monetization-mix` | Any authenticated user |
| `POST` | `/api/v1/brands/{brand_id}/monetization-mix/recompute` | OPERATOR |

## Inputs

- **`niche`** — brand niche string.
- **`revenue_by_method`** — dict mapping each `monetization_method` string to its attributed revenue total.
- **`total_revenue`** — sum of all attributed revenue; computed from `revenue_by_method` if not supplied directly.
- **`audience_size`** — brand follower sum.
- **`active_offer_types`** — list of monetization method strings currently used by the brand's active offers.

## Outputs

| Field | Type | Description |
|---|---|---|
| `current_revenue_mix` | dict | `{method: pct_of_total}` for every method with revenue > 0. Percentages sum to 1.0. |
| `dependency_risk` | float 0–1 | HHI-style score: `Σ(pct_i²)`. `1.0` = fully concentrated; `0.14` = perfectly spread across 7 paths. |
| `underused_monetization_paths` | list of objects | Methods not in `active_offer_types`, each with `{path, potential_score, rationale}`. |
| `next_best_mix` | dict | Recommended allocation; no single method exceeds 40 %. Redistributes weight toward underused paths. |
| `expected_margin_uplift` | float | Estimated margin improvement from diversification (heuristic from dependency_risk delta). |
| `expected_ltv_uplift` | float | Estimated LTV improvement from adding recurring or high-value paths. |
| `confidence` | float 0–1 | Penalised when `total_revenue == 0` or fewer than 2 active offer types. |

## Logic

### Known monetization paths

`affiliate`, `sponsorship`, `digital_product`, `membership`, `coaching`, `ads`, `email_list`.

### Dependency risk

Computed as `sum(pct_i ** 2)` over all methods in `current_revenue_mix`. A brand earning 100 % from a single method scores `1.0`; two equal methods score `0.50`; five equal methods score `0.20`.

### Next best mix construction

Begin with `current_revenue_mix`; identify any method exceeding 40 % and cap it at 40 %, distributing the surplus proportionally across underused paths (up to 3 new paths are introduced, each seeded at minimum 5 % allocation). Final allocations are renormalised to sum to 1.0.

### Expected margin uplift

`(current_dependency_risk − projected_dependency_risk) × 0.30`. A drop from `0.90` to `0.30` in dependency risk estimates `+18 %` margin improvement.

### Expected LTV uplift

`0.10` added for each newly introduced recurring path (`membership`, `email_list`, `coaching`) in `next_best_mix`, up to a ceiling of `0.30`.

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_monetization_mix` | Every 12 h (minute :30) | `revenue_ceiling` |

## Scoring Engine

Pure function: `score_monetization_mix()` in `packages/scoring/revenue_ceiling_phase_c_engines.py`.

## Persistence

- Table: `monetization_mix_reports`
- Unique constraint: one row per brand (`uq_monetization_mix_brand`)
- Recompute replaces existing row

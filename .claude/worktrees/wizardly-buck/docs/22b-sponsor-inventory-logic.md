# Sponsor Inventory and Pricing Engine — Phase C

## Overview

Evaluates every content item as a sponsorship placement, assigns category, estimates package pricing, and synthesises brand-level sponsorship package recommendations. Two tables are written: `sponsor_inventory` (one row per content item) and `sponsor_package_recommendations` (one row per brand).

## API

| Method | Path | Role |
|---|---|---|
| `GET` | `/api/v1/brands/{brand_id}/sponsor-inventory` | Any authenticated user |
| `GET` | `/api/v1/brands/{brand_id}/sponsor-package-recommendations` | Any authenticated user |
| `POST` | `/api/v1/brands/{brand_id}/sponsor-inventory/recompute` | OPERATOR |

## Inputs (per content item)

- **`content_item_id`**, **`title`**, **`niche`** — item identity and topic signal.
- **`impressions`** — raw impression count from associated `performance_metrics` rows; defaults to `0`.
- **`engagement_rate`** — from `performance_metrics`; defaults to `0.03`.
- **`audience_size`** — brand-level follower sum (shared across all items for the brand).
- **`content_type`** — one of `long_form`, `podcast`, `short_form`, `article`.

## Outputs — `sponsor_inventory` (per content item)

| Field | Type | Description |
|---|---|---|
| `sponsor_fit_score` | float 0–1 | Impressions (log-normalised) + engagement_rate contribution + content_type bonus. |
| `estimated_package_price` | float | Base rate × impressions tier × engagement multiplier. |
| `sponsor_category` | string | Mapped from niche (e.g. `finance → fintech`, `tech → b2b_saas`). |
| `confidence` | float 0–1 | Higher when impressions > 0 and engagement_rate is non-default. |
| `explanation` | string | Human-readable rationale for price and category assignment. |

### Base rates by content type

`long_form` → $500, `podcast` → $800, `short_form` → $200, `article` → $150.

### Impressions tiers

< 1 k → ×0.5; 1 k–10 k → ×1.0; 10 k–100 k → ×1.5; 100 k–1 M → ×2.0; > 1 M → ×3.0.

### Engagement multiplier

`1.0 + min(engagement_rate × 10, 2.0)` (capped at ×3.0 combined).

### Content type bonus to `sponsor_fit_score`

`podcast` → +0.15, `long_form` → +0.10, `article` → +0.05, `short_form` → +0.00.

## Outputs — `sponsor_package_recommendations` (per brand)

| Field | Type | Description |
|---|---|---|
| `recommended_package` | JSON object | `{name, deliverables: [...], duration_weeks, exclusivity: bool}`. |
| `sponsor_fit_score` | float 0–1 | Mean of selected items' individual scores. |
| `estimated_package_price` | float | Sum of selected items' estimated prices, discounted 10 % for bundle. |
| `sponsor_category` | string | Most common `sponsor_category` across selected items. |
| `confidence` | float 0–1 | Penalised when fewer than 3 content items are available. |
| `explanation` | string | Narrative description of package composition and pricing rationale. |

## Logic

- `sponsor_fit_score` = `(log10(max(impressions,1)) / 7.0) × 0.40 + engagement_rate × 0.40 + content_type_bonus × 0.20`, clamped `[0.0, 1.0]`.
- Package `exclusivity` is set to `true` when `estimated_package_price > 2000`; `duration_weeks` defaults to 4 for single placements, 8 for multi-placement bundles.
- When no `performance_metrics` rows exist for a content item, `impressions` is estimated as `audience_size × 0.10` and `confidence` is capped at `0.5`.

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_sponsor_inventory` | Every 8 h (minute :15) | `revenue_ceiling` |

## Scoring Engine

Pure functions: `score_sponsor_inventory_item()` and `score_sponsor_package()` in `packages/scoring/revenue_ceiling_phase_c_engines.py`.

## Persistence

- Tables: `sponsor_inventory`, `sponsor_package_recommendations`
- Recompute deletes all existing rows for the brand before inserting new ones
- `sponsor_package_recommendations` has unique constraint per brand (`uq_sponsor_pkg_brand`)

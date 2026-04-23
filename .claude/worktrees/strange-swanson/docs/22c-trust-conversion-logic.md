# Trust Conversion Layer — Phase C

## Overview

Audits present trust signals, surfaces a deficit score, and generates a prioritised proof-block action list with projected conversion rate uplift. One row per brand is written to `trust_conversion_reports`.

## API

| Method | Path | Role |
|---|---|---|
| `GET` | `/api/v1/brands/{brand_id}/trust-conversion` | Any authenticated user |
| `POST` | `/api/v1/brands/{brand_id}/trust-conversion/recompute` | OPERATOR |

## Inputs

- **`niche`** — used to weight which proof block types are most credible for the category.
- **Boolean trust signals**: `has_testimonials`, `has_case_studies`, `has_media_features`, `has_certifications` — sourced from brand metadata or operator-supplied flags.
- **`social_proof_count`** — integer count of public social proof items (reviews, ratings, endorsements).
- **`content_item_count`** — total published content items for the brand.
- **`avg_quality_score`** — mean `quality_score` across all content items; defaults to `0.5`.
- **`offer_conversion_rate`** — mean conversion rate across active offers; defaults to `0.02`.

## Outputs

| Field | Type | Description |
|---|---|---|
| `trust_deficit_score` | float 0.05–1.0 | Starts at `1.0`; each present signal subtracts its weight. Floor is `0.05`. |
| `recommended_proof_blocks` | list of objects | Prioritised `[{type, priority, action}]` for each missing element. |
| `missing_trust_elements` | list of strings | Names of absent trust signals in plain language. |
| `expected_uplift` | float | `trust_deficit_score × 0.25` — estimated conversion rate improvement fraction. |
| `confidence` | float 0–1 | Penalised when `content_item_count < 3` or `offer_conversion_rate` is at its default. |

## Deficit Deductions

Applied sequentially; floor enforced after all deductions:

| Signal present | Deduction |
|---|---|
| `has_testimonials = true` | −0.15 |
| `has_case_studies = true` | −0.20 |
| `social_proof_count >= 5` | −0.10 |
| `has_media_features = true` | −0.10 |
| `has_certifications = true` | −0.10 |

Minimum `trust_deficit_score` after all deductions: **0.05**.

## Proof Blocks

Generated only for missing elements, sorted by deduction weight descending (case studies first, then testimonials, then certifications, media features, social proof). Each block carries an `action` string with specific instructions.

### Niche Weighting

- `finance` and `health` niches add +1 priority rank to `certifications`.
- `tech`/`saas` niches add +1 rank to `case_studies`.
- Priority rank only affects ordering within `recommended_proof_blocks`, not the deficit deduction.

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_trust_conversion` | Every 12 h (minute :20) | `revenue_ceiling` |

## Scoring Engine

Pure function: `score_trust_conversion()` in `packages/scoring/revenue_ceiling_phase_c_engines.py`.

## Persistence

- Table: `trust_conversion_reports`
- Unique constraint: one row per brand (`uq_trust_conversion_brand`)
- Recompute replaces existing row

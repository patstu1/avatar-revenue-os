# Outbound Sponsor Sales Engine

## Overview

The Outbound Sponsor Sales Engine has two stages:

1. **Sponsor Target Identification** — ranks potential sponsors by audience fit, budget alignment, and platform overlap.
2. **Outreach Sequence Generation** — creates tailored multi-step outreach plans with estimated response rates and expected deal value.

## Inputs

### Sponsor Targets

| Source | Fields Used |
|--------|------------|
| `SponsorProfile` | `sponsor_name`, `industry`, `budget_range_min/max`, `preferred_platforms`, `preferred_content_types`, `contact_email` |
| `AudienceSegment` | `name`, `estimated_size`, `revenue_contribution`, `conversion_rate`, `avg_ltv`, `platforms`, `loyalty_score` |

### Outreach Sequences

| Source | Fields Used |
|--------|------------|
| `SponsorTarget` (DB) | `id`, `target_company_name`, `industry`, `estimated_deal_value` |
| Outreach templates (static) | `name`, `steps`, `effectiveness`, `target_industry`, `target_company_size_category` |
| Historical performance (static) | `sequence_name`, `response_rate`, `conversion_rate`, `industry`, `company_size_category` |

## Scoring Logic (`packages/scoring/expansion_pack2_phase_c_engines.py`)

### `identify_sponsor_targets`

1. **Industry match** — +0.3 fit score if sponsor industry matches audience keywords.
2. **Platform overlap** — +0.2 per overlapping platform (capped at 0.4).
3. **Budget alignment** — +0.2 if audience revenue falls within budget range.
4. **Estimated deal value** — `budget_avg × fit_score × audience_size_factor`.
5. **Package recommendation** — premium_custom (fit ≥ 0.7), standard_tailored (0.4-0.7), basic_starter (< 0.4).

### `generate_sponsor_outreach_sequence`

1. **Template matching** — selects template matching target industry + company size.
2. **Historical adjustment** — blends template effectiveness with historical response rate (70/30 weighted).
3. **Expected value** — `adjusted_response_rate × conversion_rate × estimated_deal_value`.
4. **Fallback** — defaults to "Standard Cold Outreach" with base 5% response rate.

## API Endpoints

- **GET** `/api/v1/brands/{id}/sponsor-targets` — list ranked targets
- **POST** `/api/v1/brands/{id}/sponsor-targets/recompute` — trigger recomputation (operator only)
- **GET** `/api/v1/brands/{id}/sponsor-outreach` — list outreach sequences
- **POST** `/api/v1/brands/{id}/sponsor-outreach/recompute` — trigger recomputation (operator only)

## Workers

- `recompute_all_sponsor_targets` — every 8 hours
- `recompute_all_sponsor_outreach_sequences` — every 8 hours (runs after targets)

## Frontend

`/dashboard/expansion-pack2-c/sponsor-sales` — shows targets with fit scores and outreach sequences with response rates.

## DB Tables

- `sponsor_targets` — unique on `(brand_id, target_company_name)`
- `sponsor_outreach_sequences` — unique on `(sponsor_target_id, sequence_name)`, FK to `sponsor_targets`

# High-Ticket Conversion Logic

## Inputs

- Active offers: AOV, payout amount, conversion rate, offer name keywords
- Optional content titles (anchor content for each opportunity)
- Brand niche

## Eligibility Score

Combines four signals:

| Signal | Source | Weight |
|---|---|---|
| Keyword signal | Presence of "coaching", "mastermind", "consult", "course", "program", "vip", "enterprise", "premium" in offer name | 0.35 |
| Value signal | `min(1.0, (AOV + payout) / 5000)` | 0.25 |
| Conversion signal | `min(1.0, conversion_rate * 25)` | 0.15 |
| Deterministic noise | Hash-based variation per opportunity key | small |

Formula: `min(0.98, 0.25 + keyword * 0.35 + value * 0.25 + conv * 0.15 + noise)`

## Outputs

| Field | Description |
|---|---|
| `eligibility_score` | 0..0.98, composite high-ticket fit |
| `recommended_offer_path` | `{"steps": ["Application/discovery call", "Qualification + value framing", "Proposal / payment link", "Onboarding + delivery"]}` |
| `recommended_cta` | Niche-aware CTA string |
| `expected_close_rate_proxy` | `min(0.35, 0.02 + eligibility * 0.25 + conversion_rate * 0.5)` |
| `expected_deal_value` | `max(AOV, payout * 3, 500) * (1 + keyword_signal)` |
| `expected_profit` | `deal_value * close_proxy * margin` (margin = 0.42 + keyword * 0.15) |
| `confidence` | `min(0.95, 0.4 + eligibility * 0.35 + value * 0.2)` |
| `explanation` | Human-readable summary of inputs and reasoning |

## Row Generation

One row per offer × content item pairing (capped at 10 offers × 15 content items). When no content exists, one row per offer with a `no_content` key.

## Persistence

### Table: `high_ticket_opportunities`

- `brand_id` UUID FK → brands (indexed)
- `opportunity_key` String(255), unique per brand
- `source_offer_id` UUID FK → offers (nullable)
- `source_content_item_id` UUID FK → content_items (nullable)
- All output fields above
- `is_active` Boolean, default true

Recompute deletes all rows for the brand, then inserts fresh.

## API

- `GET /api/v1/brands/{brand_id}/high-ticket-opportunities`
- `POST /api/v1/brands/{brand_id}/high-ticket-opportunities/recompute`

## Worker

Celery beat task `recompute_all_high_ticket` runs every 6 hours on the `revenue_ceiling` queue.

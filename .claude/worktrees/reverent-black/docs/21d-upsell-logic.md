# Upsell / Cross-Sell Logic

## Inputs

- Active offers sorted by priority (descending)
- Consecutive pairs: anchor offer → next offer
- Platform hint (default: "youtube")

**Requires at least 2 active offers** to produce any rows. With N offers, produces `min(N-1, 8)` upsell pairs.

## Outputs

| Field | Description |
|---|---|
| `best_next_offer` | `{"offer_id": "...", "name": "...", "monetization_method": "..."}` |
| `best_timing` | One of: `after_first_conversion`, `day_3_email`, `post-checkout`, `webinar_close` |
| `best_channel` | Platform hint or one of: `email`, `youtube_description`, `sms`, `in_app` |
| `expected_take_rate` | `min(0.45, 0.08 + (next_epc / max(50, anchor_epc + 1)) * 0.12 + hash_var)` |
| `expected_incremental_value` | `max(next_epc, next_payout) * take_rate` |
| `best_upsell_sequencing` | `{"steps": ["order_bump", "core_upsell", "continuity"]}` |
| `confidence` | `min(0.94, 0.5 + take_rate * 1.2)` |
| `explanation` | "Upsell from {anchor} → {next} (EPC lift {n_epc})" |

## Pairing Strategy

Offers sorted by priority. Each consecutive pair `(i, i+1)` forms an anchor → next relationship. This models a natural escalation ladder where the highest-priority offer leads to the next.

## Persistence

### Table: `upsell_recommendations`

- `brand_id` UUID FK → brands (indexed)
- `opportunity_key` String(255), unique per brand — format: `upsell|{anchor_id}|{next_id}`
- `anchor_offer_id` UUID FK → offers (nullable)
- `anchor_content_item_id` UUID FK → content_items (nullable)
- All output fields above
- `is_active` Boolean, default true

Recompute deletes all rows for the brand, then inserts fresh pairs.

## API

- `GET /api/v1/brands/{brand_id}/upsell-recommendations`
- `POST /api/v1/brands/{brand_id}/upsell-recommendations/recompute`

## Worker

Celery beat task `refresh_all_upsell_recommendations` runs every 12 hours on the `revenue_ceiling` queue.

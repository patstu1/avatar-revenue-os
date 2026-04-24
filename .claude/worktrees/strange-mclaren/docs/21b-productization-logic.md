# Productization Logic

## Inputs

- Brand niche
- Brand target audience
- Deterministic variety via opportunity index (6 product types)

## Product Types

Six product archetypes are generated per brand:

1. `digital_course`
2. `template_pack`
3. `membership` (recurring)
4. `saas_tool` (recurring)
5. `community` (recurring)
6. `book_bundle`

## Outputs

| Field | Description |
|---|---|
| `product_recommendation` | Human-readable product name: "{Niche} {type} — pack {n}" |
| `product_type` | One of the 6 types above |
| `target_audience` | From brand or inferred: "{niche} creators ready to implement" |
| `price_range_min` / `price_range_max` | Preset bands per type (e.g. $47–$97, $297–$997) |
| `expected_launch_value` | Base 800 + hash variation + index multiplier |
| `expected_recurring_value` | Set for membership, saas_tool, community (~18% of launch); null otherwise |
| `build_complexity` | low / medium / high (deterministic from index + niche hash) |
| `confidence` | `min(0.92, 0.45 + index * 0.08 + hash / 800)` |
| `explanation` | Summary of niche, audience, and type rationale |

## Persistence

### Table: `product_opportunities`

- `brand_id` UUID FK → brands (indexed)
- `opportunity_key` String(255), unique per brand
- All output fields above
- `is_active` Boolean, default true

Recompute deletes all rows for the brand, then inserts 6 fresh rows.

## API

- `GET /api/v1/brands/{brand_id}/product-opportunities`
- `POST /api/v1/brands/{brand_id}/product-opportunities/recompute`

## Worker

Celery beat task `recompute_all_product_opportunities` runs every 6 hours on the `revenue_ceiling` queue.

# Offer Ladder Logic

For each **opportunity** (pairing of active offer × content item when content exists; otherwise one row per offer with a `no_content` key), the engine builds:

- **Top-of-funnel asset** — short-form / post title context.
- **First / second monetization steps** — primary CTA and follow-on nurture.
- **Upsell, retention, fallback paths** — structured JSON (`steps` arrays). Fallback favors capture (lead magnet, waitlist, remarketing) when conversion rate is low.
- **Economics** — `expected_first_conversion_value` (EPC × CVR × scalar), downstream and LTV heuristics, **friction** from CVR bands, **confidence** from EPC/CVR.

## Persistence

Recompute replaces all `offer_ladders` rows for the brand.

### Table: `offer_ladders`

| Column | Type | Notes |
|---|---|---|
| `brand_id` | UUID FK → brands | indexed |
| `opportunity_key` | String(255) | indexed, `offer:{id}\|content:{id}` |
| `content_item_id` | UUID FK → content_items | nullable |
| `offer_id` | UUID FK → offers | nullable |
| `top_of_funnel_asset` | String(500) | |
| `first_monetization_step` | Text | |
| `second_monetization_step` | Text | |
| `upsell_path` | JSONB | `{"steps": [...]}` |
| `retention_path` | JSONB | `{"steps": [...]}` |
| `fallback_path` | JSONB | `{"steps": [...]}` |
| `ladder_recommendation` | Text | |
| `expected_first_conversion_value` | Float | |
| `expected_downstream_value` | Float | |
| `expected_ltv_contribution` | Float | |
| `friction_level` | String(30) | low / medium / high |
| `confidence` | Float | 0..0.95 |
| `explanation` | Text | |
| `is_active` | Boolean | default true |

## API

- `GET /api/v1/brands/{brand_id}/offer-ladders` — list active ladders
- `POST /api/v1/brands/{brand_id}/offer-ladders/recompute` — delete + rebuild all ladders for brand

## Engine

`packages/scoring/revenue_ceiling_phase_a_engines.py`:

- `build_offer_ladder_for_opportunity()` — single ladder row from opportunity + economics
- `generate_offer_ladders()` — produces one ladder per offer × content pairing (capped at 8 offers × 15 content items)

## Worker

Celery beat task `recompute_all_offer_ladders` runs every 6 hours on the `revenue_ceiling` queue.

# Revenue Density Formulas

## Data Sources

Per **content item**, joined with:

- **`performance_metrics`** aggregated by `content_item_id` — sum of `revenue` and `impressions`
- **`creator_accounts`** — sum of `follower_count` for the brand (audience total, min 1)
- **`content_items.total_cost`** and **`content_items.monetization_density_score`** — existing fields

When no performance metrics exist for a content item, heuristic fallbacks are used:
- Impressions: `500 + hash(content_id) % 2000`
- Revenue: `monetization_density_score * 2.5 + 5.0`

## Formulas

| Metric | Formula |
|---|---|
| `revenue_per_content_item` | `total_revenue` (rounded) |
| `revenue_per_1k_impressions` | `(total_revenue / impressions) * 1000` |
| `profit_per_1k_impressions` | `((revenue - total_cost) / impressions) * 1000` |
| `profit_per_audience_member` | `(revenue - total_cost) / audience_total` |
| `monetization_depth_score` | `min(1.0, 0.15 + hash_var/100 + existing_score * 0.5)` |
| `repeat_monetization_score` | `min(1.0, 0.2 + (revenue / max(1, cost+1)) * 0.1 + depth * 0.25)` |
| `ceiling_score` | `min(1.0, 0.25 + depth * 0.35 + repeat * 0.25 + min(0.3, rpm/100))` |

## Recommendation Rules

| Condition | Recommendation |
|---|---|
| `ceiling_score > 0.72` | "Near ceiling on this asset — test new channel or premium offer" |
| `rpm > 15` | "Scale winners: duplicate format + add order bump" |
| Otherwise | "Improve CTA-to-offer match + add retargeting capture" |

## Persistence

### Table: `revenue_density_reports`

- `brand_id` UUID FK → brands (indexed)
- `content_item_id` UUID FK → content_items (indexed, unique per brand)
- All metric fields above
- `recommendation` Text

Recompute deletes all rows for the brand, then inserts one per content item (capped at 200).

## API

- `GET /api/v1/brands/{brand_id}/revenue-density` — includes `content_title` from content_items join
- `POST /api/v1/brands/{brand_id}/revenue-density/recompute`

## Worker

Celery beat task `recompute_all_revenue_density` runs every 6 hours on the `revenue_ceiling` queue.

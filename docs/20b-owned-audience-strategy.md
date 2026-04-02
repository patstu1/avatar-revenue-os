# Owned Audience Strategy

Six **asset types** are synthesized per content family: newsletter, lead magnet, waitlist, SMS opt-in, community, remarketing.

## Capabilities

- **Choose owned-audience objective per content family** — `owned_audience_objective_for_family()` routes to `direct_sale`, `owned_capture`, or `hybrid` based on a direct-vs-capture score.
- **Generate owned-audience CTA variants** — three CTA strings per asset/family combination.
- **Track opt-ins by source content** — `owned_audience_events` links content items to opt-in events.
- **Track value of each owned channel** — `estimated_channel_value` on each asset.
- **Score direct sale vs capture** — `direct_vs_capture_score` (0..1) determines routing.

## Persistence

### Table: `owned_audience_assets`

| Column | Type | Notes |
|---|---|---|
| `brand_id` | UUID FK → brands | indexed |
| `asset_type` | String(80) | indexed; newsletter / lead_magnet / waitlist / sms_opt_in / community / remarketing |
| `channel_name` | String(255) | display label |
| `content_family` | String(120) | indexed, nullable |
| `objective_per_family` | JSONB | `{"family": "direct_sale\|owned_capture\|hybrid"}` |
| `cta_variants` | JSONB | list of 3 CTA strings |
| `estimated_channel_value` | Float | |
| `direct_vs_capture_score` | Float | 0..1 |
| `is_active` | Boolean | default true |

### Table: `owned_audience_events`

| Column | Type | Notes |
|---|---|---|
| `brand_id` | UUID FK → brands | indexed |
| `content_item_id` | UUID FK → content_items | indexed, nullable |
| `asset_id` | UUID FK → owned_audience_assets | indexed, nullable |
| `event_type` | String(80) | indexed; newsletter_capture / lead_magnet_signup |
| `value_contribution` | Float | channel ROI tracking |
| `source_metadata` | JSONB | `{"content_title": "...", "engine": "..."}` |

## API

- `GET /api/v1/brands/{brand_id}/owned-audience` — returns `{assets: [...], events: [...]}`
- `POST /api/v1/brands/{brand_id}/owned-audience/recompute` — delete + rebuild assets and events

## Engine

`packages/scoring/revenue_ceiling_phase_a_engines.py`:

- `owned_audience_objective_for_family()` — routing logic
- `generate_owned_audience_assets()` — CTA variants and objectives per asset type × family
- `synthesize_owned_audience_events()` — links content items to opt-in events (synthetic; replaced by real webhook data when live)

## Worker

Celery beat task `recompute_all_owned_audience` runs every 6 hours on the `revenue_ceiling` queue.

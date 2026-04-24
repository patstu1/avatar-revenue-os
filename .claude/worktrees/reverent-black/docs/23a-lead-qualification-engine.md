# Expansion Pack 2 Phase A — Lead Qualification Engine

Scores every inbound demand signal (comments, DMs, emails, booked calls, forms, chat messages) across five dimensions, then tiers each lead as **hot**, **warm**, or **cold** and recommends a next action. All outputs are persisted in `lead_opportunities` and `lead_qualification_reports`.

---

## API

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/brands/{id}/lead-opportunities` | Any authenticated | All scored leads, ordered by `composite_score` desc. |
| `GET` | `/brands/{id}/lead-qualification` | Any authenticated | Aggregate qualification report for the brand. |
| `POST` | `/brands/{id}/lead-qualification/recompute` | OPERATOR | Re-scores all leads, rebuilds `lead_opportunities`, `closer_actions`, and `lead_qualification_reports`. |

---

## Inputs

| Parameter | Source | Description |
|---|---|---|
| `lead_source` | `CommentCluster` or synthetic | Channel: `comment` \| `dm` \| `email` \| `call_booked` \| `form` \| `chat` |
| `niche` | `Brand.niche` | Used for keyword overlap in `offer_fit_score` |
| `message_text` | `CommentCluster.cluster_label` | Raw text of the lead signal (truncated to 2 000 chars) |
| `audience_size` | `sum(CreatorAccount.follower_count)` | Total followers across platforms |
| `avg_offer_aov` | `avg(Offer.average_order_value)` | Brand average AOV |
| `avg_offer_cvr` | `avg(Offer.conversion_rate)` | Brand average CVR |
| `content_engagement_rate` | `avg(PerformanceMetric.engagement_rate)` | Brand average engagement rate |
| `existing_offer_count` | `count(Offer where is_active)` | Number of live offers |

---

## Scored Dimensions

| Dimension | Range | Formula | Source bonuses |
|---|---|---|---|
| `urgency_score` | 0–1 | Keyword scan (`need`, `asap`, `urgent`, `today`, `now`, `help`, `struggling`, etc.) | `call_booked` +0.20; `dm` +0.10 |
| `budget_proxy_score` | 0–1 | Keyword scan (`invest`, `budget`, `spend`, `afford`, `premium`, etc.) + `log10(AOV)/4.0` | `call_booked` +0.15 |
| `sophistication_score` | 0–1 | Keyword scan (`strategy`, `funnel`, `roi`, `conversion`, `scale`, etc.) | `len(msg) > 100` +0.10; `email`/`form` +0.10 |
| `offer_fit_score` | 0–1 | Niche keyword overlap + `min(offer_count/5, 0.30)` + `engagement × 10` capped at 0.20 | — |
| `trust_readiness_score` | 0–1 | Keyword scan (`recommend`, `trust`, `follow`, `fan`, `love`, `been watching`, etc.) | `call_booked` +0.25; `dm` +0.10 |

---

## Derived Outputs

| Field | Type | Formula |
|---|---|---|
| `composite_score` | float 0–1 | `urgency×0.20 + budget×0.20 + soph×0.15 + fit×0.20 + trust×0.25` |
| `qualification_tier` | enum | `hot` (≥0.65), `warm` (≥0.40), `cold` (<0.40) |
| `expected_value` | float | `urgency × budget × avg_offer_aov × 0.35` |
| `likelihood_to_close` | float 0–1 | `urgency×0.25 + budget×0.20 + fit×0.20 + trust×0.20 + soph×0.15` |
| `recommended_action` | enum | `book_call` (hot), `nurture_sequence` (warm), `low_priority_follow_up` (cold) |
| `confidence` | float 0–1 | `0.35 + composite×0.45 + min(0.20, len(msg)/500)` |
| `channel_preference` | string | Passthrough of `lead_source` |

---

## Logic

- **Lead data source**: `CommentCluster` rows are used as synthetic lead proxies. Each cluster's `cluster_label` is treated as `message_text` with `lead_source = "comment"`.
- **Synthetic fallback**: when no clusters exist, 3 synthetic leads are generated (`dm`, `call_booked`, `email`) so the closer action queue is never empty.
- **Keyword scanning**: case-insensitive substring matching. Each keyword hit adds `1/len(keywords) × 3.0`, clamped to [0, 1].
- **Delete order**: FK-safe — `CloserAction` → `LeadOpportunity` → `LeadQualificationReport`.
- **Aggregation**: the `LeadQualificationReport` row stores total_leads_scored, hot/warm/cold counts, avg_composite_score, avg_expected_value, top_channel, top_recommended_action, signal_summary (JSONB).

---

## Table: `lead_opportunities`

One row per inbound lead signal. Recompute deletes and replaces all rows for the brand.

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier |
| `brand_id` | UUID FK → `brands.id` | Brand scope |
| `lead_source` | String(80) | Origin channel |
| `message_text` | Text | Raw lead message |
| `urgency_score` | Float | 0–1 |
| `budget_proxy_score` | Float | 0–1 |
| `sophistication_score` | Float | 0–1 |
| `offer_fit_score` | Float | 0–1 |
| `trust_readiness_score` | Float | 0–1 |
| `composite_score` | Float | 0–1 |
| `qualification_tier` | String(20) | `hot` \| `warm` \| `cold` |
| `recommended_action` | String(80) | Next action |
| `expected_value` | Float | Monetised prospect value |
| `likelihood_to_close` | Float | 0–1 |
| `channel_preference` | String(50) | Echo of `lead_source` |
| `confidence` | Float | 0–1 |
| `explanation` | Text | Human-readable summary |
| `is_active` | Boolean | Soft-delete flag |

## Table: `lead_qualification_reports`

One row per brand (unique constraint). Recompute replaces.

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier |
| `brand_id` | UUID FK → `brands.id` | Unique per brand |
| `total_leads_scored` | Integer | Count |
| `hot_leads` | Integer | Hot tier count |
| `warm_leads` | Integer | Warm tier count |
| `cold_leads` | Integer | Cold tier count |
| `avg_composite_score` | Float | Average |
| `avg_expected_value` | Float | Average |
| `top_channel` | String(50) | Most common channel |
| `top_recommended_action` | String(80) | Most common action |
| `signal_summary` | JSONB | Channel + action breakdowns |
| `confidence` | Float | 0–1 |
| `explanation` | Text | Summary |
| `is_active` | Boolean | Soft-delete flag |

---

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_lead_qualification` | Every 6 h (minute :02) | `revenue_ceiling` |

Runs Lead Qualification then Sales Closer in a single task; rebuilds `lead_opportunities`, `closer_actions`, and `lead_qualification_reports` for all active brands.

---

## Scoring Engine

**File**: `packages/scoring/expansion_pack2_phase_a_engines.py` — function `score_lead()`.

Pure function, no I/O, no SQLAlchemy. Returns a dict with all scored dimensions plus `EP2A: True` marker.

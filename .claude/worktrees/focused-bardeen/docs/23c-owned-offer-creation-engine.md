# Expansion Pack 2 Phase A — Owned Offer Creation Engine

Continuously monitors comment cluster themes, funnel objection patterns, content engagement signals, and audience segment data to detect repeated demand, then surfaces specific owned-product opportunities with offer type, price range, demand score, and estimated first-month revenue. All outputs are persisted in `owned_offer_recommendations`.

---

## API

| Method | Path | Role | Description |
|---|---|---|---|
| `GET` | `/brands/{id}/owned-offer-recommendations` | Any authenticated | All recommendations, ordered by `estimated_demand_score` desc. |
| `POST` | `/brands/{id}/owned-offer-recommendations/recompute` | OPERATOR | Re-evaluates all 7 detection rules, deletes and rebuilds `owned_offer_recommendations`. |

---

## Inputs

| Parameter | Source | Description |
|---|---|---|
| `niche` | `Brand.niche` | Used in rule evaluation and rationale generation |
| `brand_name` | `Brand.name` | Used in recommendation rationale strings |
| `top_comment_themes` | `CommentCluster.cluster_label` (limit 20) | Most common comment topics |
| `top_objections` | `FunnelLeakFix.suspected_cause` (limit 10) | Most common sales objections |
| `content_engagement_signals` | `ContentItem` + `PerformanceMetric` join | title, impressions, engagement_rate, revenue per item |
| `audience_segments` | `AudienceSegment` rows | name, estimated_size, avg_ltv, conversion_rate |
| `existing_offer_types` | `Offer.monetization_method` (active) | Current offer types for duplicate suppression |
| `total_audience_size` | `sum(CreatorAccount.follower_count)` | Total followers across platforms |
| `avg_monthly_revenue` | `sum(PerformanceMetric.revenue) / 12` | Monthly revenue proxy |

---

## Detection Rules

All 7 rules are evaluated in order; each triggered rule produces a recommendation row (max 8 total after deduplication).

| Rule | Signal source | Trigger condition | Recommended offer | Price range |
|---|---|---|---|---|
| `repeated_question` | `CommentCluster` themes | ≥ 2 clusters with question-pattern labels | `digital_course` or `template_pack` | $47–$297 |
| `repeated_objection` | `FunnelLeakFix.suspected_cause` | ≥ 1 objection string present | `coaching_program` | $297–$1,497 |
| `high_interest_low_conversion` | `ContentItem` + `PerformanceMetric` | Any item with `engagement_rate > 0.05` and revenue < $50 | `digital_course` | $97–$497 |
| `high_trust_weak_affiliate` | `AudienceSegment` | Any segment with `CVR < 0.02` and `LTV > 200` | `membership` or `consulting_retainer` | $29–$997 |
| `strong_owned_engagement` | `AudienceSegment` | Any segment with `size > 1000` and no existing membership | `membership` | $19–$97 |
| `educational_traffic` | `ContentItem` title + impressions | Title contains `how`/`tutorial`/`guide` AND `impressions > 5000` | `template_pack` or `swipe_file` | $27–$97 |
| `manual_request_pattern` | `CommentCluster` themes | Any theme contains `help`/`tool`/`template`/`checklist` | `swipe_file` | $17–$47 |

---

## Outputs — `owned_offer_recommendations`

| Field | Type | Description |
|---|---|---|
| `opportunity_key` | string | Slugified unique key per signal_type + slug_suffix |
| `signal_type` | string | Detection rule identifier |
| `detected_signal` | string | Human-readable description of the triggering signal |
| `recommended_offer_type` | string | `digital_course` \| `template_pack` \| `coaching_program` \| `membership` \| `consulting_retainer` \| `swipe_file` |
| `offer_name_suggestion` | string | AI-generated offer name using brand + niche + topic |
| `price_point_min` | float | Lower bound of recommended price range (USD) |
| `price_point_max` | float | Upper bound of recommended price range (USD) |
| `estimated_demand_score` | float 0–1 | Composite demand score |
| `estimated_first_month_revenue` | float | `demand_score × audience_size × 0.001 × price_min` |
| `audience_fit` | string | Description of which audience segment this serves |
| `confidence` | float 0–1 | `0.35 + demand×0.45 + clamp(revenue/20000)×0.20` |
| `explanation` | string | Human-readable justification |
| `build_priority` | enum | `high` (demand > 0.60), `medium` (> 0.35), `low` (otherwise) |

---

## Demand Score Formula

```
estimated_demand_score =
    (log10(max(total_audience_size, 1)) / 6.0) × 0.40
  + clamp(avg_monthly_revenue / 5000.0, 0.0, 1.0) × 0.30
  + deterministic_hash_variation(opportunity_key) × 0.30
```

The hash variation term is derived from `hash(opportunity_key) % 1000 / 1000.0`, ensuring stable scores across recompute cycles when inputs have not changed.

---

## Deduplication

- Via `seen_keys` set: each opportunity_key (slugified `signal_type + slug_suffix`) must be unique.
- Max 8 results per evaluation run.
- `strong_owned_engagement` and `manual_request_pattern` rules break after the first match to avoid flooding.

---

## Table: `owned_offer_recommendations`

One row per triggered detection rule per brand (after dedup). Fully deleted and rebuilt on every recompute.

| Column | Type | Description |
|---|---|---|
| `id` | UUID PK | Row identifier |
| `brand_id` | UUID FK → `brands.id` | Brand scope |
| `opportunity_key` | String(255) | Unique per brand (UQ constraint) |
| `signal_type` | String(80) | Detection rule identifier |
| `detected_signal` | Text | Triggering signal description |
| `recommended_offer_type` | String(80) | Product type |
| `offer_name_suggestion` | String(500) | AI-generated name |
| `price_point_min` | Float | Lower price bound |
| `price_point_max` | Float | Upper price bound |
| `estimated_demand_score` | Float | 0–1 |
| `estimated_first_month_revenue` | Float | Projected revenue |
| `audience_fit` | Text | Audience description |
| `confidence` | Float | 0–1 |
| `explanation` | Text | Justification |
| `build_priority` | String(20) | `high` \| `medium` \| `low` |
| `is_active` | Boolean | Soft-delete flag |

---

## Worker

| Task | Schedule | Queue |
|---|---|---|
| `recompute_all_owned_offer_recommendations` | Every 8 h (minute :08) | `revenue_ceiling` |

Runs Owned Offer Creation for all active brands. Inputs (comment clusters, funnel leak fixes, content performance) update on slower cadences than lead signals, hence the longer interval.

---

## Scoring Engine

**File**: `packages/scoring/expansion_pack2_phase_a_engines.py` — function `detect_offer_opportunities()`.

Pure function, no I/O, no SQLAlchemy. Returns a list of up to 8 dicts, each with all output fields plus `EP2A: True` marker.

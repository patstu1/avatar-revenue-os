# Phase 6 — Growth intelligence (segments, LTV, leaks, expansion, paid, trust)

## Architecture: read vs recompute

Phase 6 follows the same pattern as Phase 5:

- **POST** `/brands/{id}/growth-intel/recompute` — runs all engines, cleans prior Phase 6 rows, persists fresh outputs. Requires operator role.
- **GET** endpoints — read persisted data only. No mutations, no hidden syncs.
- **Dashboard loads** use persisted data. The UI has a "Recompute growth intel" button.

### Persistence lifecycle

1. Operator clicks "Recompute growth intel" (or a scheduled worker calls the recompute endpoint).
2. `recompute_growth_intel` cleans all Phase 6-owned rows for the brand (identified by `phase6_auto` flags, `[phase6 auto]` rationale prefix, `is_candidate=true`, `expansion_type="cross_platform_and_geo"`).
3. Engines run and insert fresh rows: segments, LTV models, leak reports, geo/language recs, trust reports, paid candidates, one `ExpansionDecision`.
4. GETs return whatever was last persisted.

### Duplicate prevention

Recompute deletes prior Phase 6 `ExpansionDecision` rows (by `expansion_type`) before inserting a new one. Repeated recomputes produce one active decision row, not an accumulating stack.

---

## Segmentation method

Audience segments are **rules-based clusters** in `packages/scoring/growth_intel.cluster_segments_rules`: one cluster per combination of **platform × geography × language × niche_focus** for active creator accounts. Each row persisted in `audience_segments` sets `segment_criteria.phase6_auto = true` for idempotent cleanup.

## LTV assumptions

`estimate_ltv_rules` is a **deterministic heuristic**, not ML. It blends payout / AOV, offer conversion rate, recurring vs one-off uplift, and multipliers for geography (tier-1 vs other), platform (YouTube / TikTok / default), and language (English vs non-English). Horizons **30d / 90d / 365d** are scaled factors on that base. Dimensions stored in `ltv_models.parameters.dimensions` with `phase6_auto: true`.

## Leak detection rules

`detect_leaks` emits rows for:

| Signal | Rule (simplified) |
|--------|-------------------|
| High views, low clicks | Impressions ≥ 3k and CTR < 0.6% |
| High clicks, low conversions | Clicks ≥ 200 and CVR < 0.8% |
| Strong content, weak offer fit | Engagement high vs RPM low vs EPC potential |
| Good retention, poor monetization | Avg watch ≥ 40%, RPM low, impressions ≥ 1.5k |
| High cost, low return | Cost > $20, profit negative, cost sizeable vs revenue |
| Strong audience, weak funnel | Follower growth ≥ 2% but CTR < 1% on volume; **or** brand funnel impressions ≥ 5k with soft CTR/conversion |

Persisted in `revenue_leak_reports` with `details.phase6_engine: true`.

## Geo / language rules

`geo_language_expansion_rules` adds recommendations when the portfolio is **concentrated**: single geography (suggest EU-5), English-only (suggest Spanish / LATAM), or TikTok without YouTube (suggest long-form). Rows use rationale prefix `[phase6 auto]`.

## Paid winner gating

`paid_amplification_candidates` calls `detect_winners` and only creates **candidate** `paid_amplification_jobs` when `is_winner` and `win_score >= 0.5`, and the content id is not already in paid jobs. Candidates are marked `is_candidate = true`.

## Trust scoring logic

`trust_score_for_account` scores **0–100** from account health, posting consistency, originality drift (penalty), fatigue (penalty), and average engagement from rollups. String **recommendations** are heuristic tips. Persisted in `trust_signal_reports` with `confidence_label` high / medium / low from score bands.

## API

| Method | Path | Side effects |
|--------|------|-------------|
| POST | `/api/v1/brands/{id}/growth-intel/recompute` | Writes all Phase 6 outputs |
| GET | `/api/v1/brands/{id}/audience-segments` | Read-only |
| GET | `/api/v1/brands/{id}/ltv` | Read-only |
| GET | `/api/v1/dashboard/leaks?brand_id=` | Read-only |
| GET | `/api/v1/brands/{id}/expansion-recommendations` | Read-only |
| GET | `/api/v1/brands/{id}/paid-amplification` | Read-only |
| GET | `/api/v1/brands/{id}/trust-signals` | Read-only |
| GET | `/api/v1/dashboard/growth-intel?brand_id=` | Read-only (bundled) |

## UI

**Growth Intel** (`/dashboard/growth`) with recompute button and 8 tabs: funnel summary, segments, LTV, leaks, geo/language, cross-platform flow, paid amplification, trust.

## Tests

- Unit: `tests/unit/test_growth_intel.py` (segmentation, LTV, leaks, geo, paid gating, cross-platform planner, trust).
- Integration: `tests/integration/test_growth_flow.py` (recompute-then-read, GETs-are-side-effect-free, no-duplicate-decisions, dashboard wiring, all brand routes).

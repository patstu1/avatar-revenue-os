# Phase 5 — Scale intelligence & AI Scale Command Center

## Purpose

Phase 5 turns portfolio-level performance into **actionable scale decisions**: when to push volume on existing accounts, when to add a new account (and what type), how to allocate capacity across platforms, and how to avoid cannibalization and saturation. Decisions are **persisted** as `ScaleRecommendation`, `ScaleDecision`, `PortfolioAllocation`, and `AllocationDecision` rows.

## Data model

| Table | Role |
|-------|------|
| `scale_recommendations` | Human-readable recommendation key, incremental profit comparisons, readiness/cannibalization/separation/confidence, weekly plan JSON, best-next-account JSON |
| `scale_decisions` | Canonical decision record for each recompute (inputs, formulas pointer, scores) |
| `account_portfolios` | Brand-level portfolio container (totals, health, strategy) |
| `portfolio_allocations` | Per–creator-account weights (% posting capacity / notional budget) |
| `allocation_decisions` | Snapshot of last allocation rebalance |

`creator_accounts.scale_role` stores **`flagship`** | **`experimental`** (optional). Seed and recompute logic default to **highest-profit = flagship**, next = **experimental** when roles are missing.

## Scale metrics (per account)

Surfaced in the command center from `CreatorAccount` + rollups: revenue, profit, profit per post, RPM (`revenue_per_mille`), CTR, conversion rate, follower growth, content fatigue, niche saturation, offer performance proxy (brand offer averages), account health, originality drift, posting capacity, diminishing returns.

## Calculations (`packages/scoring/scale.py`)

| Output | Meaning |
|--------|---------|
| **ScaleReadinessScore** | 0–100 composite: health, inverse fatigue/saturation, CTR/CVR, inverse diminishing returns, follower growth, originality, offer blend |
| **IncrementalProfitOfNewAccount** | Weekly-style uplift from cloning best `profit_per_post` × capacity × expansion confidence × (1 − cannibalization) − **fixed overhead** ($150) |
| **IncrementalProfitOfMoreVolumeOnExistingAccounts** | Σ `profit_per_post × posting_capacity × VOLUME_LIFT × (1 − diminishing_returns)` |
| **CannibalizationRisk** | Pairwise niche Jaccard on niche fields, boosted when **same platform** |
| **AudienceSegmentSeparation** | `1 − cannibalization_risk` (portfolio proxy) |
| **ExpansionConfidence** | Volume of impressions + share of profitable accounts |

Default rule: **only recommend more accounts when** `incremental_new > incremental_existing × 1.15` (constant `EXPANSION_BEATS_EXISTING_RATIO`), subject to funnel and offer-quality gates.

## Recommendation keys

Persisted `recommendation_key` examples: `do_not_scale_yet`, `scale_current_winners_harder`, `add_experimental_account`, `add_niche_spinoff_account`, `add_offer_specific_account`, `add_platform_specific_account`, `add_localized_language_account`, `add_evergreen_authority_account`, `add_trend_capture_account`, `reduce_or_suppress_weak_account`, `improve_funnel_before_scaling`, `add_new_offer_before_adding_account`.

Coarse `RecommendedAction` enum on the row is derived for ORM compatibility (`scale` / `maintain` / `experiment` / …).

## Cannibalization rules

- Token Jaccard on `niche_focus` + `sub_niche_focus` pairs.  
- Multiply by **platform overlap factor** (1.0 same platform, 0.35 cross-platform).  
- Portfolio risk = clamped average over pairs × 1.25.  
- High risk steers recommendations toward **niche spinoff** or **localization** instead of cloning the same angle.

## API

| Method | Path |
|--------|------|
| GET | `/api/v1/dashboard/scale-command-center?brand_id=` |
| GET | `/api/v1/brands/{id}/scale-recommendations` |
| POST | `/api/v1/brands/{id}/scale-recommendations/recompute` |
| GET | `/api/v1/brands/{id}/portfolio-allocations` |
| POST | `/api/v1/brands/{id}/portfolio-allocations/recompute` |

Recompute endpoints require **operator** or higher. The command center uses **read-only** revenue-leak preview (`preview_revenue_leaks`) so GET does not persist suppressions.

## Frontend

`/dashboard/scale` — **AI Scale Command Center** (10 sections).  
`/dashboard/trend-scanner` — Phase 2 trend table (moved from old scale route).

## Tests

- `tests/unit/test_scale_engine.py` — math, cannibalization, readiness, recommendation branching.  
- `tests/integration/test_scale_flow.py` — API recompute, allocation sum ≈ 100%, command center shape (needs Postgres test DB / Docker).

## Verification & audit checklist (Phase 5)

Use this to confirm the build matches the approved scope:

| Area | What to verify |
|------|----------------|
| Scale recommendations | `POST .../scale-recommendations/recompute` persists rows with `recommendation_key`, `comparison_ratio`, `score_components`, `penalties`, `best_next_account`, `weekly_action_plan`; `GET` returns primary rows before `reduce_or_suppress_weak_account`. |
| Portfolio overview | Command center `portfolio_overview.totals` sums revenue/profit across active accounts; table lists per-account Phase 5 metrics. |
| New account vs volume | `incremental_tradeoff` in command center shows both incrementals, ratio, threshold **1.15**, and interpretation string; engine constants repeated under `audit.formula_constants`. |
| Cannibalization | Portfolio-level warning when `cannibalization_risk_score > 0.5` on primary rec; engine uses niche Jaccard × platform factor. |
| Growth blockers | `growth_blockers` = `classify_bottlenecks` per active account (Phase 4 dependency). |
| Weekly plan | Primary recommendation’s `weekly_action_plan.days` echoed in command center. |
| UI | `/dashboard/scale` calls `GET /dashboard/scale-command-center?brand_id=`; tradeoff + totals + audit constants visible after recompute. |
| Tests | `tests/unit/test_scale_engine.py` (pure math); `tests/integration/test_scale_flow.py` (API + persistence; requires Postgres). |
| Migration | `f8a1c2d3e4b5_phase5_scale_command_center` applied on target DB. |

## Honest limits (Phase 5 scope)

- No full **LTV**, sponsor, paid amplification, or roadmap optimizers—only the dependencies needed for scale.heuristics.  
- **Audience segments** are proxied via niche text + platform separation, not first-party cohort ingestion.  
- **Incremental profit** models are heuristic (weekly baseline, fixed overhead), not media-mix or causal lift measurement.

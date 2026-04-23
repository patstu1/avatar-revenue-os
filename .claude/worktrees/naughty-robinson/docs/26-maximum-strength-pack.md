# Maximum Strength Pack (MXP)

The Maximum Strength Pack adds 11 operational intelligence modules to the AI Avatar Revenue OS.
Each module runs on a dedicated engine → service → API → dashboard pipeline with persisted state, audit logs, and scheduled recompute via Celery workers.

---

## 1. Experiment Engine

**Purpose:** Prioritises A/B experiments by expected upside and confidence gap, evaluates outcomes from **rules-based (synthetic_proxy) observations**, and persists an **operator action queue** — not automatic rollout to ad platforms (see `docs/33-mxp-influence-and-experiment-loop.md`).

**Tables:** `experiment_decisions`, `experiment_outcomes`, `experiment_outcome_actions`

**Engine:** `packages/scoring/experiment_decision_engine.py` — `prioritize_experiment_candidates()`, `evaluate_experiment_outcome()`

**API:** `GET .../experiment-decisions`, `GET .../experiment-outcomes`, `GET .../experiment-outcome-actions`, `POST .../experiment-decisions/recompute`, `POST .../experiment-outcomes/recompute`

**Worker:** `recompute_all_experiment_decisions` — every 6 hours (persists **decisions, outcomes, and downstream action rows** in one pass)

**Dashboard:** `/dashboard/experiment-decisions`

**Outcome-only refresh:** `POST /api/v1/brands/{brand_id}/experiment-outcomes/recompute`

**Details:** See `docs/33-mxp-influence-and-experiment-loop.md`.

---

## 2. Attribution (Contribution)

**Purpose:** Multi-touch attribution engine that scores every content piece, account, and offer on its contribution to revenue.

**Tables:** `contribution_reports`, `attribution_model_runs`

**Engine:** `packages/scoring/contribution_engine.py` — `compute_contribution_reports()`, `compare_attribution_models()`

**API:** `GET /api/v1/brands/{brand_id}/contribution-reports`, `POST /api/v1/brands/{brand_id}/contribution-reports/recompute`

**Worker:** `recompute_all_contribution_reports` — every 8 hours

**Dashboard:** `/dashboard/contribution`

---

## 3. Capacity

**Purpose:** Monitors production throughput (content generation, video rendering, posting queues) and recommends throttle/allocation decisions so the brand never over- or under-produces.

**Tables:** `capacity_reports`, `queue_allocation_decisions`

**Engine:** `packages/scoring/capacity_engine.py` — `compute_capacity_reports()`, `allocate_queues()`

**API:** `GET /api/v1/brands/{brand_id}/capacity-reports`, `GET .../queue-allocations`, `POST .../capacity-reports/recompute`

**Worker:** `recompute_all_capacity` — every 6 hours

**Dashboard:** `/dashboard/capacity`

---

## 4. Offer Lifecycle

**Purpose:** Tracks every offer through states (nascent → active → fatigued → sunset) with health, decay, and dependency-risk scores. Recommends next action per offer.

**Tables:** `offer_lifecycle_reports`, `offer_lifecycle_events`

**Engine:** `packages/scoring/offer_lifecycle_engine.py` — `assess_offer_lifecycle()`, `recommend_lifecycle_transition()`

**API:** `GET /api/v1/brands/{brand_id}/offer-lifecycle-reports`, `GET .../offer-lifecycle-events`, `POST .../offer-lifecycle-reports/recompute`

**Worker:** `recompute_all_offer_lifecycle` — every 8 hours

**Dashboard:** `/dashboard/offer-lifecycle`

---

## 5. Creative Memory

**Purpose:** Stores reusable content atoms (hooks, CTAs, angles, formats) with performance metadata and originality-caution scoring so the system can recycle winners without staleness.

**Tables:** `creative_memory_atoms`, `creative_memory_links`

**Engine:** `packages/scoring/creative_memory_engine.py` — `index_atom()`, `recommend_reuse()`, `score_originality()`

**API:** `GET /api/v1/brands/{brand_id}/creative-memory-atoms`, `POST /api/v1/brands/{brand_id}/creative-memory-atoms/recompute`

**Worker:** `recompute_creative_memory` — every 8 hours

**Dashboard:** `/dashboard/creative-memory`

---

## 6. Recovery Engine

**Purpose:** Detects performance incidents (conversion drops, engagement collapses, revenue dips) and prescribes recovery actions with expected-effect estimates.

**Tables:** `recovery_incidents`, `recovery_actions`

**Engine:** `packages/scoring/recovery_engine.py` — `detect_recovery_incidents()`, `recommend_recovery_actions()`

**API:** `GET /api/v1/brands/{brand_id}/recovery-incidents`, `POST /api/v1/brands/{brand_id}/recovery-incidents/recompute`

**Worker:** `recompute_all_recovery_incidents` — every 4 hours (`mxp` queue)

**Dashboard:** `/dashboard/recovery`

---

## 7. Deal Desk

**Purpose:** Generates deal-strategy recommendations for sponsor negotiations — pricing stance, packaging, expected margin, and close probability per deal scope.

**Tables:** `deal_desk_recommendations`, `deal_desk_events`

**Engine:** `packages/scoring/deal_desk_engine.py` — `recommend_deal_strategy()`

**API:** `GET /api/v1/brands/{brand_id}/deal-desk`, `POST /api/v1/brands/{brand_id}/deal-desk/recompute`

**Worker:** `recompute_all_deal_desk` — every 8 hours (`mxp-deal-desk-every-8h`)

**Dashboard:** `/dashboard/deal-desk`

---

## 8. Audience State

**Purpose:** Models each audience segment as a state machine (unaware → curious → evaluating → committed → lapsed) with transition probabilities and best-next-action per state.

**Tables:** `audience_state_reports`, `audience_state_events`

**Engine:** `packages/scoring/audience_state_engine.py` — `compute_state()`, `predict_transitions()`

**API:** `GET /api/v1/brands/{brand_id}/audience-states`, `POST /api/v1/brands/{brand_id}/audience-states/recompute`

**Worker:** `recompute_audience_state` — every 6 hours

**Dashboard:** `/dashboard/audience-state`

---

## 9. Reputation Monitor

**Purpose:** Scans for brand-reputation risk (negative comments, review sentiment, compliance gaps) and recommends mitigation actions before damage compounds.

**Tables:** `reputation_reports`, `reputation_events`

**Engine:** `packages/scoring/reputation_engine.py` — `assess_reputation()`

**API:** `GET /api/v1/brands/{brand_id}/reputation`, `GET .../reputation-events`, `POST .../reputation/recompute`

**Worker:** `recompute_all_reputation` — every 12 hours (`mxp` queue)

**Dashboard:** `/dashboard/reputation-monitor`

---

## 10. Market Timing

**Purpose:** Detects macro and seasonal signals (tax season, holiday spending, algorithm shifts) and scores the timing window so the brand can surge or pull back content/offers.

**Tables:** `market_timing_reports`, `macro_signal_events`

**Engine:** `packages/scoring/market_timing_engine.py` — `evaluate_market_timing()`

**API:** `GET /api/v1/brands/{brand_id}/market-timing`, `GET .../macro-signal-events`, `POST .../market-timing/recompute`

**Worker:** `recompute_all_market_timing` — every 12 hours (`mxp` queue)

**Dashboard:** `/dashboard/market-timing`

---

## 11. Kill Ledger

**Purpose:** Records deliberate kills (retired content families, sunset offers, dropped accounts) with performance snapshots and replacement recommendations, plus hindsight reviews to improve future kill decisions.

**Tables:** `kill_ledger_entries`, `kill_hindsight_reviews`

**Engine:** `packages/scoring/kill_ledger_engine.py` — `evaluate_kill_candidates()`, `review_kill_hindsight()`

**API:** `GET /api/v1/brands/{brand_id}/kill-ledger` (bundle: `entries`, `hindsight_reviews`, `entries_with_hindsight`), `POST /api/v1/brands/{brand_id}/kill-ledger/recompute` (kill detection + hindsight refresh)

**Worker:** `recompute_all_kill_ledger` — every 12 hours (`mxp-kill-ledger-every-12h`)

**Dashboard:** `/dashboard/kill-ledger`

---

## Architecture Summary

| Module | Tables | Engine | Schedule (see `workers/celery_app.py`) |
|---|---|---|---|
| Experiment Engine | 2 | experiment_decision_engine | 6h |
| Attribution | 2 | contribution_engine | 8h |
| Capacity | 2 | capacity_engine | 6h |
| Offer Lifecycle | 2 | offer_lifecycle_engine | 8h |
| Creative Memory | 2 | creative_memory_engine | 12h |
| Recovery Engine | 2 | recovery_engine | 4h |
| Deal Desk | 2 | deal_desk_engine | 8h |
| Audience State | 2 | audience_state_engine | 8h |
| Reputation | 2 | reputation_engine | 12h |
| Market Timing | 2 | market_timing_engine | 12h |
| Kill Ledger | 2 | kill_ledger_engine | 12h |

**Total:** 22 tables, 11 engines, 11 API router pairs, 11 dashboard pages.

**Schema migrations:** Linear Alembic history includes Phase A+B (`y5z6a7b8c9d0`: `experiment_decisions` … `audience_state_events`), then **`z1a2b3c4d5e6`** (experiment outcome action queue + `observation_source` on outcomes). Earlier revisions add Phase C recovery/reputation/market timing (`v0w1x2y3z4a5`), Phase D deal desk / kill ledger (`w1x2y3z4a5b6`), and hindsight uniqueness on reviews (`x3y4z5a6b7c8`). Run `alembic -c packages/db/alembic.ini upgrade head` with project root on `PYTHONPATH`.

All modules follow the standard Revenue OS pattern: thin route handler → service layer → scoring engine → persisted state with audit logs on POST recompute. No mutation-on-read. All recompute flows are explicit POST or background-task paths.

**Caveats (honest):** Cross-module influence (e.g. audience state or market timing feeding deal desk or growth commands) is **not** wired as automated downstream inputs—each module reads shared core data (brand, offers, metrics) independently. Contribution and kill hindsight use **rules + stored metrics**, not live ad-network APIs.

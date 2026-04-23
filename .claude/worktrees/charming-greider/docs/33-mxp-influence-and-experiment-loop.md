# MXP: Experiment loop and cross-module influence

This document describes **implemented** (not aspirational) wiring as of the MXP correction pass.

## Experiment outcomes — persisted path

1. **`POST /api/v1/brands/{brand_id}/experiment-decisions/recompute`** (and Celery `recompute_all_experiment_decisions`) runs `recompute_experiment_decisions`.
2. The service:
   - Loads **prior scope signals** from existing `experiment_outcomes` joined to `experiment_decisions` (deduped by scope).
   - Deletes prior `experiment_outcomes` and active `experiment_decisions` for the brand.
   - Builds candidate experiments from offers and content; **offer lifecycle** skews expected upside (fatigued/sunset offers deprioritized; healthy active offers boosted).
   - Applies **`apply_prior_scope_signals`** so historical **promote / suppress / continue** outcomes adjust `expected_upside` before scoring.
   - Runs **`prioritize_experiment_candidates`**, inserts **`experiment_decisions`** with `explanation_json.downstream` describing prior-signal and lifecycle influence.
   - For each new decision, builds **synthetic observed metrics** from offers / content / performance (rules-based proxies, not live ad APIs) and runs **`evaluate_experiment_outcome`**, then inserts **`experiment_outcomes`** with `observation_source='synthetic_proxy'`, winner/loser ids, confidence, uplift, recommended next action, and `data_boundary` + `scope_snapshot` in `explanation_json`.
   - For each outcome row, inserts **`experiment_outcome_actions`**: one execution-queue row per outcome with `execution_status='pending_operator'`, `structured_payload_json` (recommended operator steps, scope, variant ids), and an operator note that execution is **not** auto-applied to external channels.

3. **`POST /api/v1/brands/{brand_id}/experiment-outcomes/recompute`** re-runs outcome evaluation **only** for the current active decision set (no full decision rebuild) and rebuilds outcome rows + downstream action rows.

**Synthetic vs real:** `observation_source` on outcomes is **`synthetic_proxy`** until a future **`live_import`** path (or equivalent) ingests real platform stats. API responses and the dashboard label outcomes accordingly; operators should treat `synthetic_proxy` as planning signal only.

## Downstream effects (closed loop within MXP)

- **Next prioritization run:** prior outcome signals **change** input `expected_upside` per scope before scoring.
- **Promotion / suppression:** Engine rules remain defaults; **scope-level** historical outcomes **shift** who gets priority (not automatic variant rollout to production systems).
- **Operator action queue:** `experiment_outcome_actions` is the **structured handoff** after an outcome exists (not the end state). Status **pending_operator** means no external system has been wired yet.
- **Creative memory:** `recompute_creative_memory` reads `experiment_outcomes`, applies **`experiment_outcome_confidence_boost`** to atom confidence, and may append an **`experiment_learned_signal`** atom summarizing outcome counts.

## Cross-module influence (real code paths)

| Source | Target | Mechanism |
|--------|--------|-----------|
| **Audience state** (`audience_state_reports`) | **Deal desk** | Average `state_score` scales **lead_quality** on every deal context before `recommend_deal_strategy`. Persisted in `explanation_json.cross_module_influence` / `adjusted_inputs`. |
| **Market timing** (`market_timing_reports`, latest active) | **Deal desk** | `timing_score` scales **urgency** on every deal context. Same persistence as above. |
| **Market timing** (latest active) | **Experiment decisions** | `timing_score` scales **expected_upside** on all candidate experiments before prior-scope signals and prioritization; `explanation_json.downstream.market_timing_influence` and recompute summary `market_timing_influence`. |
| **Contribution** (`contribution_reports`, active scope rows) | **Deal desk** | When a report’s `(scope_type, scope_id)` matches a deal context, **lead_quality** is blended with `contribution_score` (read at recompute). `adjusted_inputs.contribution_score_applied` when used. |
| **Offer lifecycle** (`offer_lifecycle_reports`) | **Experiment decisions** | Lifecycle state + health **skew expected_upside** for offer-scoped experiments; notes in `explanation_json.downstream.offer_lifecycle_gates`. |

**Not implemented:** Automated writes from these modules into each other’s tables (no shared “orchestration” table). Influence is **read at recompute** and reflected in outputs.

## Migrations

Run **`alembic -c packages/db/alembic.ini upgrade head`** so all MXP tables exist, including Phase A+B (`y5z6a7b8c9d0`) and **`z1a2b3c4d5e6`** (outcome action queue + `observation_source` on outcomes).

## What remains partial / not a closed loop

- Synthetic experiment observations are **not** replaced by live A/B platform stats without adapters and credentials.
- Deal desk does not **write back** to audience or market-timing tables.
- Promotion/suppression **execution** in external ad/content tools is **not automated**; the **`experiment_outcome_actions`** queue is the persisted handoff until connectors are added.

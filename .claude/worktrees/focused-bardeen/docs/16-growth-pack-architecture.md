# Revenue Growth Commander / Portfolio Launch Architecture Pack

## Scope

This pack delivers persisted **growth commands** (canonical schema), **portfolio launch plans**, **account launch blueprints**, **platform allocation**, **niche deployment**, **growth blocker reports** (pack-specific `growth_blocker_reports`), **capital deployment**, **cross-account cannibalization**, and **portfolio output governor** reports — plus the **Operator Growth Command Center** UI and **scheduled workers**.

Scale Alerts remain a separate subsystem; this pack composes on **scale recommendations**, **launch candidates**, **scale blockers** (read-only input), leaks, and readiness — it does not replace Scale Alerts processing.

## Engines (deterministic)

| Logical engine | Location | Role |
|----------------|----------|------|
| Revenue Growth Commander | `packages/scoring/growth_commander.py` | Command generation, comparison, portfolio directive |
| Portfolio Launch Architecture | `packages/scoring/growth_pack/orchestrator.py` | Launch plan, blueprints, 90-day envelope |
| Growth Command Generator | Same + `canonical_fields_from_command` | Normalized command rows |
| Expansion gatekeeper | `packages/scoring/growth_pack/gatekeeper.py` + `apps/api/services/growth_gatekeeper_pipeline.py` | Primary gate (funnel → overlap → monetization → owned audience → capacity); defers expansion commands with `evidence.gating_*` |
| Platform Allocation Commander | `build_platform_allocation_rows` | Per-platform recommended vs current counts |
| Niche Deployment Commander | `build_niche_rows` | Whitespace + candidates |
| Revenue / capital / output | `build_capital_plan`, `build_portfolio_output` | Budget split, throttle |
| Cross-account cannibalization | `build_cannibalization_pairs` | Topic overlap (Jaccard) on same platform |
| Platform OS layer | `packages/scoring/growth_pack/platform_os.py` | TikTok, Instagram, YouTube, X/Twitter, Reddit, LinkedIn, Facebook |

## growth_commands canonical fields

Persisted columns include: `command_priority`, `action_deadline`, `platform`, `account_type`, `niche`, `sub_niche`, `persona_strategy_json`, `monetization_strategy_json`, `output_requirements_json`, `success_threshold_json`, `failure_threshold_json`, `expected_revenue_min` / `max`, `expected_cost`, timing, `confidence` / `urgency` (scores), `risk_score`, `blockers_json`, `required_resources` + JSON mirrors in API, `explanation_json`, `consequence_if_ignored_json`, `lifecycle_status`. Legacy JSON blobs (`comparison`, `evidence`, etc.) remain for explainability.

## APIs

Mounted under `/api/v1/brands/{brand_id}/` except single-blueprint fetch:

- `GET/POST .../growth-commands` / `recompute` — existing Growth Commander router
- `GET/POST .../portfolio-launch-plan/recompute`
- `GET/POST .../account-launch-blueprints/recompute`
- `GET/POST .../platform-allocation/recompute`
- `GET/POST .../niche-deployment/recompute`
- `GET/POST .../growth-blockers/recompute`
- `GET/POST .../capital-deployment/recompute`
- `GET/POST .../cross-account-cannibalization/recompute`
- `GET/POST .../portfolio-output/recompute`
- `GET /api/v1/account-launch-blueprints/{id}` — org-scoped

## Workers

Queue: `growth_pack`. Beat: every 6 hours `recompute_all_growth_pack` (all brands). Task `recompute_brand_growth_pack` for single brand. Tasks use `TrackedTask` → `system_jobs` for status/retries.

## UI

`/dashboard/growth-command-center` — sections wired to persisted GET endpoints; “Recompute full pack” chains all POST recomputes.

## Business inputs: first-class vs proxy vs upstream-limited

| Signal | Source | Notes |
|--------|--------|--------|
| Launch readiness score | `launch_readiness_reports` | First-class; drives funnel gate and `fix_funnel_first` when score is below 50 |
| Offer count | `offers` (active) | First-class |
| Sponsor inventory | Counts: `sponsor_profiles`, `sponsor_opportunities` (excl. closed-lost statuses) | First-class counts; score is a deterministic blend |
| Audience / owned-audience | `audience_segments.estimated_size` (sum) + `trust_signal_reports` | No dedicated email/SMS subscriber table — **proxy**: segment rollups + trust |
| Operator bandwidth | Derived from `creator_accounts.posting_capacity_per_day` × `(1 + fatigue_score)` | **Proxy** for operational load |
| Upside / comfort pressure | `scale_recommendations.incremental_profit_new_account` vs `incremental_profit_existing_push` | **Derived** ratio |
| Cross-account overlap | `build_cannibalization_pairs` (Jaccard on `niche_focus`) | First-class logic; same-platform accounts only |

**Upstream limits:** true subscriber LTV, inbox placement, and sponsor pipeline CRM stages are not ingested as separate streams; extending those would tighten owned-audience and sponsor gates beyond counts.

## Tests

- Unit: `tests/unit/test_growth_pack_orchestrator.py` — canonical mapping, allocation, cannibalization, capital, platform OS (seven platforms: TikTok, Instagram, YouTube, X/Twitter, Reddit, LinkedIn, Facebook)
- Unit: `tests/unit/test_growth_commander.py` — command engine
- Unit: `tests/unit/test_gatekeeper.py` — gatekeeper scores + deferral
- Integration (Postgres): `tests/integration/test_growth_pack_flow.py` — persisted blueprints, funnel/overlap gates, capital holdback, output throttle, seven-platform allocation. Run with `TEST_DATABASE_URL` pointing at Postgres (e.g. Docker Compose on port 5433 per `docs/01-setup.md`).

## Migrations

`n5b6c7d8e9f0_growth_pack_full` — alters `growth_commands`, creates all pack tables.

## Fit checklist (10 points)

1. **Account count** — `portfolio_launch_plans.recommended_total_account_count` + `growth_commands` + portfolio directive on runs  
2. **Next account** — blueprints + highest-priority commands  
3. **Platform, role, niche, persona, monetization** — canonical columns + blueprints  
4. **New vs output** — `comparison` on every command  
5. **Blockers** — `growth_blocker_reports` + command types `fix_funnel_first` / `add_offer_first`  
6. **Launch plan & blueprints** — persisted tables  
7. **Cannibalization** — `cross_account_cannibalization_reports`  
8. **Capital & output** — `capital_deployment_plans`, `portfolio_output_reports`  
9. **Command Center** — real API data  
10. **Explainability** — `explanation_json`, evidence, platform OS rationale JSON  

## Partial / follow-ups

- **Owned-audience**: replace or augment segment-size proxy with first-party list/subscriber metrics when available  
- **Operator bandwidth**: optional human-entered capacity ceiling (not yet a DB column)  
- **Integration tests** require a live Postgres matching `TEST_DATABASE_URL` (schema via `Base.metadata.create_all` in tests or Alembic in Docker)  

# Autonomous Execution Phase C: Funnel, Paid Operator, Sponsor, Retention, Recovery

## Overview

Phase C extends autonomous execution into revenue operations: funnels, paid amplification (winners only), sponsor pipeline automation, retention/LTV moves, and incident-driven self-healing.

## Tables (7)

| Table | Role |
|-------|------|
| `funnel_execution_runs` | Funnel actions, paths, capture mode, upside, confidence |
| `paid_operator_runs` | Winner-backed paid tests with budget band, CAC/ROI estimates |
| `paid_operator_decisions` | Scale / stop / hold / budget_adjust per run |
| `sponsor_autonomous_actions` | Inventory, packages, targets, pipeline stage, deal value |
| `retention_automation_actions` | Segment/cohort retention plays and incremental value |
| `recovery_escalations` | Detected incidents and escalation requirement |
| `self_healing_actions` | Automated response linked to escalation when applicable |

## 1. Autonomous funnel runner

- **Inputs (proxy):** funnel leak proxy from engagement/CTR, intent proxy, list growth, sequence health, brand `execution_mode` in guidelines.
- **Actions:** leak diagnosis + variant test, high-intent → concierge/high-ticket path, owned-audience capture when list growth lags, sequence repair, or maintain.
- **Outputs:** `funnel_action`, `target_funnel_path`, `cta_path`, `capture_mode` (`direct_conversion` | `owned_audience`), `execution_mode`, `expected_upside`, `confidence`, `explanation`, `diagnostics_json`.

## 2. Paid operator rules

- **Eligibility:** Organic winners only — min engagement score, revenue proxy, recency window.
- **Bands:** `safe_test_band`, `test_band`, `scale_band`, `reduced_test_band`, `paused`, `none`.
- **Decisions:** `compute_paid_operator_decision` uses CPA vs target, spend, conversions, ROI — **stop** weak tests, **scale** strong, **budget_adjust** when overspending with weak ROI, else **hold**.
- **Execution:** Default from brand guidelines; high-confidence scale paths may use `autonomous` only when brand default allows it.

## 3. Sponsor autonomy rules

- Build/rank inventory and categories, generate outreach sequence metadata, expand target lists when pipeline shallow, surface renewals/upsells when renewals due in window.
- **Outputs:** `sponsor_action`, `package_json`, `target_category`, `target_list_json`, `pipeline_stage`, `expected_deal_value`, `confidence`, `explanation`.

## 4. Retention automation rules

- **Signals:** churn risk, upsell window, repeat-purchase window, LTV tier (from engagement proxy when live LTV unavailable).
- **Actions:** reactivation, upsell tier, repeat nudge, referral ask for stable high-LTV, or monitor-only.
- **Outputs:** `retention_action`, `target_segment`, `cohort_key`, `expected_incremental_value`, `confidence`, `explanation`.

## 5. Self-healing / recovery rules

- **Incident types:** provider failure, publishing failures, conversion drop, fatigue spike, queue congestion, budget overspend, sponsor underperformance, account stagnation, weak offer economics, healthy baseline.
- **Responses:** reroute provider, retry publish, throttle paid + funnel test, rotate creative / suppress output, fair queue split, pause spend cap, adjust sponsor pitch, shift allocation, suppress offer pending review, monitor.
- **Escalation:** `none`, `operator_review`, `immediate_operator` — severity can upgrade low incidents to operator review.

## API (10)

| Method | Path |
|--------|------|
| GET | `/brands/{id}/funnel-execution` |
| POST | `/brands/{id}/funnel-execution/recompute` |
| GET | `/brands/{id}/paid-operator` |
| POST | `/brands/{id}/paid-operator/recompute` |
| GET | `/brands/{id}/sponsor-autonomy` |
| POST | `/brands/{id}/sponsor-autonomy/recompute` |
| GET | `/brands/{id}/retention-autonomy` |
| POST | `/brands/{id}/retention-autonomy/recompute` |
| GET | `/brands/{id}/recovery-autonomy` |
| POST | `/brands/{id}/recovery-autonomy/recompute` |

POST endpoints use `recompute_rate_limit` and operator role.

## Workers (5)

| Schedule | Task |
|----------|------|
| Every 4h | `run_funnel_execution` |
| Every 4h | `run_paid_operator` |
| Every 6h | `run_sponsor_autonomy` |
| Every 6h | `run_retention_autonomy` |
| Every 2h | `run_recovery_autonomy` |

Workers call the same async service functions per brand with `asyncio.run` and committed sessions.

## Dashboards

- Funnel Runner, Paid Operator, Sponsor Autonomy, Retention + LTV, Recovery + Self-Healing (under Command Center nav).

## Execution vs Recommendation Boundaries (per module)

| Module | Boundary | What it does today | What it does NOT do yet |
|--------|----------|-------------------|------------------------|
| **FunnelExecutionRun** | Recommends + queues operator action | Computes funnel actions from real `PerformanceMetric` proxy (engagement, CTR → leak/intent). Persists `run_status`, `execution_mode`, `diagnostics_json`. Engine has 4 real branch paths + fallback. | Does **not** auto-deploy landing pages, modify email sequences, or trigger A/B tests. Requires operator or downstream executor to act on `run_status=active` rows. |
| **PaidOperatorRun** | Recommends + queues operator action | Selects organic winners from `MonetizationRoute`, `PerformanceMetric`, `AutonomousRun`. Engine filters by engagement/revenue/recency. Persists budget band, CAC/ROI estimates, winner linkage. | Does **not** create ad campaigns or spend budget. No ads-platform integration exists. |
| **PaidOperatorDecision** | Recommends (synthetic input) | Decision engine has 4 real branches (stop/scale/budget_adjust/hold) driven by CPA, ROI, spend, conversions. All decisions tagged `[data_source=synthetic_estimate]` until real ad metrics connected. `execution_status` tracks operator action. | Uses self-referential estimates as input, biasing toward hold/scale. Replace with real ad-platform CPA/spend when available. |
| **SponsorAutonomousAction** | Recommends + queues operator action | Queries real `SponsorProfile` count, `SponsorOpportunity` pipeline depth and renewal status. Engine has 5 conditional branches (inventory build, rank, outreach, renewal, pipeline expand). `execution_status` tracks operator action. | Does **not** send outreach emails or create sponsor contracts. Operator must execute from persisted action. |
| **RetentionAutomationAction** | Recommends + queues operator action | Derives churn proxy from real `PerformanceMetric` engagement. Engine has 4 conditional branches (reactivation, upsell, repeat nudge, referral) + fallback. `execution_status` tracks operator action. | Does **not** trigger email/SMS sequences or modify pricing. Requires CRM/ESP integration for auto-execution. |
| **RecoveryEscalation** | Detects + escalates | Checks real `SuppressionExecution` congestion, `PerformanceMetric` engagement, `AutonomousRun` errors. 9 incident types with severity-based escalation routing. | Detection is real; resolution requires operator or self-healing action. |
| **SelfHealingAction** | Executes partially (autonomous for safe actions) | Maps each incident to a concrete action with `action_mode` (autonomous/guarded) and `escalation_requirement` (none/operator_review/immediate_operator). High-severity auto-upgrades to operator review. `execution_status` tracks completion. | "Autonomous" actions (e.g. `suppress_output_rotate_creative`, `throttle_enqueue_split_queue`, `pause_spend_cap`) describe intent but do **not** yet call external systems. They are persisted as execution-ready records for downstream executors. |

### Data source honesty

- **Funnel/retention signals**: Use `PerformanceMetric` engagement/CTR as proxy. Real funnel analytics and CRM cohort data not yet connected.
- **Paid operator decisions**: Use synthetic performance derived from engine estimates. Labeled `[data_source=synthetic_estimate]` in every decision explanation. Replace with real ad-platform metrics when integration exists.
- **Sponsor context**: Wired to real `SponsorProfile` and `SponsorOpportunity` tables for inventory completeness, pipeline depth, and renewal counts.
- **Recovery signals**: Derived from real DB state (suppression count, engagement averages, autonomous run errors). Provider failure and budget overspend require external monitoring hooks.

### Execution status lifecycle

All action models track `execution_status` with values: `proposed` → `operator_review` → `approved` → `executing` → `completed` (or `rejected`). New records default to `proposed`. Operators advance the status via:

- **PATCH** `/{brand_id}/phase-c/{module}/{record_id}/status` — advance any action's status with validation and optional operator notes.
- **POST** `/{brand_id}/phase-c/execute-approved` — batch-execute all approved actions for a brand via downstream executors.
- **POST** `/{brand_id}/phase-c/notify-operator` — collect and dispatch notifications for all `operator_review` items.

### Paid performance ingestion

- **POST** `/{brand_id}/paid-operator/{run_id}/performance` — ingest real ad-platform metrics (CPA, spend, conversions, ROI) for a paid operator run. Creates a new decision with `[data_source=real_ad_platform]` replacing synthetic estimates.

### Downstream executors (`packages/executors/phase_c_executors.py`)

| Executor | Module | Internal actions | External integration |
|----------|--------|-----------------|---------------------|
| `FunnelExecutor` | funnel_execution | Diagnose/patch, route concierge, activate capture, maintain | Landing page deploy (future) |
| `PaidCampaignExecutor` | paid_operator_decision | Hold/budget_adjust | Stop/scale campaigns via `ADS_PLATFORM_API_KEY` |
| `SponsorOutreachExecutor` | sponsor_autonomy | Build inventory, rank, expand targets | Outreach sequences via `SMTP_HOST` |
| `RetentionCampaignExecutor` | retention_autonomy | Monitor | Email/SMS flows via `ESP_API_KEY` / `SMS_API_KEY` |
| `SelfHealingExecutor` | self_healing | Throttle, suppress, pause, shift, adjust, monitor | Provider reroute (future) |

When external credentials are missing, executors complete successfully with notes indicating what is needed.

### Celery worker tasks (execution loop)

| Schedule | Task | Purpose |
|----------|------|---------|
| Every 1h | `execute_approved_actions` | Pick up approved actions across brands and dispatch to executors |
| Every 2h | `notify_operators` | Collect operator_review items and dispatch notifications |

### TypeScript API client

All lifecycle endpoints are available via `autonomous-phase-c-api.ts`: `advanceActionStatus`, `ingestPaidPerformance`, `batchExecuteApproved`, `notifyOperator`.

### Integration tests

- `test_autonomous_phase_c_flow.py` — 5 tests covering recompute + list for all modules
- `test_autonomous_phase_c_lifecycle.py` — 8 tests covering full lifecycle (propose → approve → execute → complete), rejection, invalid transitions, paid perf ingestion, batch execute, and operator notifications

## Phase D

Reserved for future expansion; not part of this pack.

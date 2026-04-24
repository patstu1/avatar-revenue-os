# Brain Architecture — Phase B: Decisions, Policies, Confidence, Cost/Upside, Arbitration

## Overview

Phase B builds the brain's decision-making layer on top of Phase A's state and memory foundations. It transforms state observations into prioritized, policy-governed, confidence-scored decisions with explicit cost/upside estimates and priority arbitration.

## Components

### 1. Master Decision Engine

Combines signals from account state, opportunity state, execution state, audience state, profit metrics, saturation, fatigue, and blocker status to produce final decision objects.

**Decision classes:**
- `launch` — new account/lane warmup
- `hold` — insufficient signal, continue monitoring
- `scale` — increase output on proven winner
- `suppress` — reduce output for saturated lane
- `monetize` — optimize offer routing or retention
- `reroute` — shift resources to better opportunity
- `recover` — stabilize at-risk account or failed execution
- `escalate` — blocker requires operator attention
- `throttle` — reduce cadence without full suppression
- `split_account` — clone winning strategy into new account
- `merge_lane` — consolidate overlapping lanes
- `test` — run controlled experiment
- `kill` — abandon failing lane entirely

Every decision persists: objective, target scope, selected action, alternatives considered, confidence, policy mode, expected upside/cost, downstream action, and explanation.

### 2. Policy Engine

Decides whether a decision should execute autonomously, with guardrails, or require manual approval.

**Policy modes:**
- `autonomous` — high confidence, low risk, within cost limits
- `guarded` — mixed signals, moderate cost, or platform-sensitive
- `manual` — high risk, high compliance, poor account health, or operator override

**Inputs:** confidence, risk, cost, platform sensitivity, compliance sensitivity, account health, budget impact, operator override rules.

**Outputs:** policy mode, reason, approval needed, hard-stop rule, rollback rule.

### 3. Confidence Engine

Scores decision reliability based on weighted factors:

| Factor | Weight |
|---|---|
| Signal strength | 25% |
| Historical precedent | 20% |
| Data completeness | 20% |
| Execution history | 15% |
| Memory support | 10% |
| Saturation penalty | -5% |
| Blocker penalty | -5% |

**Bands:** very_high (≥85%), high (≥70%), medium (≥50%), low (≥30%), very_low (<30%)

Uncertainty factors are explicitly listed when present: incomplete data, saturation risk, active blockers, weak signal, limited precedent.

### 4. Cost / Upside Estimation Layer

For each decision scope, estimates:
- **Expected upside**: revenue potential × conversion rate × traffic / 100
- **Expected cost**: content + platform + paid spend + tool costs
- **Net value**: upside − cost
- **Payback speed**: time to positive return (days)
- **Operational burden**: 0–1 scale based on spend complexity
- **Concentration risk**: portfolio share adjusted for over-concentration

### 5. Priority Arbitration Layer

When multiple decisions compete for resources, arbitration ranks them using a composite score:

`composite = (net_value × 0.4 + confidence × 30 × 0.3 + urgency × 30 × 0.3) × category_weight`

**Category weights (highest priority first):**
- recovery_action: 1.50
- funnel_fix: 1.30
- monetization_fix: 1.20
- retention_action: 1.15
- new_launch: 1.00
- more_output: 0.95
- paid_promotion: 0.90
- sponsor_action: 0.85

Winner is chosen; all rejected actions include explicit reasons.

## Tables

| Table | Purpose |
|---|---|
| `brain_decisions` | Final decision objects with class, scope, action, confidence, policy mode |
| `policy_evaluations` | Policy mode determination per decision with approval/stop/rollback rules |
| `confidence_reports` | Confidence scoring breakdown per decision scope |
| `upside_cost_estimates` | Financial estimation per decision scope |
| `arbitration_reports` | Priority ranking with winner, rejected actions, reasons |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/brain-decisions` | List active decisions |
| POST | `/brands/{id}/brain-decisions/recompute` | Full pipeline: decisions → policies → confidence → cost/upside → arbitration |
| GET | `/brands/{id}/policy-evaluations` | List active policy evaluations |
| GET | `/brands/{id}/confidence-reports` | List active confidence reports |
| GET | `/brands/{id}/upside-cost-estimates` | List active cost/upside estimates |
| GET | `/brands/{id}/arbitration-reports` | List active arbitration reports |

POST recompute is rate-limited via `recompute_rate_limit`.

## Workers

| Task | Schedule | Queue |
|---|---|---|
| `recompute_brain_decisions` | Every 4 hours | brain |

The single worker task runs the full pipeline (decisions + policies + confidence + estimates + arbitration) since all five outputs are co-dependent.

## Dashboards

1. **Brain Decisions** — decision class, scope, action, mode, confidence, upside, cost, downstream action
2. **Policy Evaluations** — action ref, mode, approval, risk, cost, hard stop, rollback, reason
3. **Confidence Reports** — scope, score, band, signal/data/saturation/blocker breakdowns
4. **Cost / Upside** — scope, upside, cost, net value, payback, ops burden, concentration
5. **Priority Arbitration** — winner, ranked priorities, rejected actions with reasons

## Execution vs Recommendation Boundaries

| Module | Behavior |
|---|---|
| Master Decision Engine | **Recommends + queues**: persists decisions with downstream action paths; does not auto-execute |
| Policy Engine | **Classifies**: determines execution mode for each decision |
| Confidence Engine | **Scores**: provides reliability assessment; influences policy mode |
| Cost / Upside | **Estimates**: financial projections to inform prioritization |
| Arbitration | **Ranks + selects**: chooses winner from competing actions |

Actual execution of decisions (content generation, monetization routing, suppression, etc.) is delegated to downstream modules (Autonomous Phase B runner, Phase C funnel/paid/sponsor/retention/recovery, Phase D agent orchestration).

## Idempotency

Repeated recompute calls deactivate all previous active records (`is_active=False`) before creating new ones, preventing duplication.

## Data Provenance

All Phase B outputs are **proxy/synthetic** until live platform data, real performance metrics, and real financial data are connected. Decision quality improves as Phase A state engines receive real data from signal ingestion, performance metrics, and attribution events.

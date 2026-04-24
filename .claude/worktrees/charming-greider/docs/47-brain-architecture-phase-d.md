# Brain Architecture — Phase D: Meta-Monitoring, Self-Correction, Readiness, Escalation

## Overview

Phase D is the final layer of the Brain Architecture Pack. It closes the brain's feedback loop by monitoring its own health, correcting drift, judging operational readiness, and escalating to the operator only when the system genuinely cannot proceed safely.

## Components

### 1. Meta-Monitoring Engine

Continuously assesses brain health across 10 dimensions:

| Dimension | Description | Healthy Threshold |
|---|---|---|
| Decision quality | % of decisions with confidence ≥ 0.5 | > 60% |
| Confidence drift | % of low-confidence decisions | < 40% |
| Policy drift | % of manual-mode policies | < 50% |
| Execution failure rate | Failures / total executions | < 30% |
| Memory quality | Non-stale entries / total entries | > 50% |
| Escalation rate | Escalation events relative to decisions | < 50% |
| Queue congestion | Queue depth / 100 | < 60% |
| Dead agent paths | Agents that errored | 0 |
| Low-signal conditions | Agents with confidence < 0.3 | 0 |
| Wasted actions | Actions that produced no value | ≤ 2 |

**Health bands:** excellent (≥85%), good (≥70%), medium (≥50%), degraded (≥30%), critical (<30%)

### 2. Self-Correction Engine

Produces automated correction actions based on monitoring findings:

| Correction Type | Trigger | Effect |
|---|---|---|
| `lower_confidence` | Many low-confidence decisions | Increases caution in future decisions |
| `increase_guard_mode` | High failures or confidence drift | Shifts policies toward guarded/manual |
| `reduce_output` | High failure rate or queue congestion | Lowers content generation cadence |
| `increase_suppression` | Waste or excessive escalations | Tightens suppression rules |
| `rerank_priorities` | Priority drift detected | Forces arbitration recalculation |
| `escalate_missing_data` | Low memory quality | Notifies operator of data gaps |
| `pause_paid` | Queue congestion > 80% | Stops paid amplification |
| `tighten_budget` | Budget overspend risk | Reduces allowable spend |
| `flag_dead_agent` | Dead agent paths detected | Marks agent for investigation |

Severity levels: critical, high, medium, low.

### 3. Acceptance / Readiness Brain

Top-level readiness judgment that determines which actions are safe to perform:

**Readiness bands:** ready (≥80%), mostly_ready (≥65%), partially_ready (≥45%), not_ready (≥20%), blocked (<20%)

**Actions evaluated:**
- `launch` — requires score ≥ 40% + accounts + offers
- `scale` — requires score ≥ 60% + healthy accounts
- `auto_run` — requires score ≥ 70% + low failure rate + decent confidence
- `paid_amplify` — requires score ≥ 60% + credentials + low failure rate
- `sponsor_push` — requires score ≥ 50% + offers
- `high_ticket_push` — requires score ≥ 65% + good confidence
- `expand_platform_count` — requires score ≥ 55% + credentials

Each action is classified as either allowed or forbidden with explicit reasoning.

### 4. Brain-Level Escalation Layer

When the brain cannot proceed safely, it generates exact operator commands:

| Escalation Type | Trigger | Urgency |
|---|---|---|
| `connect_credential` | No platform API credentials | Critical |
| `add_offer` | No active monetization offers | Critical |
| `create_account` | No creator accounts | High |
| `fix_execution_failures` | Failure rate > 40% | High |
| `review_brain_health` | Health score < 40% | High |
| `resolve_blockers` | > 3 active blockers | High |
| `approve_auto_run` | Auto-run forbidden but health OK | Medium |
| `approve_paid_amplification` | Paid blocked but credentials exist | Medium |

Each escalation includes: command, urgency, expected upside unlocked, expected cost of delay, affected scope, confidence, and explanation.

## Tables

| Table | Purpose |
|---|---|
| `meta_monitoring_reports` | Brain health snapshots with 10 dimensions, weak areas, corrections |
| `self_correction_actions` | Automated correction actions with type, target, severity |
| `readiness_brain_reports` | Readiness scores with allowed/forbidden actions and blockers |
| `brain_escalations` | Operator escalations with commands, urgency, upside/cost |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/meta-monitoring` | List meta-monitoring reports |
| POST | `/brands/{id}/meta-monitoring/recompute` | Full pipeline: monitoring → corrections → readiness → escalations |
| GET | `/brands/{id}/self-corrections` | List self-correction actions |
| GET | `/brands/{id}/readiness-brain` | List readiness brain reports |
| POST | `/brands/{id}/readiness-brain/recompute` | Same pipeline as meta-monitoring recompute |
| GET | `/brands/{id}/brain-escalations` | List brain escalations |

Both POST endpoints are rate-limited via `recompute_rate_limit`.

## Workers

| Task | Schedule | Queue |
|---|---|---|
| `recompute_meta_monitoring` | Every 2 hours | brain |

The single worker runs the full Phase D pipeline: meta-monitoring → self-correction → readiness → escalation.

## Dashboards

1. **Meta-Monitoring** — health score, band, 10 dimension breakdown, weak areas, recommended corrections
2. **Self-Corrections** — correction type, target, severity, applied status, confidence
3. **Readiness Brain** — readiness score, band, allowed/forbidden actions, blockers
4. **Brain Escalations** — escalation type, exact operator command, urgency, upside unlocked, delay cost

## Execution vs Recommendation Boundaries

| Component | Behavior |
|---|---|
| Meta-Monitoring | **Assesses**: reads brain state, produces health report |
| Self-Correction | **Recommends**: generates correction actions; does not auto-apply (applied=False until operator confirms or future auto-apply layer is added) |
| Readiness Brain | **Judges**: classifies actions as allowed/forbidden; does not enforce |
| Brain Escalation | **Notifies**: generates operator commands; does not auto-resolve |

## Idempotency

All recompute calls deactivate previous active records before creating new ones.

## Data Provenance

Phase D health scores and readiness judgments are only as accurate as the underlying Phase A/B/C data. With live platform data and real performance metrics, monitoring quality improves significantly.

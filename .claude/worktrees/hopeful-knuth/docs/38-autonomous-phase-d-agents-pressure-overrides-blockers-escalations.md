# Phase D — Agent Orchestration, Revenue Pressure, Overrides, Blockers, Escalations

## Overview

Phase D completes the Autonomous Execution + Blocker Escalation Pack. It adds five interconnected layers that turn the AI Avatar Revenue OS into a continuously self-driving, self-monitoring, and operator-escalating system.

| Layer | Purpose |
|---|---|
| **Agent Orchestration** | 12 specialist agents execute structured cycles, share memory, and pass structured outputs |
| **Revenue Pressure** | Continuously identifies where money is left on the table |
| **Override / Approval** | Governs which actions run autonomously vs guarded vs manual |
| **Blocker Detection** | Detects every class of operational blocker preventing progress |
| **Operator Escalation** | Converts blockers + pressure into exact operator commands |

---

## 1. Agent Orchestration Layer

### Specialist Agents

| Agent | Responsibility |
|---|---|
| trend_scout | Scans signals, hands off top opportunities |
| niche_allocator | Evaluates accounts, recommends allocation shifts |
| monetization_router | Identifies underused monetization classes |
| funnel_optimizer | Diagnoses funnel leaks, recommends patches |
| scale_commander | Determines scale/hold/diagnose based on revenue trend + health |
| account_launcher | Proposes new accounts when portfolio is thin |
| recovery_agent | Handles suppressions, provider failures |
| sponsor_strategist | Manages sponsor pipeline depth |
| pricing_strategist | Recommends pricing tier actions |
| retention_strategist | Monitors retention risk, triggers reactivation |
| paid_amplification_agent | Identifies winners for paid, monitors active campaigns |
| ops_watchdog | Monitors system health, escalates operator when critical |

### Tables

- **agent_runs** — one row per agent per cycle; persists input context, output, commands, status
- **agent_messages** — structured inter-agent messages (sender → receiver, type, payload)

### Behavior

- Agents share a common `brand_context` built from live DB state (accounts, offers, suppressions, health)
- Each agent produces a structured `output_json` with a recommendation
- Agents pass messages to downstream agents (e.g. trend_scout → niche_allocator)
- All runs and messages are persisted for audit
- Recompute deactivates prior cycle before persisting new

### Data Boundaries

- `avg_engagement`, `revenue_trend`, `sponsor_pipeline`, `retention_risk` — currently proxy-derived from account health + DB counts
- Will become live-truth when analytics ingestion and attribution are connected

---

## 2. Revenue Pressure Layer

### Questions Answered Every Cycle

1. Where is revenue being left on the table?
2. What monetization class is underused?
3. What platform is underbuilt?
4. What account should exist but doesn't?
5. What winner has not been fully exploited?
6. What funnel is leaking?
7. What asset class has not been activated?
8. What should be launched next?
9. What should be cut now?

### Required Outputs

- **next_commands_json** — up to 5 prioritized commands
- **next_launches_json** — up to 3 launch recommendations
- **biggest_blocker** — single most impactful blocker
- **biggest_missed_opportunity** — single biggest upside gap
- **biggest_weak_lane_to_kill** — weakest active lane
- **pressure_score** — 0..1 composite metric

### Table: `revenue_pressure_reports`

Fields: next_commands_json, next_launches_json, biggest_blocker, biggest_missed_opportunity, biggest_weak_lane_to_kill, underused_monetization_class, underbuilt_platform, missing_account_suggestion, unexploited_winner, leaking_funnel, inactive_asset_class, pressure_score, explanation

### Logic

Pressure score computed from: underused monetization count, underbuilt platform count, unexploited winners, funnel leak severity, revenue trend, suppression density.

---

## 3. Override / Approval System

### Modes

| Mode | Behavior |
|---|---|
| **autonomous** | Executes without operator approval if confidence ≥ threshold |
| **guarded** | Executes but logs to audit trail; operator can rollback |
| **manual** | Requires explicit operator approval before execution |

### Table: `override_policies`

Fields: action_ref, override_mode, confidence_threshold, approval_needed, rollback_available, rollback_plan, hard_stop_rule, audit_trail_json, explanation

### Pre-mapped Action Risk Profiles

| Action | Default Mode | Approval? | Rollback? |
|---|---|---|---|
| publish_content | guarded | No | Yes |
| increase_paid_spend | guarded | Yes | Yes |
| pause_account | guarded | Yes | Yes |
| launch_new_account | manual | Yes | No |
| approve_sponsor_deal | manual | Yes | No |
| send_outreach_email | guarded | No | Yes |
| change_pricing | manual | Yes | Yes |
| suppress_lane | autonomous | No | Yes |
| scale_winner | guarded | No | Yes |
| emergency_budget_cap | autonomous | No | No |
| create_content_brief | autonomous | No | No |
| trigger_reactivation | guarded | No | Yes |

### Hard Stop Rules

- `increase_paid_spend`: Halt if cumulative spend exceeds daily budget ceiling
- `launch_new_account`: Block if compliance check pending

---

## 4. Blocker Detection Engine

### Blocker Types

| Type | Severity | Example |
|---|---|---|
| missing_credential | high | YouTube API key expired |
| missing_offer | critical | No offers configured |
| account_not_ready | medium | Account health < 0.3 |
| funnel_blocked | high | Leak score > 0.55 |
| budget_blocked | high | Budget < $50 |
| compliance_hold | critical | Platform TOS issue |
| platform_capacity_full | medium | Platform at 95%+ capacity |
| provider_unavailable | high | Generation provider down |
| queue_failure | medium | Queue failure rate > 10% |
| policy_sensitive_lane | medium | Lane flagged for review |

### Table: `blocker_detection_reports`

Fields: blocker, severity, affected_scope, operator_action_needed, deadline_or_urgency, consequence_if_ignored, explanation, status, resolved_at

### Behavior

- Recompute deactivates stale open blockers, creates fresh detection
- Each blocker includes exact operator action needed + consequence if ignored
- Status tracks open → resolved lifecycle

---

## 5. Operator Escalation Engine

### Generation Logic

Escalations are generated from:
1. Every blocker produces an escalation with the exact operator action
2. Top 3 revenue pressure commands produce escalations

### Required Escalation Fields

| Field | Purpose |
|---|---|
| command | Exact action the operator must take |
| reason | Why this escalation exists |
| supporting_data_json | Source blocker/pressure data |
| confidence | How certain the system is |
| urgency | critical / high / medium |
| expected_upside | Dollar value of resolving |
| expected_cost | Cost to operator |
| time_to_signal | When results become visible |
| time_to_profit | When revenue impact materializes |
| risk | Severity of inaction |
| required_resources | What operator needs |
| consequence_if_ignored | What happens without action |

### Tables

- **escalation_events** — the escalation record itself
- **operator_commands** — linked to escalation_event or blocker_report; the actionable operator command

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | /brands/{id}/agent-runs | List agent runs + messages |
| GET | /brands/{id}/revenue-pressure | List revenue pressure reports |
| POST | /brands/{id}/revenue-pressure/recompute | Recompute revenue pressure |
| GET | /brands/{id}/override-policies | List override policies |
| POST | /brands/{id}/override-policies/recompute | Recompute override policies |
| GET | /brands/{id}/blocker-detection | List blocker detection reports |
| POST | /brands/{id}/blocker-detection/recompute | Recompute blocker detection |
| GET | /brands/{id}/operator-escalations | List escalations + commands |

All POST endpoints protected by recompute rate limiter. All endpoints require brand access verification.

---

## Workers (Celery Beat)

| Schedule | Task | Purpose |
|---|---|---|
| Every 2h | run_agent_orchestration | Full 12-agent cycle |
| Every 4h | run_revenue_pressure | Revenue pressure analysis |
| Every 2h | run_blocker_detection | Blocker detection sweep |
| Every 4h | run_escalation_generation | Convert blockers → operator commands |

---

## Dashboards

1. **Agent Orchestration** — shows all agent runs, their recommendations, and inter-agent messages
2. **Revenue Pressure** — shows pressure score, biggest blocker/missed opportunity, next commands + launches
3. **Override / Approval** — shows all action policies, their modes, approval requirements, rollback availability
4. **Blocker Detection** — shows all detected blockers, severity, required operator actions, status
5. **Operator Escalations** — shows all escalation events with full context + operator commands

---

## Execution vs Recommendation Boundaries

| Module | Mode |
|---|---|
| Agent Orchestration | **Recommends only** — agents produce structured recommendations; execution is delegated to downstream modules |
| Revenue Pressure | **Recommends only** — produces commands and launch suggestions for operator review |
| Override Policies | **Governs execution** — determines which downstream actions can auto-execute vs need approval |
| Blocker Detection | **Detects and persists** — identifies blockers, creates operator commands; does not auto-resolve |
| Operator Escalation | **Queues operator action** — converts blockers/pressure into actionable commands with full context |

---

## Data Provenance

| Signal | Current State |
|---|---|
| Account health | Live from DB (CreatorAccount.health_score) |
| Active accounts/offers count | Live from DB |
| Suppression count | Live from DB (SuppressionExecution) |
| Active monetization classes | Live from DB (MonetizationRoute.route_class) |
| Active platforms | Live from DB (CreatorAccount.platform) |
| Revenue trend | Proxy (default: "flat"); live when analytics pipeline connected |
| Funnel leak score | Proxy (default: 0.3); live when funnel stage metrics connected |
| Sponsor pipeline | Proxy (default: 0); live when sponsor tracking connected |
| Retention risk | Proxy (default: 0.2); live when churn detection connected |
| Provider availability | Proxy (default: true); live when provider health checks connected |

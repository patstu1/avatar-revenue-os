# Brain Architecture Pack — Phase A

## Purpose

Phase A establishes the **shared brain memory layer** and four **state engines** that provide a unified, auditable, and deterministic view of the system's understanding of accounts, opportunities, executions, and audiences.

Every downstream decision engine in the Revenue OS uses these state snapshots as inputs, ensuring the brain coordinates the full loop: ingest → score → choose → execute → monitor → scale → suppress → recover → escalate.

---

## Tables

| Table | Purpose |
|---|---|
| `brain_memory_entries` | Persistent memory of winners, losers, saturated patterns, best niches, best monetization routes, common blockers, platform learnings, and confidence adjustments. |
| `brain_memory_links` | Typed edges between memory entries (e.g., temporal sequence, causal link, similarity). |
| `account_state_snapshots` | Per-account state snapshot: newborn → warming → stable → scaling → max_output → saturated → cooling → at_risk. |
| `opportunity_state_snapshots` | Per-opportunity state: monitor → test → scale → suppress → evergreen_backlog → blocked. |
| `execution_state_snapshots` | Per-execution state: queued → autonomous → guarded → manual → blocked → failed → recovering → completed. |
| `audience_state_snapshots` | Per-segment audience state: unaware → curious → evaluating → objection_heavy → ready_to_buy → bought_once → repeat_buyer → high_ltv → churn_risk → advocate → sponsor_friendly. |
| `state_transition_events` | Immutable log of every state transition across all four engines, recording from/to states, trigger, confidence, and explanation. |

---

## State Engine Definitions

### Account State Engine

Possible states and what they mean:

| State | Meaning |
|---|---|
| `newborn` | Account < 14 days old. Not yet evaluated. |
| `warming` | Account building initial audience and trust. Low followers, early content. |
| `stable` | Consistent engagement. Modest profit. Safe to maintain. |
| `scaling` | Good profit per post, strong engagement. Ready for increased output. |
| `max_output` | Operating at near-capacity with strong profit. Peak state. |
| `saturated` | Saturation score exceeds 75%. Returns diminishing. |
| `cooling` | Fatigue detected. Output should be throttled. |
| `at_risk` | Health critical or suspended. Requires operator attention. |

Inputs: follower count, age, avg engagement, profit per post, fatigue, saturation, account health, posting capacity, output rate.

### Opportunity State Engine

| State | Meaning |
|---|---|
| `monitor` | Moderate signal. Keep watching. |
| `test` | Score and readiness sufficient to begin testing. |
| `scale` | Proven winner with positive win rate — scale aggressively. |
| `suppress` | Suppression risk > 70%. Pause or kill. |
| `evergreen_backlog` | Low urgency. May revisit later. |
| `blocked` | Has an active blocker (credential, budget, compliance, etc.). |

Inputs: opportunity score, tests run, win rate, blocker status, suppression risk, urgency, readiness.

### Execution State Engine

| State | Meaning |
|---|---|
| `queued` | Waiting for execution. |
| `autonomous` | Confidence ≥ 70%, cost within threshold. Auto-executing. |
| `guarded` | Needs operator approval (low confidence or high cost). |
| `manual` | Manual execution only (policy). |
| `blocked` | Blocked by dependency. |
| `failed` | 3+ failures. Rollback eligible. Escalation required. |
| `recovering` | 1-2 failures. Attempting recovery. |
| `completed` | Execution finished successfully. |

Inputs: execution mode, run status, failure count, confidence, estimated cost, cost approval threshold.

### Audience State Engine (V2)

| State | Meaning |
|---|---|
| `unaware` | No awareness of brand/offer. |
| `curious` | Consuming content but no intent signal. |
| `evaluating` | Viewing content and clicking CTAs. |
| `objection_heavy` | Multiple objection signals detected. |
| `ready_to_buy` | High CTA activity, no objections. |
| `bought_once` | Single purchase completed. |
| `repeat_buyer` | Multiple purchases. |
| `high_ltv` | High lifetime value customer. |
| `churn_risk` | Bought once but showing churn signals. |
| `advocate` | High LTV + referral activity. |
| `sponsor_friendly` | High sponsor fit + purchase history. |

Outputs include transition probabilities and next-best-action recommendation.

---

## Brain Memory Layer

### Entry Types

| Type | Meaning |
|---|---|
| `winner` | High-performing entity. Replicate. |
| `loser` | Underperforming entity. Avoid replicating. |
| `saturated_pattern` | Suppressed pattern. Avoid repetition. |
| `best_niche` | Proven profitable niche. |
| `best_monetization_route` | High-EPC/CVR offer pattern. |
| `best_account_type` | Account archetype that performs well. |
| `best_cta` | CTA pattern with high conversion. |
| `best_pacing` | Posting cadence that maximizes returns. |
| `common_blocker` | Frequently recurring blocker. |
| `common_fix` | Known fix for a common issue. |
| `confidence_adjustment` | Meta-entry adjusting confidence in other entries. |
| `platform_learning` | Platform-specific behavioral learning. |

### Memory Links

Links connect entries with typed relationships (temporal sequence, causal, similarity, contradiction). Each link has a strength score (0.0 – 1.0).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/brain-memory` | List active memory entries and links |
| POST | `/brands/{id}/brain-memory/recompute` | Consolidate brain memory from accounts, offers, suppressions, recovery incidents |
| GET | `/brands/{id}/account-states` | List active account state snapshots |
| POST | `/brands/{id}/account-states/recompute` | Recompute all account states |
| GET | `/brands/{id}/opportunity-states` | List active opportunity state snapshots |
| POST | `/brands/{id}/opportunity-states/recompute` | Recompute all opportunity states |
| GET | `/brands/{id}/execution-states` | List active execution state snapshots |
| POST | `/brands/{id}/execution-states/recompute` | Recompute all execution states |
| GET | `/brands/{id}/audience-states-v2` | List active audience state snapshots |
| POST | `/brands/{id}/audience-states-v2/recompute` | Recompute all audience states |

All POST endpoints are rate-limited (5/min) and require OPERATOR role.

---

## Workers

| Task | Schedule | Queue |
|---|---|---|
| `consolidate_brain_memory` | Every 6h | brain |
| `recompute_account_states` | Every 4h | brain |
| `recompute_opportunity_states` | Every 4h | brain |
| `recompute_execution_states` | Every 4h | brain |
| `recompute_audience_states` | Every 6h | brain |

---

## Execution vs Recommendation Boundaries

| Module | Behavior |
|---|---|
| Brain Memory | **Recommends only.** Consolidates patterns for other engines to consume. No autonomous execution. |
| Account State Engine | **Recommends only.** Computes state and next-expected-state. Does not change account configuration. |
| Opportunity State Engine | **Recommends only.** Classifies opportunities. Does not trigger tests or scaling. |
| Execution State Engine | **Recommends + queues.** Determines execution mode (autonomous/guarded/manual) and flags escalation needs. |
| Audience State V2 | **Recommends only.** Computes segment state and next-best-action. Does not trigger flows. |

All state transitions are persisted as immutable `state_transition_events` for auditability.

---

## Idempotency

All recompute endpoints deactivate previous active entries (set `is_active = false`) before creating new snapshots. Repeated calls produce the same count of active entries, never duplicating.

---

## Dashboards

1. **Brain Memory Dashboard** — View/consolidate memory entries and links
2. **Account State Dashboard** — View per-account state, score, transition history
3. **Opportunity State Dashboard** — View opportunity classification and urgency
4. **Execution State Dashboard** — View execution modes, failures, escalations
5. **Audience State V2 Dashboard** — View segment states, LTV, next-best-action

---

## Data Provenance

- All state computations use **deterministic, rules-based engines** with no LLM dependency
- All outputs are **proxy/synthetic** until live platform data integrations are connected
- Dashboards clearly show data source is computed from persisted inputs
- No black-box decisions — every state includes `explanation`, `confidence`, and `inputs_json`

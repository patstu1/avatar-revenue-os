# Brain Architecture — Phase C: Agent Mesh, Workflows, Context Bus, Memory Binding

## Overview

Phase C builds the brain's coordination layer on top of Phase A (state engines + memory) and Phase B (decisions + policies + confidence + arbitration). It implements a mesh of 12 specialist agents that run structured cycles, coordinate via workflows, communicate through a shared context bus, and bind to brain memory for informed decision-making.

## Components

### 1. Agent Mesh / Agent Orchestrator

12 specialist agents, each with defined inputs, outputs, memory scopes, and upstream/downstream relationships:

| Agent | Purpose | Key Memory Scopes |
|---|---|---|
| Trend Scout | Scan for profitable emerging trends | winner, loser, saturated_pattern, platform_learning |
| Niche Allocator | Assign niche/topic to accounts | best_niche, saturated_pattern |
| Monetization Router | Select optimal monetization path | best_monetization_route, winner, loser |
| Funnel Optimizer | Diagnose and fix funnel leaks | common_fix, winner, loser |
| Scale Commander | Decide when/how to scale winners | winner, best_pacing_pattern |
| Account Launcher | Launch new accounts or clone winners | best_account_type, common_blocker |
| Recovery Agent | Detect and resolve failures | common_blocker, common_fix |
| Sponsor Strategist | Build sponsor inventory and packages | winner, best_monetization_route |
| Pricing Strategist | Optimize pricing for offers/sponsors | winner, loser |
| Retention Strategist | Detect churn risk, trigger retention | winner, loser, platform_learning |
| Paid Amplification Agent | Test organic winners with paid spend | winner, loser, platform_learning |
| Ops Watchdog | Monitor system health and queue congestion | common_blocker, common_fix |

Each agent:
- Consumes structured inputs (not opaque freeform)
- Produces structured outputs
- Persists run records (`agent_runs_v2`)
- Persists input/output messages (`agent_messages_v2`)
- Binds to brain memory entries for context

### 2. Workflow Coordination Layer

Predefined workflow templates that chain agents for end-to-end operations:

| Workflow | Sequence | Purpose |
|---|---|---|
| `opportunity_to_launch` | trend_scout → niche_allocator → account_launcher | Discover opportunity, assign niche, launch account |
| `content_to_monetization` | monetization_router → funnel_optimizer | Route content to monetization, optimize funnel |
| `paid_amplification` | scale_commander → paid_amplification_agent → recovery_agent | Scale winner via paid, recover if failure |
| `retention_loop` | retention_strategist → pricing_strategist | Detect churn, trigger retention, adjust pricing |
| `recovery_chain` | ops_watchdog → recovery_agent | Detect operational issue, trigger recovery |
| `sponsor_pipeline` | sponsor_strategist → pricing_strategist → monetization_router | Build sponsor packages, price, route |

Each workflow persists:
- Chosen sequence
- Handoff events (agent-to-agent transitions with payload keys and confidence)
- Failure points (if any agent fails)
- Final outputs per agent
- Coordination decisions (persisted in `coordination_decisions`)

### 3. Shared Context Bus

Agents emit structured context events so downstream modules can react without hidden coupling.

**Event types:**
- `winner_promoted` — trend scout identified a scalable winner
- `launch_blocked` — recovery agent detected a blocker
- `funnel_leaking` — funnel optimizer found a leak
- `retention_action_triggered` — retention strategist started reactivation
- `account_scaling` — scale commander increasing output
- `sponsor_opportunity_detected` — sponsor strategist found opportunities
- `system_throttle` — ops watchdog triggered throttle

Each event includes: event_type, source_module, target_modules, payload, priority (1=critical, 5=low), consumed flag, explanation.

### 4. Agent Memory Binding

Every agent receives relevant brain memory entries (from Phase A) as input. Memory types include:
- `winner` — proven high-performing patterns
- `loser` — confirmed underperforming patterns
- `best_niche` — top-performing niches
- `best_monetization_route` — most profitable monetization methods
- `saturated_pattern` — patterns showing saturation
- `common_blocker` — frequently recurring obstacles
- `common_fix` — proven resolution patterns
- `platform_learning` — platform-specific insights
- `best_pacing_pattern` — optimal posting cadence learnings
- `best_account_type` — most successful account configurations

Memory binding increases agent confidence when relevant winners/best patterns are present, and memory references are persisted on each agent run for auditability.

## Tables

| Table | Purpose |
|---|---|
| `agent_registry` | Registry of all 12 specialist agents with schemas, scopes, relationships |
| `agent_runs_v2` | Individual agent execution records with inputs, outputs, confidence |
| `agent_messages_v2` | Structured input/output messages per agent run |
| `workflow_coordination_runs` | Workflow execution records with sequences, handoffs, failures |
| `coordination_decisions` | Per-step handoff decisions within workflows |
| `shared_context_events` | Cross-module events with type, source, targets, payload, priority |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/brands/{id}/agent-registry` | List registered agents |
| GET | `/brands/{id}/agent-runs-v2` | List recent agent runs |
| POST | `/brands/{id}/agent-mesh/recompute` | Run full agent mesh cycle + workflows + context events |
| GET | `/brands/{id}/workflow-coordination` | List workflow coordination runs |
| GET | `/brands/{id}/shared-context-events` | List shared context events |

POST recompute is rate-limited via `recompute_rate_limit`.

## Workers

| Task | Schedule | Queue |
|---|---|---|
| `recompute_agent_mesh` | Every 4 hours | brain |

The single worker runs the full orchestration cycle: registry refresh → agent runs → context event emission → workflow coordination.

## Dashboards

1. **Agent Mesh** — agent registry (12 agents) + recent runs with status, confidence, memory refs
2. **Workflow Coordination** — workflow type, status, sequence visualization, handoffs, failure points
3. **Shared Context Bus** — event type, source, targets, priority, consumed status
4. **Agent Memory** — brain memory entries + agent runs that referenced memory

## Execution vs Recommendation Boundaries

| Component | Behavior |
|---|---|
| Agent Mesh | **Recommends + persists**: agents produce structured outputs and persist them; do not auto-execute |
| Workflow Coordination | **Coordinates**: chains agent handoffs; does not trigger external side effects |
| Shared Context Bus | **Notifies**: emits events for downstream consumption; does not execute actions |
| Memory Binding | **Reads**: agents read from brain memory; do not write directly to it (Phase A memory consolidation writes) |

## Idempotency

Repeated recompute calls deactivate all previous active records for the brand before creating new ones.

## Data Provenance

All Phase C outputs are deterministic based on current persisted state. Agent outputs are **proxy/synthetic** until live data integrations (platform APIs, real performance metrics) provide real-time inputs. Memory binding quality depends on Phase A brain memory consolidation having sufficient history.

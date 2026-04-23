# AI Gatekeeper

## Overview

The AI Gatekeeper is a hard internal control system that audits, blocks, and escalates incomplete, weak, misleading, or unsafe system state. It is not a cosmetic validation layer — it actively prevents acceptance of incomplete work.

Every gate evaluates real system state and returns pass/fail with severity. No soft passes. No fake approvals.

## Architecture

10 gate modules, each with its own table, engine function, service recompute, API endpoint, and dashboard:

| Gate | Table | What it blocks |
|------|-------|---------------|
| Completion Gate | `gatekeeper_completion_reports` | Modules missing required layers (model, migration, engine, service, API, frontend, tests, docs, worker) |
| Truth Gate | `gatekeeper_truth_reports` | Modules with status mismatches — things labeled live that aren't |
| Execution Closure Gate | `gatekeeper_execution_closure_reports` | Dead-end flows, stale blockers, orphaned recommendations |
| Test Sufficiency Gate | `gatekeeper_test_reports` | Modules with zero tests or missing critical path coverage |
| Dependency Readiness Gate | `gatekeeper_dependency_reports` | External dependencies not met — missing credentials, non-live integrations |
| Contradiction Detection | `gatekeeper_contradiction_reports` | Contradictory states across modules |
| Operator Command Quality | `gatekeeper_operator_command_reports` | Vague, non-actionable, or unmeasurable operator commands |
| Expansion Permission | `gatekeeper_expansion_permissions` | Expansion attempts when prerequisites, tests, or dependencies aren't ready |
| Alert Feed | `gatekeeper_alerts` | Aggregated alerts from all failing gates, sorted by severity |
| Audit Ledger | `gatekeeper_audit_ledgers` | Every gate evaluation recorded for auditability |

## Severity Model

- **critical**: System integrity at risk. Expansion blocked. Operator must act immediately.
- **high**: Significant gap. Feature acceptance should not proceed.
- **medium**: Notable issue. Should be resolved before next phase.
- **low**: Minor. Tracked but not blocking.

## What Causes Acceptance to Be Blocked

| Condition | Severity |
|-----------|----------|
| Module missing 4+ required layers | critical |
| Module labeled "live" but actually "stubbed" or "partial" | critical |
| Pending actions with no execution path (dead end) | critical |
| Zero tests on any module | critical |
| External dependency blocked and no fallback | high |
| Contradictory states between modules (e.g. live depends on blocked) | critical |
| Duplicate primary claims for the same capability | high |
| Expansion attempted with unresolved prerequisites | blocked |

## Required Layers

Every system module is evaluated against these layers:

1. **model** — SQLAlchemy model in `packages/db/models/`
2. **migration** — Alembic migration in `packages/db/alembic/versions/`
3. **engine** — Scoring/logic engine in `packages/scoring/`
4. **service** — Service layer in `apps/api/services/`
5. **api** — Router in `apps/api/routers/`
6. **frontend** — Dashboard page in `apps/web/src/app/dashboard/`
7. **tests** — Unit or integration tests in `tests/`
8. **docs** — Documentation in `docs/`
9. **worker** — Celery worker (only for modules that require async processing)

## Completion Gate

Evaluates which layers are present for each system module. Score is computed as `1.0 - (missing / total_layers)`. If a module is in `SYSTEM_MODULES` with `has_worker: True`, the worker layer is also required.

Severity thresholds:
- 4+ missing layers → `critical`
- 1–3 missing layers → `high`
- 0 missing → `low`

## Truth Gate

Detects truth mismatches — modules that claim a status they don't actually have. The service probes filesystem layers to derive `actual_status`:

- All core layers present → `live`
- Model + engine but not full stack → `partial`
- Model only → `stubbed`
- Nothing → `planned`

If `claimed_status` is "live" but `actual_status` is "stubbed", "partial", or "planned" → `mislabeled_as_live = true`, severity = `critical`.

## Execution Closure Gate

Detects broken execution paths. A module fails if:
- `has_execution_path = false` and `pending_actions_count > 0` → dead end (critical)
- `stale_blocker_count > 0` → stale blockers unresolved (high)
- `orphaned_recommendations > 0` → recommendations with no follow-through (medium)

## Test Sufficiency Gate

Requires `total_tests >= 3` AND `has_critical_path_tests = true` to pass.

Severity:
- 0 total tests → `critical`
- No critical path tests → `high`
- No high-risk flow tests → `medium`

## Dependency Readiness Gate

Checks external provider dependencies. A module is blocked when both `credential_present = false` AND `integration_live = false`. Dependencies are mapped per module (e.g., `buffer_distribution` → `buffer`, `creator_revenue` → `stripe`).

## Contradiction Detection

Compares all module states pairwise:
- **live_depends_on_blocked**: Module A claims live but depends on Module B which is blocked → `critical`
- **duplicate_primary**: Two modules both claim primary role for the same capability → `high`

## Operator Command Quality Gate

Grades operator commands on three dimensions:
- **Actionable**: Text > 10 chars AND has a target
- **Specific**: Has target AND (has metric OR has deadline)
- **Measurable**: Has a metric

Quality score = `0.3 × actionable + 0.4 × specific + 0.3 × measurable`. Gate passes when score ≥ 0.5.

## Expansion Permission Gate

Hard gate — expansion to a new phase/pack/deploy requires ALL conditions:

1. All completion gates passing (`prerequisites_met`)
2. All blockers resolved (`blockers_resolved`)
3. Test coverage sufficient (`test_coverage_sufficient`)
4. All external dependencies ready (`dependencies_ready`)
5. No critical gates failing (`critical_gates_passing`)

If ANY condition fails, the `expansion_target` is **BLOCKED** with specific `blocking_reasons`. The service evaluates three targets: `next_phase`, `new_pack`, `production_deploy`.

## Alert Generation

Alerts are generated as side effects of gate recomputes. All failing gates produce alerts with:
- `gate_type` — which gate produced the alert
- `severity` — inherited from the failing gate
- `title` — human-readable summary
- `operator_action` — what the operator should do

Alerts are sorted by severity (critical first).

## Audit Ledger

Every gate evaluation is recorded with `gate_type`, `action`, `module_name`, `result`, and `details_json`. The audit ledger is append-only and provides full traceability of every gate decision.

## Interaction with Other Systems

| System | Interaction |
|--------|------------|
| **Scale Alerts** | Gatekeeper reads alert state for closure detection |
| **Growth Commander** | Expansion permission gates growth commands |
| **Brain** | State consistency checked across brain memory/decisions |
| **Autonomous Execution** | Execution closure verified for autonomous runs |
| **Buffer** | Distribution truth checked for stale/orphaned state |
| **Live Execution** | Connector readiness verified via dependency gate |
| **Creator Revenue** | Blocker state checked for execution closure |
| **Copilot** | Copilot can query gatekeeper alerts for operator guidance |
| **Provider Registry** | Credential readiness checked via dependency gate |

## Execution Boundaries

- Gatekeeper does **NOT** execute fixes — it only detects and blocks.
- All recomputes are operator-triggered (`OperatorUser` role required for POST).
- Any authenticated user can read gate results (`CurrentUser` for GET).
- Alerts are generated as side effects of gate recomputes.
- Expansion permissions are advisory but hard — `permission_granted = false` means do not proceed.

## API Endpoints (18 total)

Base path: `/api/v1/brands/{brand_id}/gatekeeper/`

### Recomputable Gates (8 GET + POST pairs)

| Gate | GET | POST (recompute) |
|------|-----|-------------------|
| Completion | `GET .../completion` | `POST .../completion/recompute` |
| Truth | `GET .../truth` | `POST .../truth/recompute` |
| Execution Closure | `GET .../execution-closure` | `POST .../execution-closure/recompute` |
| Test Sufficiency | `GET .../tests` | `POST .../tests/recompute` |
| Dependency Readiness | `GET .../dependencies` | `POST .../dependencies/recompute` |
| Contradictions | `GET .../contradictions` | `POST .../contradictions/recompute` |
| Operator Commands | `GET .../operator-commands` | `POST .../operator-commands/recompute` |
| Expansion Permissions | `GET .../expansion-permissions` | `POST .../expansion-permissions/recompute` |

### Read-Only (2 GETs)

| Gate | GET |
|------|-----|
| Alerts | `GET .../alerts` |
| Audit Ledger | `GET .../audit-ledger` |

## Migration

Revision: `gatekeeper_001` (down_revision: `copilot_claude_001`)

Creates all 10 gatekeeper tables with proper foreign keys to `brands.id`, timestamps, and JSON columns for flexible detail storage.

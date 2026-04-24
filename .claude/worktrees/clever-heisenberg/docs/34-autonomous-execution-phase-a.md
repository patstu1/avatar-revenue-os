# Autonomous Execution + Blocker Escalation — Phase A (control plane)

This phase delivers the **policy, gate evaluation, execution run log, and structured blocker escalation** layer. It does **not** yet wire all 14 loop steps to live publishers or content generators—that is **Phase B+** (per-step adapters).

## What exists (complete for Phase A)

| Area | Implementation |
|------|------------------|
| **Operating modes** | `fully_autonomous`, `guarded_autonomous`, `escalation_only` on `automation_execution_policies` |
| **Guardrails** | Kill-switch, min confidence (execute vs publish-sensitive steps), optional USD caps, guarded approval above cost |
| **Gate evaluation** | Deterministic engine `packages/scoring/autonomous_execution_engine.py`; **GET** `.../automation-gate-preview` is read-only (no DB writes beyond policy read) |
| **Run audit trail** | `automation_execution_runs` stores policy snapshot + payloads; PATCH status; POST rollback marks `rolled_back` |
| **Blocker escalations** | `execution_blocker_escalations` with **`exact_operator_steps_json`** (ordered steps: action, detail, verify). Notifications enqueued as `notification_deliveries` (in_app, pending) — email/Slack delivery remains adapter-bound |
| **API + audit** | Mutations log `audit_logs` via `log_action` |
| **UI** | `/dashboard/autonomous-execution` — policy, gate preview, runs, blockers |

## What is partial / next phases

| Item | Status |
|------|--------|
| **14-step loop automation** | **missing** — requires per-step workers and channel adapters |
| **Provider credentials** | **blocked** until keys provided; use blockers with exact steps to add credentials |
| **Outbound notify (email/slack)** | **partial** — deliveries queued; worker must send (existing notification worker pattern) |

## Migration

Revision **`a2b3c4d5e6f7`** — run `alembic -c packages/db/alembic.ini upgrade head`.

## Honesty

Return status for the overall pack vision: **partial** — Phase A control plane is implementable end-to-end; full autonomous loop completion requires **Phase B+** and **live integrations**.

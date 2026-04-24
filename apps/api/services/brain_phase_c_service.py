"""Brain Architecture Phase C — service layer for agent mesh, workflows, context bus, memory binding."""

from __future__ import annotations

import time
import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.brain_architecture import BrainMemoryEntry
from packages.db.models.brain_phase_c import (
    AgentMessageV2,
    AgentRegistryEntry,
    AgentRunV2,
    CoordinationDecision,
    SharedContextEvent,
    WorkflowCoordinationRun,
)
from packages.scoring.brain_phase_c_engine import (
    WORKFLOW_TEMPLATES,
    build_agent_registry,
    derive_context_events,
    run_agent,
    run_workflow,
)

# ── List helpers ──────────────────────────────────────────────────────


async def list_agent_registry(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    q = await db.execute(
        select(AgentRegistryEntry)
        .where(AgentRegistryEntry.brand_id == brand_id, AgentRegistryEntry.is_active.is_(True))
        .order_by(AgentRegistryEntry.agent_slug)
    )
    return [_registry_out(r) for r in q.scalars().all()]


async def list_agent_runs_v2(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict]:
    q = await db.execute(
        select(AgentRunV2)
        .where(AgentRunV2.brand_id == brand_id, AgentRunV2.is_active.is_(True))
        .order_by(AgentRunV2.created_at.desc())
        .limit(limit)
    )
    return [_run_out(r) for r in q.scalars().all()]


async def list_workflow_coordination(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict]:
    q = await db.execute(
        select(WorkflowCoordinationRun)
        .where(WorkflowCoordinationRun.brand_id == brand_id, WorkflowCoordinationRun.is_active.is_(True))
        .order_by(WorkflowCoordinationRun.created_at.desc())
        .limit(limit)
    )
    return [_workflow_out(r) for r in q.scalars().all()]


async def list_shared_context_events(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 200) -> list[dict]:
    q = await db.execute(
        select(SharedContextEvent)
        .where(SharedContextEvent.brand_id == brand_id, SharedContextEvent.is_active.is_(True))
        .order_by(SharedContextEvent.created_at.desc())
        .limit(limit)
    )
    return [_ctx_event_out(r) for r in q.scalars().all()]


# ── Recompute: full orchestration cycle ───────────────────────────────


async def recompute_agent_mesh(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    _health_map = {"healthy": 1.0, "warning": 0.6, "degraded": 0.35, "critical": 0.15, "suspended": 0.05}

    # Deactivate old records
    await db.execute(
        update(AgentRegistryEntry)
        .where(AgentRegistryEntry.brand_id == brand_id, AgentRegistryEntry.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(AgentRunV2)
        .where(AgentRunV2.brand_id == brand_id, AgentRunV2.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(AgentMessageV2)
        .where(AgentMessageV2.brand_id == brand_id, AgentMessageV2.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(WorkflowCoordinationRun)
        .where(WorkflowCoordinationRun.brand_id == brand_id, WorkflowCoordinationRun.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(CoordinationDecision)
        .where(CoordinationDecision.brand_id == brand_id, CoordinationDecision.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(SharedContextEvent)
        .where(SharedContextEvent.brand_id == brand_id, SharedContextEvent.is_active.is_(True))
        .values(is_active=False)
    )

    # 1. Populate agent registry
    registry_defs = build_agent_registry()
    registry_created = 0
    for rd in registry_defs:
        entry = AgentRegistryEntry(
            brand_id=brand_id,
            agent_slug=rd["agent_slug"],
            agent_label=rd["agent_label"],
            description=rd["description"],
            input_schema_json=rd["input_schema"],
            output_schema_json=rd["output_schema"],
            memory_scopes_json=rd["memory_scopes"],
            upstream_agents_json=rd["upstream_agents"],
            downstream_agents_json=rd["downstream_agents"],
        )
        db.add(entry)
        registry_created += 1

    # 2. Fetch brand context
    accts_q = await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )
    accts = accts_q.scalars().all()

    memory_q = await db.execute(
        select(BrainMemoryEntry)
        .where(BrainMemoryEntry.brand_id == brand_id, BrainMemoryEntry.is_active.is_(True))
        .order_by(BrainMemoryEntry.created_at.desc())
        .limit(30)
    )
    memories = memory_q.scalars().all()
    mem_dicts = [
        {"id": m.id, "entry_type": m.entry_type, "summary": m.summary, "confidence": m.confidence} for m in memories
    ]

    # Build context from accounts
    ctx: dict[str, Any] = {"account_count": len(accts)}
    if accts:
        a = accts[0]
        health_val = a.account_health.value if a.account_health else "healthy"
        ctx.update(
            {
                "account_state": "warming" if health_val in ("healthy", "warning") else "at_risk",
                "platform": a.platform.value if a.platform else "tiktok",
                "saturation_score": float(a.saturation_score or 0),
                "fatigue_score": float(a.fatigue_score or 0),
                "has_blocker": False,
                "opportunity_state": "monitor",
                "organic_winner": float(getattr(a, "profit_per_post", 0) or 0) > 5,
            }
        )

    # 3. Run each agent
    runs_created = 0
    messages_created = 0
    all_context_events: list[dict[str, Any]] = []

    for rd in registry_defs:
        slug = rd["agent_slug"]
        t0 = time.monotonic()
        result = run_agent(slug, ctx, mem_dicts)
        dur = int((time.monotonic() - t0) * 1000)

        run_obj = AgentRunV2(
            brand_id=brand_id,
            agent_slug=slug,
            run_status=result["status"],
            trigger="scheduled_cycle",
            inputs_json=ctx,
            outputs_json=result["outputs"],
            memory_refs_json=result["memory_refs"],
            confidence=result["confidence"],
            duration_ms=dur,
            explanation=result["explanation"],
        )
        db.add(run_obj)
        await db.flush()
        await db.refresh(run_obj)
        runs_created += 1

        msg_in = AgentMessageV2(
            brand_id=brand_id,
            run_id=run_obj.id,
            agent_slug=slug,
            direction="input",
            message_type="context",
            payload_json=ctx,
            explanation=f"Input context for {slug}",
        )
        msg_out = AgentMessageV2(
            brand_id=brand_id,
            run_id=run_obj.id,
            agent_slug=slug,
            direction="output",
            message_type="result",
            payload_json=result["outputs"],
            explanation=result["explanation"],
        )
        db.add(msg_in)
        db.add(msg_out)
        messages_created += 2

        ctx_events = derive_context_events(slug, result["outputs"], ctx)
        all_context_events.extend(ctx_events)

    # 4. Persist context events
    events_created = 0
    for ce in all_context_events:
        ev = SharedContextEvent(
            brand_id=brand_id,
            event_type=ce["event_type"],
            source_module=ce["source_module"],
            target_modules_json=ce["target_modules"],
            payload_json=ce["payload"],
            priority=ce["priority"],
            explanation=ce["explanation"],
        )
        db.add(ev)
        events_created += 1

    # 5. Run workflow coordination
    workflows_created = 0
    coord_decisions_created = 0
    for tmpl in WORKFLOW_TEMPLATES:
        wf_result = run_workflow(tmpl["type"], ctx, mem_dicts)
        wf = WorkflowCoordinationRun(
            brand_id=brand_id,
            workflow_type=tmpl["type"],
            sequence_json=wf_result["sequence"],
            status=wf_result["status"],
            handoff_events_json=wf_result["handoff_events"],
            failure_points_json=wf_result["failure_points"],
            inputs_json=ctx,
            outputs_json=wf_result["outputs"],
            explanation=wf_result["explanation"],
        )
        db.add(wf)
        await db.flush()
        await db.refresh(wf)
        workflows_created += 1

        for he in wf_result["handoff_events"]:
            cd = CoordinationDecision(
                brand_id=brand_id,
                workflow_run_id=wf.id,
                step_index=he["step_index"],
                from_agent=he["from_agent"],
                to_agent=he["to_agent"],
                decision=f"Handoff {','.join(he.get('payload_keys', []))} from {he['from_agent']} to {he['to_agent']}",
                confidence=he.get("confidence", 0.5),
                payload_json=he,
                explanation=f"Step {he['step_index']}: {he['from_agent']} -> {he['to_agent']}",
            )
            db.add(cd)
            coord_decisions_created += 1

    await db.flush()
    return {
        "registry_created": registry_created,
        "agent_runs_created": runs_created,
        "messages_created": messages_created,
        "context_events_created": events_created,
        "workflows_created": workflows_created,
        "coordination_decisions_created": coord_decisions_created,
    }


# ── Serialization helpers ─────────────────────────────────────────────


def _registry_out(r: AgentRegistryEntry) -> dict[str, Any]:
    return {
        "id": r.id,
        "brand_id": r.brand_id,
        "agent_slug": r.agent_slug,
        "agent_label": r.agent_label,
        "description": r.description,
        "input_schema_json": r.input_schema_json,
        "output_schema_json": r.output_schema_json,
        "memory_scopes_json": r.memory_scopes_json,
        "upstream_agents_json": r.upstream_agents_json,
        "downstream_agents_json": r.downstream_agents_json,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _run_out(r: AgentRunV2) -> dict[str, Any]:
    return {
        "id": r.id,
        "brand_id": r.brand_id,
        "agent_slug": r.agent_slug,
        "run_status": r.run_status,
        "trigger": r.trigger,
        "inputs_json": r.inputs_json,
        "outputs_json": r.outputs_json,
        "memory_refs_json": r.memory_refs_json,
        "confidence": r.confidence,
        "duration_ms": r.duration_ms,
        "error_detail": r.error_detail,
        "explanation": r.explanation,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _workflow_out(w: WorkflowCoordinationRun) -> dict[str, Any]:
    return {
        "id": w.id,
        "brand_id": w.brand_id,
        "workflow_type": w.workflow_type,
        "sequence_json": w.sequence_json,
        "status": w.status,
        "handoff_events_json": w.handoff_events_json,
        "failure_points_json": w.failure_points_json,
        "inputs_json": w.inputs_json,
        "outputs_json": w.outputs_json,
        "explanation": w.explanation,
        "is_active": w.is_active,
        "created_at": w.created_at,
        "updated_at": w.updated_at,
    }


def _ctx_event_out(e: SharedContextEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "brand_id": e.brand_id,
        "event_type": e.event_type,
        "source_module": e.source_module,
        "target_modules_json": e.target_modules_json,
        "payload_json": e.payload_json,
        "priority": e.priority,
        "consumed": e.consumed,
        "explanation": e.explanation,
        "is_active": e.is_active,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }

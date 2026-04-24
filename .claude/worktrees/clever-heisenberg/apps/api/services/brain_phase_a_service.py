"""Brain Architecture Phase A — service layer for memory, account/opportunity/execution/audience states."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.autonomous_phase_a import AccountOutputReport
from packages.db.models.autonomous_phase_b import AutonomousRun, MonetizationRoute, SuppressionExecution
from packages.db.models.brain_architecture import (
    AccountStateSnapshot,
    AudienceStateSnapshotV2,
    BrainMemoryEntry,
    BrainMemoryLink,
    ExecutionStateSnapshot,
    OpportunityStateSnapshot,
    StateTransitionEvent,
)
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.publishing import PerformanceMetric
from packages.db.models.recovery import RecoveryIncident
from packages.db.models.scoring import OpportunityScore
from packages.scoring.brain_phase_a_engine import (
    compute_account_state,
    compute_audience_state_v2,
    compute_execution_state,
    compute_opportunity_state,
    consolidate_brain_memory,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── helpers ───────────────────────────────────────────────────────────

def _entry_out(e: BrainMemoryEntry) -> dict[str, Any]:
    return {
        "id": e.id, "brand_id": e.brand_id, "entry_type": e.entry_type,
        "scope_type": e.scope_type, "scope_id": e.scope_id,
        "summary": e.summary, "confidence": e.confidence,
        "reuse_recommendation": e.reuse_recommendation,
        "suppression_caution": e.suppression_caution,
        "platform": e.platform, "niche": e.niche,
        "detail_json": e.detail_json, "explanation": e.explanation,
        "is_active": e.is_active, "created_at": e.created_at, "updated_at": e.updated_at,
    }


def _link_out(lk: BrainMemoryLink) -> dict[str, Any]:
    return {
        "id": lk.id, "brand_id": lk.brand_id,
        "source_entry_id": lk.source_entry_id, "target_entry_id": lk.target_entry_id,
        "link_type": lk.link_type, "strength": lk.strength,
        "explanation": lk.explanation, "is_active": lk.is_active,
        "created_at": lk.created_at, "updated_at": lk.updated_at,
    }


def _acct_state_out(s: AccountStateSnapshot) -> dict[str, Any]:
    return {
        "id": s.id, "brand_id": s.brand_id, "account_id": s.account_id,
        "current_state": s.current_state, "state_score": s.state_score,
        "previous_state": s.previous_state, "transition_reason": s.transition_reason,
        "next_expected_state": s.next_expected_state, "days_in_state": s.days_in_state,
        "platform": s.platform, "inputs_json": s.inputs_json,
        "confidence": s.confidence, "explanation": s.explanation,
        "is_active": s.is_active, "created_at": s.created_at, "updated_at": s.updated_at,
    }


def _opp_state_out(s: OpportunityStateSnapshot) -> dict[str, Any]:
    return {
        "id": s.id, "brand_id": s.brand_id,
        "opportunity_scope": s.opportunity_scope, "opportunity_id": s.opportunity_id,
        "current_state": s.current_state, "urgency": s.urgency,
        "readiness": s.readiness, "suppression_risk": s.suppression_risk,
        "expected_upside": s.expected_upside, "expected_cost": s.expected_cost,
        "inputs_json": s.inputs_json, "confidence": s.confidence,
        "explanation": s.explanation, "is_active": s.is_active,
        "created_at": s.created_at, "updated_at": s.updated_at,
    }


def _exec_state_out(s: ExecutionStateSnapshot) -> dict[str, Any]:
    return {
        "id": s.id, "brand_id": s.brand_id,
        "execution_scope": s.execution_scope, "execution_id": s.execution_id,
        "current_state": s.current_state, "transition_reason": s.transition_reason,
        "rollback_eligible": s.rollback_eligible, "escalation_required": s.escalation_required,
        "failure_count": s.failure_count, "inputs_json": s.inputs_json,
        "confidence": s.confidence, "explanation": s.explanation,
        "is_active": s.is_active, "created_at": s.created_at, "updated_at": s.updated_at,
    }


def _aud_state_out(s: AudienceStateSnapshotV2) -> dict[str, Any]:
    return {
        "id": s.id, "brand_id": s.brand_id,
        "segment_label": s.segment_label, "current_state": s.current_state,
        "state_score": s.state_score,
        "transition_likelihoods_json": s.transition_likelihoods_json,
        "next_best_action": s.next_best_action,
        "estimated_segment_size": s.estimated_segment_size,
        "estimated_ltv": s.estimated_ltv,
        "inputs_json": s.inputs_json, "confidence": s.confidence,
        "explanation": s.explanation, "is_active": s.is_active,
        "created_at": s.created_at, "updated_at": s.updated_at,
    }


# =====================================================================
# 1. Brain Memory
# =====================================================================

async def list_brain_memory(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> dict[str, Any]:
    entries_q = await db.execute(
        select(BrainMemoryEntry)
        .where(BrainMemoryEntry.brand_id == brand_id, BrainMemoryEntry.is_active.is_(True))
        .order_by(BrainMemoryEntry.created_at.desc()).limit(limit)
    )
    entries = entries_q.scalars().all()
    links_q = await db.execute(
        select(BrainMemoryLink)
        .where(BrainMemoryLink.brand_id == brand_id, BrainMemoryLink.is_active.is_(True))
        .order_by(BrainMemoryLink.created_at.desc()).limit(limit)
    )
    links = links_q.scalars().all()
    return {"entries": [_entry_out(e) for e in entries], "links": [_link_out(lk) for lk in links]}


async def recompute_brain_memory(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    _health_map = {"healthy": 1.0, "warning": 0.6, "degraded": 0.35, "critical": 0.15, "suspended": 0.05}

    accts_q = await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )
    accts = accts_q.scalars().all()
    account_ctx = []
    for a in accts:
        health_val = a.account_health.value if a.account_health else "healthy"
        account_ctx.append({
            "id": str(a.id),
            "platform": a.platform.value if a.platform else "unknown",
            "niche": a.niche_focus or "",
            "profit_per_post": float(getattr(a, "profit_per_post", 0) or 0),
            "avg_engagement": float(getattr(a, "avg_engagement", 0) or 0),
            "age_days": ((_utc_now() - a.created_at).days if a.created_at else 0),
        })

    offers_q = await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )
    offers = offers_q.scalars().all()
    offer_ctx = [{
        "id": str(o.id),
        "niche": "",
        "epc": float(o.epc or 0),
        "conversion_rate": float(o.conversion_rate or 0),
    } for o in offers]

    supp_q = await db.execute(
        select(SuppressionExecution)
        .where(SuppressionExecution.brand_id == brand_id, SuppressionExecution.is_active.is_(True))
        .order_by(SuppressionExecution.created_at.desc()).limit(20)
    )
    supps = supp_q.scalars().all()
    supp_ctx = [{
        "scope_type": s.suppression_type or "content",
        "scope_id": str(s.id),
        "platform": None,
        "reason": s.trigger_reason or "",
        "confidence": float(s.confidence or 0.5),
        "detail": {},
    } for s in supps]

    recovery_q = await db.execute(
        select(RecoveryIncident)
        .where(RecoveryIncident.brand_id == brand_id, RecoveryIncident.is_active.is_(True))
        .order_by(RecoveryIncident.created_at.desc()).limit(20)
    )
    recoveries = recovery_q.scalars().all()
    rec_ctx = [{
        "scope_type": "system",
        "scope_id": str(r.id),
        "platform": None,
        "incident_type": r.incident_type or "unknown",
        "confidence": 0.55,
        "detail": {},
        "explanation": r.explanation or "",
        "fix": r.recommended_action or None,
    } for r in recoveries]

    ctx = {
        "accounts": account_ctx,
        "offers": offer_ctx,
        "suppression_history": supp_ctx,
        "recovery_incidents": rec_ctx,
        "top_content": [],
    }
    new_entries = consolidate_brain_memory(ctx)

    await db.execute(
        update(BrainMemoryEntry)
        .where(BrainMemoryEntry.brand_id == brand_id, BrainMemoryEntry.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    entry_ids = []
    for raw in new_entries:
        sid = raw.get("scope_id")
        entry = BrainMemoryEntry(
            brand_id=brand_id,
            entry_type=raw["entry_type"],
            scope_type=raw["scope_type"],
            scope_id=uuid.UUID(sid) if sid else None,
            summary=raw["summary"],
            confidence=raw.get("confidence", 0.5),
            reuse_recommendation=raw.get("reuse_recommendation"),
            suppression_caution=raw.get("suppression_caution"),
            platform=raw.get("platform"),
            niche=raw.get("niche"),
            detail_json=raw.get("detail_json", {}),
            explanation=raw.get("explanation"),
        )
        db.add(entry)
        await db.flush()
        await db.refresh(entry)
        entry_ids.append(entry.id)
        created += 1

    links_created = 0
    if len(entry_ids) >= 2:
        for i in range(len(entry_ids) - 1):
            link = BrainMemoryLink(
                brand_id=brand_id,
                source_entry_id=entry_ids[i],
                target_entry_id=entry_ids[i + 1],
                link_type="temporal_sequence",
                strength=0.5,
                explanation="Sequentially generated memory entries",
            )
            db.add(link)
            links_created += 1

    await db.flush()
    return {"entries_created": created, "links_created": links_created}


# =====================================================================
# 2. Account State
# =====================================================================

async def list_account_states(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict[str, Any]]:
    q = await db.execute(
        select(AccountStateSnapshot)
        .where(AccountStateSnapshot.brand_id == brand_id, AccountStateSnapshot.is_active.is_(True))
        .order_by(AccountStateSnapshot.created_at.desc()).limit(limit)
    )
    return [_acct_state_out(r) for r in q.scalars().all()]


async def recompute_account_states(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    _health_map = {"healthy": 1.0, "warning": 0.6, "degraded": 0.35, "critical": 0.15, "suspended": 0.05}

    accts_q = await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )
    accts = accts_q.scalars().all()

    await db.execute(
        update(AccountStateSnapshot)
        .where(AccountStateSnapshot.brand_id == brand_id, AccountStateSnapshot.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    transitions = 0
    for a in accts:
        health_val = a.account_health.value if a.account_health else "healthy"
        age_days = (_utc_now() - a.created_at).days if a.created_at else 0
        ctx = {
            "follower_count": int(getattr(a, "follower_count", 0) or 0),
            "age_days": age_days,
            "avg_engagement": float(getattr(a, "avg_engagement", 0) or 0),
            "profit_per_post": float(getattr(a, "profit_per_post", 0) or 0),
            "fatigue_score": float(getattr(a, "fatigue_score", 0) or 0),
            "saturation_score": float(getattr(a, "saturation_score", 0) or 0),
            "account_health": health_val,
            "posting_capacity_per_day": int(getattr(a, "posting_capacity_per_day", 1) or 1),
            "output_per_week": float(getattr(a, "output_per_week", 0) or 0),
        }
        result = compute_account_state(ctx)

        prev_q = await db.execute(
            select(AccountStateSnapshot)
            .where(
                AccountStateSnapshot.brand_id == brand_id,
                AccountStateSnapshot.account_id == a.id,
                AccountStateSnapshot.is_active.is_(False),
            )
            .order_by(AccountStateSnapshot.created_at.desc()).limit(1)
        )
        prev = prev_q.scalar_one_or_none()
        prev_state = prev.current_state if prev else None

        snap = AccountStateSnapshot(
            brand_id=brand_id,
            account_id=a.id,
            current_state=result["current_state"],
            state_score=result["state_score"],
            previous_state=prev_state,
            transition_reason=result["transition_reason"],
            next_expected_state=result["next_expected_state"],
            days_in_state=age_days,
            platform=a.platform.value if a.platform else None,
            inputs_json=ctx,
            confidence=result["confidence"],
            explanation=result["explanation"],
        )
        db.add(snap)
        await db.flush()
        await db.refresh(snap)
        created += 1

        if prev_state and prev_state != result["current_state"]:
            te = StateTransitionEvent(
                brand_id=brand_id,
                engine_type="account",
                entity_id=a.id,
                from_state=prev_state,
                to_state=result["current_state"],
                trigger=result["transition_reason"],
                confidence=result["confidence"],
                explanation=result["explanation"],
            )
            db.add(te)
            transitions += 1

    await db.flush()
    return {"account_states_created": created, "transitions_recorded": transitions}


# =====================================================================
# 3. Opportunity State
# =====================================================================

async def list_opportunity_states(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict[str, Any]]:
    q = await db.execute(
        select(OpportunityStateSnapshot)
        .where(OpportunityStateSnapshot.brand_id == brand_id, OpportunityStateSnapshot.is_active.is_(True))
        .order_by(OpportunityStateSnapshot.created_at.desc()).limit(limit)
    )
    return [_opp_state_out(r) for r in q.scalars().all()]


async def recompute_opportunity_states(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    scores_q = await db.execute(
        select(OpportunityScore)
        .where(OpportunityScore.brand_id == brand_id)
        .order_by(OpportunityScore.created_at.desc()).limit(50)
    )
    scores = scores_q.scalars().all()

    await db.execute(
        update(OpportunityStateSnapshot)
        .where(OpportunityStateSnapshot.brand_id == brand_id, OpportunityStateSnapshot.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    transitions = 0
    for sc in scores:
        ctx = {
            "opportunity_score": float(sc.composite_score or 0),
            "tests_run": 0,
            "win_rate": 0.0,
            "has_blocker": False,
            "suppression_risk": 0.0,
            "urgency": float(getattr(sc, "urgency", 0.5) or 0.5),
            "readiness": float(getattr(sc, "readiness", 0.5) or 0.5),
            "expected_upside": float(getattr(sc, "expected_upside", 0) or 0),
            "expected_cost": float(getattr(sc, "expected_cost", 0) or 0),
        }
        result = compute_opportunity_state(ctx)

        prev_q = await db.execute(
            select(OpportunityStateSnapshot)
            .where(
                OpportunityStateSnapshot.brand_id == brand_id,
                OpportunityStateSnapshot.opportunity_id == sc.id,
                OpportunityStateSnapshot.is_active.is_(False),
            )
            .order_by(OpportunityStateSnapshot.created_at.desc()).limit(1)
        )
        prev = prev_q.scalar_one_or_none()
        prev_state = prev.current_state if prev else None

        snap = OpportunityStateSnapshot(
            brand_id=brand_id,
            opportunity_scope="opportunity_score",
            opportunity_id=sc.id,
            current_state=result["current_state"],
            urgency=result["urgency"],
            readiness=result["readiness"],
            suppression_risk=result["suppression_risk"],
            expected_upside=result["expected_upside"],
            expected_cost=result["expected_cost"],
            inputs_json=ctx,
            confidence=result["confidence"],
            explanation=result["explanation"],
        )
        db.add(snap)
        await db.flush()
        await db.refresh(snap)
        created += 1

        if prev_state and prev_state != result["current_state"]:
            te = StateTransitionEvent(
                brand_id=brand_id,
                engine_type="opportunity",
                entity_id=sc.id,
                from_state=prev_state,
                to_state=result["current_state"],
                trigger=result["explanation"],
                confidence=result["confidence"],
                explanation=result["explanation"],
            )
            db.add(te)
            transitions += 1

    await db.flush()
    return {"opportunity_states_created": created, "transitions_recorded": transitions}


# =====================================================================
# 4. Execution State
# =====================================================================

async def list_execution_states(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict[str, Any]]:
    q = await db.execute(
        select(ExecutionStateSnapshot)
        .where(ExecutionStateSnapshot.brand_id == brand_id, ExecutionStateSnapshot.is_active.is_(True))
        .order_by(ExecutionStateSnapshot.created_at.desc()).limit(limit)
    )
    return [_exec_state_out(r) for r in q.scalars().all()]


async def recompute_execution_states(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    runs_q = await db.execute(
        select(AutonomousRun)
        .where(AutonomousRun.brand_id == brand_id, AutonomousRun.is_active.is_(True))
        .order_by(AutonomousRun.created_at.desc()).limit(50)
    )
    runs = runs_q.scalars().all()

    await db.execute(
        update(ExecutionStateSnapshot)
        .where(ExecutionStateSnapshot.brand_id == brand_id, ExecutionStateSnapshot.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    transitions = 0
    for r in runs:
        ctx = {
            "execution_mode": r.execution_mode or "manual",
            "run_status": r.run_status or "queued",
            "failure_count": int(getattr(r, "failure_count", 0) or 0),
            "confidence": float(getattr(r, "confidence", 0.5) or 0.5),
            "estimated_cost": float(getattr(r, "estimated_cost", 0) or 0),
            "require_approval_above_cost": 75.0,
            "has_blocker": False,
        }
        result = compute_execution_state(ctx)

        prev_q = await db.execute(
            select(ExecutionStateSnapshot)
            .where(
                ExecutionStateSnapshot.brand_id == brand_id,
                ExecutionStateSnapshot.execution_id == r.id,
                ExecutionStateSnapshot.is_active.is_(False),
            )
            .order_by(ExecutionStateSnapshot.created_at.desc()).limit(1)
        )
        prev = prev_q.scalar_one_or_none()
        prev_state = prev.current_state if prev else None

        snap = ExecutionStateSnapshot(
            brand_id=brand_id,
            execution_scope="autonomous_run",
            execution_id=r.id,
            current_state=result["current_state"],
            transition_reason=result["transition_reason"],
            rollback_eligible=result["rollback_eligible"],
            escalation_required=result["escalation_required"],
            failure_count=result["failure_count"],
            inputs_json=ctx,
            confidence=result["confidence"],
            explanation=result["explanation"],
        )
        db.add(snap)
        await db.flush()
        await db.refresh(snap)
        created += 1

        if prev_state and prev_state != result["current_state"]:
            te = StateTransitionEvent(
                brand_id=brand_id,
                engine_type="execution",
                entity_id=r.id,
                from_state=prev_state,
                to_state=result["current_state"],
                trigger=result["transition_reason"],
                confidence=result["confidence"],
                explanation=result["explanation"],
            )
            db.add(te)
            transitions += 1

    await db.flush()
    return {"execution_states_created": created, "transitions_recorded": transitions}


# =====================================================================
# 5. Audience State V2
# =====================================================================

async def list_audience_states_v2(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict[str, Any]]:
    q = await db.execute(
        select(AudienceStateSnapshotV2)
        .where(AudienceStateSnapshotV2.brand_id == brand_id, AudienceStateSnapshotV2.is_active.is_(True))
        .order_by(AudienceStateSnapshotV2.created_at.desc()).limit(limit)
    )
    return [_aud_state_out(r) for r in q.scalars().all()]


async def recompute_audience_states_v2(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    from packages.db.models.offers import AudienceSegment

    segments_q = await db.execute(
        select(AudienceSegment)
        .where(AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True))
    )
    segments = segments_q.scalars().all()

    await db.execute(
        update(AudienceStateSnapshotV2)
        .where(AudienceStateSnapshotV2.brand_id == brand_id, AudienceStateSnapshotV2.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    transitions = 0
    if not segments:
        default_labels = ["top_of_funnel", "evaluating_prospects", "existing_customers"]
        for label in default_labels:
            ctx = {
                "purchase_count": 0 if "funnel" in label else 1,
                "ltv": 0 if "funnel" in label else 50.0,
                "engagement_recency_days": 7,
                "churn_risk": 0.15,
                "objection_signals": 0,
                "referral_activity": 0,
                "sponsor_fit_score": 0.0,
                "content_views_30d": 20 if "funnel" in label else 5,
                "cta_clicks_30d": 1 if "funnel" in label else 0,
            }
            result = compute_audience_state_v2(ctx)
            snap = AudienceStateSnapshotV2(
                brand_id=brand_id,
                segment_label=label,
                current_state=result["current_state"],
                state_score=result["state_score"],
                transition_likelihoods_json=result["transition_likelihoods"],
                next_best_action=result["next_best_action"],
                estimated_segment_size=0,
                estimated_ltv=result["estimated_ltv"],
                inputs_json=ctx,
                confidence=result["confidence"],
                explanation=result["explanation"],
            )
            db.add(snap)
            await db.flush()
            await db.refresh(snap)
            created += 1
    else:
        for seg in segments:
            est_size = int(seg.estimated_size or 0)
            ctx = {
                "purchase_count": int(getattr(seg, "avg_purchase_count", 0) or 0),
                "ltv": float(getattr(seg, "avg_ltv", 0) or 0),
                "engagement_recency_days": int(getattr(seg, "engagement_recency_days", 30) or 30),
                "churn_risk": float(getattr(seg, "churn_risk", 0.2) or 0.2),
                "objection_signals": 0,
                "referral_activity": 0,
                "sponsor_fit_score": 0.0,
                "content_views_30d": int(getattr(seg, "content_views_30d", 10) or 10),
                "cta_clicks_30d": int(getattr(seg, "cta_clicks_30d", 0) or 0),
            }
            result = compute_audience_state_v2(ctx)

            prev_q = await db.execute(
                select(AudienceStateSnapshotV2)
                .where(
                    AudienceStateSnapshotV2.brand_id == brand_id,
                    AudienceStateSnapshotV2.segment_label == seg.name,
                    AudienceStateSnapshotV2.is_active.is_(False),
                )
                .order_by(AudienceStateSnapshotV2.created_at.desc()).limit(1)
            )
            prev = prev_q.scalar_one_or_none()
            prev_state = prev.current_state if prev else None

            snap = AudienceStateSnapshotV2(
                brand_id=brand_id,
                segment_label=seg.name or f"segment_{seg.id}",
                current_state=result["current_state"],
                state_score=result["state_score"],
                transition_likelihoods_json=result["transition_likelihoods"],
                next_best_action=result["next_best_action"],
                estimated_segment_size=est_size,
                estimated_ltv=result["estimated_ltv"],
                inputs_json=ctx,
                confidence=result["confidence"],
                explanation=result["explanation"],
            )
            db.add(snap)
            await db.flush()
            await db.refresh(snap)
            created += 1

            if prev_state and prev_state != result["current_state"]:
                te = StateTransitionEvent(
                    brand_id=brand_id,
                    engine_type="audience",
                    entity_id=seg.id,
                    from_state=prev_state,
                    to_state=result["current_state"],
                    trigger=result["explanation"],
                    confidence=result["confidence"],
                    explanation=result["explanation"],
                )
                db.add(te)
                transitions += 1

    await db.flush()
    return {"audience_states_created": created, "transitions_recorded": transitions}

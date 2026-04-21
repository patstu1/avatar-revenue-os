"""GM situation computations (Batch 7A).

Pure read-only aggregations over the canonical data tables listed in
``gm_doctrine.CANONICAL_DATA_TABLES``. Returns plain dicts that the
``gm_operating`` router surfaces as JSON endpoints.

Five computations:

    compute_floor_status    trailing-30d revenue vs nearest floor
    compute_pipeline_state  entity counts per stage + worst bottleneck
    compute_bottlenecks     ranked list of stage-level blockages
    compute_closest_revenue what is one step from money right now
    compute_blocking_floors what specifically gates the next floor
    compute_game_plan       consolidated ranked action list (priority engine)

All five are org-scoped. Zero mutations. Zero LLM calls.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.gm_doctrine import (
    FLOOR_MONTH_1_CENTS,
    FLOOR_MONTH_12_CENTS,
    PRIORITY_RANK,
    STAGE_MACHINE,
    floor_for_month,
)
from packages.db.models.clients import Client, IntakeRequest, IntakeSubmission
from packages.db.models.delivery import Delivery, ProductionQAReview
from packages.db.models.email_pipeline import (
    EmailClassification,
    EmailMessage,
    EmailReplyDraft,
    EmailThread,
)
from packages.db.models.fulfillment import ClientProject, ProductionJob, ProjectBrief
from packages.db.models.gm_control import GMApproval, GMEscalation, StageState
from packages.db.models.proposals import Payment, PaymentLink, Proposal
from packages.db.models.system_events import OperatorAction, SystemEvent


# ═══════════════════════════════════════════════════════════════════════════
#  Floor status
# ═══════════════════════════════════════════════════════════════════════════


async def compute_floor_status(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    """Return the trailing-30-day captured revenue vs the floor for this
    month index. month_index=1 → $30K floor, month_index=12 → $1M floor.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    total_cents = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                Payment.org_id == org_id,
                Payment.status == "succeeded",
                Payment.is_active.is_(True),
                Payment.completed_at >= since,
            )
        )
    ).scalar() or 0

    payment_count = (
        await db.execute(
            select(func.count(Payment.id)).where(
                Payment.org_id == org_id,
                Payment.status == "succeeded",
                Payment.completed_at >= since,
            )
        )
    ).scalar() or 0

    floor_cents = floor_for_month(month_index)
    gap_cents = max(0, floor_cents - int(total_cents))
    ratio = (int(total_cents) / floor_cents) if floor_cents else 0.0

    # Run-rate: if last 7 days held, project to 30 days
    since_7 = now - timedelta(days=7)
    last7_cents = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(
                Payment.org_id == org_id,
                Payment.status == "succeeded",
                Payment.completed_at >= since_7,
            )
        )
    ).scalar() or 0
    projected_30d_cents = int(round((int(last7_cents) / 7.0) * 30))
    projected_ratio = (projected_30d_cents / floor_cents) if floor_cents else 0.0

    return {
        "now": now.isoformat(),
        "window_days": 30,
        "org_id": str(org_id),
        "month_index": month_index,
        "floor_cents": floor_cents,
        "floor_usd": floor_cents / 100.0,
        "trailing_30d_cents": int(total_cents),
        "trailing_30d_usd": int(total_cents) / 100.0,
        "payment_count_30d": int(payment_count),
        "gap_cents": gap_cents,
        "gap_usd": gap_cents / 100.0,
        "ratio_to_floor": round(ratio, 4),
        "last_7d_cents": int(last7_cents),
        "projected_30d_cents_at_7d_runrate": projected_30d_cents,
        "projected_ratio_to_floor": round(projected_ratio, 4),
        "floor_met": int(total_cents) >= floor_cents,
        "month_1_floor_cents": FLOOR_MONTH_1_CENTS,
        "month_12_floor_cents": FLOOR_MONTH_12_CENTS,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Pipeline state — entity counts per stage + worst bottleneck
# ═══════════════════════════════════════════════════════════════════════════


async def compute_pipeline_state(db: AsyncSession, *, org_id: uuid.UUID) -> dict:
    """Enumerate the pipeline by stage and surface the worst bottleneck.

    Returns a dict keyed by the 11 doctrine stages with entity counts and
    a "bottleneck" field highlighting the stage with the most in-flight
    entities or stuck entries.
    """
    stages: list[dict] = []

    # Stage 1 — lead.created: leads without a score/route yet
    from packages.db.models.core import Brand
    brand_ids_sub = (
        select(Brand.id).where(Brand.organization_id == org_id)
    )
    # For simplicity we surface total leads-in-org as stage_1 active
    # (the deep classification of scored-vs-unscored needs scoring
    # subsystem columns not present here; this gives an honest row count)
    from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
    stage_1_count = (
        await db.execute(
            select(func.count(LeadOpportunity.id)).where(
                LeadOpportunity.brand_id.in_(brand_ids_sub)
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(1, "lead.created", stage_1_count))

    # Stage 4 — reply.received: email_reply_drafts pending
    stage_4_count = (
        await db.execute(
            select(func.count(EmailReplyDraft.id)).where(
                EmailReplyDraft.org_id == org_id,
                EmailReplyDraft.status == "pending",
                EmailReplyDraft.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(4, "reply.received", stage_4_count))

    # Stage 5 — proposal.ready: drafts approved but no proposal yet
    # (proxy: approved drafts whose thread has no proposal)
    stage_5_pending_proposals = (
        await db.execute(
            select(func.count(Proposal.id)).where(
                Proposal.org_id == org_id,
                Proposal.status == "draft",
                Proposal.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(5, "proposal.ready", stage_5_pending_proposals))

    # Stage 6 — proposal.sent unpaid
    stage_6_count = (
        await db.execute(
            select(func.count(Proposal.id)).where(
                Proposal.org_id == org_id,
                Proposal.status == "sent",
                Proposal.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(6, "proposal.sent", stage_6_count))

    # Stage 7 — payment.completed no client (broken cascade)
    now = datetime.now(timezone.utc)
    broken_cascade = (
        await db.execute(
            select(func.count(Payment.id)).where(
                Payment.org_id == org_id,
                Payment.status == "succeeded",
                Payment.completed_at >= (now - timedelta(days=30)),
                Payment.is_active.is_(True),
            )
        )
    ).scalar() or 0
    clients_count = (
        await db.execute(
            select(func.count(Client.id)).where(
                Client.org_id == org_id,
                Client.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(7, "payment.completed",
                               {"payments_30d": broken_cascade, "clients_total": clients_count}))

    # Stage 8 — intake pending
    stage_8_count = (
        await db.execute(
            select(func.count(IntakeRequest.id)).where(
                IntakeRequest.org_id == org_id,
                IntakeRequest.status.in_(("pending", "sent", "viewed")),
                IntakeRequest.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(8, "intake.pending", stage_8_count))

    # Stage 9 — production active
    stage_9_count = (
        await db.execute(
            select(func.count(ProductionJob.id)).where(
                ProductionJob.org_id == org_id,
                ProductionJob.status == "running",
                ProductionJob.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(9, "production.active", stage_9_count))

    # Stage 10 — QA pending
    stage_10_count = (
        await db.execute(
            select(func.count(ProductionJob.id)).where(
                ProductionJob.org_id == org_id,
                ProductionJob.status == "qa_pending",
                ProductionJob.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(10, "qa", stage_10_count))

    # Stage 11 — delivery pending (qa_passed awaiting dispatch)
    stage_11_count = (
        await db.execute(
            select(func.count(ProductionJob.id)).where(
                ProductionJob.org_id == org_id,
                ProductionJob.status == "qa_passed",
                ProductionJob.is_active.is_(True),
            )
        )
    ).scalar() or 0
    stages.append(_stage_entry(11, "delivery", stage_11_count))

    # Pick worst bottleneck — stage with largest in-flight count
    def _numeric(v: Any) -> int:
        if isinstance(v, dict):
            return sum(int(x) for x in v.values() if isinstance(x, (int, float)))
        try:
            return int(v)
        except Exception:
            return 0

    worst = max(stages, key=lambda s: _numeric(s["count"])) if stages else None

    return {
        "org_id": str(org_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stages": stages,
        "bottleneck": worst,
        "total_stages_tracked": len(stages),
    }


def _stage_entry(n: int, name: str, count: Any) -> dict:
    spec = next((s for s in STAGE_MACHINE if s["n"] == n), None)
    return {
        "stage": n,
        "name": name,
        "pillar": spec["pillar"] if spec else None,
        "count": count,
        "timeout_minutes": spec["timeout_minutes"] if spec else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Bottlenecks — ranked list of stuck stages
# ═══════════════════════════════════════════════════════════════════════════


async def compute_bottlenecks(db: AsyncSession, *, org_id: uuid.UUID) -> dict:
    """Rank stage-level blockages by (is_stuck first, most overdue second).

    Reads stage_states — the same table the stuck_stage_watcher writes
    to. Bottlenecks surface the actual entities past SLA so operator can
    act, not a theoretical alert.
    """
    now = datetime.now(timezone.utc)

    stuck = (
        await db.execute(
            select(StageState).where(
                StageState.org_id == org_id,
                StageState.is_active.is_(True),
                StageState.sla_deadline.is_not(None),
            ).order_by(StageState.sla_deadline.asc())
        )
    ).scalars().all()

    ranked: list[dict] = []
    for s in stuck:
        overdue_minutes = None
        if s.sla_deadline:
            delta = now - s.sla_deadline
            overdue_minutes = int(delta.total_seconds() // 60)
        status = "stuck" if s.is_stuck else ("overdue" if (overdue_minutes and overdue_minutes > 0) else "on_track")
        ranked.append({
            "entity_type": s.entity_type,
            "entity_id": str(s.entity_id),
            "stage": s.stage,
            "entered_at": s.entered_at.isoformat() if s.entered_at else None,
            "sla_deadline": s.sla_deadline.isoformat() if s.sla_deadline else None,
            "overdue_minutes": overdue_minutes,
            "status": status,
            "stuck_reason": s.stuck_reason,
        })

    # Stuck first, then most overdue
    ranked.sort(key=lambda r: (not (r["status"] == "stuck"), -(r["overdue_minutes"] or 0)))

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "total_tracked": len(ranked),
        "total_stuck": sum(1 for r in ranked if r["status"] == "stuck"),
        "total_overdue": sum(1 for r in ranked if r["status"] in ("stuck", "overdue")),
        "ranked": ranked[:50],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Closest revenue — one-step-to-money items ranked by $
# ═══════════════════════════════════════════════════════════════════════════


async def compute_closest_revenue(db: AsyncSession, *, org_id: uuid.UUID) -> dict:
    """Enumerate entities that are one action away from money.

    Categories (ranked):
      A. proposals.status='sent' with active payment_link and no payment
         (ready to be paid — operator may need to nudge)
      B. email_reply_drafts with classification.intent in money-intent set
         and status='pending' (needs approve → send → proposal)
      C. email_reply_drafts status='approved' awaiting send worker
      D. intake_requests status='sent' but viewed more than N minutes ago
         with no submission (needs reminder)
    """
    from apps.api.services.gm_doctrine import CANONICAL_DATA_TABLES  # noqa: F401

    now = datetime.now(timezone.utc)

    # A — sent proposals not yet paid
    A_rows = (
        await db.execute(
            select(Proposal).where(
                Proposal.org_id == org_id,
                Proposal.status == "sent",
                Proposal.is_active.is_(True),
            ).order_by(Proposal.total_amount_cents.desc()).limit(25)
        )
    ).scalars().all()
    A = [
        {
            "type": "proposal_sent_unpaid",
            "proposal_id": str(p.id),
            "recipient_email": p.recipient_email,
            "amount_cents": p.total_amount_cents,
            "sent_at": p.sent_at.isoformat() if p.sent_at else None,
            "hours_since_sent": (
                int((now - p.sent_at).total_seconds() // 3600) if p.sent_at else None
            ),
        }
        for p in A_rows
    ]

    # B — approved/pending drafts with money-intent classification
    money_intents = ("pricing_request", "warm_interest", "negotiation")
    B_rows = (
        await db.execute(
            select(EmailReplyDraft, EmailClassification)
            .join(
                EmailClassification,
                EmailClassification.id == EmailReplyDraft.classification_id,
                isouter=True,
            )
            .where(
                EmailReplyDraft.org_id == org_id,
                EmailReplyDraft.status == "pending",
                EmailReplyDraft.is_active.is_(True),
                EmailClassification.intent.in_(money_intents),
            )
            .limit(25)
        )
    ).all()
    B = [
        {
            "type": "draft_pending_money_intent",
            "draft_id": str(d.id),
            "to_email": d.to_email,
            "intent": c.intent if c else None,
            "confidence": float(c.confidence) if c else None,
            "created_at": d.created_at.isoformat(),
        }
        for d, c in B_rows
    ]

    # C — approved drafts awaiting beat cycle send
    C_rows = (
        await db.execute(
            select(EmailReplyDraft).where(
                EmailReplyDraft.org_id == org_id,
                EmailReplyDraft.status == "approved",
                EmailReplyDraft.is_active.is_(True),
            ).limit(25)
        )
    ).scalars().all()
    C = [
        {
            "type": "draft_approved_pending_send",
            "draft_id": str(d.id),
            "to_email": d.to_email,
            "approved_at": d.approved_at.isoformat() if d.approved_at else None,
        }
        for d in C_rows
    ]

    # D — intakes sent but unsubmitted
    D_rows = (
        await db.execute(
            select(IntakeRequest).where(
                IntakeRequest.org_id == org_id,
                IntakeRequest.status.in_(("sent", "viewed")),
                IntakeRequest.is_active.is_(True),
            ).limit(25)
        )
    ).scalars().all()
    D = [
        {
            "type": "intake_sent_not_submitted",
            "intake_id": str(i.id),
            "client_id": str(i.client_id),
            "sent_at": i.sent_at.isoformat() if i.sent_at else None,
            "first_viewed_at": i.first_viewed_at.isoformat() if i.first_viewed_at else None,
            "reminder_count": i.reminder_count,
        }
        for i in D_rows
    ]

    total_potential_cents = sum(x.get("amount_cents", 0) or 0 for x in A)

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "total_potential_cents": total_potential_cents,
        "total_potential_usd": total_potential_cents / 100.0,
        "buckets": {
            "proposal_sent_unpaid": A,
            "draft_pending_money_intent": B,
            "draft_approved_pending_send": C,
            "intake_sent_not_submitted": D,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Blocking floors — what is specifically between us and the next floor
# ═══════════════════════════════════════════════════════════════════════════


async def compute_blocking_floors(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    """What stands between trailing-30d revenue and the next floor.

    Combines floor math + closest-revenue inventory to produce a direct
    answer: "Close these $X of in-flight money and you hit the floor."
    """
    floor = await compute_floor_status(db, org_id=org_id, month_index=month_index)
    closest = await compute_closest_revenue(db, org_id=org_id)

    gap_cents = int(floor["gap_cents"])
    potential_cents = int(closest["total_potential_cents"])
    ratio_with_in_flight = (
        ((floor["trailing_30d_cents"] + potential_cents) / floor["floor_cents"])
        if floor["floor_cents"] else 0.0
    )

    blocker_reasons: list[str] = []
    if gap_cents > potential_cents:
        blocker_reasons.append(
            f"In-flight potential ({potential_cents / 100:.0f} USD) is less than the "
            f"floor gap ({gap_cents / 100:.0f} USD). New outreach/leads required."
        )
    if not closest["buckets"]["proposal_sent_unpaid"]:
        blocker_reasons.append(
            "No proposals currently in 'sent' state — "
            "revenue engine has no in-flight closes."
        )
    if not closest["buckets"]["draft_pending_money_intent"]:
        blocker_reasons.append(
            "No money-intent replies pending — "
            "either all replies are handled or inbound is quiet."
        )
    if floor["ratio_to_floor"] >= 1.0:
        blocker_reasons = ["Floor met. Advance to next month's floor target."]

    return {
        "org_id": str(org_id),
        "month_index": month_index,
        "floor_usd": floor["floor_usd"],
        "trailing_30d_usd": floor["trailing_30d_usd"],
        "gap_usd": floor["gap_usd"],
        "in_flight_potential_usd": potential_cents / 100.0,
        "ratio_to_floor": floor["ratio_to_floor"],
        "ratio_if_all_in_flight_closes": round(ratio_with_in_flight, 4),
        "blocker_reasons": blocker_reasons,
        "floor_met": floor["floor_met"],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Game plan — ranked action list via priority engine
# ═══════════════════════════════════════════════════════════════════════════


async def compute_game_plan(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    month_index: int = 1,
) -> dict:
    """Build a ranked action list following the PRIORITY_RANK doctrine.

    Each line is a concrete action the operator (or later the GM with
    write tools) can execute. Read-only — does not mutate any row.
    """
    now = datetime.now(timezone.utc)
    plan: list[dict] = []

    # Rank 1 — revenue at immediate risk
    # a) proposal sent unpaid > 24h
    risky_proposals = (
        await db.execute(
            select(Proposal).where(
                Proposal.org_id == org_id,
                Proposal.status == "sent",
                Proposal.is_active.is_(True),
                Proposal.sent_at <= (now - timedelta(hours=24)),
            ).order_by(Proposal.total_amount_cents.desc()).limit(10)
        )
    ).scalars().all()
    for p in risky_proposals:
        plan.append({
            "priority_rank": 1, "label": "revenue_at_immediate_risk",
            "action_type": "followup_or_nudge_unpaid_proposal",
            "action_class": "approval_required",
            "entity_type": "proposal", "entity_id": str(p.id),
            "detail": f"Proposal to {p.recipient_email} for ${p.total_amount_cents/100:.0f} "
                      f"sent >{int((now-p.sent_at).total_seconds()//3600)}h ago, still unpaid.",
            "potential_cents": p.total_amount_cents,
        })

    # b) payment captured but no client row
    cascade_broken_payments = (
        await db.execute(
            select(Payment).where(
                Payment.org_id == org_id,
                Payment.status == "succeeded",
                Payment.is_active.is_(True),
                Payment.completed_at >= (now - timedelta(days=3)),
            )
        )
    ).scalars().all()
    for pay in cascade_broken_payments:
        # A client must exist for the payer email
        if not pay.customer_email:
            continue
        client_exists = (
            await db.execute(
                select(Client.id).where(
                    Client.org_id == org_id,
                    Client.primary_email == pay.customer_email,
                )
            )
        ).scalar_one_or_none()
        if client_exists is None:
            plan.append({
                "priority_rank": 1, "label": "revenue_at_immediate_risk",
                "action_type": "activate_client_from_orphan_payment",
                "action_class": "auto_execute",
                "entity_type": "payment", "entity_id": str(pay.id),
                "detail": f"Payment {pay.id} captured ${pay.amount_cents/100:.0f} from "
                          f"{pay.customer_email} with no matching client row.",
                "potential_cents": pay.amount_cents,
            })

    # Rank 2 — blocked revenue close
    # a) approved reply drafts not yet sent > 5m
    stale_approved = (
        await db.execute(
            select(EmailReplyDraft).where(
                EmailReplyDraft.org_id == org_id,
                EmailReplyDraft.status == "approved",
                EmailReplyDraft.approved_at <= (now - timedelta(minutes=5)),
                EmailReplyDraft.is_active.is_(True),
            ).limit(10)
        )
    ).scalars().all()
    for d in stale_approved:
        plan.append({
            "priority_rank": 2, "label": "blocked_revenue_close",
            "action_type": "dispatch_approved_draft",
            "action_class": "auto_execute",
            "entity_type": "email_reply_draft", "entity_id": str(d.id),
            "detail": f"Draft to {d.to_email} approved "
                      f">{int((now-d.approved_at).total_seconds()//60)}m ago, beat cycle "
                      f"should have picked it up — escalate if worker stalled.",
        })

    # b) qa_passed jobs awaiting dispatch > 15m
    undelivered = (
        await db.execute(
            select(ProductionJob).where(
                ProductionJob.org_id == org_id,
                ProductionJob.status == "qa_passed",
                ProductionJob.is_active.is_(True),
            ).limit(10)
        )
    ).scalars().all()
    for j in undelivered:
        plan.append({
            "priority_rank": 2, "label": "blocked_revenue_close",
            "action_type": "dispatch_delivery_for_qa_passed_job",
            "action_class": "auto_execute",
            "entity_type": "production_job", "entity_id": str(j.id),
            "detail": f"ProductionJob {j.id} qa_passed, awaiting delivery.",
        })

    # Rank 3 — floor-gap math (one consolidated entry)
    floor = await compute_floor_status(db, org_id=org_id, month_index=month_index)
    if not floor["floor_met"]:
        plan.append({
            "priority_rank": 3, "label": "floor_gap_math",
            "action_type": "close_floor_gap",
            "action_class": "approval_required",
            "entity_type": "floor", "entity_id": f"month_{month_index}",
            "detail": f"Trailing 30d: ${floor['trailing_30d_usd']:.0f} vs "
                      f"${floor['floor_usd']:.0f} floor. Gap ${floor['gap_usd']:.0f} "
                      f"(ratio {floor['ratio_to_floor']:.2f}).",
            "potential_cents": floor["gap_cents"],
        })

    # Rank 4 — stuck fulfillment (from gm_escalations + stage_states)
    stuck_escalations = (
        await db.execute(
            select(GMEscalation).where(
                GMEscalation.org_id == org_id,
                GMEscalation.status.in_(("open", "acknowledged")),
                GMEscalation.is_active.is_(True),
            ).order_by(GMEscalation.last_seen_at.desc()).limit(10)
        )
    ).scalars().all()
    for e in stuck_escalations:
        plan.append({
            "priority_rank": 4, "label": "stuck_fulfillment",
            "action_type": "resolve_or_action_escalation",
            "action_class": "approval_required",
            "entity_type": "gm_escalation", "entity_id": str(e.id),
            "detail": f"{e.reason_code}: {e.title}",
        })

    # Rank 5 — retention: clients with delivered work > 30d and no next project
    stale_clients = (
        await db.execute(
            select(Client).where(
                Client.org_id == org_id,
                Client.is_active.is_(True),
                Client.status == "active",
                Client.last_paid_at <= (now - timedelta(days=30)),
            ).order_by(Client.total_paid_cents.desc()).limit(10)
        )
    ).scalars().all()
    for c in stale_clients:
        plan.append({
            "priority_rank": 5, "label": "retention_expansion",
            "action_type": "propose_next_project_or_retainer",
            "action_class": "approval_required",
            "entity_type": "client", "entity_id": str(c.id),
            "detail": f"Client {c.display_name} (${c.total_paid_cents/100:.0f} LTV) "
                      f"last paid "
                      f"{int((now-c.last_paid_at).total_seconds()//86400) if c.last_paid_at else '?'}d ago.",
        })

    # Rank 6 — operational hygiene (pending approvals)
    pending_approvals = (
        await db.execute(
            select(GMApproval).where(
                GMApproval.org_id == org_id,
                GMApproval.status == "pending",
                GMApproval.is_active.is_(True),
            ).order_by(GMApproval.created_at.desc()).limit(10)
        )
    ).scalars().all()
    for a in pending_approvals:
        plan.append({
            "priority_rank": 6, "label": "operational_hygiene",
            "action_type": "decide_pending_approval",
            "action_class": "approval_required",
            "entity_type": "gm_approval", "entity_id": str(a.id),
            "detail": f"{a.action_type}: {a.title} (risk={a.risk_level})",
        })

    # Order by priority_rank ASC, then by potential_cents DESC when present
    def _sort_key(item: dict) -> tuple:
        return (item["priority_rank"], -(item.get("potential_cents") or 0))
    plan.sort(key=_sort_key)

    return {
        "org_id": str(org_id),
        "generated_at": now.isoformat(),
        "month_index": month_index,
        "total_items": len(plan),
        "floor_status": floor,
        "actions": plan,
    }

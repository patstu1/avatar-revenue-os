"""GM front-of-funnel helpers (Batch 10).

Thin wrappers over existing canonical services:

  - leads_service / sponsor_targets path (bulk import + qualification)
  - workers.outreach_worker.send_outreach_email (launch / pause)
  - reply_engine.send_approved_drafts (rewrite + send-now)
  - proposals_service.create_proposal (lead → proposal handoff)

Every helper:
  1. Org-scopes inputs via the acting user / brand.
  2. Carries avenue_slug through the downstream rows it writes.
  3. Emits the canonical domain event(s) the existing services already
     emit (so GM write endpoints can layer a gm.write.<tool> event on
     top without duplicating domain semantics).

No new business logic lives here. If a rule changes (qualification
threshold, outreach cadence, rewrite constraint), it changes in the
canonical service, not in this wrapper layer.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.core import Brand
from packages.db.models.email_pipeline import (
    EmailMessage,
    EmailReplyDraft,
    EmailThread,
)
from packages.db.models.expansion_pack2_phase_c import (
    SponsorOutreachSequence,
    SponsorTarget,
)
from packages.db.models.proposals import Proposal

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  1. Bulk lead import
# ═══════════════════════════════════════════════════════════════════════════


async def bulk_import_leads_with_avenue(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    avenue_slug: str,
    rows: list[dict[str, Any]],
    source: str = "gm_write.leads.import",
) -> dict:
    """Bulk-insert leads (``sponsor_targets``) and tag each with
    ``avenue_slug``.

    ``rows`` is a list of dicts with any subset of:
      ``company_name`` (required), ``contact_name``, ``email``, ``phone``,
      ``instagram_handle``, ``website_url``, ``industry``,
      ``estimated_size``, ``notes``, ``niche_tag``, ``estimated_deal_value``,
      ``fit_score``.

    Returns ``{imported, skipped, errors, first_lead_id}``. Emits one
    ``lead.bulk_imported`` event summarising the batch.
    """
    # Resolve the org's first active brand (lead attribution is
    # brand-scoped in the existing schema).
    brand = (
        await db.execute(
            select(Brand).where(
                Brand.organization_id == org_id, Brand.is_active.is_(True)
            ).limit(1)
        )
    ).scalar_one_or_none()
    if brand is None:
        raise ValueError(
            "No active brand for organization — create a brand "
            "before importing leads."
        )

    imported = 0
    skipped = 0
    errors: list[str] = []
    first_id: Optional[uuid.UUID] = None

    for i, raw in enumerate(rows or []):
        company = (raw.get("company_name") or "").strip()
        if not company:
            skipped += 1
            errors.append(f"row {i}: missing company_name")
            continue

        contact_info = {
            "email": (raw.get("email") or "").strip(),
            "phone": (raw.get("phone") or "").strip(),
            "name": (raw.get("contact_name") or "").strip(),
            "instagram": (raw.get("instagram_handle") or "").strip(),
            "website": (raw.get("website_url") or "").strip(),
            "size": (raw.get("estimated_size") or "").strip(),
            "niche_tag": (raw.get("niche_tag") or "").strip(),
            "notes": (raw.get("notes") or "").strip(),
            "source": source,
        }

        lead_id = uuid.uuid4()
        try:
            await db.execute(
                text(
                    """
                    INSERT INTO sponsor_targets (
                        id, brand_id, target_company_name, industry,
                        contact_info, estimated_deal_value, fit_score,
                        confidence, explanation, avenue_slug,
                        is_active, created_at, updated_at
                    ) VALUES (
                        :id, :bid, :company, :industry,
                        CAST(:contact AS JSONB), :edv, :fit,
                        :conf, :expl, :avenue,
                        true, now(), now()
                    )
                    ON CONFLICT (brand_id, target_company_name) DO NOTHING
                    """
                ),
                {
                    "id": lead_id,
                    "bid": brand.id,
                    "company": company[:255],
                    "industry": (raw.get("industry") or raw.get("niche_tag") or "")[:255],
                    "contact": json.dumps(contact_info),
                    "edv": float(raw.get("estimated_deal_value") or 0),
                    "fit": float(raw.get("fit_score") or 0.5),
                    "conf": float(raw.get("confidence") or 0.5),
                    "expl": f"Imported via {source} (avenue={avenue_slug})",
                    "avenue": avenue_slug[:60],
                },
            )
            imported += 1
            if first_id is None:
                first_id = lead_id
        except Exception as insert_exc:
            skipped += 1
            errors.append(f"row {i} ({company}): {str(insert_exc)[:200]}")

    await db.flush()

    await emit_event(
        db,
        domain="conversion",
        event_type="lead.bulk_imported",
        summary=(
            f"Bulk-imported {imported} leads for avenue={avenue_slug} "
            f"(skipped={skipped})"
        ),
        org_id=org_id,
        brand_id=brand.id,
        entity_type="brand",
        entity_id=brand.id,
        actor_type="operator",
        actor_id=source,
        details={
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],
            "avenue_slug": avenue_slug,
            "first_lead_id": str(first_id) if first_id else None,
        },
    )
    logger.info(
        "lead.bulk_imported",
        org_id=str(org_id),
        brand_id=str(brand.id),
        avenue_slug=avenue_slug,
        imported=imported,
        skipped=skipped,
    )
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:20],
        "first_lead_id": str(first_id) if first_id else None,
    }


async def parse_csv_rows(raw_csv: str) -> list[dict[str, Any]]:
    """Parse a raw CSV string into the rows format bulk_import_leads_with_avenue expects."""
    reader = csv.DictReader(io.StringIO(raw_csv))
    return [dict(row) for row in reader]


# ═══════════════════════════════════════════════════════════════════════════
#  2. Qualify a lead
# ═══════════════════════════════════════════════════════════════════════════


VALID_TIERS = ("hot", "warm", "cold", "parked", "disqualified")
VALID_INTENTS = (
    "offer_request", "pricing_question", "objection", "positive",
    "not_interested", "referral", "unclear",
)


async def qualify_lead(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    lead_id: uuid.UUID,
    intent: str,
    tier: str,
    reason_codes: list[str] | None = None,
    avenue_slug_override: str | None = None,
    notes: str | None = None,
    actor_type: str = "operator",
    actor_id: Optional[str] = None,
) -> dict:
    """Update a sponsor_target with qualification verdict.

    Writes:
      - ``sponsor_targets.fit_score`` = tier-derived numeric
      - ``sponsor_targets.confidence``
      - ``sponsor_targets.explanation`` = structured reason
      - ``sponsor_targets.avenue_slug`` if override is present

    Emits: ``lead.qualified``.
    """
    if intent not in VALID_INTENTS:
        raise ValueError(
            f"intent must be one of {VALID_INTENTS}, got {intent!r}"
        )
    if tier not in VALID_TIERS:
        raise ValueError(
            f"tier must be one of {VALID_TIERS}, got {tier!r}"
        )

    target = (
        await db.execute(
            select(SponsorTarget).where(SponsorTarget.id == lead_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise KeyError(f"Lead {lead_id} not found")

    brand = (
        await db.execute(select(Brand).where(Brand.id == target.brand_id))
    ).scalar_one_or_none()
    if brand is None or brand.organization_id != org_id:
        raise PermissionError("Lead belongs to another organization")

    tier_score = {
        "hot": 0.90, "warm": 0.70, "cold": 0.40,
        "parked": 0.20, "disqualified": 0.05,
    }[tier]

    target.fit_score = tier_score
    target.confidence = max(target.confidence or 0.0, 0.80)
    target.explanation = json.dumps(
        {
            "intent": intent,
            "tier": tier,
            "reason_codes": reason_codes or [],
            "notes": notes,
            "qualified_by": actor_id,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if avenue_slug_override:
        target.avenue_slug = avenue_slug_override[:60]
    await db.flush()

    await emit_event(
        db,
        domain="conversion",
        event_type="lead.qualified",
        summary=(
            f"Lead {target.target_company_name[:60]} → tier={tier} "
            f"intent={intent}"
        ),
        org_id=org_id,
        brand_id=brand.id,
        entity_type="sponsor_target",
        entity_id=target.id,
        actor_type=actor_type,
        actor_id=actor_id,
        details={
            "lead_id": str(target.id),
            "tier": tier,
            "intent": intent,
            "reason_codes": reason_codes or [],
            "avenue_slug": target.avenue_slug,
            "fit_score": target.fit_score,
        },
    )
    logger.info(
        "lead.qualified",
        lead_id=str(target.id),
        tier=tier,
        intent=intent,
    )
    return {
        "lead_id": str(target.id),
        "tier": tier,
        "intent": intent,
        "fit_score": target.fit_score,
        "avenue_slug": target.avenue_slug,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  3. Launch / pause outreach
# ═══════════════════════════════════════════════════════════════════════════


async def launch_outreach_for_segment(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    avenue_slug: str,
    lead_ids: list[uuid.UUID] | None = None,
    sequence_template_slug: str = "default_v1",
    max_leads: int = 200,
    actor_id: Optional[str] = None,
) -> dict:
    """Create a SponsorOutreachSequence row for each lead in scope and
    schedule the outreach worker to send the first email.

    ``lead_ids``: explicit list. If None, selects the most recently-
    imported leads for the avenue (capped at ``max_leads``).

    Returns ``{leads_scheduled, sequence_ids, skipped}``.
    Emits ``outreach.launched`` one per batch.
    """
    brand = (
        await db.execute(
            select(Brand).where(
                Brand.organization_id == org_id, Brand.is_active.is_(True)
            ).limit(1)
        )
    ).scalar_one_or_none()
    if brand is None:
        raise ValueError("No active brand for organization")

    if lead_ids:
        q = select(SponsorTarget).where(
            SponsorTarget.brand_id == brand.id,
            SponsorTarget.id.in_(lead_ids),
            SponsorTarget.is_active.is_(True),
        )
    else:
        q = (
            select(SponsorTarget)
            .where(
                SponsorTarget.brand_id == brand.id,
                SponsorTarget.avenue_slug == avenue_slug,
                SponsorTarget.is_active.is_(True),
            )
            .order_by(SponsorTarget.created_at.desc())
            .limit(max_leads)
        )
    targets = (await db.execute(q)).scalars().all()

    scheduled = 0
    skipped = 0
    sequence_ids: list[str] = []

    # Attempt to enqueue via celery; if the broker is unavailable in the
    # caller's context (tests, migrations, etc.), we still write the
    # sequence rows so the worker picks them up on its next poll.
    try:
        from workers.outreach_worker import tasks as outreach_tasks
        can_enqueue = True
    except Exception:
        outreach_tasks = None  # type: ignore
        can_enqueue = False

    for t in targets:
        existing = (
            await db.execute(
                select(SponsorOutreachSequence).where(
                    SponsorOutreachSequence.sponsor_target_id == t.id,
                    SponsorOutreachSequence.sequence_name == sequence_template_slug,
                    SponsorOutreachSequence.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped += 1
            continue
        seq = SponsorOutreachSequence(
            sponsor_target_id=t.id,
            sequence_name=sequence_template_slug,
            steps=[
                {"step": 1, "delay_hours": 0, "template": sequence_template_slug},
                {"step": 2, "delay_hours": 48, "template": f"{sequence_template_slug}_followup_1"},
                {"step": 3, "delay_hours": 168, "template": f"{sequence_template_slug}_followup_2"},
            ],
            estimated_response_rate=0.08,
            expected_value=t.estimated_deal_value or 0,
            confidence=0.6,
            explanation=f"Launched via gm_write by {actor_id}",
            avenue_slug=(t.avenue_slug or avenue_slug)[:60],
        )
        db.add(seq)
        await db.flush()
        sequence_ids.append(str(seq.id))

        if can_enqueue and outreach_tasks is not None:
            try:
                outreach_tasks.send_outreach_email.delay(
                    str(seq.id), str(brand.id), str(org_id),
                )
            except Exception as enq_exc:
                logger.warning(
                    "outreach.enqueue_failed",
                    sequence_id=str(seq.id),
                    error=str(enq_exc)[:150],
                )
        scheduled += 1

    await db.flush()

    await emit_event(
        db,
        domain="conversion",
        event_type="outreach.launched",
        summary=(
            f"Outreach launched: {scheduled} lead(s) on avenue={avenue_slug} "
            f"(sequence={sequence_template_slug})"
        ),
        org_id=org_id,
        brand_id=brand.id,
        entity_type="brand",
        entity_id=brand.id,
        actor_type="operator",
        actor_id=actor_id,
        details={
            "avenue_slug": avenue_slug,
            "sequence_template_slug": sequence_template_slug,
            "scheduled": scheduled,
            "skipped": skipped,
            "sequence_ids": sequence_ids[:50],
        },
    )
    return {
        "scheduled": scheduled,
        "skipped": skipped,
        "sequence_ids": sequence_ids[:50],
        "avenue_slug": avenue_slug,
    }


async def pause_outreach_for_avenue(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    avenue_slug: str | None = None,
    sequence_ids: list[uuid.UUID] | None = None,
    actor_id: Optional[str] = None,
) -> dict:
    """Pause outreach by marking sequences is_active=false.

    Either ``avenue_slug`` (bulk) or ``sequence_ids`` (targeted) must
    be provided. Stops future scheduled sends; in-flight tasks already
    handed to celery may complete.
    """
    brand = (
        await db.execute(
            select(Brand).where(
                Brand.organization_id == org_id, Brand.is_active.is_(True)
            ).limit(1)
        )
    ).scalar_one_or_none()
    if brand is None:
        raise ValueError("No active brand for organization")
    if not (avenue_slug or sequence_ids):
        raise ValueError("Must provide avenue_slug OR sequence_ids")

    q = select(SponsorOutreachSequence).join(
        SponsorTarget,
        SponsorTarget.id == SponsorOutreachSequence.sponsor_target_id,
    ).where(
        SponsorTarget.brand_id == brand.id,
        SponsorOutreachSequence.is_active.is_(True),
    )
    if sequence_ids:
        q = q.where(SponsorOutreachSequence.id.in_(sequence_ids))
    elif avenue_slug:
        q = q.where(SponsorOutreachSequence.avenue_slug == avenue_slug)

    rows = (await db.execute(q)).scalars().all()
    paused = 0
    for seq in rows:
        seq.is_active = False
        paused += 1
    await db.flush()

    await emit_event(
        db,
        domain="conversion",
        event_type="outreach.paused",
        summary=f"Outreach paused: {paused} sequence(s)",
        org_id=org_id,
        brand_id=brand.id,
        entity_type="brand",
        entity_id=brand.id,
        actor_type="operator",
        actor_id=actor_id,
        details={
            "paused": paused,
            "avenue_slug": avenue_slug,
            "sequence_ids": [str(s.id) for s in rows][:50],
        },
    )
    return {"paused": paused, "avenue_slug": avenue_slug}


# ═══════════════════════════════════════════════════════════════════════════
#  4. Rewrite / force-send a reply draft
# ═══════════════════════════════════════════════════════════════════════════


async def rewrite_draft(
    db: AsyncSession,
    *,
    draft: EmailReplyDraft,
    new_subject: Optional[str] = None,
    new_body_text: Optional[str] = None,
    new_body_html: Optional[str] = None,
    reason: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> EmailReplyDraft:
    """Replace a draft's subject/body, preserving the prior version in
    ``rewrite_history_json``. Does not send — status stays ``pending``."""
    if draft.status not in ("pending", "approved", "rejected"):
        raise ValueError(
            f"Cannot rewrite draft in status={draft.status}"
        )

    prior = {
        "at": datetime.now(timezone.utc).isoformat(),
        "actor": actor_id,
        "previous_subject": draft.subject,
        "previous_body_text": draft.body_text,
        "reason": reason,
    }
    history = draft.rewrite_history_json or {}
    versions = history.get("versions", []) if isinstance(history, dict) else []
    versions.append(prior)
    draft.rewrite_history_json = {"versions": versions}

    if new_subject is not None:
        draft.subject = new_subject[:1000]
    if new_body_text is not None:
        draft.body_text = new_body_text
    if new_body_html is not None:
        draft.body_html = new_body_html
    # Any rewrite returns the draft to pending so it must be re-approved
    # before the sync loop will pick it up.
    if draft.status == "approved":
        draft.status = "pending"
        draft.approved_at = None
        draft.approved_by = None
    await db.flush()

    await emit_event(
        db,
        domain="conversion",
        event_type="reply.draft.rewritten",
        summary=f"Draft rewritten by {actor_id}: {draft.to_email}",
        org_id=draft.org_id,
        entity_type="email_reply_draft",
        entity_id=draft.id,
        actor_type="operator",
        actor_id=actor_id,
        details={
            "draft_id": str(draft.id),
            "reason": reason,
            "version_count": len(versions),
            "avenue_slug": draft.avenue_slug,
        },
    )
    return draft


async def force_send_draft(
    db: AsyncSession,
    *,
    draft: EmailReplyDraft,
    actor_id: Optional[str] = None,
) -> dict:
    """Force-send a single approved draft via the existing
    ``reply_engine.send_approved_drafts`` path, bypassing the 60-second
    sync loop. Returns the send result dict.

    Draft must already be status='approved'. Call the /gm/write/drafts/
    {id}/approve endpoint first if it's still pending.
    """
    if draft.status != "approved":
        raise ValueError(
            f"Only approved drafts can be force-sent; current status={draft.status}"
        )

    from apps.api.services.reply_engine import send_approved_drafts
    result = await send_approved_drafts(db, draft.org_id)

    # send_approved_drafts processes ALL approved drafts for the org —
    # we refresh our target draft to confirm it went through.
    await db.refresh(draft)
    return {
        "draft_id": str(draft.id),
        "status": draft.status,
        "sent_at": draft.sent_at.isoformat() if draft.sent_at else None,
        "batch_result": result,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  5. Route a qualified lead directly into a Proposal
# ═══════════════════════════════════════════════════════════════════════════


async def route_lead_to_proposal(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    lead_id: uuid.UUID,
    package_slug: Optional[str],
    line_items: list[dict],
    title: Optional[str] = None,
    summary: str = "",
    notes: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> Proposal:
    """Create a Proposal from a qualified lead, carrying avenue_slug
    forward and back-linking via extra_json.source_lead_id.
    """
    from apps.api.services.proposals_service import (
        LineItemInput, create_proposal as svc_create,
    )

    target = (
        await db.execute(
            select(SponsorTarget).where(SponsorTarget.id == lead_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise KeyError(f"Lead {lead_id} not found")

    brand = (
        await db.execute(select(Brand).where(Brand.id == target.brand_id))
    ).scalar_one_or_none()
    if brand is None or brand.organization_id != org_id:
        raise PermissionError("Lead belongs to another organization")

    contact = target.contact_info or {}
    recipient_email = (contact.get("email") or "").strip().lower()
    if not recipient_email:
        raise ValueError(
            f"Lead {lead_id} has no contact email — update the lead "
            "before routing to proposal."
        )

    li_inputs: list[LineItemInput] = []
    for i, li in enumerate(line_items):
        li_inputs.append(
            LineItemInput(
                description=str(li.get("description", ""))[:500],
                unit_amount_cents=int(li.get("unit_amount_cents", 0)),
                quantity=int(li.get("quantity", 1)),
                offer_id=li.get("offer_id"),
                package_slug=li.get("package_slug") or package_slug,
                currency=str(li.get("currency", "usd")),
                position=int(li.get("position", i)),
            )
        )
    if not li_inputs:
        raise ValueError("route_lead_to_proposal requires at least one line item")

    proposal = await svc_create(
        db,
        org_id=org_id,
        brand_id=brand.id,
        recipient_email=recipient_email,
        recipient_name=contact.get("name", "") or "",
        recipient_company=target.target_company_name or "",
        title=title or f"Proposal — {target.target_company_name}",
        summary=summary,
        package_slug=package_slug,
        avenue_slug=target.avenue_slug,
        line_items=li_inputs,
        notes=notes,
        created_by_actor_type="operator",
        created_by_actor_id=actor_id,
        extra_json={
            "source_lead_id": str(target.id),
            "source": "gm_write.leads.route_to_proposal",
        },
    )
    await emit_event(
        db,
        domain="conversion",
        event_type="lead.routed_to_proposal",
        summary=f"Lead → proposal: {target.target_company_name} → {recipient_email}",
        org_id=org_id,
        brand_id=brand.id,
        entity_type="proposal",
        entity_id=proposal.id,
        actor_type="operator",
        actor_id=actor_id,
        details={
            "lead_id": str(target.id),
            "proposal_id": str(proposal.id),
            "avenue_slug": target.avenue_slug,
            "package_slug": package_slug,
            "total_amount_cents": proposal.total_amount_cents,
        },
    )
    return proposal

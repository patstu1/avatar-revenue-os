"""AI Search Authority — public test endpoint + operator visibility endpoints.

Public POST endpoint runs the full scan + score + lead handoff and returns
the partial result envelope for the homepage hero. Operator endpoints
list/detail reports + minimal action stubs (proposal handoff is wired
through the existing proposals_service).
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from apps.api.deps import DBSession, OperatorUser
from apps.api.services import ai_buyer_trust_service as svc
from apps.api.services.ai_buyer_trust_service import (
    AiBuyerTrustInputError,
    AiBuyerTrustRateLimited,
)

router = APIRouter()


class TrustTestSubmitRequest(BaseModel):
    website_url: str = Field(..., min_length=4, max_length=500)
    company_name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    contact_email: str = Field(..., min_length=5, max_length=255)
    competitor_url: Optional[str] = Field(default=None, max_length=500)
    city_or_market: Optional[str] = Field(default=None, max_length=100)
    # Honeypot — humans never fill this, bots that auto-complete by name
    # do. Frontend renders the input visually hidden (off-screen + tab
    # skipped + autocomplete=off). Backend rejects when non-empty.
    bot_field: Optional[str] = Field(default=None, max_length=300)


@router.post("/ai-search-authority/score")
async def submit_trust_test(
    body: TrustTestSubmitRequest,
    request: Request,
    db: DBSession,
):
    """Public endpoint. Runs the full AI Buyer Trust Test pipeline and
    returns the partial-result envelope. No auth — input validation +
    domain blocklists prevent abuse; the operator dashboard surfaces every
    submission for review.
    """
    request_ip = request.client.host if request.client else None
    try:
        envelope = await svc.submit_trust_test(
            db,
            website_url=body.website_url,
            company_name=body.company_name,
            industry=body.industry,
            contact_email=body.contact_email,
            competitor_url=body.competitor_url,
            city_or_market=body.city_or_market,
            request_ip=request_ip,
            bot_field=body.bot_field,
        )
    except AiBuyerTrustInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": exc.field, "message": exc.message},
        )
    except AiBuyerTrustRateLimited as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"kind": exc.kind, "message": exc.message},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )
    await db.commit()
    return envelope


@router.get("/ai-search-authority/reports")
async def list_reports(
    current_user: OperatorUser,
    db: DBSession,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    score_min: Optional[int] = Query(None, ge=0, le=100),
    score_max: Optional[int] = Query(None, ge=0, le=100),
    package_slug: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    rows = await svc.list_reports(
        db,
        org_id=current_user.organization_id,
        limit=limit,
        offset=offset,
        status=status,
        score_min=score_min,
        score_max=score_max,
        package_slug=package_slug,
        search=search,
    )
    return {"items": rows, "count": len(rows), "limit": limit, "offset": offset}


@router.get("/ai-search-authority/reports/{report_id}")
async def get_report(
    report_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    report = await svc.get_report(db, current_user.organization_id, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.post("/ai-search-authority/reports/{report_id}/request-snapshot-review")
async def request_snapshot_review(
    report_id: uuid.UUID,
    db: DBSession,
):
    """Public endpoint — the prospect requests an operator-reviewed
    Authority Snapshot for their already-submitted test result.

    No auth: the prospect already submitted contact info at test time;
    this is a follow-up signal on their own report. The endpoint flips
    the report status, emits an OperatorAction (deduped) so the
    operator inbox shows the request, and emits a SystemEvent.
    """
    from sqlalchemy import select

    from apps.api.services.event_bus import emit_action, emit_event
    from packages.db.models.authority_score_reports import AuthorityScoreReport

    row = (
        await db.execute(
            select(AuthorityScoreReport).where(AuthorityScoreReport.id == report_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if row.report_status not in (
        "snapshot_review_requested",
        "qualified",
        "proposal_created",
        "archived",
    ):
        row.report_status = "snapshot_review_requested"
        await db.flush()

    try:
        await emit_action(
            db,
            org_id=row.organization_id,
            action_type="review_buyer_trust_snapshot_request",
            title=f"Snapshot review requested: {row.company_name} (score {row.total_score})",
            description=(
                f"Prospect requested an operator-reviewed Authority Snapshot. "
                f"Website: {row.website_url}. Recommended package: "
                f"{row.recommended_package_slug or '—'}."
            ),
            priority="high",
            category="opportunity",
            brand_id=row.brand_id,
            entity_type="authority_score_report",
            entity_id=row.id,
            source_module="ai_buyer_trust_snapshot_request",
            action_payload={
                "report_id": str(row.id),
                "lead_opportunity_id": (
                    str(row.lead_opportunity_id) if row.lead_opportunity_id else None
                ),
                "recommended_package_slug": row.recommended_package_slug,
                "total_score": row.total_score,
            },
        )
    except Exception:
        pass  # action emit failure should not block the user-facing 200

    try:
        await emit_event(
            db,
            domain="growth",
            event_type="ai_buyer_trust.snapshot_review_requested",
            summary=(
                f"Snapshot review requested for {row.company_name} "
                f"(score {row.total_score})"
            ),
            severity="info",
            org_id=row.organization_id,
            brand_id=row.brand_id,
            entity_type="authority_score_report",
            entity_id=row.id,
            details={
                "report_id": str(row.id),
                "recommended_package_slug": row.recommended_package_slug,
                "total_score": row.total_score,
            },
        )
    except Exception:
        pass

    await db.commit()
    return {
        "report_id": str(row.id),
        "report_status": row.report_status,
        "message": (
            "Your AI Buyer Trust result is queued for operator review. "
            "We will follow up with the Full Authority Snapshot."
        ),
    }


@router.post("/ai-search-authority/reports/{report_id}/create-proposal")
async def create_proposal_from_report(
    report_id: uuid.UUID,
    body: dict | None,
    current_user: OperatorUser,
    db: DBSession,
):
    """Operator action — turn an Authority Score report into a Proposal.

    Reuses the existing ``proposals_service.create_proposal`` so the
    Stripe → webhook → Payment chain stays unchanged. Recommended
    package = ``report.recommended_package_slug`` unless the operator
    overrides it via ``body.override_package_slug``. When the report
    carries a ``creative_proof_slug`` and the operator opts in via
    ``body.include_creative_companion=true``, the companion slug is
    appended to the proposal as a second line item and recorded on
    ``Proposal.extra_json``.
    """
    from sqlalchemy import select

    from apps.api.services.proposals_service import LineItemInput, create_proposal
    from packages.db.models.authority_score_reports import AuthorityScoreReport
    from packages.db.models.expansion_pack2_phase_a import LeadOpportunity

    body = body or {}
    override = (body.get("override_package_slug") or None)
    include_companion = bool(body.get("include_creative_companion"))

    report = (
        await db.execute(
            select(AuthorityScoreReport).where(
                AuthorityScoreReport.id == report_id,
                AuthorityScoreReport.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    primary_slug = override or report.recommended_package_slug
    if not primary_slug:
        raise HTTPException(
            status_code=400,
            detail=(
                "Report has no recommended_package_slug and no "
                "override_package_slug was provided."
            ),
        )

    # Look up package metadata server-side from the same catalog the
    # frontend reads. Mirror lives in proofhook_packages catalog seed.
    catalog = _server_package_catalog()
    primary_pkg = catalog.get(primary_slug)
    if primary_pkg is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown package slug: {primary_slug}",
        )

    creative_slug = None
    creative_pkg = None
    if include_companion:
        companion = (
            (report.public_result or {}).get("recommended_package", {}) or {}
        ).get("creative_proof_slug")
        if companion:
            creative_slug = companion
            creative_pkg = catalog.get(companion)

    line_items = [
        LineItemInput(
            description=primary_pkg["name"],
            unit_amount_cents=primary_pkg["price_cents"],
            quantity=1,
            package_slug=primary_slug,
            position=0,
        )
    ]
    if creative_pkg:
        line_items.append(
            LineItemInput(
                description=f"{creative_pkg['name']} (Creative Proof companion)",
                unit_amount_cents=creative_pkg["price_cents"],
                quantity=1,
                package_slug=creative_slug,
                position=1,
            )
        )

    title_parts = [f"ProofHook — {primary_pkg['name']} for {report.company_name}"]
    if creative_pkg:
        title_parts.append(f"with {creative_pkg['name']}")
    title = " ".join(title_parts)

    summary = (
        f"AI Buyer Trust Score: {report.total_score}/100 ({report.score_label}). "
        f"Recommended via /ai-search-authority/score from {report.website_url}."
    )
    notes = (
        (report.public_result or {}).get("recommended_package", {}).get("rationale", "")
        if report.public_result
        else None
    )
    extra_json = {
        "ai_buyer_trust_report_id": str(report.id),
        "primary_package_slug": primary_slug,
        "creative_proof_slug": creative_slug,
        "total_score": report.total_score,
        "score_label": report.score_label,
    }

    proposal = await create_proposal(
        db,
        org_id=report.organization_id,
        recipient_email=report.contact_email,
        recipient_name=report.company_name,
        recipient_company=report.company_name,
        brand_id=report.brand_id,
        title=title,
        summary=summary,
        line_items=line_items,
        package_slug=primary_slug,
        notes=notes,
        extra_json=extra_json,
        created_by_actor_type="human",
        created_by_actor_id=str(current_user.id),
    )

    # Update report state.
    report.report_status = "proposal_created"
    await db.flush()

    # Update linked LeadOpportunity if present.
    lead_id_out = None
    if report.lead_opportunity_id:
        lead = (
            await db.execute(
                select(LeadOpportunity).where(
                    LeadOpportunity.id == report.lead_opportunity_id
                )
            )
        ).scalar_one_or_none()
        if lead is not None:
            lead.sales_stage = "proposal_sent"
            lead_id_out = str(lead.id)
            await db.flush()

    await db.commit()

    return {
        "proposal_id": str(proposal.id),
        "proposal_url": f"/dashboard/proposals/{proposal.id}",
        "report_status": report.report_status,
        "lead_opportunity_id": lead_id_out,
        "package_slug": primary_slug,
        "creative_proof_slug": creative_slug,
        "total_amount_cents": proposal.total_amount_cents,
    }


def _server_package_catalog() -> dict[str, dict[str, str | int]]:
    """Server-side mirror of apps/web/src/lib/proofhook-packages.ts so the
    proposal builder can look up display name + price-cents without
    coupling the API to the frontend bundle. Keep in sync with the
    frontend catalog when prices change.
    """
    return {
        # Creative Proof lane (pre-existing)
        "signal_entry": {"name": "Signal Entry", "price_cents": 150_000},
        "momentum_engine": {"name": "Momentum Engine", "price_cents": 250_000},
        "conversion_architecture": {"name": "Conversion Architecture", "price_cents": 350_000},
        "paid_media_engine": {"name": "Paid Media Engine", "price_cents": 450_000},
        "launch_sequence": {"name": "Launch Sequence", "price_cents": 500_000},
        "creative_command": {"name": "Creative Command", "price_cents": 750_000},
        # AI Authority lane
        "ai_search_authority_snapshot": {"name": "AI Buyer Trust Snapshot", "price_cents": 0},
        "ai_search_authority_sprint": {"name": "AI Search Authority Sprint", "price_cents": 150_000},
        "proof_infrastructure_buildout": {"name": "Proof Infrastructure Buildout", "price_cents": 500_000},
        "authority_monitoring_retainer": {"name": "Authority Monitoring Retainer", "price_cents": 150_000},
        "ai_search_authority_system": {"name": "AI Search Authority System", "price_cents": 0},
    }


@router.post("/ai-search-authority/reports/{report_id}/mark-qualified")
async def mark_qualified(
    report_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    """Minimal patch-1 action — flips report.report_status='qualified' so it
    drops out of the default operator queue. Proposal creation is the
    operator's existing /dashboard/proposals flow; this endpoint just marks
    the lead as worked. Proposal handoff link is rendered on the dashboard.
    """
    from sqlalchemy import select

    from packages.db.models.authority_score_reports import AuthorityScoreReport

    row = (
        await db.execute(
            select(AuthorityScoreReport).where(
                AuthorityScoreReport.id == report_id,
                AuthorityScoreReport.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    row.report_status = "qualified"
    await db.commit()
    return {"id": str(row.id), "report_status": row.report_status}


@router.post("/ai-search-authority/reports/{report_id}/archive")
async def archive_report(
    report_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    from sqlalchemy import select

    from packages.db.models.authority_score_reports import AuthorityScoreReport

    row = (
        await db.execute(
            select(AuthorityScoreReport).where(
                AuthorityScoreReport.id == report_id,
                AuthorityScoreReport.organization_id == current_user.organization_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")
    row.report_status = "archived"
    row.is_active = False
    await db.commit()
    return {"id": str(row.id), "report_status": row.report_status}

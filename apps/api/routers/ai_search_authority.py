"""AI Search Authority — public diagnostic + operator surface.

Endpoints:

  POST   /ai-search-authority/score                              (public)
  POST   /ai-search-authority/reports/{report_id}/request-snapshot-review (public)
  GET    /ai-search-authority/reports                            (operator)
  GET    /ai-search-authority/reports/{report_id}                (operator)
  POST   /ai-search-authority/reports/{report_id}/create-proposal (operator)

Mounted under ``/api/v1`` in apps/api/main.py.

The two public endpoints are explicitly the AI Buyer Trust Test funnel.
They never accept authentication and never reveal another submitter's
report. Operator endpoints are scoped to ``OperatorUser.organization_id``.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status

from apps.api.deps import DBSession, OperatorUser
from apps.api.schemas.ai_search_authority import (
    CreateProposalRequest,
    CreateProposalResponse,
    GapItem,
    ReportDetail,
    ReportListItem,
    ScoreSubmitRequest,
    ScoreSubmitResponse,
    SnapshotReviewResponse,
)
from apps.api.services import ai_search_authority_service as svc

router = APIRouter(prefix="/ai-search-authority", tags=["AI Search Authority"])

logger = structlog.get_logger()


# ─────────────────────────────────────────────────────────────────────
#  Public — POST /score
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/score",
    response_model=ScoreSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit the AI Buyer Trust Test diagnostic (public)",
)
async def submit_score(
    body: ScoreSubmitRequest,
    request: Request,
    db: DBSession,
) -> ScoreSubmitResponse:
    payload = svc.SubmitInput(
        submitter_email=body.submitter_email,
        submitter_name=body.submitter_name,
        submitter_company=body.submitter_company,
        submitter_url=body.submitter_url,
        submitter_role=body.submitter_role,
        submitter_revenue_band=body.submitter_revenue_band,
        vertical=body.vertical,
        buyer_type=body.buyer_type,
        industry_context=body.industry_context,
        answers=body.answers,
        notes=body.notes,
        source="public",
        submission_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    report = await svc.submit_score(db, payload)
    package = svc.PACKAGE_BY_SLUG[report.recommended_package_slug]

    return ScoreSubmitResponse(
        report_id=report.id,
        score=report.score,
        tier=report.tier,
        gaps=[
            GapItem(
                key=g["key"],
                label=g["label"],
                weight=float(g["weight"]),
                severity=g["severity"],
            )
            for g in (report.gaps_json or [])
        ],
        quick_win=report.quick_win,
        recommended_package_slug=report.recommended_package_slug,
        recommended_package_path=package.url_path,
        diagnostic_kind="answer_based",
        status=report.status,
    )


# ─────────────────────────────────────────────────────────────────────
#  Public — POST /reports/{id}/request-snapshot-review
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/reports/{report_id}/request-snapshot-review",
    response_model=SnapshotReviewResponse,
    summary="Request the Authority Snapshot review for a submitted report (public)",
)
async def request_snapshot_review(
    report_id: uuid.UUID,
    db: DBSession,
) -> SnapshotReviewResponse:
    try:
        result = await svc.request_snapshot_review(db, report_id=report_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Report not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return SnapshotReviewResponse(
        report_id=result.report.id,
        status=result.report.status,
        snapshot_requested_at=result.report.snapshot_requested_at,  # type: ignore[arg-type]
        deduped=result.deduped,
    )


# ─────────────────────────────────────────────────────────────────────
#  Operator — GET /reports
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/reports",
    response_model=list[ReportListItem],
    summary="List AI Buyer Trust Test reports (operator-only)",
)
async def list_reports(
    db: DBSession,
    operator: OperatorUser,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[ReportListItem]:
    rows = await svc.list_reports(
        db,
        org_id=operator.organization_id,
        limit=limit,
        offset=offset,
        status=status_filter,
    )
    return [ReportListItem.model_validate(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────
#  Operator — GET /reports/{id}
# ─────────────────────────────────────────────────────────────────────


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetail,
    summary="Get a single AI Buyer Trust Test report (operator-only)",
)
async def get_report(
    report_id: uuid.UUID,
    db: DBSession,
    operator: OperatorUser,
) -> ReportDetail:
    report = await svc.get_report(
        db, org_id=operator.organization_id, report_id=report_id
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportDetail.model_validate(report)


# ─────────────────────────────────────────────────────────────────────
#  Operator — POST /reports/{id}/create-proposal
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/reports/{report_id}/create-proposal",
    response_model=CreateProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Proposal for a report's recommended package (operator-only)",
)
async def create_proposal_endpoint(
    report_id: uuid.UUID,
    body: CreateProposalRequest,
    db: DBSession,
    operator: OperatorUser,
) -> CreateProposalResponse:
    payload = svc.CreateProposalInput(
        package_slug=body.package_slug,
        title=body.title,
        summary=body.summary,
        unit_amount_cents_override=body.unit_amount_cents_override,
        currency=body.currency,
        notes=body.notes,
    )
    try:
        proposal = await svc.create_proposal_from_report(
            db,
            org_id=operator.organization_id,
            report_id=report_id,
            operator_user_id=operator.id,
            payload=payload,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Report not found")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return CreateProposalResponse(
        report_id=report_id,
        proposal_id=proposal.id,
        package_slug=proposal.package_slug or "",
        total_amount_cents=proposal.total_amount_cents,
        currency=proposal.currency,
        status=proposal.status,
    )

"""AI Buyer Trust Test orchestrator.

Validates input → scans the website → scores deterministically → persists
the AuthorityScoreReport row → upserts a LeadOpportunity → emits an
OperatorAction → emits a SystemEvent → returns the public partial result.

The full pipeline is synchronous within the request handler and bounded by
the scanner's wall-clock budget (60s). Failures degrade to a friendly
public message; the report row is still persisted with the error.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.email_validation import EmailValidationError, validate_contact_email
from apps.api.services.event_bus import emit_action, emit_event
from apps.api.services.proofhook_brand_resolver import (
    ProofHookBrandNotConfigured,
    resolve_proofhook_org_and_brand,
)
from apps.api.services.url_safety import UrlSafetyError, domain_of, normalize_website_url
from apps.api.services.website_scanner import _make_signals_dict, scan_website
from packages.db.models.authority_score_reports import AuthorityScoreReport
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
from packages.scoring.ai_buyer_trust_engine import (
    confidence_label_for,
    score_ai_buyer_trust,
)

logger = structlog.get_logger()

DEDUP_WINDOW_MINUTES = 5
LEAD_SOURCE = "ai_buyer_trust_test"

# Public-form abuse protection — bounded by counts of the actual
# AuthorityScoreReport rows already persisted, so the limiter survives
# process restarts and doesn't need a separate cache. Operator testing
# inside the dashboard is unaffected (operators don't hit the public POST).
RATE_LIMIT_WINDOW_MINUTES = 60
RATE_LIMIT_PER_IP = 10
RATE_LIMIT_PER_DOMAIN = 3


class AiBuyerTrustInputError(ValueError):
    """Raised on input validation failure. Message is operator-safe."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


class AiBuyerTrustRateLimited(Exception):
    """Raised when public-form rate limits are exceeded. The router
    translates this into a 429 with a clear message. Carries the kind
    of limit that fired (``ip`` or ``domain``) for observability."""

    def __init__(self, kind: str, message: str, retry_after_seconds: int = 3600):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retry_after_seconds = retry_after_seconds


async def submit_trust_test(
    db: AsyncSession,
    *,
    website_url: str,
    company_name: str,
    industry: str,
    contact_email: str,
    competitor_url: str | None = None,
    city_or_market: str | None = None,
    request_ip: str | None = None,
    bot_field: str | None = None,
) -> dict[str, Any]:
    """End-to-end submit handler. Returns the public-result envelope.

    Side effects:
      - Inserts AuthorityScoreReport (1 row).
      - Upserts LeadOpportunity by (brand_id, contact_email) — latest scan wins.
      - Emits OperatorAction (deduped by entity).
      - Emits SystemEvent.
    """
    # ── 0. Honeypot ─────────────────────────────────────────────────────
    # Hidden form field humans never see. Bots that auto-fill named inputs
    # populate it. Reject silently with a vague 400 to avoid teaching the
    # bot anything useful, and skip every downstream side-effect.
    if bot_field is not None and str(bot_field).strip():
        raise AiBuyerTrustInputError("bot_field", "Submission rejected.")

    # ── 1. Validate inputs ─────────────────────────────────────────────
    if not company_name or not company_name.strip():
        raise AiBuyerTrustInputError("company_name", "Company name is required.")
    company_name = company_name.strip()[:255]

    if not industry or not industry.strip():
        raise AiBuyerTrustInputError("industry", "Industry is required.")
    industry = industry.strip()[:100]

    if competitor_url and competitor_url.strip():
        try:
            competitor_url = normalize_website_url(competitor_url)
        except UrlSafetyError as exc:
            raise AiBuyerTrustInputError("competitor_url", str(exc)) from exc
    else:
        competitor_url = None

    if city_or_market and city_or_market.strip():
        city_or_market = city_or_market.strip()[:100]
    else:
        city_or_market = None

    try:
        normalized_url = normalize_website_url(website_url)
    except UrlSafetyError as exc:
        raise AiBuyerTrustInputError("website_url", str(exc)) from exc

    try:
        normalized_email = validate_contact_email(contact_email)
    except EmailValidationError as exc:
        raise AiBuyerTrustInputError("contact_email", str(exc)) from exc

    domain = domain_of(normalized_url)

    # ── 2. Resolve operator org/brand from DB ──────────────────────────
    try:
        org_id, brand_id = await resolve_proofhook_org_and_brand(db)
    except ProofHookBrandNotConfigured as exc:
        # Operator-side misconfiguration. Fail closed.
        raise AiBuyerTrustInputError("__configuration__", str(exc)) from exc

    # ── 2b. Public-form rate limits (per IP + per domain) ─────────────
    # Backed by counts of already-persisted AuthorityScoreReport rows so
    # the limiter survives restarts and needs no extra cache.
    await _enforce_rate_limits(db, org_id=org_id, request_ip=request_ip, domain=domain)

    # ── 3. Dedup: same domain + email submitted within the window? ──────
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_WINDOW_MINUTES)
    existing = (
        await db.execute(
            select(AuthorityScoreReport)
            .where(
                AuthorityScoreReport.organization_id == org_id,
                AuthorityScoreReport.website_domain == domain,
                AuthorityScoreReport.contact_email == normalized_email,
                AuthorityScoreReport.created_at >= cutoff,
                AuthorityScoreReport.is_active.is_(True),
            )
            .order_by(AuthorityScoreReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None and existing.report_status in ("scored", "qualified", "proposal_created"):
        # Return the previous result rather than re-scanning.
        envelope = dict(existing.public_result or {})
        envelope.setdefault("report_id", str(existing.id))
        envelope.setdefault("status", existing.report_status)
        envelope["deduplicated"] = True
        return envelope

    # ── 4. Insert the report row in 'scanning' state ───────────────────
    report = AuthorityScoreReport(
        organization_id=org_id,
        brand_id=brand_id,
        company_name=company_name,
        website_url=normalized_url,
        website_domain=domain,
        contact_email=normalized_email,
        industry=industry,
        competitor_url=competitor_url,
        city_or_market=city_or_market,
        report_status="scanning",
        scan_started_at=datetime.now(timezone.utc),
        request_ip=request_ip,
    )
    db.add(report)
    await db.flush()

    # ── 5. Scan + score ─────────────────────────────────────────────────
    try:
        scan_result = await scan_website(normalized_url)
        signals = _make_signals_dict(scan_result)
        # Thread submitted metadata into signals so the engine personalizes
        # buyer questions ("Is {company} trustworthy?") and recommendations.
        signals["submitted"] = {
            "company_name": company_name,
            "industry": industry,
            "competitor_url": competitor_url,
            "city_or_market": city_or_market,
        }
        report.scanned_pages = scan_result.to_scanned_pages_summary()
        report.raw_signals = {
            "robots_txt_present": scan_result.robots_txt_present,
            "robots_txt_blocks_ai": scan_result.robots_txt_blocks_ai,
            "sitemap_present": scan_result.sitemap_present,
            "sitemap_url_count": scan_result.sitemap_url_count,
            "all_jsonld_types": sorted(scan_result.jsonld_types()),
            "homepage_failed": scan_result.homepage_failed,
        }

        if scan_result.homepage_failed:
            report.fetch_error = (
                (scan_result.homepage.fetch_error if scan_result.homepage else "homepage_unreachable")
                if scan_result.homepage
                else "homepage_unreachable"
            )

        report_dict = score_ai_buyer_trust(signals)
    except Exception as exc:
        # Catastrophic scanner / engine failure — record + return friendly msg.
        report.report_status = "failed"
        report.fetch_error = f"scan_engine_error: {type(exc).__name__}"
        report.scan_completed_at = datetime.now(timezone.utc)
        await db.flush()
        logger.exception("ai_buyer_trust.scan_failed", report_id=str(report.id), error=str(exc))
        return _failure_envelope(report)

    # ── 6. Persist the score onto the report row ───────────────────────
    report.total_score = report_dict["total_score"]
    report.authority_score = report_dict.get("authority_score", report_dict["total_score"])
    report.score_label = report_dict["score_label"]
    report.confidence = report_dict["confidence"]
    report.dimension_scores = report_dict["dimension_scores"]
    report.technical_scores = report_dict["technical_scores"]
    report.evidence = report_dict["evidence"]
    report.top_gaps = report_dict["top_gaps"]
    report.quick_wins = report_dict["quick_wins"]
    report.recommended_package_slug = (report_dict["recommended_package"] or {}).get("primary_slug")
    # Platform-ready fields
    report.authority_graph = report_dict.get("authority_graph") or {}
    report.buyer_questions = report_dict.get("buyer_questions") or []
    report.recommended_pages = report_dict.get("recommended_pages") or []
    report.recommended_schema = report_dict.get("recommended_schema") or []
    report.recommended_proof_assets = report_dict.get("recommended_proof_assets") or []
    report.recommended_comparison_surfaces = report_dict.get("recommended_comparison_surfaces") or []
    report.monitoring_recommendation = report_dict.get("monitoring_recommendation")
    report.formula_version = report_dict.get("formula_version", "v1")
    report.report_version = report_dict.get("report_version", "v1")
    report.scan_version = report_dict.get("scan_version", "v1")
    report.scan_completed_at = datetime.now(timezone.utc)
    if scan_result.homepage_failed:
        report.report_status = "failed"
    else:
        report.report_status = "scored"

    # Build the public envelope.
    public = _build_public_envelope(report, report_dict)
    report.public_result = public
    await db.flush()

    # ── 7. Upsert LeadOpportunity (only if a brand resolved) ────────────
    lead_id: uuid.UUID | None = None
    if brand_id is not None and report.report_status == "scored":
        lead = await _upsert_lead_opportunity(db, report=report, report_dict=report_dict, brand_id=brand_id)
        lead_id = lead.id
        report.lead_opportunity_id = lead.id
        await db.flush()

    # ── 8. Emit OperatorAction (deduped) and SystemEvent ────────────────
    await _emit_operator_action(db, report=report, org_id=org_id, brand_id=brand_id)
    await _emit_system_event(db, report=report, org_id=org_id, brand_id=brand_id, lead_id=lead_id)

    return public


# ─────────────────────────────────────────────────────────────────────
# Rate limiting (per-IP + per-domain on the public form)
# ─────────────────────────────────────────────────────────────────────


async def _enforce_rate_limits(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    request_ip: str | None,
    domain: str,
) -> None:
    """Reject when the same IP or domain has submitted too many requests
    within the rolling window. Counts active AuthorityScoreReport rows
    only — archived rows do not count. Operator dashboard testing is
    unaffected because operators don't hit the public POST.
    """
    from sqlalchemy import func, select

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)

    if request_ip:
        ip_count = (
            await db.execute(
                select(func.count(AuthorityScoreReport.id)).where(
                    AuthorityScoreReport.organization_id == org_id,
                    AuthorityScoreReport.request_ip == request_ip,
                    AuthorityScoreReport.created_at >= cutoff,
                    AuthorityScoreReport.is_active.is_(True),
                )
            )
        ).scalar_one()
        if ip_count >= RATE_LIMIT_PER_IP:
            raise AiBuyerTrustRateLimited(
                kind="ip",
                message=(
                    f"Too many submissions from this IP in the last "
                    f"{RATE_LIMIT_WINDOW_MINUTES} minutes. Try again later."
                ),
                retry_after_seconds=RATE_LIMIT_WINDOW_MINUTES * 60,
            )

    domain_count = (
        await db.execute(
            select(func.count(AuthorityScoreReport.id)).where(
                AuthorityScoreReport.organization_id == org_id,
                AuthorityScoreReport.website_domain == domain,
                AuthorityScoreReport.created_at >= cutoff,
                AuthorityScoreReport.is_active.is_(True),
            )
        )
    ).scalar_one()
    if domain_count >= RATE_LIMIT_PER_DOMAIN:
        raise AiBuyerTrustRateLimited(
            kind="domain",
            message=(
                f"This website has been submitted {domain_count} times in "
                f"the last {RATE_LIMIT_WINDOW_MINUTES} minutes. Try again "
                f"later or contact hello@proofhook.com."
            ),
            retry_after_seconds=RATE_LIMIT_WINDOW_MINUTES * 60,
        )


# ─────────────────────────────────────────────────────────────────────
# Public envelope
# ─────────────────────────────────────────────────────────────────────


def _build_public_envelope(report: AuthorityScoreReport, report_dict: dict[str, Any]) -> dict[str, Any]:
    primary_slug = (report_dict["recommended_package"] or {}).get("primary_slug")
    secondary_slug = (report_dict["recommended_package"] or {}).get("secondary_slug")
    creative_proof_slug = (report_dict["recommended_package"] or {}).get("creative_proof_slug")
    rationale = (report_dict["recommended_package"] or {}).get("rationale", "")

    # First 3 buyer questions are surfaced publicly so the prospect sees
    # tangible intelligence before the snapshot CTA.
    public_buyer_questions = (report_dict.get("buyer_questions") or [])[:3]

    return {
        "report_id": str(report.id),
        "status": report.report_status,
        "submitted": {
            "company_name": report.company_name,
            "website_url": report.website_url,
            "industry": report.industry,
        },
        "total_score": report_dict["total_score"],
        "authority_score": report_dict.get("authority_score", report_dict["total_score"]),
        "score_label": report_dict["score_label"],
        "confidence_label": report_dict["confidence_label"],
        "top_gaps": [
            {
                "public_label": g["public_label"],
                "score": g["score"],
                "detected": g["detected"],
                "missing": g["missing"],
                "why_it_matters": g["why_it_matters"],
                "recommended_fix": g["recommended_fix"],
            }
            for g in report_dict["top_gaps"]
        ],
        "quick_win": (report_dict["quick_wins"] or [None])[0],
        "buyer_questions_preview": public_buyer_questions,
        "recommended_package": {
            "primary_slug": primary_slug,
            "secondary_slug": secondary_slug,
            "creative_proof_slug": creative_proof_slug,
            "rationale": rationale,
        },
        "cta": {
            "label": "Get My Full Authority Snapshot",
            "href": "/ai-search-authority/snapshot",
        },
        "platform_hint": {
            "first_snapshot": "This is your first AI Buyer Trust Snapshot.",
            "monitoring": "Authority monitoring becomes available after your first buildout.",
            "history": "Track how your public proof improves over time.",
            "graph": "Build your Authority Graph.",
        },
        "report_version": report_dict.get("report_version", "v1"),
        "disclaimer": (
            "Instant score is based on public website signals: offers, "
            "proof, FAQs, schema, comparisons, crawlability, and trust "
            "structure. Full Authority Snapshots are operator-reviewed "
            "before recommendations are sent."
        ),
    }


def _failure_envelope(report: AuthorityScoreReport) -> dict[str, Any]:
    return {
        "report_id": str(report.id),
        "status": "failed",
        "submitted": {
            "company_name": report.company_name,
            "website_url": report.website_url,
            "industry": report.industry,
        },
        "total_score": 0,
        "score_label": "not_assessed",
        "confidence_label": "low",
        "top_gaps": [],
        "quick_win": (
            "We couldn't reach your site to score it. Confirm the URL is publicly reachable and re-run the test."
        ),
        "recommended_package": {
            "primary_slug": None,
            "secondary_slug": None,
            "creative_proof_slug": None,
            "rationale": "",
        },
        "cta": {"label": "Try again", "href": "/ai-search-authority/score"},
        "disclaimer": (
            "Based on public website signals: offers, proof, FAQs, schema, "
            "comparisons, crawlability, and trust structure."
        ),
        "fetch_error": report.fetch_error,
    }


# ─────────────────────────────────────────────────────────────────────
# LeadOpportunity upsert
# ─────────────────────────────────────────────────────────────────────


async def _upsert_lead_opportunity(
    db: AsyncSession,
    *,
    report: AuthorityScoreReport,
    report_dict: dict[str, Any],
    brand_id: uuid.UUID,
) -> LeadOpportunity:
    total = report_dict["total_score"]
    primary_slug = (report_dict["recommended_package"] or {}).get("primary_slug")
    rationale = (report_dict["recommended_package"] or {}).get("rationale", "")

    if total < 40:
        tier = "hot"
        action = "send_authority_snapshot"
    elif total < 75:
        tier = "warm"
        action = "send_sprint_proposal"
    else:
        tier = "cold"
        action = "send_retainer_proposal"

    # The existing model stores message_text as freeform; we use it to carry
    # the report_id pointer + a short summary the operator sees in lists.
    summary = (
        f"AI Buyer Trust Test — {report.company_name} ({report.website_domain}) "
        f"score {total} ({report_dict['score_label']}). "
        f"Recommended: {primary_slug or 'review'}."
    )

    # Find existing lead for the same email + brand + source.
    existing = (
        (
            await db.execute(
                select(LeadOpportunity)
                .where(
                    LeadOpportunity.brand_id == brand_id,
                    LeadOpportunity.lead_source == LEAD_SOURCE,
                    LeadOpportunity.is_active.is_(True),
                )
                .order_by(LeadOpportunity.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    # Match by email substring inside message_text since LeadOpportunity has
    # no native email column. Latest scan wins.
    same_email = next(
        (lo for lo in existing if report.contact_email in (lo.message_text or "")),
        None,
    )

    if same_email is not None:
        same_email.composite_score = total / 100.0
        same_email.qualification_tier = tier
        same_email.recommended_action = action
        same_email.package_slug = primary_slug
        same_email.confidence = report_dict["confidence"]
        same_email.explanation = rationale
        same_email.message_text = (f"{summary}\nemail={report.contact_email}\nreport_id={report.id}")[:2000]
        await db.flush()
        return same_email

    lead = LeadOpportunity(
        brand_id=brand_id,
        lead_source=LEAD_SOURCE,
        message_text=(f"{summary}\nemail={report.contact_email}\nreport_id={report.id}")[:2000],
        urgency_score=0.0,
        budget_proxy_score=0.0,
        sophistication_score=0.0,
        offer_fit_score=0.0,
        trust_readiness_score=0.0,
        composite_score=total / 100.0,
        qualification_tier=tier,
        sales_stage="new_lead",
        package_slug=primary_slug,
        recommended_action=action,
        expected_value=0.0,
        likelihood_to_close=0.0,
        channel_preference="email",
        confidence=report_dict["confidence"],
        explanation=rationale,
    )
    db.add(lead)
    await db.flush()
    return lead


# ─────────────────────────────────────────────────────────────────────
# OperatorAction + SystemEvent emission
# ─────────────────────────────────────────────────────────────────────


async def _emit_operator_action(
    db: AsyncSession,
    *,
    report: AuthorityScoreReport,
    org_id: uuid.UUID,
    brand_id: uuid.UUID | None,
) -> None:
    if report.report_status == "failed":
        # Still surface failures so the operator sees what's broken.
        priority = "low"
    elif report.total_score < 60:
        priority = "high"
    elif report.total_score < 90:
        priority = "medium"
    else:
        priority = "low"
    title = f"Review AI Buyer Trust lead: {report.company_name} (score {report.total_score})"
    description = (
        f"Submitted from {report.website_url}. Industry: {report.industry}. "
        f"Recommended package: {report.recommended_package_slug or '—'}."
    )
    try:
        await emit_action(
            db,
            org_id=org_id,
            action_type="review_buyer_trust_lead",
            title=title,
            description=description,
            priority=priority,
            category="opportunity",
            brand_id=brand_id,
            entity_type="authority_score_report",
            entity_id=report.id,
            source_module="ai_buyer_trust_service",
            action_payload={
                "report_id": str(report.id),
                "lead_opportunity_id": (str(report.lead_opportunity_id) if report.lead_opportunity_id else None),
                "recommended_package_slug": report.recommended_package_slug,
                "total_score": report.total_score,
                "score_label": report.score_label,
            },
        )
    except Exception as exc:
        logger.warning("ai_buyer_trust.operator_action_failed", error=str(exc))


async def _emit_system_event(
    db: AsyncSession,
    *,
    report: AuthorityScoreReport,
    org_id: uuid.UUID,
    brand_id: uuid.UUID | None,
    lead_id: uuid.UUID | None,
) -> None:
    event_type = "ai_buyer_trust.test_completed" if report.report_status == "scored" else "ai_buyer_trust.test_failed"
    summary = (
        f"AI Buyer Trust Test completed for {report.company_name} — score {report.total_score}"
        if report.report_status == "scored"
        else f"AI Buyer Trust Test failed for {report.company_name} — {report.fetch_error or 'unknown'}"
    )
    severity = "info" if report.report_status == "scored" else "warning"
    try:
        await emit_event(
            db,
            domain="growth",
            event_type=event_type,
            summary=summary,
            severity=severity,
            org_id=org_id,
            brand_id=brand_id,
            entity_type="authority_score_report",
            entity_id=report.id,
            details={
                "report_id": str(report.id),
                "lead_opportunity_id": str(lead_id) if lead_id else None,
                "total_score": report.total_score,
                "score_label": report.score_label,
                "recommended_package_slug": report.recommended_package_slug,
                "website_domain": report.website_domain,
                "industry": report.industry,
            },
        )
    except Exception as exc:
        logger.warning("ai_buyer_trust.system_event_failed", error=str(exc))


# ─────────────────────────────────────────────────────────────────────
# Operator-facing helpers
# ─────────────────────────────────────────────────────────────────────


async def list_reports(
    db: AsyncSession,
    org_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    score_min: int | None = None,
    score_max: int | None = None,
    package_slug: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    query = (
        select(AuthorityScoreReport)
        .where(
            AuthorityScoreReport.organization_id == org_id,
            AuthorityScoreReport.is_active.is_(True),
        )
        .order_by(AuthorityScoreReport.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status:
        query = query.where(AuthorityScoreReport.report_status == status)
    if score_min is not None:
        query = query.where(AuthorityScoreReport.total_score >= score_min)
    if score_max is not None:
        query = query.where(AuthorityScoreReport.total_score <= score_max)
    if package_slug:
        query = query.where(AuthorityScoreReport.recommended_package_slug == package_slug)
    if search:
        like = f"%{search.strip().lower()}%"
        query = query.where(
            (AuthorityScoreReport.website_domain.ilike(like))
            | (AuthorityScoreReport.company_name.ilike(like))
            | (AuthorityScoreReport.contact_email.ilike(like))
        )

    rows = (await db.execute(query)).scalars().all()
    return [_row_to_list_item(r) for r in rows]


async def get_report(db: AsyncSession, org_id: uuid.UUID, report_id: uuid.UUID) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(AuthorityScoreReport).where(
                AuthorityScoreReport.id == report_id,
                AuthorityScoreReport.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return _row_to_detail(row)


def _row_to_list_item(r: AuthorityScoreReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "company_name": r.company_name,
        "website_url": r.website_url,
        "website_domain": r.website_domain,
        "contact_email": r.contact_email,
        "industry": r.industry,
        "total_score": r.total_score,
        "score_label": r.score_label,
        "confidence_label": confidence_label_for(r.confidence or 0.0),
        "recommended_package_slug": r.recommended_package_slug,
        "report_status": r.report_status,
        "top_gap_label": _first_top_gap_label(r.top_gaps),
        "lead_opportunity_id": str(r.lead_opportunity_id) if r.lead_opportunity_id else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _row_to_detail(r: AuthorityScoreReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "organization_id": str(r.organization_id),
        "brand_id": str(r.brand_id) if r.brand_id else None,
        "lead_opportunity_id": str(r.lead_opportunity_id) if r.lead_opportunity_id else None,
        "company_name": r.company_name,
        "website_url": r.website_url,
        "website_domain": r.website_domain,
        "contact_email": r.contact_email,
        "industry": r.industry,
        "competitor_url": r.competitor_url,
        "city_or_market": r.city_or_market,
        "total_score": r.total_score,
        "score_label": r.score_label,
        "confidence": r.confidence,
        "confidence_label": confidence_label_for(r.confidence or 0.0),
        "dimension_scores": r.dimension_scores or {},
        "technical_scores": r.technical_scores or {},
        "evidence": r.evidence or {},
        "raw_signals": r.raw_signals or {},
        "scanned_pages": r.scanned_pages or [],
        "top_gaps": r.top_gaps or [],
        "quick_wins": r.quick_wins or [],
        "recommended_package_slug": r.recommended_package_slug,
        "ai_summary": r.ai_summary,
        "public_result": r.public_result or {},
        "authority_score": r.authority_score,
        "authority_graph": r.authority_graph or {},
        "buyer_questions": r.buyer_questions or [],
        "recommended_pages": r.recommended_pages or [],
        "recommended_schema": r.recommended_schema or [],
        "recommended_proof_assets": r.recommended_proof_assets or [],
        "recommended_comparison_surfaces": r.recommended_comparison_surfaces or [],
        "monitoring_recommendation": r.monitoring_recommendation,
        "report_status": r.report_status,
        "scan_started_at": r.scan_started_at.isoformat() if r.scan_started_at else None,
        "scan_completed_at": r.scan_completed_at.isoformat() if r.scan_completed_at else None,
        "fetch_error": r.fetch_error,
        "formula_version": r.formula_version,
        "report_version": r.report_version,
        "scan_version": r.scan_version,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _first_top_gap_label(top_gaps: Any) -> str | None:
    if not top_gaps or not isinstance(top_gaps, list):
        return None
    first = top_gaps[0]
    if isinstance(first, dict):
        return first.get("public_label") or first.get("dimension")
    return None


__all__ = [
    "AiBuyerTrustInputError",
    "submit_trust_test",
    "list_reports",
    "get_report",
    "LEAD_SOURCE",
]

"""AI Search Authority — public diagnostic + operator pipeline.

This service is the connective tissue between the public AI Buyer Trust Test
form and the existing Revenue OS commercial spine. Every persistence path
goes through the system-events + lead-opportunity + proposals primitives
that already exist; this module does not duplicate any CRM, ledger, or
payment logic.

V1 doctrine (read carefully):

  - Diagnostic is **answer-based**. We do not fetch URLs, parse robots.txt,
    or render pages. The score is deterministic over the submitted answers
    and labelled accordingly to the buyer in the API response.
  - Recommendation is one of the **13 approved ProofHook package slugs**.
    The catalog lives here as the operator-side source of truth and is
    mirrored by the seeded Offer rows.
  - All Stripe / proposal / payment / Client / Intake mechanics are
    delegated to ``proposals_service`` — this module does not touch
    Stripe at all.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services import proposals_service
from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.ai_search_authority import AISearchAuthorityReport
from packages.db.models.core import Brand, Organization
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity
from packages.db.models.proposals import Proposal
from packages.db.models.system_events import OperatorAction, SystemEvent

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════
#  Approved ProofHook package catalog — operator side source of truth.
#
#  Mirrors apps/web/src/lib/proofhook-packages.ts (frontend marketing) and
#  the rows seeded by scripts/seed_proofhook_packages.py (Offer table).
#  Updates here MUST stay in lockstep with both — package slug is the
#  cross-system join key (Stripe metadata, Offer.audience_fit_tags,
#  ProposalLineItem.package_slug, AISearchAuthorityReport.recommended_package_slug).
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ProofHookPackage:
    slug: str
    name: str
    category: str  # "ai_authority" | "creative_proof"
    price_cents: int
    timeline: str
    url_path: str


PROOFHOOK_PACKAGES: tuple[ProofHookPackage, ...] = (
    # AI Authority
    ProofHookPackage(
        slug="ai_buyer_trust_test",
        name="AI Buyer Trust Test",
        category="ai_authority",
        price_cents=0,
        timeline="Free",
        url_path="/ai-buyer-trust-test",
    ),
    ProofHookPackage(
        slug="authority_snapshot",
        name="Authority Snapshot",
        category="ai_authority",
        price_cents=49500,
        timeline="3–5 days",
        url_path="/services/authority-snapshot",
    ),
    ProofHookPackage(
        slug="ai_search_authority_sprint",
        name="AI Search Authority Sprint",
        category="ai_authority",
        price_cents=450000,
        timeline="10–14 days",
        url_path="/ai-search-authority",
    ),
    ProofHookPackage(
        slug="proof_infrastructure_buildout",
        name="Proof Infrastructure Buildout",
        category="ai_authority",
        price_cents=950000,
        timeline="3–4 weeks",
        url_path="/services/proof-infrastructure-buildout",
    ),
    ProofHookPackage(
        slug="authority_monitoring_retainer",
        name="Authority Monitoring Retainer",
        category="ai_authority",
        price_cents=150000,
        timeline="Monthly",
        url_path="/services/authority-monitoring-retainer",
    ),
    ProofHookPackage(
        slug="ai_authority_system",
        name="AI Authority System",
        category="ai_authority",
        price_cents=2500000,
        timeline="6–8 weeks",
        url_path="/services/ai-authority-system",
    ),
    # Creative Proof
    ProofHookPackage(
        slug="signal_entry",
        name="Signal Entry",
        category="creative_proof",
        price_cents=150000,
        timeline="7 days",
        url_path="/services/signal-entry",
    ),
    ProofHookPackage(
        slug="momentum_engine",
        name="Momentum Engine",
        category="creative_proof",
        price_cents=250000,
        timeline="Monthly",
        url_path="/services/momentum-engine",
    ),
    ProofHookPackage(
        slug="conversion_architecture",
        name="Conversion Architecture",
        category="creative_proof",
        price_cents=350000,
        timeline="10–14 days",
        url_path="/services/conversion-architecture",
    ),
    ProofHookPackage(
        slug="paid_media_engine",
        name="Paid Media Engine",
        category="creative_proof",
        price_cents=450000,
        timeline="Monthly",
        url_path="/services/paid-media-engine",
    ),
    ProofHookPackage(
        slug="launch_sequence",
        name="Launch Sequence",
        category="creative_proof",
        price_cents=500000,
        timeline="10–14 days",
        url_path="/services/launch-sequence",
    ),
    ProofHookPackage(
        slug="creative_command",
        name="Creative Command",
        category="creative_proof",
        price_cents=750000,
        timeline="Monthly",
        url_path="/services/creative-command",
    ),
    ProofHookPackage(
        slug="custom_growth_system",
        name="Custom Growth System",
        category="creative_proof",
        price_cents=2500000,
        timeline="Quoted per engagement",
        url_path="/services/custom-growth-system",
    ),
)

PACKAGE_BY_SLUG: dict[str, ProofHookPackage] = {p.slug: p for p in PROOFHOOK_PACKAGES}
APPROVED_PACKAGE_SLUGS: frozenset[str] = frozenset(PACKAGE_BY_SLUG.keys())

# Canonical ProofHook attribution slugs — used to find/auto-bootstrap the
# org + brand row that public diagnostic submissions attach to.
PROOFHOOK_ORG_SLUG = "proofhook"
PROOFHOOK_BRAND_SLUG = "proofhook"


# ═══════════════════════════════════════════════════════════════════════════
#  Scoring rubric — answer-based diagnostic.
#
#  Each question is yes/no/unknown. Total weights sum to 100. The score is
#  the sum of weights for "yes" answers; a "no" surfaces the question as a
#  gap. Unknown answers contribute 0 and do not count as gaps (we do not
#  punish honesty about what the buyer hasn't checked).
# ═══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class _Question:
    key: str
    weight: float
    label: str
    quick_win: str
    severity: str  # "high" | "medium" | "low"


_QUESTIONS: tuple[_Question, ...] = (
    _Question(
        "machine_readable_homepage",
        8,
        "Homepage explains who you are, what you sell, and who you sell to in plain language",
        "Rewrite the homepage hero so it answers who/what/who-for in two sentences a buyer can quote.",
        "high",
    ),
    _Question(
        "about_page",
        6,
        "You have a real About / Company page with founder + team information",
        "Publish an About page with the founder, the team, and a one-line origin story.",
        "medium",
    ),
    _Question(
        "structured_data",
        12,
        "Site has Organization, Service, and Product structured data (JSON-LD)",
        "Add Organization + Service JSON-LD to every page; Product/Offer JSON-LD on package pages.",
        "high",
    ),
    _Question(
        "robots_allows_ai",
        8,
        "robots.txt allows AI crawlers (GPTBot, ClaudeBot, PerplexityBot) or does not block them",
        "Audit robots.txt and explicitly allow GPTBot, ClaudeBot, and PerplexityBot.",
        "high",
    ),
    _Question(
        "sitemap_present",
        6,
        "You have a working sitemap.xml that lists every important page",
        "Generate sitemap.xml with all answer/comparison/services pages and submit to Search Console.",
        "medium",
    ),
    _Question(
        "faq_page",
        8,
        "Public FAQ page answering buyer questions in your own voice",
        "Publish a FAQ page with the top 8 buyer questions, written in plain language with FAQPage JSON-LD.",
        "high",
    ),
    _Question(
        "comparison_pages",
        6,
        "Public pages comparing your offering to the alternatives buyers consider",
        "Publish two comparison pages framing how you differ from the closest alternatives.",
        "medium",
    ),
    _Question(
        "proof_assets",
        12,
        "Public case studies, testimonials, or named-customer references",
        "Publish three named case studies or attributed testimonials with measurable outcomes.",
        "high",
    ),
    _Question(
        "third_party_citations",
        8,
        "Third parties (publications, podcasts, partners) cite or link to you",
        "Identify three publications/podcasts/partners and pitch a contribution or interview each.",
        "medium",
    ),
    _Question(
        "answer_engine_pages",
        8,
        "Content that directly answers the questions buyers ask AI search engines",
        "Publish five answer pages, one per top buyer question, written in the answer-first format.",
        "high",
    ),
    _Question(
        "internal_linking",
        6,
        "Pages link to each other in a coherent topic structure",
        "Add an internal linking map: every answer page links to two related pages and the relevant service page.",
        "medium",
    ),
    _Question(
        "analytics_tracking",
        6,
        "You can tell when buyers arrive from AI search engines (referrer or UTM tracking)",
        "Add UTM landing-page handling and a referrer report so AI-source traffic is identifiable.",
        "low",
    ),
    _Question(
        "public_pricing",
        6,
        "Pricing or a starting cost is publicly visible on a package or pricing page",
        "Publish a starting-from price for every package on its dedicated page.",
        "medium",
    ),
)

_QUESTION_BY_KEY: dict[str, _Question] = {q.key: q for q in _QUESTIONS}
_TOTAL_WEIGHT: float = sum(q.weight for q in _QUESTIONS)
assert abs(_TOTAL_WEIGHT - 100.0) < 0.001, "Diagnostic weights must sum to 100"


# ═══════════════════════════════════════════════════════════════════════════
#  Scoring + recommendation
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ScoreResult:
    score: float
    tier: str
    gaps: list[dict[str, Any]]
    quick_win: str
    recommended_package_slug: str


def score_diagnostic(answers: dict[str, Any]) -> ScoreResult:
    """Compute a deterministic answer-based score and recommendation.

    ``answers`` maps question keys to one of "yes" / "no" / "unknown".
    Unknown values are not counted as gaps; only explicit "no" answers
    surface as gaps. The recommendation slug is always one of
    ``APPROVED_PACKAGE_SLUGS``.
    """
    score = 0.0
    gaps: list[dict[str, Any]] = []
    for q in _QUESTIONS:
        raw = answers.get(q.key)
        normalised = _normalise(raw)
        if normalised == "yes":
            score += q.weight
        elif normalised == "no":
            gaps.append(
                {
                    "key": q.key,
                    "label": q.label,
                    "weight": q.weight,
                    "severity": q.severity,
                    "quick_win": q.quick_win,
                }
            )

    gaps.sort(key=lambda g: -float(g["weight"]))

    if score < 36:
        tier = "cold"
        recommended_slug = "proof_infrastructure_buildout"
    elif score < 66:
        tier = "warm"
        recommended_slug = "ai_search_authority_sprint"
    else:
        tier = "hot"
        recommended_slug = "authority_monitoring_retainer"

    quick_win = gaps[0]["quick_win"] if gaps else (
        "Maintain your structured data, FAQ, and proof assets — quarterly review keeps eligibility intact."
    )

    return ScoreResult(
        score=round(score, 2),
        tier=tier,
        gaps=gaps[:3],
        quick_win=quick_win,
        recommended_package_slug=recommended_slug,
    )


def _normalise(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    s = str(value).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return "yes"
    if s in {"no", "n", "false", "0"}:
        return "no"
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
#  Persistence — score submission
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SubmitInput:
    submitter_email: str
    submitter_name: str = ""
    submitter_company: str = ""
    submitter_url: str = ""
    submitter_role: str = ""
    submitter_revenue_band: str = ""
    vertical: str = ""
    buyer_type: str = ""
    industry_context: str = ""
    answers: dict[str, Any] | None = None
    notes: str = ""
    source: str = "public"
    submission_ip: str | None = None
    user_agent: str | None = None


async def submit_score(
    db: AsyncSession,
    payload: SubmitInput,
) -> AISearchAuthorityReport:
    """Persist a public diagnostic submission and fan out to Revenue OS.

    Side effects (all in the same transaction):
      1. Resolve / bootstrap the canonical ProofHook org + brand.
      2. Insert ``AISearchAuthorityReport`` with the computed score.
      3. Insert ``LeadOpportunity`` and link the Report to it.
      4. Emit a ``revenue.ai_search_authority.report_submitted`` SystemEvent.
      5. Create a ``review_ai_search_authority_report`` OperatorAction.

    Returns the persisted Report.
    """
    answers = dict(payload.answers or {})
    result = score_diagnostic(answers)

    org_id, brand_id = await _resolve_proofhook_context(db)

    report = AISearchAuthorityReport(
        organization_id=org_id,
        brand_id=brand_id,
        submitter_email=payload.submitter_email[:255],
        submitter_name=payload.submitter_name[:255],
        submitter_company=payload.submitter_company[:255],
        submitter_url=payload.submitter_url[:1024],
        submitter_role=payload.submitter_role[:100],
        submitter_revenue_band=payload.submitter_revenue_band[:60],
        vertical=payload.vertical[:60],
        buyer_type=payload.buyer_type[:60],
        industry_context=payload.industry_context[:255],
        answers_json=answers,
        score=result.score,
        tier=result.tier,
        gaps_json=result.gaps,
        quick_win=result.quick_win,
        recommended_package_slug=result.recommended_package_slug,
        status="submitted",
        source=payload.source[:60],
        submission_ip=payload.submission_ip,
        user_agent=payload.user_agent[:500] if payload.user_agent else None,
        notes=payload.notes or None,
    )
    db.add(report)
    await db.flush()

    # LeadOpportunity — only if we have a brand to attach to. The model
    # requires brand_id NOT NULL. _resolve_proofhook_context bootstraps
    # one in dev/test, so production should always have a brand here.
    lead: LeadOpportunity | None = None
    if brand_id is not None:
        lead = LeadOpportunity(
            brand_id=brand_id,
            lead_source=f"ai_search_authority:{payload.source}",
            message_text=_build_lead_message(payload, result),
            urgency_score=_urgency_for_tier(result.tier),
            budget_proxy_score=_budget_proxy(payload.submitter_revenue_band),
            sophistication_score=min(1.0, result.score / 100.0),
            offer_fit_score=0.85,
            trust_readiness_score=min(1.0, result.score / 100.0),
            composite_score=_composite(result.score, payload.submitter_revenue_band),
            qualification_tier=result.tier,
            sales_stage="new_lead",
            package_slug=result.recommended_package_slug,
            recommended_action=(
                f"Follow up with {payload.submitter_email} about {result.recommended_package_slug}"
            ),
            expected_value=PACKAGE_BY_SLUG[result.recommended_package_slug].price_cents / 100.0,
            likelihood_to_close=0.25 + 0.5 * (result.score / 100.0),
            channel_preference="email",
            confidence=0.7,
            explanation=(
                f"AI Buyer Trust Test submission scored {result.score}/100 ({result.tier}); "
                f"recommended {result.recommended_package_slug}."
            ),
            is_active=True,
        )
        db.add(lead)
        await db.flush()
        report.lead_opportunity_id = lead.id

    summary = (
        f"AI Buyer Trust Test submitted by {payload.submitter_email} "
        f"— score {result.score}/100 ({result.tier}) → {result.recommended_package_slug}"
    )

    event = await emit_event(
        db,
        domain="revenue",
        event_type="ai_search_authority.report_submitted",
        summary=summary,
        org_id=org_id,
        brand_id=brand_id,
        entity_type="ai_search_authority_report",
        entity_id=report.id,
        new_state="submitted",
        actor_type="public",
        actor_id=payload.submitter_email[:255],
        details={
            "report_id": str(report.id),
            "submitter_email": payload.submitter_email,
            "submitter_company": payload.submitter_company,
            "submitter_url": payload.submitter_url,
            "score": result.score,
            "tier": result.tier,
            "vertical": payload.vertical,
            "recommended_package_slug": result.recommended_package_slug,
            "lead_opportunity_id": str(lead.id) if lead is not None else None,
            "source": payload.source,
            "diagnostic_kind": "answer_based",
            "gap_count": len(result.gaps),
        },
        requires_action=True,
    )

    if org_id is not None:
        await emit_action(
            db,
            org_id=org_id,
            brand_id=brand_id,
            action_type="review_ai_search_authority_report",
            title=(
                f"Review AI Buyer Trust Test: {payload.submitter_company or payload.submitter_email} "
                f"— {result.tier} ({result.score})"
            ),
            description=(
                f"{payload.submitter_email} submitted the AI Buyer Trust Test. "
                f"Score {result.score}/100 ({result.tier}). Recommended: {result.recommended_package_slug}. "
                f"Quick win: {result.quick_win}"
            ),
            category="opportunity",
            priority=_priority_for_tier(result.tier),
            entity_type="ai_search_authority_report",
            entity_id=report.id,
            source_event_id=event.id,
            source_module="ai_search_authority_service",
            action_payload={
                "report_id": str(report.id),
                "submitter_email": payload.submitter_email,
                "recommended_package_slug": result.recommended_package_slug,
                "lead_opportunity_id": str(lead.id) if lead is not None else None,
                "next_step_endpoint": (
                    f"POST /api/v1/ai-search-authority/reports/{report.id}/create-proposal"
                ),
            },
        )

    logger.info(
        "ai_search_authority.report_submitted",
        report_id=str(report.id),
        org_id=str(org_id) if org_id else None,
        brand_id=str(brand_id) if brand_id else None,
        score=result.score,
        tier=result.tier,
        recommended_package_slug=result.recommended_package_slug,
        submitter_email=payload.submitter_email,
    )
    return report


# ═══════════════════════════════════════════════════════════════════════════
#  Persistence — snapshot review request
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SnapshotReviewResult:
    report: AISearchAuthorityReport
    deduped: bool


async def request_snapshot_review(
    db: AsyncSession,
    *,
    report_id: uuid.UUID,
) -> SnapshotReviewResult:
    """Mark a report as snapshot_requested.

    Idempotent: a second call on the same report does not re-emit the
    event, does not create a second OperatorAction (event_bus.emit_action
    handles dedup on action_type+entity), and returns ``deduped=True``.
    """
    report = await _require_report(db, report_id)

    if report.status == "snapshot_requested":
        # Already requested — short-circuit but still report success.
        return SnapshotReviewResult(report=report, deduped=True)

    if report.status not in ("submitted",):
        raise ValueError(
            f"Cannot request snapshot review from status={report.status!r}"
        )

    prior = report.status
    report.status = "snapshot_requested"
    report.snapshot_requested_at = datetime.now(timezone.utc)
    await db.flush()

    summary = (
        f"Snapshot review requested for {report.submitter_email} "
        f"(score {report.score}, {report.tier})"
    )

    event = await emit_event(
        db,
        domain="revenue",
        event_type="ai_search_authority.snapshot_requested",
        summary=summary,
        org_id=report.organization_id,
        brand_id=report.brand_id,
        entity_type="ai_search_authority_report",
        entity_id=report.id,
        previous_state=prior,
        new_state="snapshot_requested",
        actor_type="public",
        actor_id=report.submitter_email,
        details={
            "report_id": str(report.id),
            "submitter_email": report.submitter_email,
            "submitter_url": report.submitter_url,
            "recommended_package_slug": report.recommended_package_slug,
        },
        requires_action=True,
    )

    if report.organization_id is not None:
        await emit_action(
            db,
            org_id=report.organization_id,
            brand_id=report.brand_id,
            action_type="deliver_authority_snapshot",
            title=(
                f"Deliver Authority Snapshot for "
                f"{report.submitter_company or report.submitter_email}"
            ),
            description=(
                f"{report.submitter_email} requested the Authority Snapshot. "
                f"URL: {report.submitter_url or 'not provided'}. "
                f"Recommended: {report.recommended_package_slug}."
            ),
            category="opportunity",
            priority="high",
            entity_type="ai_search_authority_report",
            entity_id=report.id,
            source_event_id=event.id,
            source_module="ai_search_authority_service",
            action_payload={
                "report_id": str(report.id),
                "submitter_email": report.submitter_email,
                "submitter_url": report.submitter_url,
                "recommended_package_slug": report.recommended_package_slug,
            },
        )

    logger.info(
        "ai_search_authority.snapshot_requested",
        report_id=str(report.id),
        submitter_email=report.submitter_email,
    )

    return SnapshotReviewResult(report=report, deduped=False)


# ═══════════════════════════════════════════════════════════════════════════
#  Persistence — operator views
# ═══════════════════════════════════════════════════════════════════════════


async def list_reports(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
) -> list[AISearchAuthorityReport]:
    query = (
        select(AISearchAuthorityReport)
        .where(AISearchAuthorityReport.organization_id == org_id)
        .order_by(AISearchAuthorityReport.created_at.desc())
        .limit(min(max(1, limit), 500))
        .offset(max(0, offset))
    )
    if status:
        query = query.where(AISearchAuthorityReport.status == status)
    rows = (await db.execute(query)).scalars().all()
    return list(rows)


async def get_report(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    report_id: uuid.UUID,
) -> AISearchAuthorityReport | None:
    return (
        await db.execute(
            select(AISearchAuthorityReport).where(
                AISearchAuthorityReport.id == report_id,
                AISearchAuthorityReport.organization_id == org_id,
            )
        )
    ).scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════
#  Proposal handoff — wraps existing proposals_service.create_proposal
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CreateProposalInput:
    package_slug: str | None = None
    title: str | None = None
    summary: str | None = None
    unit_amount_cents_override: int | None = None
    currency: str = "usd"
    notes: str | None = None


async def create_proposal_from_report(
    db: AsyncSession,
    *,
    org_id: uuid.UUID,
    report_id: uuid.UUID,
    operator_user_id: uuid.UUID,
    payload: CreateProposalInput,
) -> Proposal:
    """Create a Proposal for the report's recommended package.

    Delegates entirely to ``proposals_service.create_proposal`` — this
    function only resolves the package, builds the line items, and links
    the resulting Proposal back onto the report. Stripe-side mechanics
    (payment links, webhook attribution) happen via the existing flow.
    """
    report = await _require_report(db, report_id)
    if report.organization_id != org_id:
        raise PermissionError("Report not in operator's organization")

    slug = (payload.package_slug or report.recommended_package_slug or "").strip()
    if slug not in APPROVED_PACKAGE_SLUGS:
        raise ValueError(
            f"package_slug {slug!r} is not in the approved ProofHook catalog. "
            f"Allowed: {sorted(APPROVED_PACKAGE_SLUGS)}"
        )

    package = PACKAGE_BY_SLUG[slug]
    unit_cents = (
        payload.unit_amount_cents_override
        if payload.unit_amount_cents_override is not None
        else package.price_cents
    )

    line = proposals_service.LineItemInput(
        description=f"{package.name} ({package.timeline})",
        unit_amount_cents=unit_cents,
        quantity=1,
        package_slug=slug,
        currency=payload.currency,
        position=0,
    )

    title = payload.title or f"{package.name} — for {report.submitter_company or report.submitter_email}"
    summary = payload.summary or (
        f"Proposal generated from AI Buyer Trust Test report {report.id}. "
        f"Score {report.score}/100 ({report.tier}). "
        f"Recommended package: {package.name}."
    )

    proposal = await proposals_service.create_proposal(
        db,
        org_id=org_id,
        brand_id=report.brand_id,
        recipient_email=report.submitter_email,
        recipient_name=report.submitter_name,
        recipient_company=report.submitter_company,
        title=title,
        summary=summary,
        line_items=[line],
        package_slug=slug,
        currency=payload.currency,
        created_by_actor_type="operator",
        created_by_actor_id=str(operator_user_id),
        notes=payload.notes,
        extra_json={
            "ai_search_authority_report_id": str(report.id),
            "diagnostic_score": report.score,
            "diagnostic_tier": report.tier,
            "vertical": report.vertical,
            "package_name": package.name,
            "source": "ai_search_authority_diagnostic",
        },
    )

    report.proposal_id = proposal.id
    report.proposal_created_at = datetime.now(timezone.utc)
    report.status = "proposal_sent"
    await db.flush()

    await emit_event(
        db,
        domain="revenue",
        event_type="ai_search_authority.proposal_created",
        summary=(
            f"Proposal created from AI Buyer Trust Test report — "
            f"{report.submitter_email} → {package.name}"
        ),
        org_id=org_id,
        brand_id=report.brand_id,
        entity_type="ai_search_authority_report",
        entity_id=report.id,
        previous_state="snapshot_requested",
        new_state="proposal_sent",
        actor_type="operator",
        actor_id=str(operator_user_id),
        details={
            "report_id": str(report.id),
            "proposal_id": str(proposal.id),
            "package_slug": slug,
            "package_name": package.name,
            "total_amount_cents": proposal.total_amount_cents,
            "currency": proposal.currency,
        },
    )

    return proposal


# ═══════════════════════════════════════════════════════════════════════════
#  Internals
# ═══════════════════════════════════════════════════════════════════════════


async def _require_report(db: AsyncSession, report_id: uuid.UUID) -> AISearchAuthorityReport:
    report = (
        await db.execute(
            select(AISearchAuthorityReport).where(AISearchAuthorityReport.id == report_id)
        )
    ).scalar_one_or_none()
    if report is None:
        raise LookupError(f"ai_search_authority_report {report_id} not found")
    return report


async def _resolve_proofhook_context(
    db: AsyncSession,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    """Find or bootstrap the canonical ProofHook organization + brand.

    Production has these rows seeded already (see proofhook-packages.ts
    constants and scripts/seed_proofhook_packages.py). For fresh dev or
    test databases we create them on first call so the public diagnostic
    flow always has a brand to attach the LeadOpportunity to.
    """
    brand = (
        await db.execute(select(Brand).where(Brand.slug == PROOFHOOK_BRAND_SLUG))
    ).scalar_one_or_none()
    if brand is not None:
        return brand.organization_id, brand.id

    # No proofhook brand yet — find or create the canonical org first.
    org = (
        await db.execute(
            select(Organization).where(Organization.slug == PROOFHOOK_ORG_SLUG)
        )
    ).scalar_one_or_none()
    if org is None:
        org = (
            await db.execute(
                select(Organization).where(Organization.is_active.is_(True)).limit(1)
            )
        ).scalar_one_or_none()
    if org is None:
        org = Organization(
            name="ProofHook",
            slug=PROOFHOOK_ORG_SLUG,
            is_active=True,
        )
        db.add(org)
        await db.flush()

    brand = Brand(
        organization_id=org.id,
        name="ProofHook",
        slug=PROOFHOOK_BRAND_SLUG,
        niche="b2b_services",
        is_active=True,
    )
    db.add(brand)
    await db.flush()
    return org.id, brand.id


def _build_lead_message(payload: SubmitInput, result: ScoreResult) -> str:
    parts = [
        "AI Buyer Trust Test submission",
        f"Email: {payload.submitter_email}",
        f"Name: {payload.submitter_name or '(not provided)'}",
        f"Company: {payload.submitter_company or '(not provided)'}",
        f"URL: {payload.submitter_url or '(not provided)'}",
        f"Vertical: {payload.vertical or '(not provided)'}",
        f"Buyer type: {payload.buyer_type or '(not provided)'}",
        f"Revenue band: {payload.submitter_revenue_band or '(not provided)'}",
        "",
        f"Score: {result.score}/100 ({result.tier})",
        f"Recommended: {result.recommended_package_slug}",
        f"Quick win: {result.quick_win}",
    ]
    if result.gaps:
        parts.append("")
        parts.append("Top gaps:")
        for g in result.gaps:
            parts.append(f"  - {g['label']} (weight {g['weight']}, {g['severity']})")
    if payload.notes:
        parts.append("")
        parts.append(f"Notes: {payload.notes}")
    return "\n".join(parts)


def _urgency_for_tier(tier: str) -> float:
    return {"hot": 0.9, "warm": 0.6, "cold": 0.4}.get(tier, 0.5)


def _budget_proxy(revenue_band: str) -> float:
    band = (revenue_band or "").lower().strip()
    if any(k in band for k in ("10m", "25m", "50m", "100m", "enterprise")):
        return 0.95
    if any(k in band for k in ("5m", "1m", "2m")):
        return 0.8
    if any(k in band for k in ("500k", "750k", "250k")):
        return 0.6
    if any(k in band for k in ("100k", "50k")):
        return 0.4
    return 0.5


def _composite(score: float, revenue_band: str) -> float:
    return round(0.6 * (score / 100.0) + 0.4 * _budget_proxy(revenue_band), 4)


def _priority_for_tier(tier: str) -> str:
    return {"hot": "high", "warm": "medium", "cold": "low"}.get(tier, "medium")


# Re-export the SystemEvent + OperatorAction types for tests/operator UI
# imports — keeps callers from reaching directly into packages.db.models.
__all__ = [
    "APPROVED_PACKAGE_SLUGS",
    "PACKAGE_BY_SLUG",
    "PROOFHOOK_PACKAGES",
    "PROOFHOOK_BRAND_SLUG",
    "PROOFHOOK_ORG_SLUG",
    "ProofHookPackage",
    "ScoreResult",
    "SubmitInput",
    "SnapshotReviewResult",
    "CreateProposalInput",
    "score_diagnostic",
    "submit_score",
    "request_snapshot_review",
    "list_reports",
    "get_report",
    "create_proposal_from_report",
    "OperatorAction",
    "SystemEvent",
]

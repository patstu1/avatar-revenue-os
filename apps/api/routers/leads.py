"""Lead capture + operator-facing lead management.

Two surfaces on one router:

- ``POST /leads/capture``: public, no auth. Hit by external offer landing
  pages. Writes into ``lead_opportunities``. Unchanged from prior behavior.

- ``POST /leads`` / ``POST /leads/import-csv`` / ``GET /leads`` /
  ``GET /leads/stats``: operator-only (``OperatorUser``). Writes into
  ``sponsor_targets`` via raw SQL. Ported from ``claude/wizardly-buck``.
"""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Query, Request, UploadFile
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, text

from apps.api.deps import DBSession, OperatorUser
from packages.db.models.core import Brand
from packages.db.models.expansion_pack2_phase_a import LeadOpportunity

router = APIRouter()


# ═════════════════════════════════════════════════════════════════════════
# PUBLIC LEAD CAPTURE — unchanged
# ═════════════════════════════════════════════════════════════════════════

class LeadCaptureRequest(BaseModel):
    offer_slug: str
    brand_slug: str
    name: str
    email: str
    company: str = ""
    message: str = ""
    revenue: str = ""


@router.post("/leads/capture")
async def capture_lead(body: LeadCaptureRequest, request: Request, db: DBSession):
    """Public endpoint: capture an inbound lead from an offer landing page.

    No authentication required — this is hit by the public offer pages.
    Persists the lead into lead_opportunities for the matching brand.
    """
    # Resolve brand
    brand = (await db.execute(
        select(Brand).where(Brand.slug == body.brand_slug, Brand.is_active.is_(True))
    )).scalar_one_or_none()

    if not brand:
        return {"captured": False, "reason": "brand_not_found"}

    # Resolve offer_id from slug match
    offer_id = None
    try:
        from packages.db.models.offers import Offer
        offers = (await db.execute(
            select(Offer).where(Offer.brand_id == brand.id, Offer.is_active.is_(True))
        )).scalars().all()
        # Match by slug-ified name
        for o in offers:
            slug = o.name.lower().replace(" ", "-").replace("_", "-")
            if slug == body.offer_slug or body.offer_slug in slug:
                offer_id = o.id
                break
    except Exception:
        pass

    # Persist lead
    lead = LeadOpportunity(
        brand_id=brand.id,
        lead_source=f"landing_page:{body.offer_slug}",
        message_text=f"Name: {body.name}\nEmail: {body.email}\nCompany: {body.company}\nRevenue: {body.revenue}\n\n{body.message}",
        urgency_score=0.5,
        budget_proxy_score=0.5,
        sophistication_score=0.5,
        offer_fit_score=0.8 if offer_id else 0.5,
        trust_readiness_score=0.7,
        composite_score=0.6,
        qualification_tier="warm",
        recommended_action=f"Follow up with {body.name} at {body.email} about {body.offer_slug}",
        expected_value=0,
        likelihood_to_close=0.3,
        channel_preference="email",
        confidence=0.7,
        explanation=f"Inbound lead from {body.offer_slug} landing page",
        is_active=True,
    )
    db.add(lead)

    # Also log as system event
    try:
        from packages.db.models.system_events import SystemEvent
        db.add(SystemEvent(
            organization_id=brand.organization_id,
            brand_id=brand.id,
            event_type="lead.captured",
            entity_type="lead_opportunity",
            entity_id=lead.id,
            severity="info",
            domain="revenue",
            summary=f"Lead captured: {body.name} ({body.email}) for {body.offer_slug}",
            details_json={
                "name": body.name,
                "email": body.email,
                "company": body.company,
                "offer_slug": body.offer_slug,
                "source_ip": request.client.host if request.client else None,
            },
        ))
    except Exception:
        pass

    await db.commit()

    return {
        "captured": True,
        "lead_id": str(lead.id),
        "brand": brand.name,
        "offer_slug": body.offer_slug,
    }


# ═════════════════════════════════════════════════════════════════════════
# OPERATOR-FACING LEAD MANAGEMENT — ported from claude/wizardly-buck
# ═════════════════════════════════════════════════════════════════════════
#
# These endpoints are auth-scoped (OperatorUser), write into the
# ``sponsor_targets`` table via raw SQL (no ORM model dependency), and
# power the dashboard/leads/outbound UIs. They are a separate data plane
# from /leads/capture (which writes into lead_opportunities for the public
# funnel).


# --- Legacy niche→brand_id fallback (DO NOT TREAT AS CANONICAL TRUTH) ----
#
# Ported verbatim from wizardly-buck. These UUIDs correspond to seeded
# brand rows in an earlier Revenue_OS deployment and MAY NOT EXIST in the
# current database. They are only used as a last-resort default when a CSV
# row arrives without any org-configurable niche→brand routing.
#
# TODO(phase-5): replace with an org-configurable ``lead_routing_rule``
# entry in integration_providers (or a dedicated lead_routing table) so
# niche→brand mapping becomes system-managed. Once that lands, delete this
# dict entirely.
_LEGACY_NICHE_BRAND_FALLBACK = {
    "beauty": "a108a231-e2e3-40ce-b391-6024e6b26abd",
    "skincare": "a108a231-e2e3-40ce-b391-6024e6b26abd",
    "fitness": "23b5fa22-502c-4d9f-93af-6f3efe4bed95",
    "health": "23b5fa22-502c-4d9f-93af-6f3efe4bed95",
    "supplement": "23b5fa22-502c-4d9f-93af-6f3efe4bed95",
    "saas": "dbf36602-f203-41e2-be81-176dba59ed70",
    "ai": "dbf36602-f203-41e2-be81-176dba59ed70",
    "tech": "dbf36602-f203-41e2-be81-176dba59ed70",
}


async def _resolve_default_brand_id(db, org_id: uuid.UUID, niche: str) -> Optional[uuid.UUID]:
    """Pick a default brand for CSV import rows.

    Priority:
      1. If the org has exactly one active brand, use it.
      2. Otherwise, try the legacy niche→brand_id fallback map above, but
         only if that brand actually exists in the DB for this org.
      3. Otherwise, pick the org's first active brand by creation order.
    """
    brands = (await db.execute(
        select(Brand).where(
            Brand.organization_id == org_id,
            Brand.is_active.is_(True),
        ).order_by(Brand.created_at)
    )).scalars().all()

    if not brands:
        return None

    if len(brands) == 1:
        return brands[0].id

    # Legacy fallback, only if it actually resolves to one of this org's brands.
    legacy_id_str = _LEGACY_NICHE_BRAND_FALLBACK.get(niche.lower())
    if legacy_id_str:
        try:
            legacy_uuid = uuid.UUID(legacy_id_str)
            for b in brands:
                if b.id == legacy_uuid:
                    return legacy_uuid
        except ValueError:
            pass

    return brands[0].id


class LeadCreate(BaseModel):
    company_name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram_handle: Optional[str] = None
    website_url: Optional[str] = None
    industry: str = "beauty"
    estimated_size: Optional[str] = None
    niche_tag: str = "beauty"
    notes: Optional[str] = None


class LeadResponse(BaseModel):
    id: str
    company_name: str
    contact_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    instagram_handle: Optional[str] = None
    website_url: Optional[str] = None
    industry: str
    niche_tag: str
    estimated_size: Optional[str] = None
    fit_score: float
    outreach_status: str
    created_at: str


class LeadImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[str]
    total_leads: int


class LeadStats(BaseModel):
    total: int
    by_niche: dict
    by_status: dict
    with_email: int
    with_phone: int


@router.post("/leads", response_model=LeadResponse, status_code=201)
async def create_lead(body: LeadCreate, current_user: OperatorUser, db: DBSession):
    """Create a single operator-entered lead into sponsor_targets."""
    lead_id = uuid.uuid4()
    now_iso = datetime.now(timezone.utc).isoformat()

    # TODO(phase-5): resolve brand_id properly from a system-managed
    # org→brand mapping. Using the org's first/only brand for now.
    brand_id = await _resolve_default_brand_id(db, current_user.organization_id, body.niche_tag)
    if brand_id is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active brand found for this organization — create a brand before importing leads.",
        )

    contact_json = json.dumps({
        "email": body.email or "",
        "phone": body.phone or "",
        "name": body.contact_name or "",
        "instagram": body.instagram_handle or "",
        "website": body.website_url or "",
        "size": body.estimated_size or "",
        "niche_tag": body.niche_tag,
        "notes": body.notes or "",
    })

    await db.execute(text("""
        INSERT INTO sponsor_targets (
            id, brand_id, target_company_name, industry, contact_info,
            estimated_deal_value, fit_score, confidence, explanation,
            is_active, created_at, updated_at
        ) VALUES (
            :id, :bid, :company, :industry, CAST(:contact AS JSONB),
            1500, 0.5, 0.5, :explanation,
            true, now(), now()
        )
    """), {
        "id": lead_id,
        "bid": brand_id,
        "company": body.company_name,
        "industry": body.niche_tag,
        "contact": contact_json,
        "explanation": f"Manual entry: {body.niche_tag} lead",
    })
    await db.commit()

    return LeadResponse(
        id=str(lead_id),
        company_name=body.company_name,
        contact_name=body.contact_name,
        email=body.email,
        phone=body.phone,
        instagram_handle=body.instagram_handle,
        website_url=body.website_url,
        industry=body.niche_tag,
        niche_tag=body.niche_tag,
        estimated_size=body.estimated_size,
        fit_score=0.5,
        outreach_status="new",
        created_at=now_iso,
    )


@router.post("/leads/import-csv", response_model=LeadImportResult)
async def import_leads_csv(
    current_user: OperatorUser,
    db: DBSession,
    file: UploadFile = File(...),
):
    """Bulk import leads from CSV into ``sponsor_targets``.

    Required column: ``company_name``. All others optional.
    Accepted aliases: company, contact_email/email, contact_phone/phone,
    name/contact_name, ig/instagram/instagram_handle, url/website/website_url,
    niche/niche_tag/industry/category, size/employees/estimated_size, notes.

    Duplicates (by company name within the org's brands) are skipped.
    """
    content = await file.read()
    text_content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_content))

    imported = 0
    skipped = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        company = (row.get("company_name") or row.get("company") or "").strip()
        if not company:
            skipped += 1
            continue

        email = (row.get("email") or row.get("contact_email") or "").strip()
        phone = (row.get("phone") or row.get("contact_phone") or "").strip()
        contact_name = (row.get("contact_name") or row.get("name") or "").strip()
        instagram = (row.get("instagram_handle") or row.get("instagram") or row.get("ig") or "").strip()
        website = (row.get("website_url") or row.get("website") or row.get("url") or "").strip()
        industry = (
            row.get("industry") or row.get("niche_tag") or row.get("niche") or row.get("category") or "beauty"
        ).strip()
        size = (row.get("estimated_size") or row.get("size") or row.get("employees") or "").strip()
        notes = (row.get("notes") or "").strip()

        # Deduplicate by company name (org-scoped via org's brands).
        existing = (await db.execute(text("""
            SELECT st.id FROM sponsor_targets st
            JOIN brands b ON b.id = st.brand_id
            WHERE b.organization_id = :oid AND st.target_company_name = :name
            LIMIT 1
        """), {"oid": current_user.organization_id, "name": company})).scalar_one_or_none()

        if existing:
            skipped += 1
            continue

        try:
            brand_id = await _resolve_default_brand_id(db, current_user.organization_id, industry)
            if brand_id is None:
                errors.append(f"Row {i}: no active brand for org — skip")
                skipped += 1
                continue

            contact_json = json.dumps({
                "email": email, "phone": phone, "name": contact_name,
                "instagram": instagram, "website": website,
                "size": size, "niche_tag": industry, "notes": notes,
            })

            # Rough deal-value estimate by size string.
            deal_value = 2500
            if size and any(k in size.lower() for k in ["large", "50+", "100+", "enterprise"]):
                deal_value = 7500
            elif size and any(k in size.lower() for k in ["small", "1-10", "startup"]):
                deal_value = 1500

            await db.execute(text("""
                INSERT INTO sponsor_targets (
                    id, brand_id, target_company_name, industry, contact_info,
                    estimated_deal_value, fit_score, confidence, explanation,
                    is_active, created_at, updated_at
                ) VALUES (
                    :id, :bid, :company, :industry, CAST(:contact AS JSONB),
                    :deal, 0.5, 0.5, :explanation,
                    true, now(), now()
                )
            """), {
                "id": uuid.uuid4(),
                "bid": brand_id,
                "company": company,
                "industry": industry,
                "contact": contact_json,
                "deal": deal_value,
                "explanation": f"CSV import: {industry}",
            })
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)[:120]}")

    await db.commit()

    total = (await db.execute(text("""
        SELECT count(*) FROM sponsor_targets st
        JOIN brands b ON b.id = st.brand_id
        WHERE b.organization_id = :oid AND st.is_active = true
    """), {"oid": current_user.organization_id})).scalar() or 0

    return LeadImportResult(imported=imported, skipped=skipped, errors=errors[:10], total_leads=total)


@router.get("/leads", response_model=list[LeadResponse])
async def list_leads(
    current_user: OperatorUser,
    db: DBSession,
    niche: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """List operator-managed leads for the user's org.

    Scoped to sponsor_targets owned by the user's organization (joined via brands).
    """
    q = """
        SELECT st.id, st.target_company_name, st.industry, st.contact_info,
               st.estimated_deal_value, st.fit_score, st.is_active, st.created_at
        FROM sponsor_targets st
        JOIN brands b ON b.id = st.brand_id
        WHERE b.organization_id = :oid AND st.is_active = true
    """
    params: dict = {"oid": current_user.organization_id}
    if niche:
        q += " AND st.industry = :niche"
        params["niche"] = niche
    q += " ORDER BY st.created_at DESC LIMIT 50 OFFSET :offset"
    params["offset"] = (page - 1) * 50

    rows = (await db.execute(text(q), params)).fetchall()

    results: list[LeadResponse] = []
    for r in rows:
        ci = r.contact_info or {}
        seq = (await db.execute(text(
            "SELECT steps FROM sponsor_outreach_sequences WHERE sponsor_target_id = :tid ORDER BY created_at DESC LIMIT 1"
        ), {"tid": r.id})).scalar_one_or_none()

        status = "new"
        if seq:
            steps = seq if isinstance(seq, list) else []
            if any(isinstance(s, dict) and s.get("status") == "replied" for s in steps):
                status = "replied"
            elif any(isinstance(s, dict) and s.get("status") == "sent" for s in steps):
                status = "contacted"

        results.append(LeadResponse(
            id=str(r.id),
            company_name=r.target_company_name,
            contact_name=ci.get("name"),
            email=ci.get("email"),
            phone=ci.get("phone"),
            instagram_handle=ci.get("instagram"),
            website_url=ci.get("website"),
            industry=r.industry,
            niche_tag=ci.get("niche_tag", r.industry),
            estimated_size=ci.get("size"),
            fit_score=float(r.fit_score or 0),
            outreach_status=status,
            created_at=str(r.created_at),
        ))

    return results


@router.get("/leads/stats", response_model=LeadStats)
async def lead_stats(current_user: OperatorUser, db: DBSession):
    """Per-org lead database stats (sponsor_targets, org-scoped)."""
    params = {"oid": current_user.organization_id}

    total = (await db.execute(text("""
        SELECT count(*) FROM sponsor_targets st
        JOIN brands b ON b.id = st.brand_id
        WHERE b.organization_id = :oid AND st.is_active = true
    """), params)).scalar() or 0

    by_niche = dict((await db.execute(text("""
        SELECT st.industry, count(*) FROM sponsor_targets st
        JOIN brands b ON b.id = st.brand_id
        WHERE b.organization_id = :oid AND st.is_active = true
        GROUP BY st.industry
    """), params)).fetchall())

    with_email = (await db.execute(text("""
        SELECT count(*) FROM sponsor_targets st
        JOIN brands b ON b.id = st.brand_id
        WHERE b.organization_id = :oid AND st.is_active = true
          AND st.contact_info->>'email' IS NOT NULL
          AND st.contact_info->>'email' != ''
    """), params)).scalar() or 0

    with_phone = (await db.execute(text("""
        SELECT count(*) FROM sponsor_targets st
        JOIN brands b ON b.id = st.brand_id
        WHERE b.organization_id = :oid AND st.is_active = true
          AND st.contact_info->>'phone' IS NOT NULL
          AND st.contact_info->>'phone' != ''
    """), params)).scalar() or 0

    return LeadStats(
        total=total,
        by_niche=by_niche,
        by_status={"new": total},
        with_email=with_email,
        with_phone=with_phone,
    )

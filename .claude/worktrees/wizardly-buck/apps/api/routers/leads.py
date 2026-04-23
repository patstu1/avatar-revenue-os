"""Lead management — import, list, and manage B2B outreach targets.

Supports CSV import, manual entry, and auto-wiring to outreach sequences.
"""
import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import DBSession, OperatorUser

router = APIRouter(tags=["leads"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

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
    contact_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    instagram_handle: Optional[str]
    website_url: Optional[str]
    industry: str
    niche_tag: str
    estimated_size: Optional[str]
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/leads", response_model=LeadResponse, status_code=201)
async def create_lead(body: LeadCreate, current_user: OperatorUser, db: DBSession):
    """Create a single lead manually."""
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc).isoformat()

    await db.execute(text("""
        INSERT INTO sponsor_targets (id, brand_id, target_company_name, industry, contact_info,
            estimated_deal_value, fit_score, confidence, explanation, is_active, created_at, updated_at)
        VALUES (:id, :bid, :company, :industry, :contact::jsonb,
            1500, 0.5, 0.5, :explanation, true, now(), now())
    """), {
        "id": lead_id,
        "bid": current_user.organization_id,  # use org_id as brand_id placeholder
        "company": body.company_name,
        "industry": body.niche_tag,
        "contact": f'{{"email":"{body.email or ""}","phone":"{body.phone or ""}","name":"{body.contact_name or ""}","instagram":"{body.instagram_handle or ""}","website":"{body.website_url or ""}","size":"{body.estimated_size or ""}","niche_tag":"{body.niche_tag}","notes":"{body.notes or ""}"}}',
        "explanation": f"Manual entry: {body.niche_tag} lead",
    })
    await db.commit()

    return LeadResponse(
        id=str(lead_id), company_name=body.company_name, contact_name=body.contact_name,
        email=body.email, phone=body.phone, instagram_handle=body.instagram_handle,
        website_url=body.website_url, industry=body.niche_tag, niche_tag=body.niche_tag,
        estimated_size=body.estimated_size, fit_score=0.5, outreach_status="new", created_at=now,
    )


@router.post("/leads/import-csv", response_model=LeadImportResult)
async def import_leads_csv(current_user: OperatorUser, db: DBSession, file: UploadFile = File(...)):
    """Bulk import leads from CSV.

    CSV columns (header row required):
    company_name, contact_name, email, phone, instagram_handle, website_url, industry, niche_tag, estimated_size, notes

    Only company_name is required. All other fields are optional.
    """
    content = await file.read()
    text_content = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text_content))

    imported = 0
    skipped = 0
    errors = []

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
        industry = (row.get("industry") or row.get("niche_tag") or row.get("niche") or row.get("category") or "beauty").strip()
        size = (row.get("estimated_size") or row.get("size") or row.get("employees") or "").strip()
        notes = (row.get("notes") or "").strip()

        # Skip duplicates by company name
        existing = (await db.execute(text(
            "SELECT id FROM sponsor_targets WHERE target_company_name = :name LIMIT 1"
        ), {"name": company})).scalar_one_or_none()

        if existing:
            skipped += 1
            continue

        try:
            import json
            contact_json = json.dumps({
                "email": email, "phone": phone, "name": contact_name,
                "instagram": instagram, "website": website,
                "size": size, "niche_tag": industry, "notes": notes,
            })

            # Pick brand_id based on niche
            niche_brand_map = {
                "beauty": "a108a231-e2e3-40ce-b391-6024e6b26abd",
                "skincare": "a108a231-e2e3-40ce-b391-6024e6b26abd",
                "fitness": "23b5fa22-502c-4d9f-93af-6f3efe4bed95",
                "health": "23b5fa22-502c-4d9f-93af-6f3efe4bed95",
                "supplement": "23b5fa22-502c-4d9f-93af-6f3efe4bed95",
                "saas": "dbf36602-f203-41e2-be81-176dba59ed70",
                "ai": "dbf36602-f203-41e2-be81-176dba59ed70",
                "tech": "dbf36602-f203-41e2-be81-176dba59ed70",
            }
            brand_id = niche_brand_map.get(industry.lower(), "a108a231-e2e3-40ce-b391-6024e6b26abd")

            # Estimate deal value based on size
            deal_value = 2500
            if size and any(k in size.lower() for k in ["large", "50+", "100+", "enterprise"]):
                deal_value = 7500
            elif size and any(k in size.lower() for k in ["small", "1-10", "startup"]):
                deal_value = 1500

            await db.execute(text("""
                INSERT INTO sponsor_targets (id, brand_id, target_company_name, industry, contact_info,
                    estimated_deal_value, fit_score, confidence, explanation, is_active, created_at, updated_at)
                VALUES (:id, :bid::uuid, :company, :industry, :contact::jsonb,
                    :deal, 0.5, 0.5, :explanation, true, now(), now())
            """), {
                "id": uuid.uuid4(), "bid": brand_id,
                "company": company, "industry": industry, "contact": contact_json,
                "deal": deal_value, "explanation": f"CSV import: {industry}",
            })
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {str(e)[:100]}")

    await db.commit()

    total = (await db.execute(text("SELECT count(*) FROM sponsor_targets WHERE is_active = true"))).scalar() or 0

    return LeadImportResult(imported=imported, skipped=skipped, errors=errors[:10], total_leads=total)


@router.get("/leads", response_model=list[LeadResponse])
async def list_leads(current_user: OperatorUser, db: DBSession,
                     niche: Optional[str] = None, page: int = Query(1, ge=1)):
    """List all leads with optional niche filter."""
    q = "SELECT id, target_company_name, industry, contact_info, estimated_deal_value, fit_score, is_active, created_at FROM sponsor_targets WHERE is_active = true"
    params: dict = {}
    if niche:
        q += " AND industry = :niche"
        params["niche"] = niche
    q += " ORDER BY created_at DESC LIMIT 50 OFFSET :offset"
    params["offset"] = (page - 1) * 50

    rows = (await db.execute(text(q), params)).fetchall()

    results = []
    for r in rows:
        ci = r.contact_info or {}
        # Check outreach status
        seq = (await db.execute(text(
            "SELECT steps FROM sponsor_outreach_sequences WHERE sponsor_target_id = :tid ORDER BY created_at DESC LIMIT 1"
        ), {"tid": r.id})).scalar_one_or_none()

        status = "new"
        if seq:
            steps = seq if isinstance(seq, list) else []
            if any(s.get("status") == "replied" for s in steps):
                status = "replied"
            elif any(s.get("status") == "sent" for s in steps):
                status = "contacted"

        results.append(LeadResponse(
            id=str(r.id), company_name=r.target_company_name,
            contact_name=ci.get("name"), email=ci.get("email"), phone=ci.get("phone"),
            instagram_handle=ci.get("instagram"), website_url=ci.get("website"),
            industry=r.industry, niche_tag=ci.get("niche_tag", r.industry),
            estimated_size=ci.get("size"), fit_score=float(r.fit_score or 0),
            outreach_status=status, created_at=str(r.created_at),
        ))

    return results


@router.get("/leads/stats", response_model=LeadStats)
async def lead_stats(current_user: OperatorUser, db: DBSession):
    """Lead database stats."""
    total = (await db.execute(text("SELECT count(*) FROM sponsor_targets WHERE is_active = true"))).scalar() or 0
    by_niche = dict((await db.execute(text(
        "SELECT industry, count(*) FROM sponsor_targets WHERE is_active = true GROUP BY industry"
    ))).fetchall())
    with_email = (await db.execute(text(
        "SELECT count(*) FROM sponsor_targets WHERE is_active = true AND contact_info->>'email' != ''"
    ))).scalar() or 0
    with_phone = (await db.execute(text(
        "SELECT count(*) FROM sponsor_targets WHERE is_active = true AND contact_info->>'phone' != ''"
    ))).scalar() or 0

    return LeadStats(total=total, by_niche=by_niche, by_status={"new": total}, with_email=with_email, with_phone=with_phone)

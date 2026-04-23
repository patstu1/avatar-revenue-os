"""Landing Page Engine API — authenticated management + public rendering."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.rate_limit import recompute_rate_limit
from apps.api.schemas.landing_pages import LandingPageOut, LPVariantOut, LPQualityOut, RecomputeSummaryOut
from apps.api.services import landing_page_service as svc
from packages.db.models.core import Brand

router = APIRouter()

async def _rb(brand_id, current_user, db):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Brand not accessible")

@router.get("/{brand_id}/landing-pages", response_model=list[LandingPageOut])
async def list_pages(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_pages(db, brand_id)

@router.post("/{brand_id}/landing-pages/recompute", response_model=RecomputeSummaryOut)
async def recompute(brand_id: uuid.UUID, current_user: OperatorUser, db: DBSession, _rl=Depends(recompute_rate_limit)):
    await _rb(brand_id, current_user, db); result = await svc.recompute_landing_pages(db, brand_id); await db.commit(); return RecomputeSummaryOut(**result)

@router.get("/{brand_id}/landing-page-variants", response_model=list[LPVariantOut])
async def list_variants(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_variants(db, brand_id)

@router.get("/{brand_id}/landing-page-quality", response_model=list[LPQualityOut])
async def list_quality(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    await _rb(brand_id, current_user, db); return await svc.list_quality(db, brand_id)

@router.post("/{brand_id}/landing-pages/{page_id}/publish")
async def publish_page(brand_id: uuid.UUID, page_id: uuid.UUID, current_user: OperatorUser, db: DBSession, publish_method: str = "manual", destination_url: str = ""):
    await _rb(brand_id, current_user, db)
    result = await svc.publish_page(db, page_id, publish_method, destination_url)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    await db.commit()
    return result


# ── Public Landing Page Routes (no auth) ─────────────────────────────


public_router = APIRouter()


@public_router.get("/lp/{page_id}")
async def get_public_landing_page_json(page_id: uuid.UUID, db: DBSession):
    """Public endpoint: return landing page data as JSON for frontend rendering."""
    from packages.db.models.landing_pages import LandingPage
    page = (await db.execute(
        select(LandingPage).where(
            LandingPage.id == page_id,
            LandingPage.is_active.is_(True),
            LandingPage.publish_status == "published",
        )
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Landing page not found or not published")
    brand = (await db.execute(select(Brand).where(Brand.id == page.brand_id))).scalar_one_or_none()
    return {
        "page_id": str(page.id),
        "brand_name": brand.name if brand else "",
        "brand_slug": brand.slug if brand else "",
        "page_type": page.page_type,
        "headline": page.headline,
        "subheadline": page.subheadline,
        "hook_angle": page.hook_angle,
        "proof_blocks": page.proof_blocks or [],
        "objection_blocks": page.objection_blocks or [],
        "cta_blocks": page.cta_blocks or [],
        "disclosure_blocks": page.disclosure_blocks or [],
        "media_blocks": page.media_blocks or [],
        "destination_url": page.destination_url,
        "tracking_params": page.tracking_params or {},
    }


@public_router.get("/lp/{page_id}/render", response_class=HTMLResponse)
async def render_public_landing_page(page_id: uuid.UUID, db: DBSession):
    """Public endpoint: server-render a landing page as full HTML.

    This allows any generated landing page to be publicly reachable without
    hardcoded Next.js pages — the system generates HTML dynamically from DB.
    """
    from packages.db.models.landing_pages import LandingPage
    page = (await db.execute(
        select(LandingPage).where(
            LandingPage.id == page_id,
            LandingPage.is_active.is_(True),
            LandingPage.publish_status == "published",
        )
    )).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Landing page not found or not published")

    brand = (await db.execute(select(Brand).where(Brand.id == page.brand_id))).scalar_one_or_none()
    brand_name = brand.name if brand else "Brand"
    brand_slug = brand.slug if brand else ""

    # Build CTA HTML
    cta_html = ""
    for cta in (page.cta_blocks or []):
        url = cta.get("url", page.destination_url or "#")
        text = cta.get("text", "Get Started")
        cta_html += f'<a href="{url}" class="cta-btn">{text}</a>\n'

    # Build proof blocks
    proof_html = ""
    for p in (page.proof_blocks or []):
        proof_html += f'<div class="proof-block"><p>{p.get("text", "")}</p></div>\n'

    # Build objection blocks
    objection_html = ""
    for obj in (page.objection_blocks or []):
        objection_html += f'<div class="objection-block"><h4>{obj.get("objection", "")}</h4><p>{obj.get("answer", "")}</p></div>\n'

    # Build disclosure
    disclosure_html = ""
    for d in (page.disclosure_blocks or []):
        disclosure_html += f'<p class="disclosure">{d.get("text", "")}</p>\n'

    # Lead capture form
    form_html = f"""
    <form class="lead-form" method="POST" action="/api/v1/leads/capture">
      <input type="hidden" name="brand_slug" value="{brand_slug}" />
      <input type="hidden" name="offer_slug" value="{page.page_type}" />
      <input name="name" placeholder="Your name" required />
      <input name="email" type="email" placeholder="Your email" required />
      <input name="company" placeholder="Company (optional)" />
      <textarea name="message" placeholder="Tell us about your needs..."></textarea>
      <button type="submit">Submit</button>
    </form>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{page.headline} — {brand_name}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; background: #f8f9fa; }}
    .hero {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 4rem 2rem; text-align: center; }}
    .hero h1 {{ font-size: 2.5rem; margin-bottom: 1rem; line-height: 1.2; }}
    .hero h2 {{ font-size: 1.2rem; font-weight: 400; opacity: 0.9; }}
    .content {{ max-width: 800px; margin: 0 auto; padding: 3rem 2rem; }}
    .cta-section {{ text-align: center; padding: 2rem; }}
    .cta-btn {{ display: inline-block; background: #667eea; color: #fff; padding: 16px 40px; border-radius: 8px; text-decoration: none; font-size: 1.1rem; font-weight: 600; margin: 0.5rem; }}
    .cta-btn:hover {{ background: #5a67d8; }}
    .proof-block {{ background: #fff; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .objection-block {{ margin: 1.5rem 0; padding: 1.5rem; border-left: 4px solid #667eea; background: #fff; }}
    .objection-block h4 {{ color: #667eea; margin-bottom: 0.5rem; }}
    .disclosure {{ font-size: 0.8rem; color: #666; margin-top: 2rem; text-align: center; }}
    .lead-form {{ max-width: 500px; margin: 2rem auto; padding: 2rem; background: #fff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
    .lead-form input, .lead-form textarea {{ width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }}
    .lead-form button {{ width: 100%; padding: 14px; background: #667eea; color: #fff; border: none; border-radius: 6px; font-size: 1.1rem; font-weight: 600; cursor: pointer; margin-top: 12px; }}
    .lead-form button:hover {{ background: #5a67d8; }}
  </style>
</head>
<body>
  <div class="hero">
    <h1>{page.headline}</h1>
    <h2>{page.subheadline or ''}</h2>
  </div>
  <div class="content">
    <div class="cta-section">{cta_html}</div>
    {proof_html}
    {objection_html}
    <h3 style="text-align:center;margin:2rem 0 1rem;">Get in Touch</h3>
    {form_html}
    {disclosure_html}
  </div>
  <script>
    document.querySelector('.lead-form').addEventListener('submit', async (e) => {{
      e.preventDefault();
      const fd = new FormData(e.target);
      const body = Object.fromEntries(fd.entries());
      try {{
        const res = await fetch('/api/v1/leads/capture', {{
          method: 'POST', headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(body),
        }});
        if (res.ok) {{
          e.target.innerHTML = '<p style="text-align:center;font-size:1.2rem;color:#667eea;padding:2rem;">Thank you! We will be in touch soon.</p>';
        }}
      }} catch(err) {{ console.error(err); }}
    }});
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)

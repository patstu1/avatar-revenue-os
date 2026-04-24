"""Lead Magnet Auto-Generation + Email List Pipeline.

Analyzes top-performing content -> generates lead magnets via AI -> creates real PDFs ->
builds & deploys landing pages -> manages email nurture sequences -> tracks subscriber revenue.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.landing_pages import LandingPage
from packages.db.models.publishing import PerformanceMetric
from packages.media.landing_page_builder import LandingPageBuilder
from packages.media.pdf_generator import PDFGenerator
from packages.media.storage import get_storage

logger = logging.getLogger(__name__)

LEAD_MAGNET_TYPES = [
    {
        "type": "checklist",
        "prompt_suffix": "Create a concise, actionable checklist (10-15 items) that someone can use immediately.",
    },
    {"type": "guide", "prompt_suffix": "Create a short guide (800-1200 words) with practical steps and examples."},
    {"type": "template", "prompt_suffix": "Create a fill-in-the-blank template that saves the reader hours of work."},
    {
        "type": "cheatsheet",
        "prompt_suffix": "Create a one-page cheatsheet with the most important facts, formulas, or steps.",
    },
    {"type": "swipe_file", "prompt_suffix": "Create a swipe file of 10-15 proven examples they can model."},
]

EMAIL_NURTURE_SEQUENCE = [
    {
        "day": 0,
        "type": "welcome",
        "subject_template": "Here's your {magnet_type}: {topic}",
        "purpose": "Deliver the lead magnet + set expectations",
    },
    {
        "day": 2,
        "type": "value",
        "subject_template": "The #1 mistake people make with {topic}",
        "purpose": "Deliver pure value, build trust",
    },
    {
        "day": 5,
        "type": "monetize",
        "subject_template": "The tool that changed everything for me ({topic})",
        "purpose": "Soft sell of affiliate offer",
    },
    {
        "day": 7,
        "type": "value",
        "subject_template": "Advanced {topic} strategy most people miss",
        "purpose": "More value, maintain engagement",
    },
    {
        "day": 10,
        "type": "monetize",
        "subject_template": "{topic}: Limited time offer inside",
        "purpose": "Direct offer with urgency",
    },
    {
        "day": 14,
        "type": "value",
        "subject_template": "Quick {topic} win you can do today",
        "purpose": "Re-engage, provide quick value",
    },
]


# ---------------------------------------------------------------------------
# Core pipeline: generate content -> PDF -> landing page -> deploy
# ---------------------------------------------------------------------------


async def generate_and_deploy_lead_magnet(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
    topic: str,
    target_audience: str,
) -> dict[str, Any]:
    """End-to-end lead magnet pipeline: AI content -> real PDF -> deployed landing page.

    Returns:
        {"pdf_url": str, "landing_page_url": str, "page_id": str, ...}
    """
    # ── 1. Load brand for context ──
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        return {"success": False, "error": "Brand not found"}

    brand_name = brand.name
    guidelines = brand.brand_guidelines or {}
    brand_colors = guidelines.get("colors")  # e.g. {"primary": "#1a1a2e", ...}
    logo_url = guidelines.get("logo_url")

    # ── 2. Pick magnet type ──
    magnet_config = LEAD_MAGNET_TYPES[hash(topic) % len(LEAD_MAGNET_TYPES)]
    magnet_type = magnet_config["type"]

    # ── 3. Generate content text via LLM ──
    sections = await _generate_content_via_llm(topic, target_audience, magnet_config, brand_name)
    if not sections:
        return {"success": False, "error": "AI content generation returned no content"}

    title = f"{magnet_type.replace('_', ' ').title()}: {topic}"

    # ── 4. Create real PDF ──
    pdf_gen = PDFGenerator()
    pdf_path = pdf_gen.generate_lead_magnet(
        title=title,
        sections=sections,
        brand_name=brand_name,
        brand_colors=brand_colors,
        logo_url=logo_url,
    )
    logger.info("PDF generated at %s for topic=%s", pdf_path, topic)

    # ── 5. Upload PDF to cloud storage ──
    storage = get_storage()
    pdf_key = storage.generate_key(prefix=f"lead_magnets/{brand_id}", extension="pdf")
    pdf_url = storage.upload_file(pdf_path, key=pdf_key, content_type="application/pdf")
    logger.info("PDF uploaded: %s", pdf_url)

    # ── 6. Build landing page HTML ──
    builder = LandingPageBuilder()
    headline = f"Free {magnet_type.replace('_', ' ').title()}: {topic}"
    body_copy = (
        f"Get instant access to this {magnet_type.replace('_', ' ')} "
        f"designed for {target_audience}. Download it now and start seeing results."
    )
    html = await builder.build_landing_page(
        title=title,
        headline=headline,
        body=body_copy,
        cta_text="Download Free Now",
        download_url=pdf_url,
        brand_colors=brand_colors,
    )

    # ── 7. Deploy landing page ──
    slug = f"{brand.slug}-{magnet_type}-{uuid.uuid4().hex[:6]}"
    deploy_result = await builder.deploy(html, project_name=slug)
    landing_page_url = deploy_result["url"]
    deployment_id = deploy_result["deployment_id"]
    logger.info("Landing page deployed: %s (id=%s)", landing_page_url, deployment_id)

    # ── 8. Store in database ──
    page = LandingPage(
        brand_id=brand_id,
        page_type="lead_magnet",
        headline=headline,
        subheadline=body_copy,
        hook_angle="value_first",
        destination_url=landing_page_url,
        cta_blocks=[{"type": "email_capture", "text": "Download Free Now", "magnet_type": magnet_type}],
        proof_blocks=[{"type": "content_proof", "text": f"Based on our most popular content about {topic}"}],
        tracking_params={
            "magnet_type": magnet_type,
            "topic": topic,
            "pdf_url": pdf_url,
            "deployment_id": deployment_id,
            "target_audience": target_audience,
        },
        status="published",
        publish_status="published",
        truth_label="published",
    )
    db.add(page)
    await db.flush()

    return {
        "success": True,
        "pdf_url": pdf_url,
        "landing_page_url": landing_page_url,
        "page_id": str(page.id),
        "deployment_id": deployment_id,
        "magnet_type": magnet_type,
        "topic": topic,
        "headline": headline,
    }


# ---------------------------------------------------------------------------
# LLM content generation
# ---------------------------------------------------------------------------


async def _generate_content_via_llm(
    topic: str,
    target_audience: str,
    magnet_config: dict,
    brand_name: str,
) -> list[dict[str, str]]:
    """Call the AI provider to generate structured lead-magnet content sections.

    Returns a list of {"heading": str, "body": str} dicts, or an empty list on failure.
    """
    from apps.api.services.content_generation_service import _get_ai_client
    from packages.scoring.tiered_routing_engine import route_to_provider

    provider_key = route_to_provider("text", "hero")
    client = await _get_ai_client(provider_key)

    magnet_type = magnet_config["type"]
    prompt = f"""Create a lead magnet about: {topic}
Target audience: {target_audience}
Brand: {brand_name}
Type: {magnet_type}
{magnet_config["prompt_suffix"]}

IMPORTANT: Structure your response as clearly separated sections. Use this exact format:

## Section Title Here
Section body content here...

## Next Section Title
Next section body...

Create 4-8 sections. Make it genuinely valuable — this is what convinces people to join the email list.
"""

    system = (
        "You are an expert content marketer creating high-value lead magnets that convert "
        "visitors to email subscribers. Write in a professional, actionable tone."
    )

    try:
        if hasattr(client, "generate"):
            result = await client.generate(prompt, max_tokens=3000, system=system)
        else:
            return []

        if not result.get("success"):
            logger.warning("AI generation failed: %s", result.get("error", "unknown"))
            return []

        raw_text = result["data"]["text"]
        return _parse_sections(raw_text)

    except Exception:
        logger.exception("LLM content generation failed for topic=%s", topic)
        return []


def _parse_sections(text: str) -> list[dict[str, str]]:
    """Parse markdown-ish text into a list of {"heading": str, "body": str} dicts."""
    sections: list[dict[str, str]] = []
    current_heading = ""
    current_body_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## "):
            # Flush previous section
            if current_heading:
                sections.append(
                    {
                        "heading": current_heading,
                        "body": "\n".join(current_body_lines).strip(),
                    }
                )
            current_heading = stripped[3:].strip()
            current_body_lines = []
        elif stripped.startswith("# ") and not current_heading:
            # Top-level heading — use as first section heading
            current_heading = stripped.lstrip("#").strip()
            current_body_lines = []
        else:
            current_body_lines.append(line)

    # Flush last section
    if current_heading:
        sections.append(
            {
                "heading": current_heading,
                "body": "\n".join(current_body_lines).strip(),
            }
        )

    # Fallback: if no markdown headings found, treat entire text as one section
    if not sections and text.strip():
        sections.append(
            {
                "heading": "Overview",
                "body": text.strip(),
            }
        )

    return sections


# ---------------------------------------------------------------------------
# Opportunity identification (unchanged logic)
# ---------------------------------------------------------------------------


async def identify_lead_magnet_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    """Analyze top-performing content to identify lead magnet topics."""
    top_content = list(
        (
            await db.execute(
                select(ContentItem)
                .join(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
                .where(
                    ContentItem.brand_id == brand_id,
                    ContentItem.status == "published",
                )
                .order_by(PerformanceMetric.impressions.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )

    opportunities = []
    for ci in top_content:
        existing = (
            await db.execute(
                select(LandingPage).where(
                    LandingPage.brand_id == brand_id,
                    LandingPage.page_type == "lead_magnet",
                    LandingPage.headline.contains(ci.title[:50]),
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue

        magnet_type = LEAD_MAGNET_TYPES[hash(ci.title) % len(LEAD_MAGNET_TYPES)]
        opportunities.append(
            {
                "content_item_id": str(ci.id),
                "topic": ci.title,
                "platform": ci.platform,
                "magnet_type": magnet_type["type"],
                "prompt_suffix": magnet_type["prompt_suffix"],
            }
        )

    return opportunities[:3]


async def generate_lead_magnet(db: AsyncSession, brand_id: uuid.UUID, topic: str, magnet_type: str) -> dict[str, Any]:
    """Generate lead magnet content via AI and create a landing page.

    This is the original lightweight path that creates a DB record without
    a real PDF or deployment.  For the full pipeline, use generate_and_deploy_lead_magnet().
    """
    from apps.api.services.content_generation_service import _get_ai_client
    from packages.scoring.tiered_routing_engine import route_to_provider

    provider_key = route_to_provider("text", "hero")
    client = await _get_ai_client(provider_key)

    magnet_config = next((m for m in LEAD_MAGNET_TYPES if m["type"] == magnet_type), LEAD_MAGNET_TYPES[0])
    prompt = f"""Create a lead magnet about: {topic}

Type: {magnet_type}
{magnet_config["prompt_suffix"]}

Format the output clearly with headers and bullet points.
Make it genuinely valuable — this is what convinces people to join the email list.
"""

    system = "You are an expert content marketer creating high-value lead magnets that convert visitors to email subscribers."
    result = (
        await client.generate(prompt, max_tokens=2048, system=system)
        if hasattr(client, "generate")
        else {"success": False}
    )

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "AI generation failed")}

    magnet_content = result["data"]["text"]

    (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()

    page = LandingPage(
        brand_id=brand_id,
        page_type="lead_magnet",
        headline=f"Free {magnet_type.replace('_', ' ').title()}: {topic}",
        subheadline=f"Get instant access to this {magnet_type.replace('_', ' ')} — delivered straight to your inbox.",
        hook_angle="value_first",
        cta_blocks=[{"type": "email_capture", "text": "Get Free Access", "magnet_type": magnet_type}],
        proof_blocks=[{"type": "content_proof", "text": f"Based on our most popular content about {topic}"}],
        tracking_params={"magnet_type": magnet_type, "topic": topic},
        status="draft",
        publish_status="unpublished",
        truth_label="recommendation_only",
    )
    db.add(page)
    await db.flush()

    return {
        "success": True,
        "page_id": str(page.id),
        "magnet_type": magnet_type,
        "topic": topic,
        "content_length": len(magnet_content),
        "headline": page.headline,
    }


# ---------------------------------------------------------------------------
# Email nurture helpers
# ---------------------------------------------------------------------------


def build_nurture_email(sequence_step: dict, topic: str, magnet_type: str, offer_name: str = "") -> dict[str, Any]:
    """Build a single nurture email from the sequence template."""
    subject = sequence_step["subject_template"].format(topic=topic, magnet_type=magnet_type)
    return {
        "day": sequence_step["day"],
        "type": sequence_step["type"],
        "subject": subject,
        "purpose": sequence_step["purpose"],
        "offer_name": offer_name if sequence_step["type"] == "monetize" else "",
    }


def build_full_nurture_sequence(topic: str, magnet_type: str, offer_name: str = "") -> list[dict[str, Any]]:
    """Build a complete email nurture sequence for a lead magnet."""
    return [build_nurture_email(step, topic, magnet_type, offer_name) for step in EMAIL_NURTURE_SEQUENCE]

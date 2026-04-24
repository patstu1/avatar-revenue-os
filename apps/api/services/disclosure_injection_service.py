"""Disclosure Auto-Injection Service — inject FTC/platform disclosure at generation + publish."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PLATFORM_DISCLOSURE_RULES: dict[str, dict[str, Any]] = {
    "youtube": {
        "affiliate_disclosure": "This video contains affiliate links. I may earn a commission at no extra cost to you.",
        "sponsored_disclosure": "This video is sponsored by {sponsor_name}.",
        "placement": "description_top",
        "visual_required": True,
    },
    "instagram": {
        "affiliate_disclosure": "#ad #affiliate",
        "sponsored_disclosure": "Paid partnership with {sponsor_name}",
        "placement": "caption_start",
        "visual_required": False,
        "use_branded_content_tag": True,
    },
    "tiktok": {
        "affiliate_disclosure": "#ad #affiliate",
        "sponsored_disclosure": "#ad Sponsored by {sponsor_name}",
        "placement": "caption_start",
        "visual_required": False,
    },
    "x": {
        "affiliate_disclosure": "#ad",
        "sponsored_disclosure": "#ad Sponsored",
        "placement": "text_end",
        "visual_required": False,
    },
    "linkedin": {
        "affiliate_disclosure": "Contains affiliate links. #ad",
        "sponsored_disclosure": "Sponsored content by {sponsor_name}. #ad",
        "placement": "text_end",
        "visual_required": False,
    },
    "default": {
        "affiliate_disclosure": "This content contains affiliate links. #ad",
        "sponsored_disclosure": "Sponsored content. #ad",
        "placement": "text_end",
        "visual_required": False,
    },
}


def get_disclosure_text(platform: str, disclosure_type: str, sponsor_name: str = "") -> str:
    rules = PLATFORM_DISCLOSURE_RULES.get(platform.lower(), PLATFORM_DISCLOSURE_RULES["default"])
    template = rules.get(f"{disclosure_type}_disclosure", rules.get("affiliate_disclosure", "#ad"))
    return template.format(sponsor_name=sponsor_name) if sponsor_name else template


def inject_disclosure_into_content(content_text: str, platform: str, disclosure_type: str, sponsor_name: str = "") -> dict[str, Any]:
    """Inject the correct disclosure text into content based on platform rules."""
    rules = PLATFORM_DISCLOSURE_RULES.get(platform.lower(), PLATFORM_DISCLOSURE_RULES["default"])
    disclosure = get_disclosure_text(platform, disclosure_type, sponsor_name)
    placement = rules.get("placement", "text_end")

    if disclosure.lower() in content_text.lower():
        return {"text": content_text, "disclosure_injected": False, "reason": "already_present"}

    if placement == "caption_start" or placement == "description_top":
        result = f"{disclosure}\n\n{content_text}"
    else:
        result = f"{content_text}\n\n{disclosure}"

    return {"text": result, "disclosure_injected": True, "disclosure_text": disclosure, "placement": placement}


async def check_and_inject_disclosure(db: AsyncSession, content_item_id: uuid.UUID) -> dict[str, Any]:
    """Check if content needs disclosure and inject it. Called before publish."""
    from packages.db.models.content import ContentItem

    ci = (await db.execute(select(ContentItem).where(ContentItem.id == content_item_id))).scalar_one_or_none()
    if not ci:
        return {"injected": False, "reason": "content_not_found"}

    needs_disclosure = False
    disclosure_type = "affiliate"
    sponsor_name = ""

    if ci.offer_id:
        needs_disclosure = True
        disclosure_type = "affiliate"
    if ci.monetization_method and "affiliate" in str(ci.monetization_method).lower():
        needs_disclosure = True
        disclosure_type = "affiliate"

    metadata = ci.audience_response_profile or {} if hasattr(ci, "audience_response_profile") else {}
    if metadata.get("has_affiliate_links") or metadata.get("affiliate_offer_id"):
        needs_disclosure = True
        disclosure_type = "affiliate"
    if metadata.get("is_sponsored") or metadata.get("sponsor_name"):
        needs_disclosure = True
        disclosure_type = "sponsored"
        sponsor_name = metadata.get("sponsor_name", "")

    if not needs_disclosure:
        return {"injected": False, "reason": "no_disclosure_required"}

    platform = getattr(ci.platform, "value", str(ci.platform)) if ci.platform else "default"
    text = ci.description or ci.title or ""
    result = inject_disclosure_into_content(text, platform, disclosure_type, sponsor_name)

    if result["disclosure_injected"]:
        ci.description = result["text"]
        await db.flush()

    return {"injected": result["disclosure_injected"], "platform": platform, "disclosure_type": disclosure_type, "disclosure_text": result.get("disclosure_text", "")}


def validate_disclosure_present(content_text: str, platform: str, disclosure_type: str) -> dict[str, Any]:
    """Validate that required disclosure is present in content text."""
    rules = PLATFORM_DISCLOSURE_RULES.get(platform.lower(), PLATFORM_DISCLOSURE_RULES["default"])
    disclosure = rules.get(f"{disclosure_type}_disclosure", "")

    keywords = ["#ad", "affiliate", "sponsored", "paid partnership"]
    has_any = any(kw.lower() in content_text.lower() for kw in keywords)

    if has_any:
        return {"valid": True, "disclosure_found": True}
    return {"valid": False, "disclosure_found": False, "required_text": disclosure, "platform": platform}

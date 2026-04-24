"""Attribution URL Builder — generates tracked URLs at publish time.

Two strategies:
1. UTM tagging: Appends utm_source/medium/campaign/content params to offer URL
2. Server-side routing: Encodes destination in base64 for server redirect (future)

Used by the publishing pipeline to inject monetization context into captions.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.offers import Offer
from packages.db.models.revenue_assignment import RevenueAssignment

logger = structlog.get_logger()


def build_tracking_url(
    offer_url: str,
    *,
    brand_slug: str = "",
    platform: str = "",
    content_id: str = "",
    account_id: str = "",
    offer_id: str = "",
    extra_params: dict | None = None,
) -> str:
    """Build a UTM-tagged tracking URL from an offer URL.

    Returns the original URL with UTM params appended. Does not modify
    the URL if it's empty or invalid.
    """
    if not offer_url:
        return ""

    parsed = urlparse(offer_url)
    existing_params = parse_qs(parsed.query, keep_blank_values=True)

    # Build UTM params
    utm = {
        "utm_source": platform or "organic",
        "utm_medium": "social",
        "utm_campaign": brand_slug or "brand",
        "utm_content": content_id[:8] if content_id else "",
    }

    # Request ID for attribution
    rid = hashlib.md5(f"{content_id}:{account_id}:{offer_id}:{platform}".encode()).hexdigest()[:12]
    utm["rid"] = rid

    if extra_params:
        utm.update(extra_params)

    # Merge with existing params (don't overwrite existing UTM)
    for k, v in utm.items():
        if k not in existing_params and v:
            existing_params[k] = [v]

    new_query = urlencode({k: v[0] if isinstance(v, list) else v for k, v in existing_params.items()})
    return urlunparse(parsed._replace(query=new_query))


def build_caption_with_cta(
    base_caption: str,
    offer: Any | None = None,
    tracking_url: str = "",
    hashtags: list[str] | None = None,
) -> str:
    """Build a publish-ready caption with CTA and tracking link.

    Combines the content caption with an offer CTA and hashtags.
    """
    parts = [base_caption.strip()]

    if offer and tracking_url:
        cta = getattr(offer, "cta_template", None)
        if cta and "{url}" in cta:
            parts.append(cta.replace("{url}", tracking_url))
        else:
            parts.append(f"\n{tracking_url}")

    if hashtags:
        tag_str = " ".join(f"#{t.strip('#')}" for t in hashtags[:10])
        parts.append(tag_str)

    return "\n\n".join(parts)


async def select_offer_for_publish(
    db: AsyncSession,
    brand_id: uuid.UUID,
    platform: str = "",
    account_id: uuid.UUID | None = None,
) -> Offer | None:
    """Select an offer for publish-time monetization using weighted rotation.

    1. Check RevenueAssignments for specific account/platform matches
    2. Fall back to all active offers for the brand
    3. Use weighted random selection (rotation_weight field)
    """
    # First try: specific revenue assignments
    assignment_query = select(RevenueAssignment).where(
        RevenueAssignment.brand_id == brand_id,
        RevenueAssignment.is_active.is_(True),
    )
    if account_id:
        assignment_query = assignment_query.where(
            (RevenueAssignment.creator_account_id == account_id) | (RevenueAssignment.creator_account_id.is_(None))
        )
    if platform:
        assignment_query = assignment_query.where(
            (RevenueAssignment.platform == platform) | (RevenueAssignment.platform.is_(None))
        )
    assignment_query = assignment_query.order_by(RevenueAssignment.priority.desc())

    assignments = list((await db.execute(assignment_query)).scalars().all())

    if assignments:
        # Load offers from assignments
        offer_ids = [a.offer_id for a in assignments]
        offers_result = await db.execute(select(Offer).where(Offer.id.in_(offer_ids), Offer.is_active.is_(True)))
        offers = list(offers_result.scalars().all())

        if offers:
            # Build weight map (assignment weight_override takes precedence)
            assignment_map = {a.offer_id: a for a in assignments}
            weights = []
            for o in offers:
                a = assignment_map.get(o.id)
                w = a.weight_override if (a and a.weight_override is not None) else o.rotation_weight
                weights.append(max(w, 0.01))  # Ensure positive weight

            selected = random.choices(offers, weights=weights, k=1)[0]

            logger.info(
                "offer_selected_from_assignment",
                offer_id=str(selected.id),
                offer_name=selected.name,
                brand_id=str(brand_id),
                platform=platform,
            )
            return selected

    # Fallback: weighted selection from all active brand offers
    all_offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )

    if not all_offers:
        return None

    weights = [max(o.rotation_weight, 0.01) for o in all_offers]
    selected = random.choices(all_offers, weights=weights, k=1)[0]

    logger.info(
        "offer_selected_fallback",
        offer_id=str(selected.id),
        offer_name=selected.name,
        brand_id=str(brand_id),
        platform=platform,
    )
    return selected


async def build_publish_monetization_context(
    db: AsyncSession,
    content_item: Any,
    creator_account: Any,
    brand_slug: str = "",
) -> dict:
    """Build the full monetization context for a PublishJob.

    Returns a dict to be stored in PublishJob.publish_config containing:
    - offer_id, offer_name, offer_url
    - tracking_url (UTM-tagged)
    - caption_with_cta
    - attribution_rid
    """
    brand_id = getattr(content_item, "brand_id", None)
    platform = str(getattr(creator_account, "platform", "") or "").lower()
    if hasattr(platform, "value"):
        platform = platform.value

    offer = await select_offer_for_publish(
        db,
        brand_id,
        platform=platform,
        account_id=getattr(creator_account, "id", None),
    )

    if not offer:
        return {"monetization": "none", "reason": "no_active_offers"}

    tracking_url = build_tracking_url(
        offer.offer_url or "",
        brand_slug=brand_slug,
        platform=platform,
        content_id=str(getattr(content_item, "id", "")),
        account_id=str(getattr(creator_account, "id", "")),
        offer_id=str(offer.id),
    )

    # Build caption
    base_caption = getattr(content_item, "description", "") or getattr(content_item, "title", "") or ""
    tags = getattr(content_item, "hashtags", None) or getattr(content_item, "tags", None) or []
    caption = build_caption_with_cta(base_caption, offer=offer, tracking_url=tracking_url, hashtags=tags)

    rid = hashlib.md5(f"{content_item.id}:{creator_account.id}:{offer.id}:{platform}".encode()).hexdigest()[:12]

    return {
        "monetization": "active",
        "offer_id": str(offer.id),
        "offer_name": offer.name,
        "offer_url": offer.offer_url,
        "tracking_url": tracking_url,
        "caption_with_cta": caption,
        "attribution_rid": rid,
        "monetization_method": str(offer.monetization_method.value) if offer.monetization_method else None,
        "payout_amount": offer.payout_amount,
    }

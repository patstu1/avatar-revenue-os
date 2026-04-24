"""Affiliate Link Injector — generate real tracked links and inject into content.

This module is the bridge between content generation and affiliate monetization.
It takes content text + a list of affiliate placements, generates real tracked
links via the appropriate network client, shortens them, injects them into the
content at the right positions, adds FTC/platform disclosure, and stores the
link-to-offer mapping in the database for attribution tracking.

Usage:
    from apps.api.services.affiliate_link_injector import inject_affiliate_links

    result = await inject_affiliate_links(
        content_text="Check out this camera...",
        affiliate_placements=[
            {
                "offer_id": "uuid-of-af-offer",
                "network": "amazon",
                "asin": "B09V3KXJPB",
                "anchor_text": "this camera",
                "position": "inline",
            },
        ],
        platform="youtube",
        brand_id=brand_id,
        org_id=org_id,
        db=db,
    )
    # result["text"] -> modified content with real links + disclosure
    # result["links_injected"] -> list of link records created
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ── Network → Link Generator Dispatch ────────────────────────────────

def _generate_tracked_url(placement: dict[str, Any]) -> dict[str, Any]:
    """Generate a tracked affiliate URL based on the placement's network.

    Dispatches to the appropriate network client's link generation method.
    Returns dict with success, tracked_url, network.
    """
    network = placement.get("network", "").lower()

    if network == "amazon":
        from packages.clients.affiliate_network_clients import AmazonAssociatesLinkGenerator
        gen = AmazonAssociatesLinkGenerator(associate_tag=placement.get("associate_tag", ""))
        asin = placement.get("asin", "")
        if not asin:
            return {"success": False, "error": "asin required for amazon links"}
        return gen.generate_product_link(
            asin,
            sub_tag=placement.get("sub_tag", placement.get("tracking_id", "")),
        )

    elif network == "impact":
        from packages.clients.affiliate_network_clients import ImpactClient
        client = ImpactClient()
        campaign_id = placement.get("campaign_id", "")
        destination_url = placement.get("destination_url", "")
        if not campaign_id or not destination_url:
            return {"success": False, "error": "campaign_id and destination_url required for impact links"}
        # Use the static builder (sync) for inline injection.
        # The async create_tracking_link can be used in batch pre-generation.
        url = client.build_tracking_link(
            campaign_id,
            placement.get("affiliate_id", client.account_sid),
            destination_url,
        )
        return {"success": True, "tracked_url": url, "network": "impact", "method": "constructed"}

    elif network == "shareasale":
        from packages.clients.affiliate_network_clients import ShareASaleClient
        client = ShareASaleClient()
        destination_url = placement.get("destination_url", "")
        if not destination_url:
            return {"success": False, "error": "destination_url required for shareasale links"}
        return client.create_custom_link(
            destination_url,
            affiliate_id=placement.get("affiliate_id", ""),
            merchant_id=placement.get("merchant_id", ""),
            tracking_id=placement.get("tracking_id", ""),
        )

    elif network == "cj":
        from packages.clients.affiliate_network_clients import CJClient
        client = CJClient()
        advertiser_id = placement.get("advertiser_id", "")
        destination_url = placement.get("destination_url", "")
        if not advertiser_id or not destination_url:
            return {"success": False, "error": "advertiser_id and destination_url required for cj links"}
        return client.create_link(
            advertiser_id,
            destination_url,
            sid=placement.get("tracking_id", ""),
        )

    elif network == "clickbank":
        from packages.clients.affiliate_program_clients import ClickBankClient
        vendor = placement.get("vendor", "")
        affiliate_id = placement.get("affiliate_id", "")
        if not vendor or not affiliate_id:
            return {"success": False, "error": "vendor and affiliate_id required for clickbank links"}
        url = ClickBankClient.build_hop_link(
            vendor, affiliate_id, tracking_id=placement.get("tracking_id", ""),
        )
        return {"success": True, "tracked_url": url, "network": "clickbank"}

    elif network == "etsy":
        from packages.clients.affiliate_program_clients import EtsyAffiliateClient
        listing_url = placement.get("destination_url", placement.get("listing_url", ""))
        affiliate_id = placement.get("affiliate_id", "")
        if not listing_url or not affiliate_id:
            return {"success": False, "error": "destination_url and affiliate_id required for etsy links"}
        url = EtsyAffiliateClient.build_affiliate_link(listing_url, affiliate_id)
        return {"success": True, "tracked_url": url, "network": "etsy"}

    elif placement.get("destination_url"):
        # Generic: if we have a raw destination URL but unknown network, return it directly
        return {"success": True, "tracked_url": placement["destination_url"], "network": network or "direct"}

    return {"success": False, "error": f"unsupported network: {network}"}


async def _shorten_url(long_url: str, title: str = "") -> dict[str, Any]:
    """Shorten a URL using the configured link shortener backend."""
    from packages.clients.link_shortener import LinkShortener
    shortener = LinkShortener()
    return await shortener.shorten(long_url, title=title)


# ── Content Injection ────────────────────────────────────────────────

def _inject_link_into_text(
    text: str,
    anchor_text: str,
    url: str,
    position: str = "inline",
    platform: str = "",
) -> str:
    """Inject a link into content text.

    Position modes:
        - inline: Replace the first occurrence of anchor_text with a linked version
        - append: Add the link at the end of the text
        - description: Add as a numbered link in description area
        - bio: Format for bio link

    Platform affects formatting:
        - youtube: plain URLs in description (no markdown)
        - instagram/tiktok: link in bio reference
        - x/linkedin: inline URLs
        - default: markdown-style links
    """
    platform = platform.lower() if platform else ""

    if position == "inline":
        if platform in ("youtube",):
            # YouTube descriptions: replace anchor text with "anchor_text (URL)"
            if anchor_text and anchor_text in text:
                text = text.replace(anchor_text, f"{anchor_text} ({url})", 1)
            else:
                text += f"\n{url}"
        elif platform in ("instagram", "tiktok"):
            # IG/TikTok: can't embed links, add "Link in bio" reference
            if anchor_text and anchor_text in text:
                text = text.replace(anchor_text, f"{anchor_text} (link in bio)", 1)
            text += f"\n\n{url}"
        elif platform in ("x",):
            # Twitter/X: inline URL replaces anchor text
            if anchor_text and anchor_text in text:
                text = text.replace(anchor_text, f"{anchor_text} {url}", 1)
            else:
                text += f" {url}"
        else:
            # Default (LinkedIn, blog, newsletter): markdown link
            if anchor_text and anchor_text in text:
                text = text.replace(anchor_text, f"[{anchor_text}]({url})", 1)
            else:
                text += f"\n\n{url}"

    elif position == "append":
        text += f"\n\n{url}"

    elif position == "description":
        # Numbered link list (YouTube description style)
        # Count existing numbered links
        existing = len(re.findall(r"^\d+\.\s", text, re.MULTILINE))
        link_num = existing + 1
        label = anchor_text or "Link"
        text += f"\n{link_num}. {label}: {url}"

    elif position == "bio":
        text += f"\n\nLink: {url}"

    return text


# ── Main Entry Point ─────────────────────────────────────────────────

async def inject_affiliate_links(
    content_text: str,
    affiliate_placements: list[dict[str, Any]],
    *,
    platform: str = "",
    brand_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    content_item_id: uuid.UUID | None = None,
    db: AsyncSession | None = None,
    add_disclosure: bool = True,
    shorten_links: bool = True,
) -> dict[str, Any]:
    """Generate real tracked affiliate links, shorten, inject into content, and persist.

    Args:
        content_text: The raw content text to inject links into.
        affiliate_placements: List of placement dicts, each with:
            - offer_id: UUID of the AffiliateOffer (optional, for DB linkage)
            - network: amazon | impact | shareasale | cj | clickbank | etsy | ...
            - anchor_text: Text in content to link (for inline placement)
            - position: inline | append | description | bio
            - ... network-specific fields (asin, campaign_id, destination_url, etc.)
        platform: Target platform (youtube, instagram, tiktok, x, linkedin, etc.)
        brand_id: Brand UUID for DB records.
        org_id: Organization UUID.
        content_item_id: Content item UUID (for linking AffiliateLink to content).
        db: Database session (required for persistence).
        add_disclosure: Whether to inject FTC disclosure text.
        shorten_links: Whether to shorten generated links.

    Returns:
        dict with:
            - text: Modified content with links + disclosure
            - links_injected: List of link details
            - disclosure_added: Whether disclosure was injected
            - errors: List of any per-placement errors
    """
    modified_text = content_text
    links_injected: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for placement in affiliate_placements:
        # Step 1: Generate the real tracked URL
        link_result = _generate_tracked_url(placement)
        if not link_result.get("success"):
            errors.append({
                "placement": placement.get("anchor_text", placement.get("network", "unknown")),
                "error": link_result.get("error", "link_generation_failed"),
            })
            continue

        tracked_url = link_result["tracked_url"]
        final_url = tracked_url
        short_url = None
        shortener_link_id = ""

        # Step 2: Shorten
        if shorten_links:
            shorten_result = await _shorten_url(
                tracked_url,
                title=placement.get("anchor_text", placement.get("product_name", "")),
            )
            if shorten_result.get("success") and shorten_result.get("short_url"):
                final_url = shorten_result["short_url"]
                short_url = shorten_result["short_url"]
                shortener_link_id = shorten_result.get("link_id", "")

        # Step 3: Inject into content
        anchor_text = placement.get("anchor_text", "")
        position = placement.get("position", "inline")
        modified_text = _inject_link_into_text(
            modified_text, anchor_text, final_url, position=position, platform=platform,
        )

        link_info = {
            "network": link_result.get("network", placement.get("network", "")),
            "tracked_url": tracked_url,
            "short_url": short_url,
            "final_url": final_url,
            "anchor_text": anchor_text,
            "position": position,
            "offer_id": placement.get("offer_id"),
            "shortener_link_id": shortener_link_id,
        }
        links_injected.append(link_info)

        # Step 4: Persist to DB (link → offer mapping for attribution)
        if db and brand_id:
            try:
                from packages.db.models.affiliate_intel import AffiliateLink

                offer_uuid = None
                if placement.get("offer_id"):
                    try:
                        offer_uuid = uuid.UUID(str(placement["offer_id"]))
                    except (ValueError, AttributeError):
                        pass

                if offer_uuid:
                    af_link = AffiliateLink(
                        brand_id=brand_id,
                        offer_id=offer_uuid,
                        content_item_id=content_item_id,
                        platform=platform or None,
                        full_url=tracked_url,
                        short_url=short_url,
                        utm_params=placement.get("utm_params", {}),
                        disclosure_applied=add_disclosure,
                        click_count=0,
                        conversion_count=0,
                    )
                    db.add(af_link)
                    await db.flush()
                    link_info["af_link_id"] = str(af_link.id)
            except Exception as e:
                logger.warning(
                    "affiliate_link_injector.persist_failed",
                    error=str(e),
                    offer_id=placement.get("offer_id"),
                )
                errors.append({
                    "placement": anchor_text,
                    "error": f"db_persist_failed: {e}",
                })

    # Step 5: Add FTC disclosure
    disclosure_added = False
    if add_disclosure and links_injected:
        from apps.api.services.disclosure_injection_service import inject_disclosure_into_content
        disclosure_result = inject_disclosure_into_content(
            modified_text, platform or "default", "affiliate",
        )
        modified_text = disclosure_result["text"]
        disclosure_added = disclosure_result.get("disclosure_injected", False)

    # Step 6: Emit event for tracking
    if db and brand_id and links_injected:
        try:
            from apps.api.services.event_bus import emit_event
            await emit_event(
                db,
                domain="affiliate",
                event_type="affiliate.links_injected",
                summary=f"Injected {len(links_injected)} affiliate link(s) into content for {platform or 'unknown'} platform",
                brand_id=brand_id,
                org_id=org_id,
                entity_type="content_item",
                entity_id=content_item_id,
                details={
                    "links_count": len(links_injected),
                    "networks": list({li["network"] for li in links_injected}),
                    "platform": platform,
                    "disclosure_added": disclosure_added,
                    "errors_count": len(errors),
                },
            )
        except Exception as e:
            logger.warning("affiliate_link_injector.event_emit_failed", error=str(e))

    return {
        "text": modified_text,
        "links_injected": links_injected,
        "disclosure_added": disclosure_added,
        "errors": errors,
        "original_length": len(content_text),
        "modified_length": len(modified_text),
    }


# ── Batch Pre-Generation (async network calls) ──────────────────────

async def pregenerate_tracking_links(
    placements: list[dict[str, Any]],
    *,
    brand_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Pre-generate tracked links via async API calls for placements that support it.

    Use this before inject_affiliate_links when you want to use the Impact API
    or other async link creation APIs instead of URL construction fallbacks.

    Updates each placement dict in-place with 'pregenerated_url' if successful.
    """
    results = []
    for placement in placements:
        network = placement.get("network", "").lower()

        if network == "impact":
            from packages.clients.affiliate_network_clients import ImpactClient
            client = ImpactClient()
            result = await client.create_tracking_link(
                placement.get("campaign_id", ""),
                placement.get("destination_url", ""),
                sub_id_1=placement.get("sub_id_1", str(brand_id) if brand_id else ""),
                sub_id_2=placement.get("tracking_id", ""),
            )
            if result.get("success"):
                placement["pregenerated_url"] = result["tracked_url"]
            results.append(result)
        else:
            # Sync link generation handled by inject_affiliate_links
            results.append({"success": True, "note": f"{network} uses sync generation"})

    return results

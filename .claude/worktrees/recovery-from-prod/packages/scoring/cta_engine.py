"""Dynamic CTA Rotation Engine — platform-specific CTA templates with performance tracking."""
from __future__ import annotations
import random
from typing import Any

CTA_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "youtube": [
        {"id": "yt_link_desc", "text": "Check the link in the description for more", "style": "soft"},
        {"id": "yt_subscribe", "text": "Subscribe and hit the bell — new content daily", "style": "growth"},
        {"id": "yt_comment", "text": "Drop your biggest question in the comments", "style": "engagement"},
        {"id": "yt_freebie", "text": "Grab the free guide — link in description", "style": "lead_capture"},
        {"id": "yt_urgency", "text": "This won't last — check the link before it's gone", "style": "urgency"},
        {"id": "yt_social_proof", "text": "Over 10,000 people have already grabbed this — link below", "style": "social_proof"},
    ],
    "tiktok": [
        {"id": "tt_bio", "text": "Link in bio", "style": "soft"},
        {"id": "tt_follow", "text": "Follow for part 2", "style": "growth"},
        {"id": "tt_save", "text": "Save this before it gets buried", "style": "urgency"},
        {"id": "tt_comment", "text": "Comment 'SEND' and I'll DM you the link", "style": "engagement"},
        {"id": "tt_stitch", "text": "Stitch this with your results", "style": "engagement"},
        {"id": "tt_freebie", "text": "Free resource in my bio — go grab it", "style": "lead_capture"},
    ],
    "instagram": [
        {"id": "ig_bio", "text": "Link in bio for the full breakdown", "style": "soft"},
        {"id": "ig_save", "text": "Save this post — you'll need it later", "style": "engagement"},
        {"id": "ig_dm", "text": "DM me 'START' and I'll send you the guide", "style": "lead_capture"},
        {"id": "ig_share", "text": "Share this with someone who needs to hear it", "style": "engagement"},
        {"id": "ig_comment", "text": "Which tip resonated most? Comment below", "style": "engagement"},
        {"id": "ig_freebie", "text": "I made a free cheatsheet — link in bio", "style": "lead_capture"},
    ],
    "x": [
        {"id": "x_repost", "text": "Repost if this helped", "style": "engagement"},
        {"id": "x_follow", "text": "Follow me for daily insights like this", "style": "growth"},
        {"id": "x_thread", "text": "Want the full breakdown? Bookmark this thread", "style": "engagement"},
        {"id": "x_link", "text": "Full guide here:", "style": "soft"},
        {"id": "x_reply", "text": "Reply with your biggest challenge and I'll help", "style": "engagement"},
    ],
    "linkedin": [
        {"id": "li_follow", "text": "Follow for more insights like this", "style": "growth"},
        {"id": "li_comment", "text": "What's your experience with this? Share below", "style": "engagement"},
        {"id": "li_repost", "text": "Repost to help your network", "style": "engagement"},
        {"id": "li_newsletter", "text": "Subscribe to my newsletter for the deep dive — link in comments", "style": "lead_capture"},
        {"id": "li_dm", "text": "DM me if you want to discuss this further", "style": "engagement"},
    ],
}


def select_cta(
    platform: str,
    style_preference: str = "any",
    performance_history: dict[str, float] | None = None,
    has_offer: bool = False,
    has_lead_magnet: bool = False,
) -> dict[str, Any]:
    """Select the best CTA for a post based on platform, style, and performance data."""
    templates = CTA_LIBRARY.get(platform.lower(), CTA_LIBRARY.get("youtube", []))
    if not templates:
        return {"id": "default", "text": "Link in bio", "style": "soft"}

    if has_lead_magnet:
        lead_ctas = [t for t in templates if t["style"] == "lead_capture"]
        if lead_ctas:
            templates = lead_ctas
    elif has_offer:
        monetized = [t for t in templates if t["style"] in ("soft", "urgency", "social_proof")]
        if monetized:
            templates = monetized
    elif style_preference != "any":
        filtered = [t for t in templates if t["style"] == style_preference]
        if filtered:
            templates = filtered

    if performance_history:
        scored = []
        for t in templates:
            ctr = performance_history.get(t["id"], 0.5)
            scored.append((t, ctr))
        scored.sort(key=lambda x: x[1], reverse=True)
        top_3 = scored[:3]
        return random.choice(top_3)[0]

    return random.choice(templates)


def get_all_cta_ids(platform: str) -> list[str]:
    """Get all CTA template IDs for a platform for tracking."""
    return [t["id"] for t in CTA_LIBRARY.get(platform.lower(), [])]

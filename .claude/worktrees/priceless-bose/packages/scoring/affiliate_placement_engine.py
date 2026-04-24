"""Affiliate Placement Engine — test and optimize where affiliate links are placed.

Placements: link-in-bio, in-caption, pinned-comment, description-top, end-card
Each placement type is A/B tested and the system learns which converts best per platform.
"""
from __future__ import annotations
import random
from typing import Any

PLACEMENT_TYPES = [
    {"id": "link_in_bio", "label": "Link in Bio", "platforms": ["tiktok", "instagram"], "injection_point": "cta"},
    {"id": "in_caption", "label": "In Caption/Description", "platforms": ["youtube", "instagram", "tiktok", "x", "linkedin"], "injection_point": "body"},
    {"id": "pinned_comment", "label": "Pinned Comment", "platforms": ["youtube", "tiktok", "instagram"], "injection_point": "post_publish"},
    {"id": "description_top", "label": "Top of Description", "platforms": ["youtube"], "injection_point": "body_top"},
    {"id": "end_card", "label": "End Card / CTA Screen", "platforms": ["youtube"], "injection_point": "cta"},
    {"id": "story_swipe_up", "label": "Swipe Up / Link Sticker", "platforms": ["instagram", "tiktok"], "injection_point": "media_overlay"},
]

DEFAULT_PLATFORM_PLACEMENTS: dict[str, list[str]] = {
    "youtube": ["description_top", "in_caption", "pinned_comment", "end_card"],
    "tiktok": ["link_in_bio", "in_caption", "pinned_comment"],
    "instagram": ["link_in_bio", "in_caption", "story_swipe_up"],
    "x": ["in_caption"],
    "linkedin": ["in_caption"],
}


def select_placement(
    platform: str,
    performance_history: dict[str, float] | None = None,
    exploration_rate: float = 0.2,
) -> dict[str, Any]:
    """Select the best affiliate link placement for a platform.

    Uses epsilon-greedy: explore new placements 20% of the time,
    exploit the best-performing placement 80% of the time.
    """
    available = DEFAULT_PLATFORM_PLACEMENTS.get(platform.lower(), ["in_caption"])
    if not available:
        return {"placement_id": "in_caption", "label": "In Caption", "injection_point": "body"}

    if performance_history and random.random() > exploration_rate:
        scored = [(pid, performance_history.get(pid, 0.5)) for pid in available]
        scored.sort(key=lambda x: x[1], reverse=True)
        best_id = scored[0][0]
    else:
        best_id = random.choice(available)

    placement = next((p for p in PLACEMENT_TYPES if p["id"] == best_id), PLACEMENT_TYPES[1])
    return {
        "placement_id": placement["id"],
        "label": placement["label"],
        "injection_point": placement["injection_point"],
    }


def build_placement_instruction(placement: dict[str, Any], affiliate_link: str, product_name: str) -> str:
    """Build a prompt instruction telling the AI where to place the affiliate link."""
    pid = placement.get("placement_id", "in_caption")

    if pid == "link_in_bio":
        return f"CTA: Tell viewers to check the link in your bio for {product_name}. Do NOT put the URL in the caption."
    elif pid == "in_caption":
        return f"Include this link naturally in the caption/description: {affiliate_link} — recommend {product_name} as a genuine suggestion."
    elif pid == "pinned_comment":
        return f"Do NOT include the link in the main caption. Mention '{product_name}' and say 'link in the comments'. The link will be added as a pinned comment."
    elif pid == "description_top":
        return f"Put this link at the very top of the description: {affiliate_link} — '{product_name} (link above)' in the video CTA."
    elif pid == "end_card":
        return f"Mention {product_name} in the final CTA. Say 'click the card on screen' or 'link in the description'."
    elif pid == "story_swipe_up":
        return f"Tell viewers to swipe up or tap the link sticker for {product_name}. Keep it urgent."
    return f"Recommend {product_name} naturally. Link: {affiliate_link}"


def get_placement_for_experiment(platform: str) -> list[dict[str, Any]]:
    """Generate placement variants for A/B testing."""
    available = DEFAULT_PLATFORM_PLACEMENTS.get(platform.lower(), ["in_caption"])
    return [
        {**next((p for p in PLACEMENT_TYPES if p["id"] == pid), {}), "variant_name": pid}
        for pid in available
    ]

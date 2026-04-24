"""Voice Profile Engine — generate unique voice profiles per account.

Each account gets a persistent, differentiated voice so no two accounts sound alike.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

WRITING_STYLES = [
    "conversational_direct",
    "storyteller_narrative",
    "data_driven_analytical",
    "provocative_contrarian",
    "empathetic_supportive",
    "high_energy_motivational",
    "dry_witty_humor",
    "academic_authoritative",
    "street_smart_practical",
    "minimalist_punchy",
]

VOCABULARY_LEVELS = ["casual", "accessible", "professional", "technical", "elite"]

EMOJI_USAGE = ["none", "minimal", "moderate", "heavy"]

HOOK_STYLES = [
    "bold_claim",
    "shocking_stat",
    "question_hook",
    "story_open",
    "pain_point",
    "curiosity_gap",
    "contrarian_take",
    "personal_confession",
]

SIGNATURE_PHRASES_POOL = [
    "Here's the thing",
    "Let me break this down",
    "Nobody talks about this",
    "The truth is",
    "Real talk",
    "Pay attention to this",
    "Most people get this wrong",
    "I tested this myself",
    "The data shows",
    "Stop scrolling — this matters",
    "Think about this",
    "Hot take",
    "Unpopular opinion",
    "Game changer",
    "Listen carefully",
    "Quick reality check",
    "This changed everything for me",
    "Don't sleep on this",
    "Mark my words",
    "You need to hear this",
]

CTA_STYLES = [
    "soft_suggest",
    "direct_command",
    "curiosity_driven",
    "urgency_based",
    "social_proof",
    "benefit_focused",
    "question_close",
]

PARAGRAPH_STYLES = [
    "one_liner_punchy",
    "short_paragraphs",
    "long_flowing",
    "bullet_heavy",
    "mixed",
]


def generate_voice_profile(account_id: str, platform: str, niche: str) -> dict[str, Any]:
    """Generate a unique, deterministic voice profile for an account.

    Uses account_id as seed for reproducibility — same account always gets same voice.
    """
    seed = int(hashlib.sha256(f"{account_id}:{platform}:{niche}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    style = rng.choice(WRITING_STYLES)
    vocab = rng.choice(VOCABULARY_LEVELS)
    emoji = rng.choice(EMOJI_USAGE)
    hook = rng.choice(HOOK_STYLES)
    cta = rng.choice(CTA_STYLES)
    paragraph = rng.choice(PARAGRAPH_STYLES)

    phrases = rng.sample(SIGNATURE_PHRASES_POOL, min(4, len(SIGNATURE_PHRASES_POOL)))

    platform_adjustments = {
        "tiktok": {"vocab": "casual", "emoji": "moderate", "paragraph": "one_liner_punchy"},
        "instagram": {"emoji": "moderate", "paragraph": "short_paragraphs"},
        "linkedin": {"vocab": "professional", "emoji": "none", "paragraph": "short_paragraphs"},
        "x": {"paragraph": "one_liner_punchy"},
        "youtube": {"paragraph": "mixed"},
    }
    adj = platform_adjustments.get(platform, {})
    vocab = adj.get("vocab", vocab)
    emoji = adj.get("emoji", emoji)
    paragraph = adj.get("paragraph", paragraph)

    return {
        "style": style,
        "vocabulary_level": vocab,
        "emoji_usage": emoji,
        "preferred_hook_style": hook,
        "cta_style": cta,
        "paragraph_style": paragraph,
        "signature_phrases": phrases,
        "tone_keywords": _tone_keywords_for_style(style),
        "avoid_keywords": _avoid_keywords_for_style(style),
        "platform": platform,
        "niche": niche,
    }


def _tone_keywords_for_style(style: str) -> list[str]:
    mapping = {
        "conversational_direct": ["casual", "clear", "friendly", "approachable"],
        "storyteller_narrative": ["vivid", "immersive", "personal", "flowing"],
        "data_driven_analytical": ["precise", "factual", "structured", "evidence-based"],
        "provocative_contrarian": ["bold", "challenging", "edgy", "thought-provoking"],
        "empathetic_supportive": ["warm", "understanding", "encouraging", "gentle"],
        "high_energy_motivational": ["pumped", "urgent", "inspiring", "dynamic"],
        "dry_witty_humor": ["clever", "understated", "ironic", "sharp"],
        "academic_authoritative": ["thorough", "authoritative", "formal", "researched"],
        "street_smart_practical": ["real", "no-BS", "hands-on", "actionable"],
        "minimalist_punchy": ["tight", "impactful", "spare", "powerful"],
    }
    return mapping.get(style, ["clear", "engaging"])


def _avoid_keywords_for_style(style: str) -> list[str]:
    mapping = {
        "conversational_direct": ["verbose", "jargon", "formal"],
        "data_driven_analytical": ["emotional", "vague", "anecdotal"],
        "provocative_contrarian": ["safe", "generic", "agreeable"],
        "minimalist_punchy": ["wordy", "meandering", "filler"],
    }
    return mapping.get(style, [])


def build_voice_prompt_injection(profile: dict[str, Any]) -> str:
    """Convert a voice profile into a prompt injection string for AI content generation."""
    parts = [
        f"VOICE STYLE: {profile.get('style', 'conversational_direct').replace('_', ' ')}",
        f"VOCABULARY: {profile.get('vocabulary_level', 'accessible')}",
    ]
    phrases = profile.get("signature_phrases", [])
    if phrases:
        parts.append(f"USE THESE PHRASES NATURALLY: {', '.join(phrases[:3])}")
    tones = profile.get("tone_keywords", [])
    if tones:
        parts.append(f"TONE: {', '.join(tones)}")
    avoids = profile.get("avoid_keywords", [])
    if avoids:
        parts.append(f"AVOID: {', '.join(avoids)}")
    emoji = profile.get("emoji_usage", "minimal")
    if emoji == "none":
        parts.append("NO EMOJIS")
    elif emoji == "heavy":
        parts.append("USE EMOJIS LIBERALLY")
    return "\n".join(parts)

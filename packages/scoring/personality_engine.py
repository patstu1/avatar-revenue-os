"""AI Personality Engine — generate character identities, manage memory, build prompts.

Creates persistent AI personalities that audiences follow and trust.
Each personality has a name, backstory, visual identity, voice, catchphrases,
and memory of past content — driving parasocial relationships and higher conversion.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

CHARACTER_ARCHETYPES = {
    "expert": {"description": "Authoritative, knowledgeable, data-driven", "tone": "confident", "energy": "moderate"},
    "mentor": {"description": "Supportive, experienced, guiding", "tone": "warm", "energy": "calm"},
    "provocateur": {"description": "Bold, contrarian, challenges norms", "tone": "edgy", "energy": "high"},
    "entertainer": {"description": "Fun, relatable, uses humor", "tone": "playful", "energy": "high"},
    "investigator": {"description": "Curious, research-heavy, reveals hidden truths", "tone": "serious", "energy": "focused"},
    "motivator": {"description": "Inspiring, action-oriented, pump-up energy", "tone": "urgent", "energy": "very_high"},
    "storyteller": {"description": "Narrative-driven, personal anecdotes, emotional", "tone": "warm", "energy": "moderate"},
    "analyst": {"description": "Data-first, charts, comparisons, objective", "tone": "neutral", "energy": "calm"},
}

NICHE_CHARACTER_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "personal_finance": [
        {"name": "Alex Cash", "archetype": "expert", "tagline": "Making money simple", "backstory": "Former Wall Street analyst who quit to teach everyday people how to build wealth. No BS, just math.", "traits": ["direct", "numbers-focused", "anti-guru"]},
        {"name": "Morgan Wealth", "archetype": "mentor", "tagline": "Your money mentor", "backstory": "Paid off $80K in debt and now helps others do the same. Real stories, real strategies.", "traits": ["empathetic", "practical", "encouraging"]},
    ],
    "make_money_online": [
        {"name": "Riley Hustle", "archetype": "provocateur", "tagline": "The anti-guru guru", "backstory": "Built 3 businesses from a laptop. Calls out scams and shows what actually works.", "traits": ["blunt", "transparent", "action-oriented"]},
        {"name": "Jordan Scale", "archetype": "analyst", "tagline": "Data-driven income", "backstory": "Tests every side hustle and shows the real numbers — no hype, just receipts.", "traits": ["analytical", "skeptical", "thorough"]},
    ],
    "health_fitness": [
        {"name": "Sam Strong", "archetype": "motivator", "tagline": "No excuses fitness", "backstory": "Lost 60 pounds and became a certified trainer. Believes everyone can transform.", "traits": ["energetic", "tough-love", "inspiring"]},
        {"name": "Taylor Wellness", "archetype": "mentor", "tagline": "Health made human", "backstory": "Recovered from burnout through fitness. Focuses on sustainable habits over quick fixes.", "traits": ["patient", "holistic", "science-based"]},
    ],
    "tech_reviews": [
        {"name": "Chris Circuit", "archetype": "expert", "tagline": "Tech truth, no fluff", "backstory": "Engineer who reviews tech the way engineers think about it — specs, benchmarks, real-world tests.", "traits": ["precise", "honest", "detail-oriented"]},
        {"name": "Avery Digital", "archetype": "entertainer", "tagline": "Tech for real people", "backstory": "Makes tech fun and understandable. No jargon, just 'should you buy this or not.'", "traits": ["funny", "relatable", "concise"]},
    ],
    "ai_tools": [
        {"name": "Nova AI", "archetype": "investigator", "tagline": "Testing every AI tool so you don't have to", "backstory": "AI researcher who tests tools obsessively and reports the honest results.", "traits": ["curious", "thorough", "future-focused"]},
        {"name": "Kai Automate", "archetype": "expert", "tagline": "Automate everything", "backstory": "Built AI workflows that save businesses 20+ hours/week. Shows exactly how.", "traits": ["systematic", "practical", "efficiency-obsessed"]},
    ],
    "default": [
        {"name": "River", "archetype": "expert", "tagline": "Real talk, real results", "backstory": "Industry insider sharing the insights that matter.", "traits": ["authentic", "direct", "knowledgeable"]},
    ],
}

CATCHPHRASE_TEMPLATES = [
    "Here's what nobody tells you about {topic}",
    "Let's break this down",
    "Real talk — {topic}",
    "The data doesn't lie",
    "This changed everything for me",
    "Pay attention to this part",
    "Most people get this wrong",
    "Here's the thing about {topic}",
    "I tested this so you don't have to",
    "Let me show you the receipts",
]

INTRO_TEMPLATES = [
    "What's up everyone, {name} here",
    "Alright, let's talk about {topic}",
    "{name} here with something important",
    "You need to see this — {name} here",
    "Stop scrolling — this is important",
]

OUTRO_TEMPLATES = [
    "If this helped, you know what to do",
    "Drop a comment if you want part 2",
    "Follow for more like this — {name} out",
    "Link in the description — go grab it",
    "See you in the next one",
]


def generate_personality(account_id: str, niche: str, platform: str = "youtube") -> dict[str, Any]:
    """Generate a complete AI personality for an account."""
    seed = int(hashlib.sha256(f"{account_id}:{niche}:{platform}".encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    templates = NICHE_CHARACTER_TEMPLATES.get(niche, NICHE_CHARACTER_TEMPLATES["default"])
    template = rng.choice(templates)
    archetype_info = CHARACTER_ARCHETYPES.get(template["archetype"], CHARACTER_ARCHETYPES["expert"])

    topic_placeholder = niche.replace("_", " ")
    catchphrases = [rng.choice(CATCHPHRASE_TEMPLATES).format(topic=topic_placeholder, name=template["name"]) for _ in range(3)]
    intros = [rng.choice(INTRO_TEMPLATES).format(name=template["name"], topic=topic_placeholder) for _ in range(2)]
    outros = [rng.choice(OUTRO_TEMPLATES).format(name=template["name"]) for _ in range(2)]

    return {
        "character_name": template["name"],
        "character_tagline": template["tagline"],
        "character_backstory": template["backstory"],
        "character_archetype": template["archetype"],
        "personality_traits": template["traits"],
        "communication_style": archetype_info["tone"],
        "energy_level": archetype_info["energy"],
        "catchphrases": catchphrases,
        "intro_phrases": intros,
        "outro_phrases": outros,
        "favorite_topics": [niche.replace("_", " ")],
        "expertise_areas": [niche.replace("_", " ")],
    }


def build_personality_prompt(personality: dict[str, Any], memories: list[dict[str, Any]] | None = None) -> str:
    """Build a prompt injection that makes the AI write AS this character."""
    parts = [
        f"CHARACTER: You are {personality.get('character_name', 'the host')}.",
        f"TAGLINE: \"{personality.get('character_tagline', '')}\"",
        f"BACKSTORY: {personality.get('character_backstory', '')}",
        f"ARCHETYPE: {personality.get('character_archetype', 'expert')} — {CHARACTER_ARCHETYPES.get(personality.get('character_archetype', ''), {}).get('description', '')}",
    ]

    traits = personality.get("personality_traits", [])
    if traits:
        parts.append(f"PERSONALITY: {', '.join(traits)}")

    parts.append(f"ENERGY: {personality.get('energy_level', 'moderate')}")
    parts.append(f"STYLE: {personality.get('communication_style', 'direct')}")

    catchphrases = personality.get("catchphrases", [])
    if catchphrases:
        parts.append(f"USE THESE NATURALLY: {' | '.join(catchphrases[:3])}")

    intros = personality.get("intro_phrases", [])
    if intros:
        parts.append(f"OPEN WITH SOMETHING LIKE: {intros[0]}")

    outros = personality.get("outro_phrases", [])
    if outros:
        parts.append(f"CLOSE WITH SOMETHING LIKE: {outros[0]}")

    forbidden = personality.get("forbidden_phrases", [])
    if forbidden:
        parts.append(f"NEVER SAY: {', '.join(forbidden)}")

    if memories:
        recent = [m for m in memories if m.get("importance_score", 0) >= 0.5][:5]
        if recent:
            parts.append("\nCHARACTER MEMORY (reference these naturally when relevant):")
            for m in recent:
                parts.append(f"  - [{m.get('memory_type', '')}] {m.get('memory_value', '')}")

    parts.append("\nWRITE THE ENTIRE SCRIPT IN THIS CHARACTER'S VOICE. Stay in character at all times.")

    return "\n".join(parts)

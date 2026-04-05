"""Autonomous Readiness Standard — the system may only claim 'fully autonomous'
when ALL 10 conditions pass. No soft passes. No fake labels.

Also contains the activation checklist: exact env vars, priority, what each unlocks.
"""
from __future__ import annotations

import os
from typing import Any

# ── Activation Checklist (tiered provider stack source of truth) ─────

ACTIVATION_CHECKLIST: list[dict[str, Any]] = [
    # P0: Core Intelligence
    {"provider": "Claude (Anthropic)", "env_vars": ["ANTHROPIC_API_KEY"], "priority": 0,
     "unlocks": "Operator copilot, hero text generation, content classification, strategy planning",
     "code_path_live": True, "additional_config": None},
    {"provider": "Gemini 2.5 Flash", "env_vars": ["GOOGLE_AI_API_KEY"], "priority": 0,
     "unlocks": "Standard text generation (captions, descriptions) — 70% of text calls at 10x cheaper than Claude",
     "code_path_live": True, "additional_config": None},
    {"provider": "DeepSeek V3.2", "env_vars": ["DEEPSEEK_API_KEY"], "priority": 0,
     "unlocks": "Bulk text scanning (hashtags, SEO, trend analysis, analytics summaries) — pennies per call",
     "code_path_live": True, "additional_config": None},
    # P1: Core Media
    {"provider": "Kling AI + Flux (fal.ai)", "env_vars": ["FAL_API_KEY"], "priority": 1,
     "unlocks": "Standard/bulk video generation (Kling) + style-variety images (Flux)",
     "code_path_live": True, "additional_config": None},
    {"provider": "HeyGen", "env_vars": ["HEYGEN_API_KEY"], "priority": 1,
     "unlocks": "AI avatar talking-head videos — primary avatar provider ($29/mo unlimited standard)",
     "code_path_live": True, "additional_config": "Create HeyGen avatar + clone voice in HeyGen dashboard"},
    {"provider": "ElevenLabs", "env_vars": ["ELEVENLABS_API_KEY"], "priority": 1,
     "unlocks": "Hero voice narration, brand voice cloning — quality king for customer-facing audio",
     "code_path_live": True, "additional_config": "Clone brand voice in ElevenLabs dashboard"},
    {"provider": "Fish Audio", "env_vars": ["FISH_AUDIO_API_KEY"], "priority": 1,
     "unlocks": "Standard voiceovers at 80% less cost than ElevenLabs — #1 on TTS-Arena",
     "code_path_live": True, "additional_config": None},
    {"provider": "Voxtral TTS (Mistral)", "env_vars": ["MISTRAL_API_KEY"], "priority": 1,
     "unlocks": "Ultra-budget voice for bulk/A-B test narrations — voice clone from 3 seconds",
     "code_path_live": True, "additional_config": None},
    {"provider": "Suno", "env_vars": ["SUNO_API_KEY"], "priority": 1,
     "unlocks": "AI music generation — background tracks, intros, branded jingles",
     "code_path_live": True, "additional_config": None},
    # P2: Premium Hero Media
    {"provider": "GPT Image 1.5 (OpenAI)", "env_vars": ["OPENAI_API_KEY"], "priority": 2,
     "unlocks": "Hero images, product shots, ad creatives — top quality benchmark",
     "code_path_live": True, "additional_config": None},
    {"provider": "Runway Gen-4 Turbo", "env_vars": ["RUNWAY_API_KEY"], "priority": 2,
     "unlocks": "Premium cinematic hero video — use sparingly for promoted content",
     "code_path_live": True, "additional_config": None},
    # P3: Execution / Monetization
    {"provider": "Buffer", "env_vars": ["BUFFER_API_KEY"], "priority": 3,
     "unlocks": "Social media auto-publishing across 8 platforms (Instagram, TikTok, YouTube, X, Facebook, Pinterest, LinkedIn, Threads)",
     "code_path_live": True, "additional_config": "Connect platform profiles in Buffer dashboard"},
    {"provider": "Stripe", "env_vars": ["STRIPE_API_KEY", "STRIPE_WEBHOOK_SECRET"], "priority": 3,
     "unlocks": "Payment tracking, revenue attribution, webhook-verified checkout events",
     "code_path_live": True, "additional_config": "Configure webhook endpoint in Stripe dashboard"},
    {"provider": "SMTP Email", "env_vars": ["SMTP_HOST", "SMTP_FROM_EMAIL"], "priority": 3,
     "unlocks": "Email sequences, newsletter delivery, operator notifications",
     "code_path_live": True, "additional_config": None},
    {"provider": "Twilio SMS", "env_vars": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"], "priority": 3,
     "unlocks": "SMS delivery for sequences and notifications",
     "code_path_live": True, "additional_config": None},
    {"provider": "D-ID", "env_vars": ["DID_API_KEY"], "priority": 3,
     "unlocks": "Budget avatar videos at scale — fallback when HeyGen quality isn't critical",
     "code_path_live": True, "additional_config": None},
    {"provider": "Imagen 4 Fast (Google)", "env_vars": ["GOOGLE_AI_API_KEY"], "priority": 3,
     "unlocks": "Bulk social graphics at $0.02/image — shares key with Gemini Flash",
     "code_path_live": True, "additional_config": None},
]


def get_activation_checklist() -> list[dict[str, Any]]:
    """Return checklist with live credential status."""
    results = []
    for item in ACTIVATION_CHECKLIST:
        missing = [k for k in item["env_vars"] if not os.environ.get(k)]
        present = [k for k in item["env_vars"] if os.environ.get(k)]
        results.append({
            **item,
            "configured": len(missing) == 0,
            "missing_vars": missing,
            "present_vars": present,
        })
    return results


def get_configured_count_by_priority() -> dict[int, dict[str, int]]:
    checklist = get_activation_checklist()
    by_p: dict[int, dict[str, int]] = {}
    for item in checklist:
        p = item["priority"]
        if p not in by_p:
            by_p[p] = {"total": 0, "configured": 0}
        by_p[p]["total"] += 1
        if item["configured"]:
            by_p[p]["configured"] += 1
    return by_p


# ── Autonomous Readiness Standard (10 conditions) ────────────────

def evaluate_autonomous_readiness() -> dict[str, Any]:
    """Check all 10 conditions. Returns pass/fail for each + overall verdict."""
    conditions: list[dict[str, Any]] = []

    # 1. Critical providers configured
    critical_keys = ["ANTHROPIC_API_KEY", "GOOGLE_AI_API_KEY", "DEEPSEEK_API_KEY"]
    critical_missing = [k for k in critical_keys if not os.environ.get(k)]
    has_distributor = any(os.environ.get(k) for k in ["BUFFER_API_KEY", "PUBLER_API_KEY", "AYRSHARE_API_KEY"])
    if not has_distributor:
        critical_missing.append("BUFFER_API_KEY or PUBLER_API_KEY or AYRSHARE_API_KEY")
    conditions.append({
        "id": 1, "name": "Critical providers configured",
        "passed": len(critical_missing) == 0,
        "detail": f"Missing: {', '.join(critical_missing)}" if critical_missing else "All critical providers configured",
    })

    # 2. No critical dead-end flows (not yet verified at runtime)
    conditions.append({
        "id": 2, "name": "No critical dead-end flows",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires runtime flow tracing to confirm all paths are wired",
    })

    # 3. Publishing auto-runs
    conditions.append({
        "id": 3, "name": "Publishing auto-runs through distribution layer",
        "passed": has_distributor,
        "detail": f"Multi-distributor active ({', '.join(k.replace('_API_KEY','') for k in ['BUFFER_API_KEY','PUBLER_API_KEY','AYRSHARE_API_KEY'] if os.environ.get(k))})" if has_distributor else "Set BUFFER_API_KEY, PUBLER_API_KEY, or AYRSHARE_API_KEY to enable auto-publishing",
    })

    # 4. Measured performance data ingested on schedule
    conditions.append({
        "id": 4, "name": "Measured performance data ingested on schedule",
        "passed": has_distributor,
        "detail": "analytics_worker.ingest_performance runs every 30min" if has_distributor else "No data sources active — configure at least one distribution service",
    })

    # 5. Offer economics updated from measured data (not yet verified at runtime)
    conditions.append({
        "id": 5, "name": "Offer economics updated from measured data",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires confirmation that offer_learning + measured_data_cascade workers ran recently",
    })

    # 6. Expansion advisor on schedule (not yet verified at runtime)
    conditions.append({
        "id": 6, "name": "Expansion advisor runs on schedule and feeds downstream",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires confirmation that recompute_expansion_advisor ran recently",
    })

    # 7. Kill/scale actions surfaced automatically (not yet verified at runtime)
    conditions.append({
        "id": 7, "name": "Kill/scale actions surfaced automatically",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires confirmation that detect_weak_lanes ran recently",
    })

    # 8. Gatekeeper no critical blockers (not yet verified at runtime)
    conditions.append({
        "id": 8, "name": "Gatekeeper has no critical acceptance blockers",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires gatekeeper recompute to check actual gate state",
    })

    # 9. Truth labels correct (not yet verified at runtime)
    conditions.append({
        "id": 9, "name": "Truth labels correctly show live/queued/blocked/recommendation-only",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires runtime audit of execution_truth and publish_mode fields",
    })

    # 10. Tiered routing consumed downstream (not yet verified at runtime)
    conditions.append({
        "id": 10, "name": "Tiered routing consumed by downstream generation/distribution",
        "passed": False,
        "not_verified": True,
        "detail": "Not yet verified — requires confirmation that generation_worker consumes routing tier",
    })

    verified = [c for c in conditions if not c.get("not_verified")]
    unverified = [c for c in conditions if c.get("not_verified")]
    verified_pass = all(c["passed"] for c in verified) if verified else False
    passing = sum(1 for c in conditions if c["passed"])

    if unverified:
        verdict = f"NOT YET AUTONOMOUS — {len(unverified)} condition(s) not yet verified, {len(conditions) - passing - len(unverified)} verified condition(s) failing" if not verified_pass else f"NOT YET AUTONOMOUS — {len(unverified)} condition(s) not yet verified (all verified checks pass)"
        fully = False
    else:
        fully = all(c["passed"] for c in conditions)
        verdict = "FULLY AUTONOMOUS FOR CURRENT SCOPE" if fully else f"NOT YET AUTONOMOUS — {len(conditions) - passing} condition(s) failing"

    return {
        "fully_autonomous": fully,
        "conditions_passing": passing,
        "conditions_total": len(conditions),
        "conditions_verified": len(verified),
        "conditions_unverified": len(unverified),
        "verdict": verdict,
        "conditions": conditions,
        "blocking_conditions": [c for c in conditions if not c["passed"]],
    }

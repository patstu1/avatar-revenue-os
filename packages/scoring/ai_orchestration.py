"""AI Model Orchestration Engine — Intelligent multi-model routing with cost optimization.

Routes AI tasks to the optimal model based on task type, quality requirements,
cost constraints, and historical performance data. Implements quality gates
that auto-reject and regenerate low-quality output.
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1.  MODEL REGISTRY  &  COST TRACKING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class TaskPerformance:
    task_type: str
    avg_quality_score: float
    avg_latency_ms: float
    success_rate: float
    sample_count: int
    cost_efficiency: float  # quality / cost ratio

    def update(self, quality: float, latency_ms: float, succeeded: bool, cost: float) -> None:
        n = self.sample_count
        self.avg_quality_score = (self.avg_quality_score * n + quality) / (n + 1)
        self.avg_latency_ms = (self.avg_latency_ms * n + latency_ms) / (n + 1)
        self.success_rate = (self.success_rate * n + (1.0 if succeeded else 0.0)) / (n + 1)
        self.sample_count = n + 1
        if cost > 0:
            self.cost_efficiency = self.avg_quality_score / cost


@dataclass
class ModelProfile:
    model_id: str
    provider: str
    cost_per_1k_input: float
    cost_per_1k_output: float
    avg_latency_ms: float
    quality_score: float  # 0–1 empirical quality
    max_context_tokens: int
    capabilities: set[str]
    rate_limit_rpm: int
    current_load_pct: float = 0.0
    error_rate_24h: float = 0.0
    task_performance: dict[str, TaskPerformance] = field(default_factory=dict)

    @property
    def effective_quality(self) -> float:
        penalty = min(self.error_rate_24h * 2.0, 0.3)
        return max(0.0, self.quality_score - penalty)

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens / 1000.0) * self.cost_per_1k_input + (output_tokens / 1000.0) * self.cost_per_1k_output

    def record_task(self, task_type: str, quality: float, latency_ms: float, succeeded: bool, cost: float) -> None:
        if task_type not in self.task_performance:
            self.task_performance[task_type] = TaskPerformance(
                task_type=task_type,
                avg_quality_score=quality,
                avg_latency_ms=latency_ms,
                success_rate=1.0 if succeeded else 0.0,
                sample_count=0,
                cost_efficiency=quality / max(cost, 0.0001),
            )
        self.task_performance[task_type].update(quality, latency_ms, succeeded, cost)


# ---------------------------------------------------------------------------
# All 18 models — real approximate 2025 pricing
# Text models: cost per 1K tokens
# Image models: cost_per_1k_input = cost per image (divided by 1K for API consistency)
# Video models: cost per second mapped to 1K-token slots
# Voice models: cost per 1K characters
# Music: flat per-generation cost mapped similarly
# ---------------------------------------------------------------------------

MODEL_REGISTRY: dict[str, ModelProfile] = {
    # ── TEXT ────────────────────────────────────────────────────────────
    "claude-sonnet-4": ModelProfile(
        model_id="claude-sonnet-4",
        provider="anthropic",
        cost_per_1k_input=0.003,  # $3 / 1M tokens
        cost_per_1k_output=0.015,  # $15 / 1M tokens
        avg_latency_ms=2800,
        quality_score=0.97,
        max_context_tokens=200_000,
        capabilities={"text", "code", "reasoning", "planning", "hero_copy", "orchestration"},
        rate_limit_rpm=4000,
    ),
    "gemini-2.5-flash": ModelProfile(
        model_id="gemini-2.5-flash",
        provider="google",
        cost_per_1k_input=0.00015,  # $0.15 / 1M tokens
        cost_per_1k_output=0.0006,  # $0.60 / 1M tokens (non-thinking)
        avg_latency_ms=900,
        quality_score=0.91,
        max_context_tokens=1_048_576,
        capabilities={"text", "code", "reasoning", "captions", "descriptions"},
        rate_limit_rpm=10_000,
    ),
    "deepseek-chat": ModelProfile(
        model_id="deepseek-chat",
        provider="deepseek",
        cost_per_1k_input=0.00028,  # $0.28 / 1M tokens
        cost_per_1k_output=0.00042,  # $0.42 / 1M tokens (non-cache)
        avg_latency_ms=1200,
        quality_score=0.85,
        max_context_tokens=128_000,
        capabilities={"text", "code", "data_scanning", "seo", "hashtags", "bulk_text"},
        rate_limit_rpm=6000,
    ),
    # ── IMAGE ──────────────────────────────────────────────────────────
    "gpt-image-1": ModelProfile(
        model_id="gpt-image-1",
        provider="openai",
        cost_per_1k_input=0.040,  # ~$0.04 per image (1024×1024 high)
        cost_per_1k_output=0.0,
        avg_latency_ms=12_000,
        quality_score=0.96,
        max_context_tokens=4096,  # prompt limit ~4K chars
        capabilities={"image", "hero_images", "ad_creatives", "product_shots"},
        rate_limit_rpm=500,
    ),
    "imagen-4-fast": ModelProfile(
        model_id="imagen-4-fast",
        provider="google",
        cost_per_1k_input=0.020,  # ~$0.02 per image
        cost_per_1k_output=0.0,
        avg_latency_ms=6_000,
        quality_score=0.89,
        max_context_tokens=4096,
        capabilities={"image", "thumbnails", "bulk_graphics", "social_images"},
        rate_limit_rpm=1000,
    ),
    "flux-pro-v1.1": ModelProfile(
        model_id="flux-pro-v1.1",
        provider="fal",
        cost_per_1k_input=0.055,  # ~$0.055 per image
        cost_per_1k_output=0.0,
        avg_latency_ms=8_000,
        quality_score=0.90,
        max_context_tokens=2048,
        capabilities={"image", "artistic_styles", "variety_images"},
        rate_limit_rpm=800,
    ),
    # ── VIDEO ──────────────────────────────────────────────────────────
    "runway-gen4-turbo": ModelProfile(
        model_id="runway-gen4-turbo",
        provider="runway",
        cost_per_1k_input=0.096,  # ~$0.48 / 5-sec clip → $0.096/sec
        cost_per_1k_output=0.0,
        avg_latency_ms=90_000,
        quality_score=0.95,
        max_context_tokens=1000,
        capabilities={"video", "cinematic", "hero_video", "image_to_video"},
        rate_limit_rpm=60,
    ),
    "kling-v2": ModelProfile(
        model_id="kling-v2",
        provider="kling",
        cost_per_1k_input=0.070,  # ~$0.07/sec
        cost_per_1k_output=0.0,
        avg_latency_ms=120_000,
        quality_score=0.87,
        max_context_tokens=1000,
        capabilities={"video", "b_roll", "social_clips", "text_to_video"},
        rate_limit_rpm=120,
    ),
    "wan-2.2": ModelProfile(
        model_id="wan-2.2",
        provider="fal",
        cost_per_1k_input=0.030,  # ~$0.03/sec — cheapest
        cost_per_1k_output=0.0,
        avg_latency_ms=150_000,
        quality_score=0.78,
        max_context_tokens=500,
        capabilities={"video", "bulk_video", "text_to_video"},
        rate_limit_rpm=200,
    ),
    "higgsfield-cinema": ModelProfile(
        model_id="higgsfield-cinema",
        provider="higgsfield",
        cost_per_1k_input=0.120,  # premium cinematic
        cost_per_1k_output=0.0,
        avg_latency_ms=180_000,
        quality_score=0.93,
        max_context_tokens=1000,
        capabilities={"video", "cinematic", "camera_movement", "multi_character", "speech_video"},
        rate_limit_rpm=30,
    ),
    # ── AVATAR ─────────────────────────────────────────────────────────
    "heygen-avatar": ModelProfile(
        model_id="heygen-avatar",
        provider="heygen",
        cost_per_1k_input=0.050,  # ~$29/mo creator plan, ~$0.05/min effective
        cost_per_1k_output=0.0,
        avg_latency_ms=180_000,
        quality_score=0.93,
        max_context_tokens=3000,  # script char limit
        capabilities={"avatar", "lip_sync", "talking_head", "interactive_streaming"},
        rate_limit_rpm=30,
    ),
    "d-id-talks": ModelProfile(
        model_id="d-id-talks",
        provider="d-id",
        cost_per_1k_input=0.025,  # budget: ~$0.025/min pay-per-use
        cost_per_1k_output=0.0,
        avg_latency_ms=120_000,
        quality_score=0.80,
        max_context_tokens=3000,
        capabilities={"avatar", "lip_sync", "budget_avatar"},
        rate_limit_rpm=60,
    ),
    "tavus-avatar": ModelProfile(
        model_id="tavus-avatar",
        provider="tavus",
        cost_per_1k_input=0.060,
        cost_per_1k_output=0.0,
        avg_latency_ms=200_000,
        quality_score=0.86,
        max_context_tokens=5000,
        capabilities={"avatar", "lip_sync", "async_video", "personalized_video"},
        rate_limit_rpm=20,
    ),
    # ── VOICE ──────────────────────────────────────────────────────────
    "elevenlabs-v2": ModelProfile(
        model_id="elevenlabs-v2",
        provider="elevenlabs",
        cost_per_1k_input=0.240,  # ~$0.24 / 1K chars (scale plan)
        cost_per_1k_output=0.0,
        avg_latency_ms=2_500,
        quality_score=0.97,
        max_context_tokens=40_000,  # 40K chars per request
        capabilities={"voice", "voice_cloning", "streaming_audio", "hero_narration", "multilingual"},
        rate_limit_rpm=500,
    ),
    "fish-audio-tts": ModelProfile(
        model_id="fish-audio-tts",
        provider="fish_audio",
        cost_per_1k_input=0.015,  # $15 / 1M chars
        cost_per_1k_output=0.0,
        avg_latency_ms=1_800,
        quality_score=0.88,
        max_context_tokens=10_000,
        capabilities={"voice", "bulk_voiceover", "standard_tts"},
        rate_limit_rpm=1000,
    ),
    "voxtral-mini": ModelProfile(
        model_id="voxtral-mini",
        provider="mistral",
        cost_per_1k_input=0.016,  # $0.016 / 1K chars — ultra budget
        cost_per_1k_output=0.0,
        avg_latency_ms=2_000,
        quality_score=0.79,
        max_context_tokens=8_000,
        capabilities={"voice", "voice_cloning", "ultra_budget", "bulk_tts"},
        rate_limit_rpm=2000,
    ),
    # ── REALTIME VOICE (OpenAI) ────────────────────────────────────────
    "openai-realtime-voice": ModelProfile(
        model_id="openai-realtime-voice",
        provider="openai",
        cost_per_1k_input=0.100,  # $100/1M input tokens audio
        cost_per_1k_output=0.200,  # $200/1M output tokens audio
        avg_latency_ms=500,  # sub-second streaming latency
        quality_score=0.92,
        max_context_tokens=128_000,
        capabilities={"voice", "realtime_voice", "conversational", "streaming_audio"},
        rate_limit_rpm=200,
    ),
    # ── MUSIC ──────────────────────────────────────────────────────────
    "suno-v4": ModelProfile(
        model_id="suno-v4",
        provider="suno",
        cost_per_1k_input=0.100,  # ~$0.10 per generation on pro plan
        cost_per_1k_output=0.0,
        avg_latency_ms=30_000,
        quality_score=0.90,
        max_context_tokens=3000,  # lyrics / description limit
        capabilities={"music", "background_tracks", "jingles", "intros"},
        rate_limit_rpm=60,
    ),
}


# Tier-to-task-type mapping: which models are preferred for each tier
_TIER_MODEL_PREFERENCES: dict[str, dict[str, list[str]]] = {
    "hero": {
        "text": ["claude-sonnet-4"],
        "image": ["gpt-image-1", "flux-pro-v1.1"],
        "video": ["runway-gen4-turbo", "higgsfield-cinema"],
        "avatar": ["heygen-avatar"],
        "voice": ["elevenlabs-v2"],
        "music": ["suno-v4"],
    },
    "standard": {
        "text": ["gemini-2.5-flash"],
        "image": ["imagen-4-fast", "flux-pro-v1.1"],
        "video": ["kling-v2"],
        "avatar": ["heygen-avatar", "d-id-talks"],
        "voice": ["fish-audio-tts"],
        "music": ["suno-v4"],
    },
    "bulk": {
        "text": ["deepseek-chat", "gemini-2.5-flash"],
        "image": ["imagen-4-fast"],
        "video": ["wan-2.2", "kling-v2"],
        "avatar": ["d-id-talks", "tavus-avatar"],
        "voice": ["voxtral-mini", "fish-audio-tts"],
        "music": ["suno-v4"],
    },
}


def _extract_media_type(task_type: str) -> str:
    """Normalise granular task types to a media category."""
    mapping = {
        "hero_text": "text",
        "standard_text": "text",
        "bulk_text": "text",
        "caption": "text",
        "script": "text",
        "hook": "text",
        "email": "text",
        "blog": "text",
        "hero_image": "image",
        "thumbnail": "image",
        "social_image": "image",
        "hero_video": "video",
        "social_clip": "video",
        "b_roll": "video",
        "cinematic": "video",
        "avatar_video": "avatar",
        "talking_head": "avatar",
        "hero_voice": "voice",
        "voiceover": "voice",
        "narration": "voice",
        "background_music": "music",
        "jingle": "music",
    }
    return mapping.get(task_type, task_type)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2.  INTELLIGENT MODEL ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# Scoring weights by quality tier
_TIER_WEIGHTS: dict[str, dict[str, float]] = {
    "hero": {"quality": 0.50, "cost": 0.05, "latency": 0.05, "load": 0.10, "preference": 0.30},
    "standard": {"quality": 0.30, "cost": 0.20, "latency": 0.15, "load": 0.10, "preference": 0.25},
    "bulk": {"quality": 0.10, "cost": 0.40, "latency": 0.15, "load": 0.15, "preference": 0.20},
}


def select_optimal_model(
    task_type: str,
    quality_requirement: str = "standard",
    max_cost_per_unit: float = 1.0,
    max_latency_ms: int = 300_000,
    content_length: int = 1000,
    required_capabilities: set[str] | None = None,
) -> tuple[str, dict]:
    """Select the optimal model considering quality, cost, latency, and load balancing.

    Returns (model_id, reasoning_dict).
    """
    media_type = _extract_media_type(task_type)
    tier = quality_requirement if quality_requirement in _TIER_WEIGHTS else "standard"
    weights = _TIER_WEIGHTS[tier]
    preferred = _TIER_MODEL_PREFERENCES.get(tier, {}).get(media_type, [])

    # Step 1: Filter by capabilities
    candidates: list[ModelProfile] = []
    rejection_reasons: dict[str, str] = {}

    for mid, mp in MODEL_REGISTRY.items():
        if required_capabilities and not required_capabilities.issubset(mp.capabilities):
            missing = required_capabilities - mp.capabilities
            rejection_reasons[mid] = f"missing capabilities: {missing}"
            continue

        if not required_capabilities and media_type not in mp.capabilities:
            rejection_reasons[mid] = f"no '{media_type}' capability"
            continue

        if content_length > mp.max_context_tokens:
            rejection_reasons[mid] = f"content_length {content_length} > context limit {mp.max_context_tokens}"
            continue

        est_cost = mp.estimated_cost(content_length, content_length // 2)
        if est_cost > max_cost_per_unit and max_cost_per_unit > 0:
            rejection_reasons[mid] = f"estimated cost ${est_cost:.4f} > max ${max_cost_per_unit:.4f}"
            continue

        if mp.avg_latency_ms > max_latency_ms:
            rejection_reasons[mid] = f"latency {mp.avg_latency_ms}ms > max {max_latency_ms}ms"
            continue

        if mp.error_rate_24h > 0.50:
            rejection_reasons[mid] = f"error rate {mp.error_rate_24h:.0%} too high"
            continue

        candidates.append(mp)

    if not candidates:
        fallback = preferred[0] if preferred and preferred[0] in MODEL_REGISTRY else next(iter(MODEL_REGISTRY))
        return fallback, {
            "selected": fallback,
            "reason": "no candidates passed all filters — falling back to tier preference",
            "rejection_reasons": rejection_reasons,
            "score": 0.0,
        }

    # Step 2: Compute normalisation ranges
    costs = []
    latencies = []
    for c in candidates:
        costs.append(c.estimated_cost(content_length, content_length // 2))
        latencies.append(c.avg_latency_ms)

    cost_min, cost_max = min(costs), max(costs)
    lat_min, lat_max = min(latencies), max(latencies)
    cost_range = cost_max - cost_min if cost_max != cost_min else 1.0
    lat_range = lat_max - lat_min if lat_max != lat_min else 1.0

    # Step 3: Score every candidate
    scored: list[tuple[float, ModelProfile, dict]] = []
    for mp in candidates:
        est_cost = mp.estimated_cost(content_length, content_length // 2)
        norm_cost = 1.0 - ((est_cost - cost_min) / cost_range)
        norm_latency = 1.0 - ((mp.avg_latency_ms - lat_min) / lat_range)
        load_score = 1.0 - min(mp.current_load_pct / 100.0, 1.0)
        if mp.model_id in preferred:
            position = preferred.index(mp.model_id)
            pref_score = max(0.5, 1.0 - position * 0.15)
        else:
            pref_score = 0.0

        # Historical performance bonus
        hist_bonus = 0.0
        if task_type in mp.task_performance:
            tp = mp.task_performance[task_type]
            if tp.sample_count >= 5:
                hist_bonus = tp.avg_quality_score * 0.1 * min(tp.sample_count / 100, 1.0)

        quality = mp.effective_quality + hist_bonus

        composite = (
            weights["quality"] * quality
            + weights["cost"] * norm_cost
            + weights["latency"] * norm_latency
            + weights["load"] * load_score
            + weights["preference"] * pref_score
        )

        detail = {
            "quality": round(quality, 4),
            "norm_cost": round(norm_cost, 4),
            "norm_latency": round(norm_latency, 4),
            "load_score": round(load_score, 4),
            "pref_score": round(pref_score, 4),
            "hist_bonus": round(hist_bonus, 4),
            "estimated_cost": round(est_cost, 6),
            "composite": round(composite, 4),
        }
        scored.append((composite, mp, detail))

    scored.sort(key=lambda t: t[0], reverse=True)
    winner_score, winner, winner_detail = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None

    reasoning: dict[str, Any] = {
        "selected": winner.model_id,
        "provider": winner.provider,
        "score": round(winner_score, 4),
        "breakdown": winner_detail,
        "tier": tier,
        "media_type": media_type,
        "candidates_evaluated": len(candidates),
        "candidates_rejected": len(rejection_reasons),
        "rejection_summary": rejection_reasons,
    }
    if runner_up:
        reasoning["runner_up"] = {
            "model_id": runner_up[1].model_id,
            "score": round(runner_up[0], 4),
            "margin": round(winner_score - runner_up[0], 4),
        }

    return winner.model_id, reasoning


def compute_task_cost_estimate(
    model_id: str,
    input_tokens: int,
    expected_output_tokens: int,
) -> dict[str, Any]:
    """Estimate cost with breakdown."""
    mp = MODEL_REGISTRY.get(model_id)
    if not mp:
        return {"error": f"Unknown model: {model_id}", "total_cost": 0.0}

    input_cost = (input_tokens / 1000.0) * mp.cost_per_1k_input
    output_cost = (expected_output_tokens / 1000.0) * mp.cost_per_1k_output
    total = input_cost + output_cost

    return {
        "model_id": model_id,
        "provider": mp.provider,
        "input_tokens": input_tokens,
        "output_tokens": expected_output_tokens,
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total, 6),
        "cost_per_1k_input": mp.cost_per_1k_input,
        "cost_per_1k_output": mp.cost_per_1k_output,
        "quality_score": mp.quality_score,
        "estimated_latency_ms": mp.avg_latency_ms,
    }


def optimize_batch_routing(
    tasks: list[dict[str, Any]],
    total_budget: float,
) -> list[dict[str, Any]]:
    """Route a batch of tasks to minimise total cost while meeting quality targets.

    Uses priority-based allocation: hero tasks get premium models first,
    then remaining budget is distributed to standard / bulk tasks.
    """
    if not tasks:
        return []

    tier_priority = {"hero": 0, "standard": 1, "bulk": 2}
    indexed = [(i, t) for i, t in enumerate(tasks)]
    indexed.sort(key=lambda x: tier_priority.get(x[1].get("quality", "standard"), 1))

    results: list[dict[str, Any]] = [{}] * len(tasks)
    remaining_budget = total_budget
    allocated_budget: dict[int, float] = {}

    # Pass 1: assign proportional budget ceilings
    total_weight = 0.0
    task_weights: list[float] = []
    for _, t in indexed:
        tier = t.get("quality", "standard")
        w = {"hero": 3.0, "standard": 1.5, "bulk": 1.0}.get(tier, 1.0)
        task_weights.append(w)
        total_weight += w

    budget_per_weight = total_budget / max(total_weight, 0.001)

    # Pass 2: route each task within its budget slice
    for idx_pos, (orig_idx, task) in enumerate(indexed):
        task_type = task.get("task_type", "text")
        quality = task.get("quality", "standard")
        max_cost = task.get("max_cost", budget_per_weight * task_weights[idx_pos])
        content_length = task.get("content_length", 500)
        capabilities = task.get("required_capabilities")
        if isinstance(capabilities, list):
            capabilities = set(capabilities)

        budget_ceiling = min(max_cost, remaining_budget)
        if budget_ceiling <= 0:
            budget_ceiling = 0.001

        model_id, reasoning = select_optimal_model(
            task_type=task_type,
            quality_requirement=quality,
            max_cost_per_unit=budget_ceiling,
            max_latency_ms=task.get("max_latency_ms", 300_000),
            content_length=content_length,
            required_capabilities=capabilities,
        )

        est = compute_task_cost_estimate(model_id, content_length, content_length // 2)
        actual_cost = est["total_cost"]
        remaining_budget -= actual_cost
        allocated_budget[orig_idx] = actual_cost

        results[orig_idx] = {
            "task_index": orig_idx,
            "task_type": task_type,
            "quality_tier": quality,
            "assigned_model": model_id,
            "estimated_cost": actual_cost,
            "budget_ceiling": round(budget_ceiling, 6),
            "reasoning": reasoning,
        }

    total_cost = sum(allocated_budget.values())
    budget_utilisation = total_cost / total_budget if total_budget > 0 else 0.0

    for r in results:
        r["batch_summary"] = {
            "total_tasks": len(tasks),
            "total_estimated_cost": round(total_cost, 6),
            "total_budget": total_budget,
            "budget_utilisation_pct": round(budget_utilisation * 100, 2),
            "budget_remaining": round(remaining_budget, 6),
        }

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3.  QUALITY  GATE  SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class QualityReport:
    content_id: str
    overall_score: float  # 0–100
    passed: bool
    dimension_scores: dict[str, float]
    issues: list[str]
    improvement_suggestions: list[str]
    regeneration_recommended: bool
    estimated_revenue_impact: float  # projected RPM delta (positive = better)


# ── Text analysis helpers (stdlib only) ────────────────────────────────

_SYLLABLE_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)
_SENTENCE_TERMINATORS = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"[a-zA-Z]+")


def _count_syllables(word: str) -> int:
    matches = _SYLLABLE_RE.findall(word)
    count = len(matches)
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def _flesch_kincaid_grade(text: str) -> float:
    words = _WORD_RE.findall(text)
    if not words:
        return 0.0
    sentences = [s.strip() for s in _SENTENCE_TERMINATORS.split(text) if s.strip()]
    num_sentences = max(len(sentences), 1)
    num_words = len(words)
    num_syllables = sum(_count_syllables(w) for w in words)
    return 0.39 * (num_words / num_sentences) + 11.8 * (num_syllables / num_words) - 15.59


def _flesch_reading_ease(text: str) -> float:
    words = _WORD_RE.findall(text)
    if not words:
        return 0.0
    sentences = [s.strip() for s in _SENTENCE_TERMINATORS.split(text) if s.strip()]
    num_sentences = max(len(sentences), 1)
    num_words = len(words)
    num_syllables = sum(_count_syllables(w) for w in words)
    return 206.835 - 1.015 * (num_words / num_sentences) - 84.6 * (num_syllables / num_words)


_POWER_WORDS = frozenset(
    [
        "free",
        "proven",
        "secret",
        "instant",
        "guaranteed",
        "exclusive",
        "limited",
        "discover",
        "unlock",
        "transform",
        "breakthrough",
        "ultimate",
        "now",
        "today",
        "easy",
        "fast",
        "shocking",
        "revealed",
        "urgent",
        "save",
        "boost",
        "skyrocket",
        "dominate",
        "massive",
        "incredible",
        "results",
        "insider",
        "hack",
        "money",
        "profit",
        "growth",
        "success",
        "winning",
        "powerful",
        "explosive",
        "unstoppable",
    ]
)

_EMOTIONAL_TRIGGERS = frozenset(
    [
        "imagine",
        "what if",
        "you deserve",
        "stop wasting",
        "tired of",
        "finally",
        "never again",
        "struggling",
        "dream",
        "fear",
        "love",
        "hate",
        "freedom",
        "security",
        "pain",
        "pleasure",
        "wish",
        "hope",
        "believe",
        "trust",
    ]
)

_CTA_PHRASES = frozenset(
    [
        "click",
        "sign up",
        "subscribe",
        "download",
        "get started",
        "buy now",
        "learn more",
        "join",
        "register",
        "order",
        "start",
        "try",
        "grab",
        "claim",
        "shop",
        "book",
        "reserve",
        "apply",
        "enroll",
        "watch",
        "tap",
        "swipe",
        "link in bio",
        "comment below",
        "drop a",
        "save this",
        "share this",
        "follow for",
        "dm me",
    ]
)

_SPAM_WORDS = frozenset(
    [
        "!!!",
        "100%",
        "act now",
        "no obligation",
        "click here",
        "congratulations",
        "winner",
        "selected",
        "dear friend",
        "make money fast",
    ]
)

_FILLER_PHRASES = frozenset(
    [
        "in this article",
        "as we all know",
        "it goes without saying",
        "needless to say",
        "in today's world",
        "at the end of the day",
        "it is what it is",
        "for all intents and purposes",
    ]
)

# Platform-specific ideal readability ranges (Flesch Reading Ease)
_PLATFORM_READABILITY: dict[str, tuple[float, float]] = {
    "hook": (60.0, 90.0),  # simple, punchy
    "script": (50.0, 80.0),  # conversational
    "caption": (55.0, 85.0),  # social-friendly
    "email": (50.0, 75.0),  # professional but accessible
    "blog": (40.0, 70.0),  # slightly more complex OK
}


def _score_readability(text: str, content_type: str) -> tuple[float, list[str]]:
    fre = _flesch_reading_ease(text)
    ideal_low, ideal_high = _PLATFORM_READABILITY.get(content_type, (45.0, 80.0))

    if ideal_low <= fre <= ideal_high:
        score = 90.0 + 10.0 * (1.0 - abs(fre - (ideal_low + ideal_high) / 2) / ((ideal_high - ideal_low) / 2))
    elif fre < ideal_low:
        distance = ideal_low - fre
        score = max(30.0, 90.0 - distance * 1.5)
    else:
        distance = fre - ideal_high
        score = max(40.0, 90.0 - distance * 1.0)

    issues: list[str] = []
    if fre < ideal_low - 15:
        issues.append(f"Text is too complex (Flesch {fre:.0f}). Simplify sentences and use shorter words.")
    if fre > ideal_high + 15:
        issues.append(f"Text is overly simplistic (Flesch {fre:.0f}). Add more substance or detail.")

    words = _WORD_RE.findall(text)
    if words:
        avg_word_len = sum(len(w) for w in words) / len(words)
        if avg_word_len > 6.5:
            issues.append("Average word length is high. Consider simpler vocabulary.")
            score -= 5

    return min(100.0, max(0.0, score)), issues


def _score_relevance(text: str, brand_keywords: list[str] | None, target_audience: str) -> tuple[float, list[str]]:
    issues: list[str] = []
    text_lower = text.lower()
    words = _WORD_RE.findall(text_lower)
    word_count = len(words) or 1

    kw_score = 70.0  # baseline

    if brand_keywords:
        found = sum(1 for kw in brand_keywords if kw.lower() in text_lower)
        kw_ratio = found / max(len(brand_keywords), 1)
        kw_score = 50.0 + kw_ratio * 50.0
        if kw_ratio < 0.2:
            issues.append(f"Only {found}/{len(brand_keywords)} brand keywords present. Add relevant terms.")
    else:
        unique_ratio = len(set(words)) / word_count
        kw_score = 50.0 + unique_ratio * 40.0

    if target_audience:
        audience_tokens = set(_WORD_RE.findall(target_audience.lower()))
        overlap = sum(1 for t in audience_tokens if t in text_lower and len(t) > 3)
        audience_bonus = min(15.0, overlap * 5.0)
        kw_score += audience_bonus
        if overlap == 0 and len(audience_tokens) > 1:
            issues.append("No audience-specific language detected. Tailor copy to target demographic.")

    return min(100.0, max(0.0, kw_score)), issues


def _compute_ngrams(words: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]


def _score_originality(text: str) -> tuple[float, list[str]]:
    issues: list[str] = []
    words = _WORD_RE.findall(text.lower())
    if len(words) < 10:
        return 60.0, ["Content is very short — originality assessment limited."]

    bigrams = _compute_ngrams(words, 2)
    trigrams = _compute_ngrams(words, 3)

    if bigrams:
        bigram_counts = Counter(bigrams)
        unique_bigrams = sum(1 for c in bigram_counts.values() if c == 1)
        bigram_uniqueness = unique_bigrams / len(bigrams)
    else:
        bigram_uniqueness = 0.5

    if trigrams:
        trigram_counts = Counter(trigrams)
        unique_trigrams = sum(1 for c in trigram_counts.values() if c == 1)
        trigram_uniqueness = unique_trigrams / len(trigrams)
    else:
        trigram_uniqueness = 0.5

    text_lower = text.lower()
    filler_count = sum(1 for p in _FILLER_PHRASES if p in text_lower)
    filler_penalty = filler_count * 8.0

    score = (bigram_uniqueness * 40.0 + trigram_uniqueness * 40.0 + 20.0) - filler_penalty

    repeated_trigrams = [" ".join(ng) for ng, c in Counter(trigrams).items() if c >= 3]
    if repeated_trigrams:
        issues.append(f"Repetitive phrasing detected: {', '.join(repeated_trigrams[:3])}")
        score -= len(repeated_trigrams) * 5.0
    if filler_count > 0:
        issues.append(f"{filler_count} filler phrase(s) detected. Remove for tighter copy.")

    return min(100.0, max(0.0, score)), issues


def _score_engagement(text: str, content_type: str) -> tuple[float, list[str]]:
    issues: list[str] = []
    text_lower = text.lower()
    words = set(_WORD_RE.findall(text_lower))
    word_list = _WORD_RE.findall(text_lower)

    # Hook strength: first sentence analysis
    sentences = [s.strip() for s in _SENTENCE_TERMINATORS.split(text) if s.strip()]
    hook_score = 50.0
    if sentences:
        first = sentences[0].lower()
        first_words = set(_WORD_RE.findall(first))
        power_in_hook = first_words & _POWER_WORDS
        hook_score += len(power_in_hook) * 10.0
        if first.endswith("?"):
            hook_score += 10.0
        if any(trigger in first for trigger in _EMOTIONAL_TRIGGERS):
            hook_score += 12.0
        if len(first.split()) > 25:
            hook_score -= 10.0
            issues.append("Opening sentence is too long. Hooks should be punchy (under 20 words).")
        first_word_lower = first.split()[0] if first.split() else ""
        if first_word_lower in ("you", "your", "stop", "imagine", "what", "how", "why", "this", "here"):
            hook_score += 8.0

    # Emotional trigger density
    emotional_hits = sum(1 for t in _EMOTIONAL_TRIGGERS if t in text_lower)
    emotional_score = min(20.0, emotional_hits * 5.0)

    # Power word density
    power_hits = words & _POWER_WORDS
    power_density = len(power_hits) / max(len(word_list), 1)
    power_score = min(20.0, power_density * 300.0)

    # Question usage (engagement driver)
    question_count = text.count("?")
    question_score = min(10.0, question_count * 3.0)

    total = hook_score * 0.4 + emotional_score + power_score + question_score
    total = min(100.0, max(0.0, total))

    if hook_score < 50:
        issues.append("Weak hook. Start with a question, bold claim, or emotional trigger.")
    if emotional_hits == 0:
        issues.append("No emotional triggers found. Add language that connects on a personal level.")
    if not power_hits:
        issues.append("No power words detected. Inject urgency or desire words.")

    return total, issues


def _score_brand_voice(text: str, brand_keywords: list[str] | None) -> tuple[float, list[str]]:
    issues: list[str] = []
    if not brand_keywords:
        return 70.0, []

    text_lower = text.lower()
    found = sum(1 for kw in brand_keywords if kw.lower() in text_lower)
    ratio = found / max(len(brand_keywords), 1)

    score = 40.0 + ratio * 60.0

    # Tone consistency: check for spam words that break brand trust
    spam_found = [w for w in _SPAM_WORDS if w.lower() in text_lower]
    if spam_found:
        score -= len(spam_found) * 10.0
        issues.append(f"Spammy language detected: {', '.join(spam_found[:3])}. Adjust tone.")

    if ratio < 0.3:
        issues.append(f"Brand voice alignment is low ({found}/{len(brand_keywords)} keywords). Infuse brand language.")

    return min(100.0, max(0.0, score)), issues


def _score_cta_strength(text: str, content_type: str) -> tuple[float, list[str]]:
    issues: list[str] = []
    text_lower = text.lower()

    cta_hits = [p for p in _CTA_PHRASES if p in text_lower]
    sentences = [s.strip() for s in _SENTENCE_TERMINATORS.split(text) if s.strip()]
    last_sentence = sentences[-1].lower() if sentences else ""

    # CTA presence
    if not cta_hits:
        score = 20.0
        issues.append("No call-to-action detected. Add a clear, direct CTA.")
    else:
        score = 50.0 + min(30.0, len(cta_hits) * 10.0)

    # CTA in final position (strongest placement)
    cta_in_closing = any(p in last_sentence for p in _CTA_PHRASES)
    if cta_in_closing:
        score += 15.0
    elif cta_hits:
        issues.append("CTA is not at the end. Move your strongest CTA to the closing sentence.")

    # Urgency amplifiers near CTA
    urgency_words = {"now", "today", "limited", "last chance", "hurry", "don't miss", "before"}
    if any(u in text_lower for u in urgency_words):
        score += 10.0
    else:
        if content_type in ("hook", "email", "caption"):
            issues.append("Consider adding urgency language near your CTA.")

    # Penalise too many CTAs (dilution)
    if len(cta_hits) > 3:
        score -= (len(cta_hits) - 3) * 5.0
        issues.append("Too many CTAs dilute conversion. Focus on one primary action.")

    return min(100.0, max(0.0, score)), issues


# Dimension weights for the overall score
_QUALITY_DIMENSION_WEIGHTS: dict[str, float] = {
    "readability": 0.15,
    "relevance": 0.18,
    "originality": 0.12,
    "engagement_potential": 0.22,
    "brand_voice": 0.13,
    "cta_strength": 0.20,
}


def score_text_quality(
    text: str,
    content_type: str = "caption",
    brand_voice_keywords: list[str] | None = None,
    target_audience: str = "",
    min_score: float = 70.0,
) -> QualityReport:
    """Multi-dimensional content quality scoring across 6 dimensions."""
    content_id = hashlib.sha256(text.encode()).hexdigest()[:16]

    if not text or not text.strip():
        return QualityReport(
            content_id=content_id,
            overall_score=0.0,
            passed=False,
            dimension_scores={d: 0.0 for d in _QUALITY_DIMENSION_WEIGHTS},
            issues=["Empty content provided."],
            improvement_suggestions=["Provide actual content to evaluate."],
            regeneration_recommended=True,
            estimated_revenue_impact=-5.0,
        )

    all_issues: list[str] = []
    dim_scores: dict[str, float] = {}

    readability, r_issues = _score_readability(text, content_type)
    dim_scores["readability"] = round(readability, 2)
    all_issues.extend(r_issues)

    relevance, rel_issues = _score_relevance(text, brand_voice_keywords, target_audience)
    dim_scores["relevance"] = round(relevance, 2)
    all_issues.extend(rel_issues)

    originality, o_issues = _score_originality(text)
    dim_scores["originality"] = round(originality, 2)
    all_issues.extend(o_issues)

    engagement, e_issues = _score_engagement(text, content_type)
    dim_scores["engagement_potential"] = round(engagement, 2)
    all_issues.extend(e_issues)

    brand_voice, bv_issues = _score_brand_voice(text, brand_voice_keywords)
    dim_scores["brand_voice"] = round(brand_voice, 2)
    all_issues.extend(bv_issues)

    cta, cta_issues = _score_cta_strength(text, content_type)
    dim_scores["cta_strength"] = round(cta, 2)
    all_issues.extend(cta_issues)

    # Weighted overall
    overall = sum(dim_scores[d] * _QUALITY_DIMENSION_WEIGHTS[d] for d in _QUALITY_DIMENSION_WEIGHTS)
    overall = round(overall, 2)
    passed = overall >= min_score

    # Improvement suggestions based on weakest dimensions
    sorted_dims = sorted(dim_scores.items(), key=lambda x: x[1])
    suggestions: list[str] = []
    for dim_name, dim_val in sorted_dims[:3]:
        if dim_val < 70.0:
            suggestions.append(f"Improve {dim_name} (score: {dim_val:.0f}/100).")

    regen = overall < (min_score * 0.8) or any(d < 30.0 for d in dim_scores.values())

    # RPM impact estimate: +/- based on distance from 75 (average content)
    rpm_delta = (overall - 75.0) * 0.06  # rough: each point above 75 = +$0.06 RPM

    return QualityReport(
        content_id=content_id,
        overall_score=overall,
        passed=passed,
        dimension_scores=dim_scores,
        issues=all_issues,
        improvement_suggestions=suggestions,
        regeneration_recommended=regen,
        estimated_revenue_impact=round(rpm_delta, 2),
    )


def should_regenerate(
    quality_report: QualityReport,
    attempt_number: int,
    max_attempts: int = 3,
) -> tuple[bool, str]:
    """Decide whether to regenerate content based on quality and attempt count."""
    if attempt_number >= max_attempts:
        if quality_report.overall_score >= 40.0:
            return False, "max_attempts_reached_acceptable"
        return False, "max_attempts_reached_low_quality"

    if quality_report.passed:
        return False, "quality_passed"

    if quality_report.overall_score < 30.0:
        return True, "critically_low_quality"

    if quality_report.regeneration_recommended:
        return True, "below_threshold_regen_recommended"

    critical_dims = ["engagement_potential", "cta_strength", "readability"]
    for d in critical_dims:
        if quality_report.dimension_scores.get(d, 100.0) < 35.0:
            return True, f"critical_dimension_failure:{d}"

    improvement_possible = (max_attempts - attempt_number) >= 1
    if improvement_possible and quality_report.overall_score < 60.0:
        return True, "marginal_quality_retry_available"

    return False, "acceptable_within_tolerance"


class QualityGateManager:
    """Manages the quality gate pipeline for all content types."""

    def __init__(self, min_scores: dict[str, float] | None = None):
        self._min_scores: dict[str, float] = min_scores or {
            "hook": 75.0,
            "script": 70.0,
            "caption": 65.0,
            "email": 72.0,
            "blog": 68.0,
        }
        self._default_min = 70.0
        self._history: list[QualityReport] = []

    @property
    def history(self) -> list[QualityReport]:
        return list(self._history)

    def _min_for(self, content_type: str) -> float:
        return self._min_scores.get(content_type, self._default_min)

    def evaluate(
        self,
        content: str,
        content_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> QualityReport:
        meta = metadata or {}
        report = score_text_quality(
            text=content,
            content_type=content_type,
            brand_voice_keywords=meta.get("brand_keywords"),
            target_audience=meta.get("target_audience", ""),
            min_score=self._min_for(content_type),
        )
        self._history.append(report)
        return report

    def evaluate_and_decide(
        self,
        content: str,
        content_type: str,
        attempt: int = 1,
        metadata: dict[str, Any] | None = None,
        max_attempts: int = 3,
    ) -> tuple[QualityReport, bool, str]:
        """Returns (report, should_proceed, action_instruction)."""
        report = self.evaluate(content, content_type, metadata)
        regen, reason = should_regenerate(report, attempt, max_attempts)

        if report.passed:
            return report, True, "publish"

        if regen:
            # Build targeted regeneration instructions
            weak_dims = sorted(report.dimension_scores.items(), key=lambda x: x[1])[:2]
            focus_areas = ", ".join(f"{d} ({v:.0f}/100)" for d, v in weak_dims)
            instruction = f"regenerate — focus on: {focus_areas}. {'; '.join(report.improvement_suggestions[:2])}"
            return report, False, instruction

        return report, True, "publish_with_warning"

    def batch_evaluate(
        self,
        items: list[dict[str, Any]],
    ) -> list[tuple[QualityReport, bool, str]]:
        """Evaluate a batch of content items."""
        results: list[tuple[QualityReport, bool, str]] = []
        for item in items:
            r = self.evaluate_and_decide(
                content=item.get("content", ""),
                content_type=item.get("content_type", "caption"),
                attempt=item.get("attempt", 1),
                metadata=item.get("metadata"),
                max_attempts=item.get("max_attempts", 3),
            )
            results.append(r)
        return results

    def summary_stats(self) -> dict[str, Any]:
        if not self._history:
            return {"total": 0}
        scores = [r.overall_score for r in self._history]
        passed = sum(1 for r in self._history if r.passed)
        return {
            "total": len(self._history),
            "passed": passed,
            "failed": len(self._history) - passed,
            "pass_rate": round(passed / len(self._history), 4),
            "avg_score": round(sum(scores) / len(scores), 2),
            "min_score": round(min(scores), 2),
            "max_score": round(max(scores), 2),
            "regen_recommended": sum(1 for r in self._history if r.regeneration_recommended),
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4.  A/B  CONTENT  EXPERIMENTATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@dataclass
class ExperimentVariant:
    variant_id: str
    name: str
    content_params: dict[str, Any]
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    revenue: float = 0.0

    @property
    def ctr(self) -> float:
        return self.clicks / max(self.impressions, 1)

    @property
    def conversion_rate(self) -> float:
        return self.conversions / max(self.impressions, 1)

    @property
    def revenue_per_impression(self) -> float:
        return self.revenue / max(self.impressions, 1)

    def record_event(self, event_type: str, revenue: float = 0.0) -> None:
        self.impressions += 1 if event_type == "impression" else 0
        self.clicks += 1 if event_type == "click" else 0
        if event_type == "conversion":
            self.conversions += 1
            self.revenue += revenue


@dataclass
class Experiment:
    experiment_id: str
    name: str
    variants: list[ExperimentVariant]
    status: str = "running"  # "running", "concluded", "stopped"
    start_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    min_sample_size: int = 200
    confidence_threshold: float = 0.95

    @property
    def total_impressions(self) -> int:
        return sum(v.impressions for v in self.variants)

    @property
    def control(self) -> ExperimentVariant | None:
        return self.variants[0] if self.variants else None

    def get_variant(self, variant_id: str) -> ExperimentVariant | None:
        for v in self.variants:
            if v.variant_id == variant_id:
                return v
        return None


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using the Abramowitz & Stegun approximation (|error| < 7.5e-8)."""
    if x < -8.0:
        return 0.0
    if x > 8.0:
        return 1.0
    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    poly = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    cdf = 1.0 - d * math.exp(-0.5 * x * x) * poly
    return 0.5 + sign * (cdf - 0.5)


def _norm_ppf(p: float) -> float:
    """Inverse normal CDF (percent-point function) via rational approximation.

    Accurate to ~4.5e-4 across (0, 1).  Uses the Beasley-Springer-Moro algorithm.
    """
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0

    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )


def compute_experiment_significance(
    control: ExperimentVariant,
    treatment: ExperimentVariant,
) -> dict[str, Any]:
    """Statistical significance testing using Z-test for proportions.

    Returns z-score, p-value, confidence interval, winner determination,
    effect size (Cohen's h), and estimated sample size to reach significance.
    """
    n_c = max(control.impressions, 1)
    n_t = max(treatment.impressions, 1)
    p_c = control.conversion_rate
    p_t = treatment.conversion_rate

    # Pooled proportion under H0
    pooled = (control.conversions + treatment.conversions) / (n_c + n_t) if (n_c + n_t) > 0 else 0.0
    pooled = max(min(pooled, 0.9999), 0.0001)

    se = math.sqrt(pooled * (1.0 - pooled) * (1.0 / n_c + 1.0 / n_t))
    se = max(se, 1e-10)

    z_score = (p_t - p_c) / se
    p_value = 2.0 * (1.0 - _norm_cdf(abs(z_score)))

    # Confidence interval for the difference (p_t - p_c) using unpooled SE
    se_diff = math.sqrt((p_c * (1.0 - p_c) / n_c) + (p_t * (1.0 - p_t) / n_t)) if n_c > 1 and n_t > 1 else se
    se_diff = max(se_diff, 1e-10)
    z_95 = 1.96
    ci_lower = (p_t - p_c) - z_95 * se_diff
    ci_upper = (p_t - p_c) + z_95 * se_diff

    # Cohen's h: effect size for proportions
    def _arcsin_transform(p: float) -> float:
        return 2.0 * math.asin(math.sqrt(max(min(p, 1.0), 0.0)))

    cohens_h = abs(_arcsin_transform(p_t) - _arcsin_transform(p_c))

    # Effect size interpretation
    if cohens_h < 0.2:
        effect_size_label = "negligible"
    elif cohens_h < 0.5:
        effect_size_label = "small"
    elif cohens_h < 0.8:
        effect_size_label = "medium"
    else:
        effect_size_label = "large"

    # Required sample size to detect the observed difference at 80% power, alpha=0.05
    z_alpha = 1.96
    z_beta = 0.842  # 80% power
    effect = abs(p_t - p_c)
    if effect > 0.0001:
        avg_p = (p_c + p_t) / 2.0
        required_n = math.ceil(((z_alpha + z_beta) ** 2 * 2.0 * avg_p * (1.0 - avg_p)) / (effect**2))
    else:
        required_n = 999_999

    # Winner determination
    is_significant = p_value < 0.05
    if is_significant:
        winner = treatment.variant_id if p_t > p_c else control.variant_id
        winner_label = treatment.name if p_t > p_c else control.name
    else:
        winner = None
        winner_label = "no winner yet"

    # Relative lift
    relative_lift = ((p_t - p_c) / p_c) if p_c > 0.0001 else 0.0

    # Revenue analysis
    rpi_c = control.revenue_per_impression
    rpi_t = treatment.revenue_per_impression
    revenue_lift = rpi_t - rpi_c
    revenue_lift_pct = (revenue_lift / rpi_c * 100.0) if rpi_c > 0.0001 else 0.0

    # Revenue confidence interval (approximate using same SE scaling)
    se_rev = math.sqrt((_variance_estimate(control) / n_c) + (_variance_estimate(treatment) / n_t))
    rev_ci_lower = revenue_lift - z_95 * se_rev
    rev_ci_upper = revenue_lift + z_95 * se_rev

    return {
        "z_score": round(z_score, 4),
        "p_value": round(p_value, 6),
        "is_significant": is_significant,
        "confidence_level": round(1.0 - p_value, 4),
        "ci_95_lower": round(ci_lower, 6),
        "ci_95_upper": round(ci_upper, 6),
        "cohens_h": round(cohens_h, 4),
        "effect_size_label": effect_size_label,
        "winner": winner,
        "winner_label": winner_label,
        "control_rate": round(p_c, 6),
        "treatment_rate": round(p_t, 6),
        "relative_lift_pct": round(relative_lift * 100.0, 2),
        "required_sample_per_arm": required_n,
        "current_sample_control": n_c,
        "current_sample_treatment": n_t,
        "sample_pct_complete": round(min(n_c, n_t) / max(required_n, 1) * 100.0, 1),
        "revenue_per_impression_control": round(rpi_c, 6),
        "revenue_per_impression_treatment": round(rpi_t, 6),
        "revenue_lift_per_impression": round(revenue_lift, 6),
        "revenue_lift_pct": round(revenue_lift_pct, 2),
        "revenue_ci_95_lower": round(rev_ci_lower, 6),
        "revenue_ci_95_upper": round(rev_ci_upper, 6),
    }


def _variance_estimate(v: ExperimentVariant) -> float:
    """Estimate per-impression revenue variance from available data."""
    n = max(v.impressions, 1)
    v.revenue / n
    # Without per-event data, approximate variance using Bernoulli-like bound
    p = v.conversion_rate
    avg_rev_per_conv = v.revenue / max(v.conversions, 1)
    return p * (1.0 - p) * (avg_rev_per_conv**2)


def recommend_experiment_action(experiment: Experiment) -> dict[str, Any]:
    """Recommend whether to continue, stop, or declare a winner."""
    if len(experiment.variants) < 2:
        return {
            "action": "error",
            "reason": "Need at least 2 variants (control + treatment).",
            "experiment_id": experiment.experiment_id,
        }

    control = experiment.variants[0]
    best_treatment: ExperimentVariant | None = None
    best_result: dict[str, Any] | None = None
    all_results: list[dict[str, Any]] = []

    for treatment in experiment.variants[1:]:
        result = compute_experiment_significance(control, treatment)
        result["variant_id"] = treatment.variant_id
        result["variant_name"] = treatment.name
        all_results.append(result)

        if best_result is None or result["relative_lift_pct"] > best_result["relative_lift_pct"]:
            best_result = result
            best_treatment = treatment

    if best_result is None:
        return {"action": "error", "reason": "No treatment results computed."}

    total_n = experiment.total_impressions
    min_reached = all(v.impressions >= experiment.min_sample_size for v in experiment.variants)

    # Decision tree
    if best_result["is_significant"] and min_reached:
        if best_result["relative_lift_pct"] > 0:
            action = "declare_winner"
            reason = (
                f"{best_treatment.name} wins with {best_result['relative_lift_pct']:.1f}% lift "
                f"(p={best_result['p_value']:.4f}, n={best_treatment.impressions})"
            )
        else:
            action = "declare_winner"
            reason = (
                f"Control ({control.name}) wins — treatment showed "
                f"{best_result['relative_lift_pct']:.1f}% change (p={best_result['p_value']:.4f})"
            )
    elif not min_reached:
        smallest = min(v.impressions for v in experiment.variants)
        pct_done = smallest / max(experiment.min_sample_size, 1) * 100
        action = "continue"
        reason = f"Minimum sample not yet reached ({smallest}/{experiment.min_sample_size}, {pct_done:.0f}% complete)"
    elif best_result["p_value"] < 0.10:
        action = "continue"
        reason = (
            f"Trending toward significance (p={best_result['p_value']:.4f}). "
            f"Estimated {best_result['required_sample_per_arm']} samples per arm needed."
        )
    elif total_n > experiment.min_sample_size * 5:
        action = "stop_inconclusive"
        reason = (
            f"5× min sample reached ({total_n} impressions) with no significance. "
            f"Effect too small to detect reliably (Cohen's h={best_result['cohens_h']:.3f})."
        )
    else:
        action = "continue"
        reason = f"Not yet significant (p={best_result['p_value']:.4f}). More data needed."

    # Revenue projection if winner is declared
    projected_monthly_revenue_delta = 0.0
    if action == "declare_winner" and best_result["revenue_lift_per_impression"] != 0:
        avg_monthly_impressions = total_n * 30.0 / max((datetime.now(timezone.utc) - experiment.start_date).days, 1)
        projected_monthly_revenue_delta = best_result["revenue_lift_per_impression"] * avg_monthly_impressions

    return {
        "experiment_id": experiment.experiment_id,
        "experiment_name": experiment.name,
        "action": action,
        "reason": reason,
        "confidence_threshold": experiment.confidence_threshold,
        "total_impressions": total_n,
        "min_sample_size": experiment.min_sample_size,
        "best_treatment": {
            "variant_id": best_treatment.variant_id if best_treatment else None,
            "name": best_treatment.name if best_treatment else None,
        },
        "significance_results": all_results,
        "projected_monthly_revenue_delta": round(projected_monthly_revenue_delta, 2),
    }


def create_experiment(
    name: str,
    variant_configs: list[dict[str, Any]],
    min_sample_size: int = 200,
    confidence_threshold: float = 0.95,
) -> Experiment:
    """Factory for creating a properly initialised experiment."""
    variants = []
    for i, cfg in enumerate(variant_configs):
        vid = cfg.get("variant_id", f"v{i}")
        vname = cfg.get("name", f"Variant {i}" if i > 0 else "Control")
        variants.append(
            ExperimentVariant(
                variant_id=vid,
                name=vname,
                content_params=cfg.get("params", {}),
            )
        )
    return Experiment(
        experiment_id=uuid.uuid4().hex[:12],
        name=name,
        variants=variants,
        min_sample_size=min_sample_size,
        confidence_threshold=confidence_threshold,
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5.  CONVENIENCE / ORCHESTRATION FACADE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def route_and_gate(
    task_type: str,
    quality_requirement: str,
    content: str,
    budget: float = 1.0,
    brand_keywords: list[str] | None = None,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """End-to-end: select a model, then quality-gate the content it would produce.

    This is a dry-run evaluator — it routes to the best model and scores the
    provided content as if that model produced it. Useful for pipeline simulation
    and post-generation gating.
    """
    model_id, routing = select_optimal_model(
        task_type=task_type,
        quality_requirement=quality_requirement,
        max_cost_per_unit=budget,
    )
    cost_est = compute_task_cost_estimate(model_id, len(content.split()) * 2, len(content.split()))

    gate = QualityGateManager()
    report, proceed, instruction = gate.evaluate_and_decide(
        content=content,
        content_type=_extract_media_type(task_type),
        attempt=1,
        metadata={"brand_keywords": brand_keywords},
        max_attempts=max_attempts,
    )

    return {
        "model_id": model_id,
        "routing": routing,
        "cost_estimate": cost_est,
        "quality_report": {
            "overall_score": report.overall_score,
            "passed": report.passed,
            "dimensions": report.dimension_scores,
            "issues": report.issues,
            "suggestions": report.improvement_suggestions,
        },
        "proceed": proceed,
        "instruction": instruction,
    }

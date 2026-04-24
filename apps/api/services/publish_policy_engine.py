"""Publish Policy Engine — deterministic, first-match rule evaluation.

Evaluates content against publish_policy_rules in priority order.
First matching rule wins. No LLM calls. Pure rules. Fast and auditable.

Tiers:
    auto_publish      — auto-approve, publish worker picks up
    sample_review     — auto-approve, flag deterministic sample for async review
    manual_approval   — hold for human approval
    block             — reject, create operator action
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.publish_policy import PublishPolicyRule

logger = structlog.get_logger()

# ── In-memory rule cache (60-second TTL) ─────────────────────────────────────

_rule_cache: dict[str, tuple[float, list[PublishPolicyRule]]] = {}
_CACHE_TTL = 60.0


async def _load_rules(db: AsyncSession, brand_id: uuid.UUID) -> list[PublishPolicyRule]:
    """Load active rules for a brand, preferring brand-specific over global.

    Returns rules ordered by priority ASC, created_at ASC.
    """
    cache_key = str(brand_id)
    now = time.monotonic()
    if cache_key in _rule_cache:
        cached_at, cached_rules = _rule_cache[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_rules

    result = await db.execute(
        select(PublishPolicyRule)
        .where(
            PublishPolicyRule.is_active.is_(True),
            (PublishPolicyRule.brand_id == brand_id) | (PublishPolicyRule.brand_id.is_(None)),
        )
        .order_by(PublishPolicyRule.priority.asc(), PublishPolicyRule.created_at.asc())
    )
    rules = list(result.scalars().all())
    _rule_cache[cache_key] = (now, rules)
    return rules


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass
class PublishPolicyResult:
    tier: str                       # auto_publish | sample_review | manual_approval | block
    rule_id: uuid.UUID | None    # Which rule matched
    rule_name: str                  # Human-readable name
    sample_flagged: bool            # If sample_review, was this item selected?
    explanation: str                # Why this tier was chosen
    factors: dict = field(default_factory=dict)  # All evaluated factors for audit


# ── Deterministic sampling ───────────────────────────────────────────────────


def _deterministic_sample(content_id: uuid.UUID, sample_rate: float) -> bool:
    """Deterministic yes/no for sample review. Same content_id always returns same answer."""
    if sample_rate <= 0.0:
        return False
    if sample_rate >= 1.0:
        return True
    digest = hashlib.md5(str(content_id).encode()).digest()
    return (digest[0] / 255.0) < sample_rate


# ── Context builder ──────────────────────────────────────────────────────────


def build_policy_context(
    content_item: Any,
    qa_score: float | None = None,
    confidence: str | None = None,
    account_health: str | None = None,
    account_age_days: int | None = None,
    governance_level: str | None = None,
) -> dict:
    """Assemble the factor dict from content item and related data."""
    tags = []
    if hasattr(content_item, "tags") and content_item.tags:
        tags = content_item.tags if isinstance(content_item.tags, list) else []

    return {
        "content_type": getattr(content_item, "content_type", None),
        "platform": getattr(content_item, "platform", None),
        "monetization_method": getattr(content_item, "monetization_method", None),
        "hook_type": getattr(content_item, "hook_type", None),
        "creative_structure": getattr(content_item, "creative_structure", None),
        "has_offer": getattr(content_item, "offer_id", None) is not None,
        "tags": tags,
        "qa_score": qa_score,
        "confidence": confidence,
        "account_health": account_health,
        "account_age_days": account_age_days,
        "governance_level": governance_level,
    }


# ── Rule matching ────────────────────────────────────────────────────────────

_CONFIDENCE_ORDER = {"high": 3, "medium": 2, "low": 1, "insufficient": 0}


def _rule_matches(rule: PublishPolicyRule, ctx: dict) -> bool:
    """Check if all non-NULL fields on the rule match the context. NULL = wildcard."""

    # String equality checks (NULL on rule = don't care)
    string_checks = [
        (rule.match_content_type, ctx.get("content_type")),
        (rule.match_platform, ctx.get("platform")),
        (rule.match_monetization_method, ctx.get("monetization_method")),
        (rule.match_hook_type, ctx.get("hook_type")),
        (rule.match_creative_structure, ctx.get("creative_structure")),
        (rule.match_account_health, ctx.get("account_health")),
        (rule.match_governance_level, ctx.get("governance_level")),
    ]
    for rule_val, ctx_val in string_checks:
        if rule_val is not None:
            # Normalize both sides for enum-value comparison
            rv = str(rule_val).lower().strip() if rule_val else ""
            cv = str(ctx_val).lower().strip() if ctx_val else ""
            if rv != cv:
                return False

    # QA score range checks
    qa = ctx.get("qa_score")
    if rule.min_qa_score is not None:
        if qa is None or qa < rule.min_qa_score:
            return False
    if rule.max_qa_score is not None:
        if qa is not None and qa >= rule.max_qa_score:
            return False

    # Account age check (match if account is NEWER than threshold)
    if rule.max_account_age_days is not None:
        age = ctx.get("account_age_days")
        if age is None or age > rule.max_account_age_days:
            return False

    # Confidence level check
    if rule.min_confidence is not None:
        ctx_conf = _CONFIDENCE_ORDER.get(str(ctx.get("confidence", "insufficient")).lower(), 0)
        rule_conf = _CONFIDENCE_ORDER.get(str(rule.min_confidence).lower(), 0)
        if ctx_conf < rule_conf:
            return False

    # Offer presence check
    if rule.match_has_offer is not None:
        if rule.match_has_offer != ctx.get("has_offer", False):
            return False

    # Tag sensitivity check (match if content tags contain ANY of the rule's tags)
    if rule.match_tags_contain:
        content_tags = set(str(t).lower() for t in (ctx.get("tags") or []))
        rule_tags = set(str(t).lower() for t in rule.match_tags_contain)
        if not content_tags.intersection(rule_tags):
            return False

    return True


# ── Main evaluation function ─────────────────────────────────────────────────


async def evaluate_publish_policy(
    db: AsyncSession,
    content_item: Any,
    qa_score: float | None = None,
    confidence: str | None = None,
    account_health: str | None = None,
    account_age_days: int | None = None,
    governance_level: str | None = None,
) -> PublishPolicyResult:
    """Evaluate content against publish policy rules. Returns the tier decision.

    SAFETY: If qa_score is None/missing, defaults to manual_approval (not auto_publish).
    """
    brand_id = getattr(content_item, "brand_id", None)
    content_id = getattr(content_item, "id", None)

    ctx = build_policy_context(
        content_item,
        qa_score=qa_score,
        confidence=confidence,
        account_health=account_health,
        account_age_days=account_age_days,
        governance_level=governance_level,
    )

    # Safety: if qa_score is None/missing, we cannot auto-publish
    qa_is_missing = qa_score is None

    rules = await _load_rules(db, brand_id) if brand_id else []

    matched_rule = None
    for rule in rules:
        if _rule_matches(rule, ctx):
            matched_rule = rule
            break

    if matched_rule is None:
        # No rule matched — safe fallback
        result = PublishPolicyResult(
            tier="manual_approval",
            rule_id=None,
            rule_name="no_rule_matched",
            sample_flagged=False,
            explanation="No publish policy rule matched. Defaulting to manual approval.",
            factors=ctx,
        )
    else:
        tier = matched_rule.tier

        # Safety override: never auto-publish if QA score is missing
        if qa_is_missing and tier in ("auto_publish", "sample_review"):
            tier = "manual_approval"
            explanation = (
                f"Rule '{matched_rule.name}' (priority {matched_rule.priority}) matched for "
                f"{matched_rule.tier}, but qa_score is missing. Overriding to manual_approval."
            )
        else:
            explanation = (
                f"Rule '{matched_rule.name}' (priority {matched_rule.priority}): {tier}. "
                f"{matched_rule.description or ''}"
            )

        sample_flagged = False
        if tier == "sample_review" and content_id:
            sample_flagged = _deterministic_sample(content_id, matched_rule.sample_rate)

        result = PublishPolicyResult(
            tier=tier,
            rule_id=matched_rule.id,
            rule_name=matched_rule.name,
            sample_flagged=sample_flagged,
            explanation=explanation,
            factors=ctx,
        )

    # Structured log for every decision
    logger.info(
        "publish_policy_decision",
        content_id=str(content_id),
        brand_id=str(brand_id),
        matched_rule_name=result.rule_name,
        matched_rule_priority=matched_rule.priority if matched_rule else None,
        resulting_tier=result.tier,
        sample_flagged=result.sample_flagged,
        qa_score=qa_score,
        confidence=confidence,
        tags=ctx.get("tags"),
        monetization_method=ctx.get("monetization_method"),
        account_health=account_health,
        explanation=result.explanation,
    )

    return result

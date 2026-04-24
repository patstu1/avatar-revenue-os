"""Intelligence Bridge — connects the intelligence layer to the control layer.

The intelligence layer (brain decisions, pattern memory, experiments, failure
families, discovery) already computes rich outputs. This bridge service:

1. Reads intelligence outputs and translates them into OperatorActions
2. Creates SystemEvents when intelligence produces notable insights
3. Builds a unified intelligence summary for the control layer
4. Connects pattern memory to content generation parameters
5. Enforces kill ledger by checking experiments before generation

This is the missing horizontal connection that makes intelligence
influence action rather than just exist as reports.
"""
import uuid
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from packages.db.models.brain_architecture import (
    AccountStateSnapshot,
)
from packages.db.models.brain_phase_b import (
    BrainDecision,
)
from packages.db.models.core import Brand
from packages.db.models.failure_family import FailureFamilyReport, SuppressionRule
from packages.db.models.kill_ledger import KillLedgerEntry
from packages.db.models.pattern_memory import (
    LosingPatternMemory,
    PatternDecayReport,
    WinningPatternMemory,
)
from packages.db.models.promote_winner import (
    ActiveExperiment,
    PromotedWinnerRule,
    PWExperimentWinner,
)
from packages.db.models.scoring import RecommendationQueue

logger = structlog.get_logger()


# ── Intelligence Summary for Control Layer ──────────────────────────────

async def get_intelligence_summary(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: Optional[uuid.UUID] = None,
) -> dict:
    """Build a unified intelligence summary for the control layer.

    This aggregates outputs from all intelligence subsystems into a single
    actionable view the operator can use to make decisions.
    """
    brand_filter = Brand.organization_id == org_id
    if brand_id:
        brand_ids = [brand_id]
    else:
        q = await db.execute(select(Brand.id).where(brand_filter))
        brand_ids = [r[0] for r in q.all()]

    if not brand_ids:
        return _empty_summary()

    # --- Active brain decisions ---
    decisions_q = await db.execute(
        select(BrainDecision)
        .where(BrainDecision.brand_id.in_(brand_ids), BrainDecision.is_active.is_(True))
        .order_by(BrainDecision.expected_upside.desc().nullslast())
        .limit(10)
    )
    active_decisions = decisions_q.scalars().all()

    # --- Winning patterns ---
    winners_q = await db.execute(
        select(WinningPatternMemory)
        .where(WinningPatternMemory.brand_id.in_(brand_ids), WinningPatternMemory.is_active.is_(True))
        .order_by(WinningPatternMemory.win_score.desc())
        .limit(10)
    )
    top_patterns = winners_q.scalars().all()

    # --- Pattern decay alerts ---
    decay_q = await db.execute(
        select(PatternDecayReport)
        .where(PatternDecayReport.brand_id.in_(brand_ids))
        .order_by(PatternDecayReport.created_at.desc())
        .limit(5)
    )
    decaying_patterns = decay_q.scalars().all()

    # --- Active experiments ---
    experiments_q = await db.execute(
        select(ActiveExperiment)
        .where(ActiveExperiment.brand_id.in_(brand_ids), ActiveExperiment.status == "active")
        .order_by(ActiveExperiment.created_at.desc())
        .limit(10)
    )
    active_experiments = experiments_q.scalars().all()

    # --- Promoted winner rules ---
    rules_q = await db.execute(
        select(PromotedWinnerRule)
        .where(PromotedWinnerRule.brand_id.in_(brand_ids), PromotedWinnerRule.is_active.is_(True))
        .order_by(PromotedWinnerRule.weight_boost.desc())
        .limit(10)
    )
    promoted_rules = rules_q.scalars().all()

    # --- Active suppression rules ---
    suppressions_q = await db.execute(
        select(SuppressionRule)
        .where(SuppressionRule.brand_id.in_(brand_ids), SuppressionRule.is_active.is_(True))
        .limit(10)
    )
    active_suppressions = suppressions_q.scalars().all()

    # --- Failure families ---
    failures_q = await db.execute(
        select(FailureFamilyReport)
        .where(FailureFamilyReport.brand_id.in_(brand_ids))
        .order_by(FailureFamilyReport.failure_count.desc())
        .limit(5)
    )
    top_failures = failures_q.scalars().all()

    # --- Kill ledger ---
    killed_q = await db.execute(
        select(KillLedgerEntry)
        .where(KillLedgerEntry.brand_id.in_(brand_ids), KillLedgerEntry.is_active.is_(True))
        .order_by(KillLedgerEntry.created_at.desc())
        .limit(5)
    )
    kill_entries = killed_q.scalars().all()

    # --- Top opportunities ---
    opps_q = await db.execute(
        select(RecommendationQueue)
        .where(RecommendationQueue.brand_id.in_(brand_ids))
        .order_by(RecommendationQueue.composite_score.desc())
        .limit(5)
    )
    top_opportunities = opps_q.scalars().all()

    # --- Account states ---
    acct_states_q = await db.execute(
        select(AccountStateSnapshot)
        .where(AccountStateSnapshot.brand_id.in_(brand_ids), AccountStateSnapshot.is_active.is_(True))
        .order_by(AccountStateSnapshot.state_score.asc())
        .limit(10)
    )
    account_states = acct_states_q.scalars().all()

    return {
        "active_decisions": [
            {
                "id": str(d.id),
                "decision_class": d.decision_class,
                "objective": d.objective,
                "selected_action": d.selected_action,
                "confidence": d.confidence,
                "expected_upside": d.expected_upside,
                "expected_cost": d.expected_cost,
                "explanation": d.explanation,
            }
            for d in active_decisions
        ],
        "top_patterns": [
            {
                "id": str(p.id),
                "pattern_type": p.pattern_type,
                "pattern_name": p.pattern_name,
                "win_score": p.win_score,
                "confidence": p.confidence,
                "usage_count": p.usage_count,
                "performance_band": p.performance_band,
                "platform": p.platform,
            }
            for p in top_patterns
        ],
        "decaying_patterns": [
            {
                "id": str(d.id),
                "decay_rate": d.decay_rate,
                "decay_reason": d.decay_reason,
                "previous_win_score": d.previous_win_score,
                "current_win_score": d.current_win_score,
                "recommendation": d.recommendation,
            }
            for d in decaying_patterns
        ],
        "active_experiments": [
            {
                "id": str(e.id),
                "tested_variable": e.tested_variable,
                "target_platform": e.target_platform,
                "primary_metric": e.primary_metric,
                "status": e.status,
            }
            for e in active_experiments
        ],
        "promoted_rules": [
            {
                "id": str(r.id),
                "rule_type": r.rule_type,
                "rule_key": r.rule_key,
                "rule_value": r.rule_value,
                "weight_boost": r.weight_boost,
                "target_platform": r.target_platform,
            }
            for r in promoted_rules
        ],
        "active_suppressions": [
            {
                "id": str(s.id),
                "family_type": s.family_type,
                "family_key": s.family_key,
                "suppression_mode": s.suppression_mode,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s in active_suppressions
        ],
        "top_failures": [
            {
                "id": str(f.id),
                "family_type": f.family_type,
                "family_key": f.family_key,
                "failure_count": f.failure_count,
                "avg_fail_score": f.avg_fail_score,
                "recommended_alternative": f.recommended_alternative,
            }
            for f in top_failures
        ],
        "kill_ledger": [
            {
                "id": str(k.id),
                "killed_entity_type": k.scope_type,
                "killed_entity_id": str(k.scope_id) if k.scope_id else None,
                "reason": k.kill_reason,
            }
            for k in kill_entries
        ],
        "top_opportunities": [
            {
                "id": str(o.id),
                "rank": o.rank,
                "composite_score": o.composite_score,
                "recommended_action": o.recommended_action,
            }
            for o in top_opportunities
        ],
        "account_health": [
            {
                "id": str(a.id),
                "account_id": str(a.account_id) if a.account_id else None,
                "current_state": a.current_state,
                "state_score": a.state_score,
                "platform": a.platform,
                "days_in_state": a.days_in_state,
            }
            for a in account_states
        ],
        # Aggregate counts
        "counts": {
            "active_decisions": len(active_decisions),
            "winning_patterns": len(top_patterns),
            "decaying_patterns": len(decaying_patterns),
            "active_experiments": len(active_experiments),
            "promoted_rules": len(promoted_rules),
            "active_suppressions": len(active_suppressions),
            "failure_families": len(top_failures),
            "kill_ledger_entries": len(kill_entries),
            "top_opportunities": len(top_opportunities),
        },
    }


def _empty_summary() -> dict:
    return {
        "active_decisions": [],
        "top_patterns": [],
        "decaying_patterns": [],
        "active_experiments": [],
        "promoted_rules": [],
        "active_suppressions": [],
        "top_failures": [],
        "kill_ledger": [],
        "top_opportunities": [],
        "account_health": [],
        "counts": {k: 0 for k in [
            "active_decisions", "winning_patterns", "decaying_patterns",
            "active_experiments", "promoted_rules", "active_suppressions",
            "failure_families", "kill_ledger_entries", "top_opportunities",
        ]},
    }


# ── Translate Intelligence into Operator Actions ──────────────────────

async def surface_intelligence_actions(
    db: AsyncSession,
    org_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> list[dict]:
    """Scan intelligence outputs and create operator actions for notable findings.

    Called by the brain worker after recompute. Translates intelligence
    insights into actionable items for the control layer.
    """
    actions_created = []

    # 1. High-confidence scale decisions → "Scale this account" action
    scale_decisions = await db.execute(
        select(BrainDecision).where(
            BrainDecision.brand_id == brand_id,
            BrainDecision.is_active.is_(True),
            BrainDecision.decision_class == "scale",
            BrainDecision.confidence >= 0.7,
        )
    )
    for d in scale_decisions.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="scale_account",
            title=f"Scale opportunity: {d.objective[:60]}",
            description=f"Brain decision recommends scaling. Action: {d.selected_action}. "
                       f"Expected upside: ${d.expected_upside:.0f}. Confidence: {d.confidence:.0%}.",
            category="opportunity",
            priority="high" if d.expected_upside and d.expected_upside > 100 else "medium",
            brand_id=brand_id,
            entity_type="brain_decision",
            entity_id=d.id,
            source_module="brain_phase_b",
            action_payload={
                "decision_class": d.decision_class,
                "selected_action": d.selected_action,
                "expected_upside": d.expected_upside,
            },
        )
        actions_created.append({"type": "scale", "action_id": str(action.id)})

    # 2. Recovery decisions → "Recover this account" action
    recovery_decisions = await db.execute(
        select(BrainDecision).where(
            BrainDecision.brand_id == brand_id,
            BrainDecision.is_active.is_(True),
            BrainDecision.decision_class == "recover",
        )
    )
    for d in recovery_decisions.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="recover_account",
            title=f"Recovery needed: {d.objective[:60]}",
            description=f"Brain decision flagged recovery. Action: {d.selected_action}. "
                       f"Explanation: {d.explanation[:200] if d.explanation else 'N/A'}",
            category="failure",
            priority="high",
            brand_id=brand_id,
            entity_type="brain_decision",
            entity_id=d.id,
            source_module="brain_phase_b",
        )
        actions_created.append({"type": "recovery", "action_id": str(action.id)})

    # 3. Suppress/throttle/kill decisions → autonomous suppression actions
    suppress_decisions = await db.execute(
        select(BrainDecision).where(
            BrainDecision.brand_id == brand_id,
            BrainDecision.is_active.is_(True),
            BrainDecision.decision_class.in_(["suppress", "throttle", "kill"]),
        )
    )
    for d in suppress_decisions.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="suppress_losing_offer",
            title=f"Brain: {d.decision_class} — {d.objective[:60]}",
            description=f"Action: {d.selected_action}. {d.explanation[:200] if d.explanation else ''}",
            category="monetization", priority="high",
            brand_id=brand_id, entity_type="brain_decision", entity_id=d.id,
            source_module="brain_phase_b",
            action_payload={"autonomy_level": "autonomous", "confidence": d.confidence or 0.7,
                            "decision_class": d.decision_class},
        )
        actions_created.append({"type": d.decision_class, "action_id": str(action.id)})

    # 4. Monetize decisions → attach offer or create monetization flow
    monetize_decisions = await db.execute(
        select(BrainDecision).where(
            BrainDecision.brand_id == brand_id,
            BrainDecision.is_active.is_(True),
            BrainDecision.decision_class == "monetize",
            BrainDecision.confidence >= 0.5,
        )
    )
    for d in monetize_decisions.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="attach_offer_to_content",
            title=f"Monetize: {d.objective[:60]}",
            description=f"Brain recommends monetization. Action: {d.selected_action}. "
                       f"Expected upside: ${d.expected_upside:.0f}." if d.expected_upside else f"Brain: monetize {d.objective[:60]}",
            category="monetization", priority="medium",
            brand_id=brand_id, entity_type="brain_decision", entity_id=d.id,
            source_module="brain_phase_b",
            action_payload={"autonomy_level": "autonomous" if (d.confidence or 0) >= 0.7 else "assisted",
                            "confidence": d.confidence or 0.5},
        )
        actions_created.append({"type": "monetize", "action_id": str(action.id)})

    # 5. Test decisions → experiment launch actions
    test_decisions = await db.execute(
        select(BrainDecision).where(
            BrainDecision.brand_id == brand_id,
            BrainDecision.is_active.is_(True),
            BrainDecision.decision_class == "test",
        )
    )
    for d in test_decisions.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="launch_offer_test",
            title=f"Test: {d.objective[:60]}",
            description=f"Brain recommends testing. {d.explanation[:200] if d.explanation else ''}",
            category="monetization", priority="medium",
            brand_id=brand_id, entity_type="brain_decision", entity_id=d.id,
            source_module="brain_phase_b",
            action_payload={"autonomy_level": "assisted", "confidence": d.confidence or 0.5},
        )
        actions_created.append({"type": "test", "action_id": str(action.id)})

    # 6. Decaying patterns → "Pattern losing effectiveness" alert
    decay_reports = await db.execute(
        select(PatternDecayReport).where(
            PatternDecayReport.brand_id == brand_id,
            PatternDecayReport.decay_rate > 0.2,  # Significant decay
        ).order_by(PatternDecayReport.created_at.desc()).limit(3)
    )
    for d in decay_reports.scalars().all():
        await emit_event(
            db, domain="intelligence", event_type="pattern.decaying",
            summary=f"Pattern losing effectiveness: {d.decay_reason[:80] if d.decay_reason else 'unknown'} "
                   f"(score: {d.previous_win_score:.2f} → {d.current_win_score:.2f})",
            org_id=org_id, brand_id=brand_id,
            entity_type="pattern_decay_report", entity_id=d.id,
            severity="warning",
            details={
                "decay_rate": d.decay_rate,
                "previous_score": d.previous_win_score,
                "current_score": d.current_win_score,
                "recommendation": d.recommendation,
            },
        )

    # 4. Experiment winners → "Promote winning experiment" action
    recent_winners = await db.execute(
        select(PWExperimentWinner).where(
            PWExperimentWinner.brand_id.in_(
                select(ActiveExperiment.brand_id).where(ActiveExperiment.brand_id == brand_id)
            ),
            PWExperimentWinner.promoted.is_(False),
        ).order_by(PWExperimentWinner.created_at.desc()).limit(3)
    )
    for w in recent_winners.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="promote_experiment_winner",
            title=f"Experiment winner detected (margin: {w.win_margin:.1%})",
            description=f"Experiment produced a winner with {w.confidence:.0%} confidence. "
                       f"Review and promote to production rules.",
            category="opportunity",
            priority="medium",
            brand_id=brand_id,
            entity_type="experiment_winner",
            entity_id=w.id,
            source_module="promote_winner",
        )
        actions_created.append({"type": "experiment_winner", "action_id": str(action.id)})

    # 5. High-failure families → "Address failure pattern" action
    high_failures = await db.execute(
        select(FailureFamilyReport).where(
            FailureFamilyReport.brand_id == brand_id,
            FailureFamilyReport.failure_count >= 3,
        ).order_by(FailureFamilyReport.failure_count.desc()).limit(3)
    )
    for f in high_failures.scalars().all():
        action = await emit_action(
            db, org_id=org_id,
            action_type="address_failure_pattern",
            title=f"Recurring failure: {f.family_type} '{f.family_key[:40]}'",
            description=f"This pattern has failed {f.failure_count} times. "
                       f"Recommended alternative: {f.recommended_alternative or 'none suggested'}.",
            category="failure",
            priority="high" if f.failure_count >= 5 else "medium",
            brand_id=brand_id,
            entity_type="failure_family",
            entity_id=f.id,
            source_module="failure_family",
        )
        actions_created.append({"type": "failure_pattern", "action_id": str(action.id)})

    await db.flush()

    logger.info(
        "intelligence_bridge.actions_surfaced",
        brand_id=str(brand_id),
        actions_created=len(actions_created),
    )

    return actions_created


# ── Kill Ledger Enforcement ──────────────────────────────────────────

async def check_kill_ledger(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    entity_type: Optional[str] = None,
    pattern_type: Optional[str] = None,
    pattern_key: Optional[str] = None,
) -> dict:
    """Check the kill ledger before attempting an action.

    Returns whether the action is blocked and why. Should be called
    before content generation, experiment creation, or offer activation
    to prevent repeating known-dead approaches.
    """
    query = select(KillLedgerEntry).where(
        KillLedgerEntry.brand_id == brand_id,
        KillLedgerEntry.is_active.is_(True),
    )

    if entity_type:
        query = query.where(KillLedgerEntry.scope_type == entity_type)

    results = await db.execute(query.limit(50))
    entries = results.scalars().all()

    if not entries:
        return {"blocked": False, "kill_entries": []}

    # Check if any kill entry matches the requested pattern
    matches = []
    for entry in entries:
        detail = entry.detail_json or {}
        entry_pattern_type = detail.get("pattern_type")
        entry_pattern_key = detail.get("pattern_key") or detail.get("family_key")

        if pattern_type and entry_pattern_type == pattern_type:
            if pattern_key and entry_pattern_key == pattern_key:
                matches.append(entry)
            elif not pattern_key:
                matches.append(entry)

    if matches:
        return {
            "blocked": True,
            "reason": f"Kill ledger: {len(matches)} matching entries found",
            "kill_entries": [
                {
                    "id": str(e.id),
                    "killed_entity_type": e.scope_type,
                    "reason": e.kill_reason,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in matches
            ],
        }

    return {"blocked": False, "kill_entries": []}


# ── Pattern Intelligence for Content Generation ─────────────────────

async def get_generation_intelligence(
    db: AsyncSession,
    brand_id: uuid.UUID,
    *,
    platform: Optional[str] = None,
    content_type: Optional[str] = None,
) -> dict:
    """Get intelligence context for content generation.

    Returns winning patterns, losing patterns, suppressed families,
    and promoted rules that should influence the next generation.
    This is called by the content lifecycle service before generation.
    """
    # Winning patterns (boost these)
    win_query = select(WinningPatternMemory).where(
        WinningPatternMemory.brand_id == brand_id,
        WinningPatternMemory.is_active.is_(True),
    ).order_by(WinningPatternMemory.win_score.desc()).limit(8)
    if platform:
        win_query = win_query.where(WinningPatternMemory.platform == platform)

    winners = (await db.execute(win_query)).scalars().all()

    # Losing patterns (avoid these)
    lose_query = select(LosingPatternMemory).where(
        LosingPatternMemory.brand_id == brand_id,
        LosingPatternMemory.is_active.is_(True),
    ).order_by(LosingPatternMemory.fail_score.desc()).limit(5)
    losers = (await db.execute(lose_query)).scalars().all()

    # Suppression rules (block these)
    supp_query = select(SuppressionRule).where(
        SuppressionRule.brand_id == brand_id,
        SuppressionRule.is_active.is_(True),
    ).limit(10)
    suppressions = (await db.execute(supp_query)).scalars().all()

    # Promoted winner rules (highest priority)
    rules_query = select(PromotedWinnerRule).where(
        PromotedWinnerRule.brand_id == brand_id,
        PromotedWinnerRule.is_active.is_(True),
    ).order_by(PromotedWinnerRule.weight_boost.desc()).limit(5)
    if platform:
        rules_query = rules_query.where(PromotedWinnerRule.target_platform == platform)
    promoted = (await db.execute(rules_query)).scalars().all()

    # Kill ledger check
    kill_check = await check_kill_ledger(db, brand_id)

    return {
        "winning_patterns": [
            {
                "type": w.pattern_type,
                "name": w.pattern_name,
                "score": w.win_score,
                "confidence": w.confidence,
                "band": w.performance_band,
            }
            for w in winners
        ],
        "losing_patterns": [
            {
                "type": l.pattern_type,
                "name": l.pattern_name,
                "score": l.fail_score,
                "reason": l.suppress_reason,
            }
            for l in losers
        ],
        "suppressed_families": [
            {
                "type": s.family_type,
                "key": s.family_key,
                "mode": s.suppression_mode,
            }
            for s in suppressions
        ],
        "promoted_rules": [
            {
                "type": r.rule_type,
                "key": r.rule_key,
                "value": r.rule_value,
                "boost": r.weight_boost,
                "platform": r.target_platform,
            }
            for r in promoted
        ],
        "kill_ledger_blocked": kill_check["blocked"],
        "kill_entries": kill_check.get("kill_entries", []),
        "total_intelligence_signals": (
            len(winners) + len(losers) + len(suppressions) + len(promoted)
        ),
    }

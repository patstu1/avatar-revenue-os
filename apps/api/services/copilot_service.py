"""Operator Copilot — sessions, messages, grounded summaries."""
from __future__ import annotations

import os
import uuid

import structlog
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.copilot import CopilotChatMessage, CopilotChatSession
from packages.db.models.core import Brand, User
from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
from packages.scoring.copilot_engine import (
    build_missing_items,
    build_operator_actions,
    build_provider_readiness,
    build_provider_summary,
    build_quick_status,
    generate_grounded_response,
)

logger = structlog.get_logger()


def _message_to_dict(m: CopilotChatMessage) -> dict[str, Any]:
    gs = m.grounding_sources
    if gs is None:
        grounding: list[Any] | None = []
    elif isinstance(gs, list):
        grounding = gs
    else:
        grounding = [gs]
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "grounding_sources": grounding,
        "truth_boundaries": m.truth_boundaries or {},
        "quick_prompt_key": m.quick_prompt_key,
        "confidence": m.confidence,
        "generation_mode": getattr(m, "generation_mode", None),
        "generation_model": getattr(m, "generation_model", None),
        "context_hash": getattr(m, "context_hash", None),
        "failure_reason": getattr(m, "failure_reason", None),
    }


async def get_session_for_user(db: AsyncSession, session_id: uuid.UUID, user: User) -> CopilotChatSession | None:
    sess = (
        await db.execute(select(CopilotChatSession).where(CopilotChatSession.id == session_id))
    ).scalar_one_or_none()
    if not sess or not sess.is_active:
        return None
    brand = (await db.execute(select(Brand).where(Brand.id == sess.brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != user.organization_id:
        return None
    return sess


async def _copilot_context(db: AsyncSession, brand_id: uuid.UUID) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Gather grounded context from real DB state — not empty lists."""
    from packages.db.models.scale_alerts import OperatorAlert, GrowthCommand
    from packages.db.models.creator_revenue import CreatorRevenueBlocker
    from packages.db.models.live_execution import MessagingBlocker
    from packages.db.models.buffer_distribution import BufferBlocker
    from packages.db.models.provider_registry import ProviderBlocker
    from packages.db.models.gatekeeper import GatekeeperAlert
    from packages.db.models.expansion_advisor import AccountExpansionAdvisory
    from packages.db.models.autonomous_execution import ExecutionBlockerEscalation

    def _to_dicts(rows, **extra_fields):
        out = []
        for r in rows:
            d = {}
            for col in r.__table__.columns:
                v = getattr(r, col.name, None)
                d[col.name] = str(v) if hasattr(v, 'hex') else v
            d.update(extra_fields)
            out.append(d)
        return out

    scale_alerts = _to_dicts(list((await db.execute(
        select(OperatorAlert).where(OperatorAlert.brand_id == brand_id, OperatorAlert.is_active.is_(True)).limit(20)
    )).scalars().all()))

    growth_commands = _to_dicts(list((await db.execute(
        select(GrowthCommand).where(GrowthCommand.brand_id == brand_id, GrowthCommand.is_active.is_(True)).limit(20)
    )).scalars().all()))

    cr_blockers = _to_dicts(list((await db.execute(
        select(CreatorRevenueBlocker).where(CreatorRevenueBlocker.brand_id == brand_id, CreatorRevenueBlocker.is_active.is_(True), CreatorRevenueBlocker.resolved.is_(False)).limit(20)
    )).scalars().all()))

    msg_blockers = _to_dicts(list((await db.execute(
        select(MessagingBlocker).where(MessagingBlocker.brand_id == brand_id, MessagingBlocker.is_active.is_(True), MessagingBlocker.resolved.is_(False)).limit(20)
    )).scalars().all()))

    buf_blockers = _to_dicts(list((await db.execute(
        select(BufferBlocker).where(BufferBlocker.brand_id == brand_id, BufferBlocker.is_active.is_(True), BufferBlocker.resolved.is_(False)).limit(20)
    )).scalars().all()))

    prov_blockers = _to_dicts(list((await db.execute(
        select(ProviderBlocker).where(ProviderBlocker.brand_id == brand_id, ProviderBlocker.is_active.is_(True), ProviderBlocker.resolved.is_(False)).limit(20)
    )).scalars().all()))

    gk_alerts = _to_dicts(list((await db.execute(
        select(GatekeeperAlert).where(GatekeeperAlert.brand_id == brand_id, GatekeeperAlert.is_active.is_(True)).limit(10)
    )).scalars().all()))

    expansion_advisories = _to_dicts(list((await db.execute(
        select(AccountExpansionAdvisory).where(AccountExpansionAdvisory.brand_id == brand_id, AccountExpansionAdvisory.is_active.is_(True)).limit(5)
    )).scalars().all()))

    autonomous_escalations = []
    try:
        autonomous_escalations = _to_dicts(list((await db.execute(
            select(ExecutionBlockerEscalation).where(ExecutionBlockerEscalation.brand_id == brand_id, ExecutionBlockerEscalation.is_active.is_(True)).limit(10)
        )).scalars().all()))
    except Exception:
        logger.debug("autonomous_escalations unavailable", exc_info=True)

    all_blockers = scale_alerts + cr_blockers + msg_blockers + buf_blockers + prov_blockers + gk_alerts
    failed_items = [a for a in scale_alerts if "fail" in str(a.get("alert_type", "")).lower() or "weak_lane" in str(a.get("alert_type", "")).lower()]
    pending_actions = expansion_advisories + [g for g in growth_commands if g.get("status") == "pending_approval"]
    provider_audit = build_provider_summary()
    quick = build_quick_status(all_blockers, failed_items, pending_actions, provider_audit)

    # ── Runtime truth: real counts from live DB ──────────────────
    from packages.db.models.content import ContentItem
    from packages.db.models.offers import Offer
    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.buffer_distribution import BufferProfile, BufferPublishJob

    content_count = (await db.execute(
        select(func.count(ContentItem.id)).where(ContentItem.brand_id == brand_id)
    )).scalar() or 0
    published_count = (await db.execute(
        select(func.count(ContentItem.id)).where(ContentItem.brand_id == brand_id, ContentItem.status == "published")
    )).scalar() or 0
    offer_count = (await db.execute(
        select(func.count(Offer.id)).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalar() or 0
    account_count = (await db.execute(
        select(func.count(CreatorAccount.id)).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalar() or 0
    buffer_channel_count = (await db.execute(
        select(func.count(BufferProfile.id)).where(BufferProfile.brand_id == brand_id, BufferProfile.is_active.is_(True))
    )).scalar() or 0
    buffer_connected_count = (await db.execute(
        select(func.count(BufferProfile.id)).where(
            BufferProfile.brand_id == brand_id,
            BufferProfile.is_active.is_(True),
            BufferProfile.credential_status == "connected",
        )
    )).scalar() or 0
    publish_job_count = (await db.execute(
        select(func.count(BufferPublishJob.id)).where(
            BufferPublishJob.brand_id == brand_id,
            BufferPublishJob.status == "published",
        )
    )).scalar() or 0

    quick["runtime_truth"] = {
        "content_count": content_count,
        "published_count": published_count,
        "offer_count": offer_count,
        "creator_account_count": account_count,
        "buffer_channel_count": buffer_channel_count,
        "buffer_connected_count": buffer_connected_count,
        "total_publishing_accounts": account_count + buffer_channel_count,
        "publish_jobs_published": publish_job_count,
        "has_publishing_capability": buffer_connected_count > 0,
        "has_content": content_count > 0,
        "has_offers": offer_count > 0,
    }

    winning_pattern_rows = list((await db.execute(
        select(WinningPatternMemory)
        .where(WinningPatternMemory.brand_id == brand_id, WinningPatternMemory.is_active.is_(True))
        .order_by(desc(WinningPatternMemory.win_score))
        .limit(10)
    )).scalars().all())
    losing_pattern_rows = list((await db.execute(
        select(LosingPatternMemory)
        .where(LosingPatternMemory.brand_id == brand_id, LosingPatternMemory.is_active.is_(True))
        .order_by(desc(LosingPatternMemory.fail_score))
        .limit(5)
    )).scalars().all())
    quick["winning_patterns"] = [
        {"pattern_type": r.pattern_type, "pattern_name": r.pattern_name, "win_score": r.win_score}
        for r in winning_pattern_rows
    ]
    quick["losing_patterns"] = [
        {"pattern_type": r.pattern_type, "pattern_name": r.pattern_name, "fail_score": r.fail_score}
        for r in losing_pattern_rows
    ]

    from packages.db.models.promote_winner import ActiveExperiment, PromotedWinnerRule
    active_exps = list((await db.execute(
        select(ActiveExperiment).where(ActiveExperiment.brand_id == brand_id, ActiveExperiment.status == "active").limit(10)
    )).scalars().all())
    promo_rules = list((await db.execute(
        select(PromotedWinnerRule).where(PromotedWinnerRule.brand_id == brand_id, PromotedWinnerRule.is_active.is_(True)).limit(10)
    )).scalars().all())
    quick["active_experiments"] = [{"name": e.experiment_name, "variable": e.tested_variable, "status": e.status} for e in active_exps]
    quick["promoted_winner_rules"] = [{"rule_type": r.rule_type, "rule_key": r.rule_key, "boost": r.weight_boost} for r in promo_rules]

    from packages.db.models.capital_allocator import CapitalAllocationReport, CAAllocationDecision
    alloc_report = (await db.execute(
        select(CapitalAllocationReport).where(CapitalAllocationReport.brand_id == brand_id).order_by(CapitalAllocationReport.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if alloc_report:
        quick["capital_allocation"] = {
            "total_budget": alloc_report.total_budget, "hero_spend": alloc_report.hero_spend,
            "bulk_spend": alloc_report.bulk_spend, "starved_count": alloc_report.starved_count,
            "target_count": alloc_report.target_count,
        }
        starved_decisions = list((await db.execute(
            select(CAAllocationDecision).where(CAAllocationDecision.report_id == alloc_report.id, CAAllocationDecision.starved.is_(True))
        )).scalars().all())
        quick["starved_lanes"] = [d.explanation for d in starved_decisions[:5]]

    from packages.db.models.account_state_intel import AccountStateReport
    acct_states = list((await db.execute(
        select(AccountStateReport).where(AccountStateReport.brand_id == brand_id, AccountStateReport.is_active.is_(True))
    )).scalars().all())
    quick["account_states"] = [
        {"account_id": str(s.account_id), "state": s.current_state, "monetization": s.monetization_intensity, "cadence": s.posting_cadence, "expansion": s.expansion_eligible, "next_move": s.next_best_move}
        for s in acct_states[:10]
    ]

    from packages.db.models.quality_governor import QualityGovernorReport, QualityBlock
    qg_fails = list((await db.execute(
        select(QualityGovernorReport).where(QualityGovernorReport.brand_id == brand_id, QualityGovernorReport.verdict == "fail", QualityGovernorReport.is_active.is_(True)).limit(10)
    )).scalars().all())
    qg_blocks = list((await db.execute(
        select(QualityBlock).where(QualityBlock.brand_id == brand_id, QualityBlock.is_active.is_(True)).limit(10)
    )).scalars().all())
    quick["quality_failures"] = [{"content_item_id": str(r.content_item_id), "score": r.total_score, "verdict": r.verdict} for r in qg_fails]
    quick["quality_blocks"] = [{"content_item_id": str(b.content_item_id), "reason": b.block_reason} for b in qg_blocks]

    from packages.db.models.objection_mining import ObjectionCluster, ObjectionPriorityReport
    obj_clusters = list((await db.execute(
        select(ObjectionCluster).where(ObjectionCluster.brand_id == brand_id, ObjectionCluster.is_active.is_(True)).order_by(ObjectionCluster.avg_monetization_impact.desc()).limit(5)
    )).scalars().all())
    quick["top_objections"] = [{"type": c.objection_type, "count": c.signal_count, "impact": c.avg_monetization_impact, "angle": c.recommended_response_angle} for c in obj_clusters]
    obj_report = (await db.execute(
        select(ObjectionPriorityReport).where(ObjectionPriorityReport.brand_id == brand_id).order_by(ObjectionPriorityReport.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if obj_report:
        quick["objection_summary"] = obj_report.summary

    from apps.api.services.opportunity_cost_service import get_top_actions
    try:
        top_actions = await get_top_actions(db, brand_id, limit=5)
        quick["top_opportunity_actions"] = top_actions
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)
        quick["top_opportunity_actions"] = []

    from packages.db.models.failure_family import SuppressionRule, FailureFamilyReport
    ff_reports = list((await db.execute(
        select(FailureFamilyReport).where(FailureFamilyReport.brand_id == brand_id, FailureFamilyReport.is_active.is_(True)).order_by(FailureFamilyReport.failure_count.desc()).limit(5)
    )).scalars().all())
    ff_rules = list((await db.execute(
        select(SuppressionRule).where(SuppressionRule.brand_id == brand_id, SuppressionRule.is_active.is_(True))
    )).scalars().all())
    quick["failure_families"] = [{"type": f.family_type, "key": f.family_key, "count": f.failure_count, "alt": f.recommended_alternative} for f in ff_reports]
    quick["active_suppressions"] = [{"type": r.family_type, "key": r.family_key, "mode": r.suppression_mode, "reason": r.reason} for r in ff_rules]

    from packages.db.models.campaigns import Campaign as CampModel, CampaignBlocker as CBModel
    camps = list((await db.execute(select(CampModel).where(CampModel.brand_id == brand_id, CampModel.is_active.is_(True)).order_by(CampModel.confidence.desc()).limit(5))).scalars().all())
    camp_blockers = list((await db.execute(select(CBModel).where(CBModel.brand_id == brand_id, CBModel.is_active.is_(True)).limit(5))).scalars().all())
    quick["campaigns"] = [{"name": c.campaign_name, "type": c.campaign_type, "status": c.launch_status, "confidence": c.confidence} for c in camps]
    quick["campaign_blockers"] = [{"type": b.blocker_type, "desc": b.description} for b in camp_blockers]

    from packages.db.models.affiliate_intel import AffiliateOffer as AFO, AffiliateLeak as AFL, AffiliateBlocker as AFB
    af_top = list((await db.execute(select(AFO).where(AFO.brand_id == brand_id, AFO.is_active.is_(True)).order_by(AFO.rank_score.desc()).limit(5))).scalars().all())
    af_leaks = list((await db.execute(select(AFL).where(AFL.brand_id == brand_id, AFL.is_active.is_(True)).limit(5))).scalars().all())
    af_blockers = list((await db.execute(select(AFB).where(AFB.brand_id == brand_id, AFB.is_active.is_(True)).limit(5))).scalars().all())
    quick["top_affiliate_offers"] = [{"name": o.product_name, "epc": o.epc, "rank": o.rank_score} for o in af_top]
    quick["affiliate_leaks"] = [{"type": l.leak_type, "severity": l.severity, "loss": l.revenue_loss_estimate} for l in af_leaks]
    quick["affiliate_blockers"] = [{"type": b.blocker_type, "desc": b.description} for b in af_blockers]

    from packages.db.models.brand_governance import BrandGovernanceViolation as BGV
    bg_violations = list((await db.execute(select(BGV).where(BGV.brand_id == brand_id, BGV.is_active.is_(True)).order_by(BGV.created_at.desc()).limit(5))).scalars().all())
    quick["governance_violations"] = [{"type": v.violation_type, "severity": v.severity, "detail": v.detail[:100]} for v in bg_violations]

    from packages.db.models.enterprise_security import ComplianceControlReport, RiskOverrideEvent
    compliance_fails = list((await db.execute(select(ComplianceControlReport).where(ComplianceControlReport.organization_id == brand_id, ComplianceControlReport.status == "not_met", ComplianceControlReport.is_active.is_(True)).limit(5))).scalars().all())
    risk_overrides = list((await db.execute(select(RiskOverrideEvent).where(RiskOverrideEvent.organization_id == brand_id, RiskOverrideEvent.is_active.is_(True)).limit(3))).scalars().all())
    quick["compliance_gaps"] = [{"framework": c.framework, "control": c.control_name, "status": c.status} for c in compliance_fails]
    quick["risk_overrides"] = [{"type": r.override_type, "reason": r.reason[:80]} for r in risk_overrides]

    from packages.db.models.workflow_builder import WorkflowInstance
    pending_wf = list((await db.execute(select(WorkflowInstance).where(WorkflowInstance.status == "in_progress", WorkflowInstance.is_active.is_(True)).limit(5))).scalars().all())
    quick["pending_workflows"] = [{"resource": i.resource_type, "step": i.current_step_order, "status": i.status} for i in pending_wf]

    from packages.db.models.hyperscale import ScaleHealthReport as SHR
    scale_health = (await db.execute(select(SHR).where(SHR.organization_id == brand_id).order_by(SHR.created_at.desc()).limit(1))).scalar_one_or_none()
    if scale_health:
        quick["scale_health"] = {"status": scale_health.health_status, "queue_depth": scale_health.queue_depth_total, "ceiling_pct": scale_health.ceiling_utilization_pct, "recommendation": scale_health.recommendation}

    from packages.db.models.integrations_listening import ListeningCluster as LC
    listening_clusters = list((await db.execute(select(LC).where(LC.organization_id == brand_id, LC.is_active.is_(True)).order_by(LC.signal_count.desc()).limit(3))).scalars().all())
    quick["listening_signals"] = [{"type": c.cluster_type, "count": c.signal_count, "action": c.recommended_action} for c in listening_clusters]

    try:
        from apps.api.services.executive_intel_service import get_executive_summary
        exec_summary = await get_executive_summary(db, brand_id)
        if exec_summary.get("status") != "no_data":
            quick["executive_summary"] = exec_summary
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.offer_lab_service import get_best_offer
        best_offer = await get_best_offer(db, brand_id)
        if best_offer.get("offer_id"):
            quick["best_offer"] = best_offer
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.revenue_leak_service import get_leak_summary
        leak_summary = await get_leak_summary(db, brand_id)
        if leak_summary.get("total_leaks", 0) > 0:
            quick["revenue_leaks"] = leak_summary
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.digital_twin_service import get_top_recommendations
        sim_recs = await get_top_recommendations(db, brand_id)
        if sim_recs:
            quick["simulation_recommendations"] = sim_recs
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.recovery_engine_service import get_recovery_summary
        rec_summary = await get_recovery_summary(db, brand_id)
        if rec_summary.get("open_incidents", 0) > 0:
            quick["recovery_status"] = rec_summary
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.operator_permission_service import get_autonomy_summary
        autonomy = await get_autonomy_summary(db, brand_id)
        quick["autonomy_matrix"] = autonomy
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.causal_attribution_service import get_attribution_summary
        causal = await get_attribution_summary(db, brand_id)
        if causal.get("reports"):
            quick["causal_attribution"] = causal
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    try:
        from apps.api.services.trend_viral_service import get_top_opportunities
        trends = await get_top_opportunities(db, brand_id, limit=3)
        if trends:
            quick["top_trend_opportunities"] = trends
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    # Fleet status, warmup phases, shadow ban alerts
    try:
        from packages.db.models.autonomous_farm import FleetStatusReport, AccountWarmupPlan, AccountVoiceProfile
        fleet = (await db.execute(
            select(FleetStatusReport).where(FleetStatusReport.is_active.is_(True)).order_by(FleetStatusReport.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        if fleet:
            quick["fleet_status"] = {
                "total_accounts": fleet.total_accounts,
                "warming": fleet.accounts_warming,
                "scaling": fleet.accounts_scaling,
                "plateaued": fleet.accounts_plateaued,
                "suspended": fleet.accounts_suspended,
                "retired": fleet.accounts_retired,
                "posts_today": fleet.total_posts_today,
                "revenue_30d": fleet.total_revenue_30d,
                "expansion_recommended": fleet.expansion_recommended,
                "expansion_details": fleet.expansion_details,
            }

        warmup_plans = list((await db.execute(
            select(AccountWarmupPlan).where(AccountWarmupPlan.brand_id == brand_id, AccountWarmupPlan.is_active.is_(True))
        )).scalars().all())
        quick["warmup_accounts"] = [
            {"account_id": str(w.account_id), "phase": w.current_phase, "age_days": w.age_days,
             "max_posts_per_day": w.max_posts_per_day, "monetization_allowed": w.monetization_allowed,
             "shadow_ban_detected": w.shadow_ban_detected, "shadow_ban_severity": w.shadow_ban_severity}
            for w in warmup_plans
        ]
        shadow_banned = [w for w in warmup_plans if w.shadow_ban_detected]
        if shadow_banned:
            quick["shadow_ban_alerts"] = [
                {"account_id": str(w.account_id), "severity": w.shadow_ban_severity, "cooldown_until": w.cooldown_until}
                for w in shadow_banned
            ]
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    # Revenue forecast
    try:
        from packages.scoring.revenue_forecast_engine import forecast_revenue, generate_forecast_summary
        from packages.db.models.publishing import PerformanceMetric
        from sqlalchemy import func as sqlfunc
        from datetime import timedelta
        daily_revs = [
            float(r[0]) for r in (await db.execute(
                select(sqlfunc.coalesce(sqlfunc.sum(PerformanceMetric.revenue), 0.0))
                .where(PerformanceMetric.brand_id == brand_id, PerformanceMetric.measured_at >= datetime.now(timezone.utc) - timedelta(days=30))
                .group_by(sqlfunc.date(PerformanceMetric.measured_at))
                .order_by(sqlfunc.date(PerformanceMetric.measured_at))
            )).all()
        ]
        if daily_revs and len(daily_revs) >= 7:
            forecast = forecast_revenue(daily_revs)
            quick["revenue_forecast"] = {
                "forecast_30d": forecast["forecast_revenue_30d"],
                "trend": forecast["trend_direction"],
                "confidence": forecast["confidence"],
                "summary": generate_forecast_summary(forecast),
            }
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    # Monthly accumulated revenue
    try:
        from packages.db.models.publishing import PerformanceMetric
        from sqlalchemy import func as sqlfunc
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        mtd_revenue = (await db.execute(
            select(sqlfunc.coalesce(sqlfunc.sum(PerformanceMetric.revenue), 0.0))
            .where(PerformanceMetric.brand_id == brand_id, PerformanceMetric.measured_at >= month_start)
        )).scalar() or 0.0
        quick["monthly_revenue_mtd"] = round(float(mtd_revenue), 2)
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    # Niche research data for setup guidance
    try:
        from packages.scoring.niche_research_engine import rank_niches, get_affiliate_programs_for_niche, NICHE_AFFILIATE_MAP
        from packages.clients.affiliate_program_clients import AFFILIATE_PROGRAMS, get_best_programs_for_niche
        from packages.db.models.accounts import CreatorAccount

        top_niches = rank_niches(top_n=10)
        quick["niche_rankings"] = [
            {"niche": n["niche"], "platform": n["platform"], "score": n["composite_score"],
             "monetization": n["monetization_score"], "cpm": n["avg_cpm"], "evergreen": n["evergreen"]}
            for n in top_niches
        ]

        all_programs = []
        for key, prog in AFFILIATE_PROGRAMS.items():
            all_programs.append({
                "name": prog["name"], "key": key, "type": prog["type"],
                "commission": prog["commission_range"], "avg_payout": prog["avg_payout"],
                "best_niches": prog["best_niches"][:5],
                "configured": all(os.environ.get(k) for k in prog["env_keys"]) if prog["env_keys"] else True,
            })
        all_programs.sort(key=lambda x: x["avg_payout"], reverse=True)
        quick["affiliate_programs"] = all_programs

        current_accounts = list((await db.execute(
            select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
        )).scalars().all())

        # Also count Buffer-connected channels as publishing accounts
        from packages.db.models.buffer_distribution import BufferProfile
        buffer_channels = list((await db.execute(
            select(BufferProfile).where(
                BufferProfile.brand_id == brand_id,
                BufferProfile.is_active.is_(True),
            )
        )).scalars().all())

        quick["current_accounts"] = [
            {"platform": getattr(a.platform, 'value', str(a.platform)), "username": a.platform_username, "niche": a.niche_focus or "general", "source": "creator_account"}
            for a in current_accounts
        ]
        # Add Buffer channels not already covered by creator accounts
        creator_platforms = set(getattr(a.platform, 'value', str(a.platform)) for a in current_accounts)
        for bp in buffer_channels:
            bp_platform = getattr(bp.platform, 'value', str(bp.platform))
            quick["current_accounts"].append({
                "platform": bp_platform,
                "username": bp.display_name,
                "niche": "general",
                "source": "buffer_profile",
                "buffer_profile_id": bp.buffer_profile_id,
                "credential_status": bp.credential_status,
            })

        covered_platforms = set(getattr(a.platform, 'value', str(a.platform)) for a in current_accounts)
        covered_platforms |= set(getattr(bp.platform, 'value', str(bp.platform)) for bp in buffer_channels)
        all_platforms = {"youtube", "tiktok", "instagram", "x", "linkedin"}
        missing_platforms = all_platforms - covered_platforms
        quick["missing_platforms"] = list(missing_platforms)

        # Real publishing capability summary
        connected_buffer = [bp for bp in buffer_channels if bp.credential_status == "connected"]
        quick["publishing_channels_connected"] = len(connected_buffer)
        quick["publishing_ready"] = len(connected_buffer) > 0

        brand_obj = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        niche = brand_obj.niche if brand_obj else "general"
        niche_programs = get_best_programs_for_niche(niche)
        quick["recommended_affiliates_for_niche"] = [
            {"name": p["name"], "commission": p["commission_range"], "avg_payout": p["avg_payout"]}
            for p in niche_programs[:5]
        ]
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    # Revenue by niche
    try:
        from packages.db.models.publishing import PerformanceMetric
        from packages.db.models.accounts import CreatorAccount
        from sqlalchemy import func as sqlfunc

        niche_revenue = {}
        accts = list((await db.execute(
            select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
        )).scalars().all())
        for acct in accts:
            niche = acct.niche_focus or "general"
            rev = (await db.execute(
                select(sqlfunc.coalesce(sqlfunc.sum(PerformanceMetric.revenue), 0.0))
                .where(PerformanceMetric.creator_account_id == acct.id)
            )).scalar() or 0.0
            niche_revenue[niche] = niche_revenue.get(niche, 0) + float(rev)
        if niche_revenue:
            quick["revenue_by_niche"] = {k: round(v, 2) for k, v in sorted(niche_revenue.items(), key=lambda x: x[1], reverse=True)}
    except Exception:
        logger.debug("copilot context enrichment failed", exc_info=True)

    actions = build_operator_actions(scale_alerts, growth_commands, cr_blockers, msg_blockers, buf_blockers, prov_blockers, autonomous_escalations)
    missing = build_missing_items()
    return quick, actions, missing, provider_audit


async def list_sessions(db: AsyncSession, brand_id: uuid.UUID, user_id: uuid.UUID) -> list[CopilotChatSession]:
    rows = (
        await db.execute(
            select(CopilotChatSession)
            .where(
                CopilotChatSession.brand_id == brand_id,
                CopilotChatSession.user_id == user_id,
                CopilotChatSession.is_active.is_(True),
            )
            .order_by(CopilotChatSession.updated_at.desc())
        )
    ).scalars().all()
    return list(rows)


async def create_session(db: AsyncSession, brand_id: uuid.UUID, user_id: uuid.UUID, title: str) -> CopilotChatSession:
    sess = CopilotChatSession(brand_id=brand_id, user_id=user_id, title=title or "Operator session")
    db.add(sess)
    await db.flush()
    return sess


async def list_messages(db: AsyncSession, session_id: uuid.UUID, user: User) -> list[dict[str, Any]] | None:
    sess = await get_session_for_user(db, session_id, user)
    if not sess:
        return None
    rows = (
        await db.execute(
            select(CopilotChatMessage)
            .where(
                CopilotChatMessage.session_id == session_id,
                CopilotChatMessage.is_active.is_(True),
            )
            .order_by(CopilotChatMessage.created_at.asc())
        )
    ).scalars().all()
    return [_message_to_dict(m) for m in rows]


async def post_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    user: User,
    content: str,
    quick_prompt_key: str | None,
) -> list[dict[str, Any]] | None:
    sess = await get_session_for_user(db, session_id, user)
    if not sess:
        return None
    if sess.user_id != user.id:
        return None

    user_msg = CopilotChatMessage(
        session_id=sess.id,
        role="user",
        content=content,
        quick_prompt_key=quick_prompt_key,
        grounding_sources=[],
        truth_boundaries={},
        generation_mode=None,
        generation_model=None,
        context_hash=None,
        failure_reason=None,
    )
    db.add(user_msg)
    await db.flush()

    quick, actions, missing, providers = await _copilot_context(db, sess.brand_id)

    from packages.clients.claude_client import ClaudeCopilotClient
    claude = ClaudeCopilotClient()
    claude_result = await claude.generate_response(content, quick, actions, missing, providers)

    if claude_result.get("generation_mode") == "claude" and claude_result.get("content"):
        gen_mode = "claude"
        gen_content = claude_result["content"]
        gen_model = claude_result.get("model", "")
        gen_confidence = float(claude_result.get("confidence", 0.95))
        gen_truth = claude_result.get("truth_boundaries") or {}
        gen_sources = claude_result.get("grounding_sources") or []
        gen_hash = claude_result.get("context_hash", "")
        gen_failure = None
    else:
        gen_mode = "fallback_rule_based"
        fallback = generate_grounded_response(content, quick, actions, missing, providers)
        gen_content = fallback["content"]
        gen_model = "rule_engine"
        gen_confidence = float(fallback.get("confidence", 0.7))
        gen_truth = fallback.get("truth_boundaries") or {}
        gen_truth["generation_fallback"] = True
        gen_truth["fallback_reason"] = claude_result.get("failure_reason", "unknown")
        gen_sources = fallback.get("grounding_sources") or []
        gen_hash = claude_result.get("context_hash", "")
        gen_failure = claude_result.get("failure_reason")

    assistant_msg = CopilotChatMessage(
        session_id=sess.id,
        role="assistant",
        content=gen_content,
        grounding_sources=gen_sources,
        truth_boundaries=gen_truth,
        confidence=gen_confidence,
        generation_mode=gen_mode,
        generation_model=gen_model,
        context_hash=gen_hash,
        failure_reason=gen_failure,
    )
    db.add(assistant_msg)

    sess.message_count = (sess.message_count or 0) + 2
    sess.last_message_at = datetime.now(timezone.utc).isoformat()

    await db.flush()
    return [_message_to_dict(user_msg), _message_to_dict(assistant_msg)]


async def get_quick_status_bundle(_db: AsyncSession, _brand_id: uuid.UUID) -> dict[str, Any]:
    quick, _, _, _ = await _copilot_context(_db, _brand_id)
    return quick


async def get_operator_actions_bundle(_db: AsyncSession, _brand_id: uuid.UUID) -> list[dict[str, Any]]:
    _, actions, _, _ = await _copilot_context(_db, _brand_id)
    return actions


async def get_missing_items_bundle(_db: AsyncSession, _brand_id: uuid.UUID) -> list[dict[str, Any]]:
    return build_missing_items()


async def get_providers_bundle(_db: AsyncSession, _brand_id: uuid.UUID) -> list[dict[str, Any]]:
    return build_provider_summary()


async def get_provider_readiness_bundle(_db: AsyncSession, _brand_id: uuid.UUID) -> list[dict[str, Any]]:
    return build_provider_readiness()

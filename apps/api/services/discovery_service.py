"""Discovery service — orchestrates signal ingestion, scoring, forecasting, and recommendations.

This is the core Phase 2 service. All engines compose here. No business logic in routers.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import (
    ActorType, ConfidenceLevel, DecisionMode, DecisionType,
    JobStatus, RecommendedAction, SignalClassification, SignalStrength,
)
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.decisions import MonetizationDecision, OpportunityDecision
from packages.db.models.discovery import NicheCluster, TopicCandidate, TopicSignal, TopicSource, TrendSignal
from packages.db.models.offers import Offer
from packages.db.models.publishing import SignalIngestionRun
from packages.db.models.scoring import (
    OfferFitScore, OpportunityScore, ProfitForecast,
    RecommendationQueue, SaturationReport,
)
from packages.scoring.forecast import ForecastInput, compute_profit_forecast
from packages.scoring.offer_fit import OfferFitInput, compute_offer_fit
from packages.scoring.opportunity import OpportunityInput, compute_opportunity_score
from packages.scoring.saturation import SaturationInput, compute_saturation


async def ingest_signals(
    db: AsyncSession,
    brand_id: uuid.UUID,
    source_type: str = "manual_seed",
    topics: list[dict] | None = None,
) -> dict:
    """Ingest topic candidates from a signal source into the database."""
    run = SignalIngestionRun(
        brand_id=brand_id,
        source_type=source_type,
        status=JobStatus.RUNNING,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    created = 0
    if topics:
        for t in topics:
            candidate = TopicCandidate(
                brand_id=brand_id,
                title=t.get("title", ""),
                description=t.get("description"),
                keywords=t.get("keywords", []),
                category=t.get("category"),
                estimated_search_volume=t.get("volume", 0),
                trend_velocity=t.get("velocity", 0.0),
                relevance_score=t.get("relevance", 0.5),
            )
            db.add(candidate)
            created += 1

            if t.get("trend_keyword"):
                signal = TrendSignal(
                    brand_id=brand_id,
                    signal_type=source_type,
                    keyword=t["trend_keyword"],
                    volume=t.get("volume", 0),
                    velocity=t.get("velocity", 0.0),
                    strength=_classify_signal_strength(t.get("velocity", 0.0)),
                    is_actionable=t.get("velocity", 0.0) > 0.3,
                )
                db.add(signal)

    run.status = JobStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.records_fetched = created
    run.records_processed = created
    await db.flush()

    return {"run_id": str(run.id), "records_created": created, "source_type": source_type}


async def get_signals(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Get all signal data for a brand."""
    topics = (await db.execute(
        select(TopicCandidate).where(TopicCandidate.brand_id == brand_id).order_by(TopicCandidate.created_at.desc()).limit(100)
    )).scalars().all()

    trends = (await db.execute(
        select(TrendSignal).where(TrendSignal.brand_id == brand_id).order_by(TrendSignal.created_at.desc()).limit(100)
    )).scalars().all()

    runs = (await db.execute(
        select(SignalIngestionRun).where(SignalIngestionRun.brand_id == brand_id).order_by(SignalIngestionRun.created_at.desc()).limit(20)
    )).scalars().all()

    return {"topic_candidates": topics, "trend_signals": trends, "ingestion_runs": runs}


async def compute_niches(db: AsyncSession, brand_id: uuid.UUID) -> list:
    """Compute niche clusters from topic candidates."""
    topics = (await db.execute(
        select(TopicCandidate).where(
            TopicCandidate.brand_id == brand_id,
            TopicCandidate.is_rejected.is_(False),
        )
    )).scalars().all()

    category_groups: dict[str, list] = {}
    for t in topics:
        cat = t.category or "uncategorized"
        category_groups.setdefault(cat, []).append(t)

    await db.execute(delete(NicheCluster).where(NicheCluster.brand_id == brand_id))

    clusters = []
    for cat, cat_topics in category_groups.items():
        all_kw = []
        for t in cat_topics:
            if t.keywords:
                all_kw.extend(t.keywords if isinstance(t.keywords, list) else [])

        avg_volume = sum(t.estimated_search_volume for t in cat_topics) / max(len(cat_topics), 1)
        avg_velocity = sum(t.trend_velocity for t in cat_topics) / max(len(cat_topics), 1)
        content_gap = max(0.0, 1.0 - len(cat_topics) / 20.0)
        monetization_potential = min(avg_velocity * 2 + content_gap, 1.0)

        cluster = NicheCluster(
            brand_id=brand_id,
            cluster_name=cat,
            keywords=list(set(all_kw))[:20],
            estimated_audience_size=int(avg_volume * len(cat_topics)),
            monetization_potential=round(monetization_potential, 3),
            competition_density=round(1.0 - content_gap, 3),
            content_gap_score=round(content_gap, 3),
            saturation_level=round(min(len(cat_topics) / 15.0, 1.0), 3),
            recommended_entry_angle=f"Focus on underserved angles in {cat}" if content_gap > 0.5 else f"Differentiate through unique perspective in {cat}",
        )
        db.add(cluster)
        clusters.append(cluster)

    await db.flush()
    return clusters


async def compute_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> list:
    """Score all unprocessed topic candidates and build opportunity queue."""
    topics = (await db.execute(
        select(TopicCandidate).where(
            TopicCandidate.brand_id == brand_id,
            TopicCandidate.is_rejected.is_(False),
        )
    )).scalars().all()

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()

    offers = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all()

    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    best_offer_epc = max((o.epc for o in offers), default=0.0)
    best_offer_cr = max((o.conversion_rate for o in offers), default=0.0)
    has_offers = len(offers) > 0

    results = []
    for topic in topics:
        inp = OpportunityInput(
            buyer_intent=topic.relevance_score * 0.8,
            trend_velocity=min(topic.trend_velocity, 1.0),
            trend_acceleration=min(topic.trend_velocity * 0.5, 1.0),
            content_gap=0.5,
            historical_win_rate=0.3 if topic.estimated_search_volume > 1000 else 0.1,
            offer_fit=min(best_offer_epc / 3.0, 1.0) if has_offers else 0.0,
            expected_profit_score=min(best_offer_cr * 10, 1.0) if has_offers else 0.0,
            platform_suitability=0.6 if accounts else 0.3,
            brand_fit_boost=0.05 if brand and brand.niche and topic.category and brand.niche.lower() in (topic.category or "").lower() else 0.0,
        )

        result = compute_opportunity_score(inp)

        score = OpportunityScore(
            brand_id=brand_id,
            topic_candidate_id=topic.id,
            composite_score=result.composite_score,
            trend_score=result.weighted_components.get("trend_velocity", 0),
            audience_fit_score=result.weighted_components.get("buyer_intent", 0),
            monetization_score=result.weighted_components.get("offer_fit", 0),
            competition_score=result.weighted_components.get("content_gap", 0),
            originality_score=1.0 - result.penalties.get("similarity_penalty", 0),
            saturation_penalty=result.penalties.get("saturation_penalty", 0),
            fatigue_penalty=result.penalties.get("audience_fatigue_penalty", 0),
            score_components=result.weighted_components,
            confidence=ConfidenceLevel(result.confidence) if result.confidence in [e.value for e in ConfidenceLevel] else ConfidenceLevel.MEDIUM,
            explanation=result.explanation,
        )
        db.add(score)
        await db.flush()

        decision = OpportunityDecision(
            brand_id=brand_id,
            decision_type=DecisionType.OPPORTUNITY,
            decision_mode=DecisionMode.GUARDED_AUTO,
            actor_type=ActorType.SYSTEM,
            topic_candidate_id=topic.id,
            opportunity_score_id=score.id,
            input_snapshot={"topic_title": topic.title, "velocity": topic.trend_velocity},
            formulas_used={"opportunity_score": "v1"},
            score_components=result.weighted_components,
            penalties=result.penalties,
            composite_score=result.composite_score,
            confidence=ConfidenceLevel(result.confidence) if result.confidence in [e.value for e in ConfidenceLevel] else ConfidenceLevel.MEDIUM,
            recommended_action=_score_to_action(result.composite_score, result.confidence),
            explanation=result.explanation,
        )
        db.add(decision)

        topic.is_processed = True
        results.append({"topic_id": str(topic.id), "title": topic.title, "score": result.composite_score, "confidence": result.confidence})

    await db.flush()
    return results


async def compute_offer_fit_for_topic(
    db: AsyncSession, brand_id: uuid.UUID, topic_id: uuid.UUID,
) -> list:
    """Score all active offers against a specific topic."""
    topic = (await db.execute(
        select(TopicCandidate).where(TopicCandidate.id == topic_id)
    )).scalar_one_or_none()
    if not topic:
        raise ValueError(f"Topic {topic_id} not found")

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    offers = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all()

    results = []
    for offer in offers:
        inp = OfferFitInput(
            topic_keywords=topic.keywords if isinstance(topic.keywords, list) else [],
            offer_audience_tags=offer.audience_fit_tags if isinstance(offer.audience_fit_tags, list) else [],
            offer_epc=offer.epc,
            offer_conversion_rate=offer.conversion_rate,
            offer_payout=offer.payout_amount,
            brand_niche=brand.niche or "" if brand else "",
            offer_niche_relevance=0.6,
            topic_buyer_intent=topic.relevance_score,
        )
        result = compute_offer_fit(inp)

        fit = OfferFitScore(
            brand_id=brand_id,
            offer_id=offer.id,
            topic_candidate_id=topic.id,
            fit_score=result.fit_score,
            audience_alignment=result.audience_alignment,
            intent_match=result.intent_match,
            friction_score=result.friction_score,
            repeatability_score=result.repeatability_score,
            revenue_potential=result.revenue_potential,
            confidence=ConfidenceLevel(result.confidence) if result.confidence in [e.value for e in ConfidenceLevel] else ConfidenceLevel.MEDIUM,
            explanation=result.explanation,
        )
        db.add(fit)

        results.append({
            "offer_id": str(offer.id),
            "offer_name": offer.name,
            "fit_score": result.fit_score,
            "confidence": result.confidence,
            "explanation": result.explanation,
        })

    await db.flush()
    return sorted(results, key=lambda x: -x["fit_score"])


async def compute_forecast_for_topic(
    db: AsyncSession, brand_id: uuid.UUID, topic_id: uuid.UUID,
) -> dict:
    """Compute profit forecast for a topic using best available offer and account data."""
    topic = (await db.execute(select(TopicCandidate).where(TopicCandidate.id == topic_id))).scalar_one_or_none()
    if not topic:
        raise ValueError(f"Topic {topic_id} not found")

    best_offer = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)).order_by(Offer.epc.desc())
    )).scalars().first()

    best_account = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
        .order_by(CreatorAccount.total_revenue.desc())
    )).scalars().first()

    impressions = topic.estimated_search_volume if topic.estimated_search_volume > 0 else 5000
    ctr = best_account.ctr if best_account and best_account.ctr > 0 else 0.025
    cr = best_offer.conversion_rate if best_offer and best_offer.conversion_rate > 0 else 0.02
    value = best_offer.payout_amount if best_offer else 20.0

    inp = ForecastInput(
        expected_impressions=impressions,
        expected_ctr=ctr,
        expected_conversion_rate=cr,
        expected_value_per_conversion=value,
        expected_generation_cost=2.50,
        expected_distribution_cost=0.50,
        fatigue_penalty_dollars=0.0,
        risk_penalty_dollars=0.0,
    )
    result = compute_profit_forecast(inp)

    forecast = ProfitForecast(
        brand_id=brand_id,
        topic_candidate_id=topic.id,
        offer_id=best_offer.id if best_offer else None,
        creator_account_id=best_account.id if best_account else None,
        estimated_impressions=impressions,
        estimated_ctr=ctr,
        estimated_conversion_rate=cr,
        estimated_revenue=result.expected_revenue,
        estimated_cost=result.expected_cost,
        estimated_profit=result.expected_profit,
        estimated_rpm=result.expected_rpm,
        estimated_epc=result.expected_epc,
        confidence=ConfidenceLevel(result.confidence) if result.confidence in [e.value for e in ConfidenceLevel] else ConfidenceLevel.MEDIUM,
        assumptions=result.assumptions,
        explanation=result.explanation,
    )
    db.add(forecast)
    await db.flush()

    return {
        "forecast_id": str(forecast.id),
        "expected_profit": result.expected_profit,
        "expected_revenue": result.expected_revenue,
        "expected_cost": result.expected_cost,
        "rpm": result.expected_rpm,
        "epc": result.expected_epc,
        "roi": result.roi,
        "confidence": result.confidence,
        "explanation": result.explanation,
    }


async def compute_saturation_report(db: AsyncSession, brand_id: uuid.UUID) -> list:
    """Compute saturation reports for all active accounts and niches."""
    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    clusters = (await db.execute(
        select(NicheCluster).where(NicheCluster.brand_id == brand_id)
    )).scalars().all()

    results = []
    for acct in accounts:
        inp = SaturationInput(
            total_posts_in_niche=0,
            posts_last_30d=int(acct.posting_capacity_per_day * 30 * 0.7),
            posts_last_7d=int(acct.posting_capacity_per_day * 7 * 0.8),
            unique_topics_covered=5,
            total_topics_available=max(len(clusters) * 3, 10),
            avg_engagement_last_7d=acct.ctr * 100,
            avg_engagement_last_30d=acct.ctr * 100 * 1.1,
            audience_overlap_pct=acct.cannibalization_risk.get("overlap", 0.0) if isinstance(acct.cannibalization_risk, dict) else 0.0,
            account_follower_growth_rate=acct.follower_growth_rate,
        )
        result = compute_saturation(inp)

        report = SaturationReport(
            brand_id=brand_id,
            creator_account_id=acct.id,
            saturation_score=result.saturation_score,
            fatigue_score=result.fatigue_score,
            originality_score=result.originality_score,
            topic_overlap_pct=result.topic_overlap_pct,
            audience_overlap_pct=result.audience_overlap_pct,
            recommended_action=RecommendedAction(result.recommended_action) if result.recommended_action in [e.value for e in RecommendedAction] else RecommendedAction.MONITOR,
            explanation=result.explanation,
            details={"account_username": acct.platform_username, "platform": acct.platform.value},
        )
        db.add(report)
        results.append({
            "account_id": str(acct.id),
            "username": acct.platform_username,
            "saturation": result.saturation_score,
            "fatigue": result.fatigue_score,
            "action": result.recommended_action,
        })

    await db.flush()
    return results


async def build_recommendation_queue(db: AsyncSession, brand_id: uuid.UUID) -> list:
    """Build ranked recommendation queue from scored opportunities."""
    scores = (await db.execute(
        select(OpportunityScore)
        .where(OpportunityScore.brand_id == brand_id)
        .order_by(OpportunityScore.composite_score.desc())
        .limit(50)
    )).scalars().all()

    await db.execute(delete(RecommendationQueue).where(RecommendationQueue.brand_id == brand_id))

    offers = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)).order_by(Offer.epc.desc())
    )).scalars().all()
    best_offer = offers[0] if offers else None

    account = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)).order_by(CreatorAccount.total_revenue.desc())
    )).scalars().first()

    recs = []
    for rank, score in enumerate(scores, 1):
        action = _score_to_action(score.composite_score, score.confidence.value if hasattr(score.confidence, 'value') else str(score.confidence))
        classification = _action_to_classification(action)

        rec = RecommendationQueue(
            brand_id=brand_id,
            topic_candidate_id=score.topic_candidate_id,
            offer_id=best_offer.id if best_offer else None,
            creator_account_id=account.id if account else None,
            rank=rank,
            composite_score=score.composite_score,
            recommended_action=action,
            classification=classification,
            explanation=score.explanation or f"Ranked #{rank} with score {score.composite_score:.3f}",
        )
        db.add(rec)
        recs.append(rec)

    await db.flush()
    return recs


async def trigger_brief_for_topic(
    db: AsyncSession, brand_id: uuid.UUID, topic_id: uuid.UUID,
) -> dict:
    """Prepare a brief trigger from a recommended topic. Creates the content_brief stub."""
    from packages.db.models.content import ContentBrief
    from packages.db.enums import ContentType

    topic = (await db.execute(select(TopicCandidate).where(TopicCandidate.id == topic_id))).scalar_one_or_none()
    if not topic:
        raise ValueError(f"Topic {topic_id} not found")

    score = (await db.execute(
        select(OpportunityScore)
        .where(OpportunityScore.topic_candidate_id == topic_id)
        .order_by(OpportunityScore.composite_score.desc())
    )).scalars().first()

    best_offer = (await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)).order_by(Offer.epc.desc())
    )).scalars().first()

    brief = ContentBrief(
        brand_id=brand_id,
        topic_candidate_id=topic.id,
        offer_id=best_offer.id if best_offer else None,
        title=topic.title,
        content_type=ContentType.SHORT_VIDEO,
        hook=f"Hook based on: {topic.title}",
        angle=topic.description or "Data-driven approach",
        key_points=topic.keywords if isinstance(topic.keywords, list) else [],
        cta_strategy=f"Drive to {best_offer.name}" if best_offer else "Engagement-focused CTA",
        monetization_integration=best_offer.monetization_method.value if best_offer else None,
        status="triggered",
    )
    db.add(brief)
    await db.flush()

    return {
        "brief_id": str(brief.id),
        "title": brief.title,
        "status": "triggered",
        "offer": best_offer.name if best_offer else None,
        "opportunity_score": score.composite_score if score else None,
    }


def _classify_signal_strength(velocity: float) -> SignalStrength:
    if velocity > 0.7:
        return SignalStrength.STRONG
    elif velocity > 0.4:
        return SignalStrength.MODERATE
    elif velocity > 0.1:
        return SignalStrength.WEAK
    return SignalStrength.INSUFFICIENT


def _score_to_action(score: float, confidence: str) -> RecommendedAction:
    if confidence == "insufficient":
        return RecommendedAction.MONITOR
    if score >= 0.7:
        return RecommendedAction.SCALE
    elif score >= 0.5:
        return RecommendedAction.MAINTAIN
    elif score >= 0.3:
        return RecommendedAction.MONITOR
    elif score >= 0.15:
        return RecommendedAction.REDUCE
    return RecommendedAction.SUPPRESS


def _action_to_classification(action: RecommendedAction) -> SignalClassification:
    mapping = {
        RecommendedAction.SCALE: SignalClassification.SCALE,
        RecommendedAction.MAINTAIN: SignalClassification.MAINTAIN,
        RecommendedAction.MONITOR: SignalClassification.MONITOR,
        RecommendedAction.REDUCE: SignalClassification.MONITOR,
        RecommendedAction.SUPPRESS: SignalClassification.SUPPRESS,
        RecommendedAction.EXPERIMENT: SignalClassification.MONITOR,
    }
    return mapping.get(action, SignalClassification.MONITOR)

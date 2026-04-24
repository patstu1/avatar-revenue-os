"""Autonomous Growth Engine — Self-optimizing revenue growth operations.

Combines intelligent budget allocation, winner pattern replication,
audience micro-segmentation, and self-healing workflow management
into a unified autonomous growth system.

Pure functions. No I/O.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 1. Intelligent Budget Allocator with Real-time ROI Rebalancing
# ---------------------------------------------------------------------------

@dataclass
class ChannelPerformance:
    channel_id: str
    name: str
    current_budget: float
    spend_to_date: float
    revenue_generated: float
    conversions: int
    impressions: int
    roi: float
    marginal_roi: float
    saturation_pct: float
    min_viable_budget: float
    max_effective_budget: float


@dataclass
class BudgetAllocation:
    total_budget: float
    allocations: list[dict]
    rebalance_actions: list[dict]
    expected_total_revenue: float
    expected_blended_roi: float
    optimization_score: float


def _marginal_roi_at_budget(
    base_roi: float,
    saturation_pct: float,
    budget: float,
    max_budget: float,
) -> float:
    """ROI at a given budget level accounting for diminishing returns.

    ROI(b) = base_roi * (1 - saturation_pct * (b / max_budget)^0.7)
    The 0.7 exponent models a concave saturation curve (steeper early).
    """
    if max_budget <= 0:
        return 0.0
    ratio = min(budget / max_budget, 1.0)
    return max(0.0, base_roi * (1.0 - saturation_pct * (ratio ** 0.7)))


def _expected_revenue_at_budget(
    base_roi: float,
    saturation_pct: float,
    budget: float,
    max_budget: float,
) -> float:
    """Integral of marginal ROI over budget gives total revenue."""
    if budget <= 0 or max_budget <= 0:
        return 0.0
    steps = 20
    step_size = budget / steps
    total = 0.0
    for i in range(steps):
        b = step_size * (i + 0.5)
        total += _marginal_roi_at_budget(base_roi, saturation_pct, b, max_budget) * step_size
    return total


def optimize_budget_allocation(
    channels: list[ChannelPerformance],
    total_budget: float,
    min_roi_threshold: float = 2.0,
    rebalance_aggressiveness: float = 0.3,
) -> BudgetAllocation:
    """Optimize budget allocation across channels to maximize total revenue.

    Uses marginal ROI equalization: allocate budget until marginal ROI
    is equal across all channels (economic equilibrium). Accounts for
    diminishing returns, min/max budgets, and rebalance constraints.
    """
    if not channels or total_budget <= 0:
        return BudgetAllocation(
            total_budget=total_budget,
            allocations=[],
            rebalance_actions=[],
            expected_total_revenue=0.0,
            expected_blended_roi=0.0,
            optimization_score=0.0,
        )

    viable = [
        ch for ch in channels
        if ch.min_viable_budget <= total_budget and ch.roi >= min_roi_threshold * 0.5
    ]
    if not viable:
        viable = sorted(channels, key=lambda c: c.roi, reverse=True)[:1]

    alloc = {ch.channel_id: ch.min_viable_budget for ch in viable}
    allocated = sum(alloc.values())

    if allocated > total_budget:
        ranked = sorted(viable, key=lambda c: c.roi, reverse=True)
        alloc = {}
        allocated = 0.0
        for ch in ranked:
            if allocated + ch.min_viable_budget <= total_budget:
                alloc[ch.channel_id] = ch.min_viable_budget
                allocated += ch.min_viable_budget
        viable = [ch for ch in viable if ch.channel_id in alloc]

    remaining = total_budget - allocated
    increment = max(total_budget * 0.01, 1.0)
    ch_map = {ch.channel_id: ch for ch in viable}

    for _ in range(1000):
        if remaining < increment * 0.1:
            break

        best_cid = None
        best_mroi = -1.0
        for ch in viable:
            cid = ch.channel_id
            cur = alloc[cid]
            if cur >= ch.max_effective_budget:
                continue
            mroi = _marginal_roi_at_budget(
                ch.roi, ch.saturation_pct, cur, ch.max_effective_budget,
            )
            if mroi > best_mroi:
                best_mroi = mroi
                best_cid = cid

        if best_cid is None or best_mroi < min_roi_threshold * 0.25:
            break

        ch = ch_map[best_cid]
        add = min(increment, remaining, ch.max_effective_budget - alloc[best_cid])
        alloc[best_cid] += add
        remaining -= add

    if remaining > 0:
        ranked = sorted(viable, key=lambda c: c.roi, reverse=True)
        for ch in ranked:
            space = ch.max_effective_budget - alloc[ch.channel_id]
            add = min(remaining, space)
            if add > 0:
                alloc[ch.channel_id] += add
                remaining -= add
            if remaining <= 0:
                break

    rebalance_actions: list[dict] = []
    for ch in viable:
        cid = ch.channel_id
        delta = alloc[cid] - ch.current_budget
        max_move = ch.current_budget * rebalance_aggressiveness
        if abs(delta) > max_move and ch.current_budget > 0:
            clamped = ch.current_budget + math.copysign(max_move, delta)
            excess = alloc[cid] - clamped
            alloc[cid] = clamped
            remaining += excess

    if remaining > 0:
        ranked = sorted(viable, key=lambda c: c.roi, reverse=True)
        for ch in ranked:
            space = ch.max_effective_budget - alloc[ch.channel_id]
            add = min(remaining, space)
            if add > 0:
                alloc[ch.channel_id] += add
                remaining -= add
            if remaining <= 0:
                break

    for ch in viable:
        delta = alloc[ch.channel_id] - ch.current_budget
        if abs(delta) > 1.0:
            direction = "increase" if delta > 0 else "decrease"
            rebalance_actions.append({
                "channel_id": ch.channel_id,
                "channel_name": ch.name,
                "current": round(ch.current_budget, 2),
                "new": round(alloc[ch.channel_id], 2),
                "delta": round(delta, 2),
                "direction": direction,
                "reason": (
                    f"Marginal ROI {direction}: channel "
                    f"{'under' if delta > 0 else 'over'}-allocated relative to ROI"
                ),
            })

    allocation_list: list[dict] = []
    total_expected_rev = 0.0
    for ch in viable:
        cid = ch.channel_id
        budget = alloc[cid]
        exp_rev = _expected_revenue_at_budget(
            ch.roi, ch.saturation_pct, budget, ch.max_effective_budget,
        )
        exp_roi = exp_rev / budget if budget > 0 else 0.0
        total_expected_rev += exp_rev
        allocation_list.append({
            "channel_id": cid,
            "channel_name": ch.name,
            "allocated": round(budget, 2),
            "expected_roi": round(exp_roi, 4),
            "expected_revenue": round(exp_rev, 2),
        })

    total_allocated = sum(a["allocated"] for a in allocation_list)
    blended_roi = total_expected_rev / total_allocated if total_allocated > 0 else 0.0

    mrois = []
    for ch in viable:
        m = _marginal_roi_at_budget(
            ch.roi, ch.saturation_pct, alloc[ch.channel_id], ch.max_effective_budget,
        )
        mrois.append(m)
    if len(mrois) >= 2:
        spread = max(mrois) - min(mrois)
        mean_m = statistics.mean(mrois)
        opt_score = max(0.0, 1.0 - (spread / (mean_m + 0.01)))
    else:
        opt_score = 0.8

    return BudgetAllocation(
        total_budget=total_budget,
        allocations=allocation_list,
        rebalance_actions=rebalance_actions,
        expected_total_revenue=round(total_expected_rev, 2),
        expected_blended_roi=round(blended_roi, 4),
        optimization_score=round(max(0.0, min(1.0, opt_score)), 4),
    )


def compute_channel_saturation(
    historical_spend: list[float],
    historical_revenue: list[float],
) -> tuple[float, float]:
    """Estimate saturation point and current saturation percentage.

    Fits a logistic curve: revenue = L / (1 + e^(-k*(spend - x0)))
    Uses a grid-search approach over (L, k, x0) since we're stdlib-only.
    Returns (saturation_pct, max_effective_budget).
    """
    if len(historical_spend) < 3 or len(historical_revenue) < 3:
        return 0.0, max(historical_spend) if historical_spend else 0.0

    n = min(len(historical_spend), len(historical_revenue))
    spend = historical_spend[:n]
    revenue = historical_revenue[:n]

    pairs = sorted(zip(spend, revenue), key=lambda p: p[0])
    spend = [p[0] for p in pairs]
    revenue = [p[1] for p in pairs]

    max_rev = max(revenue) if revenue else 1.0
    max_spend = max(spend) if spend else 1.0

    best_sse = float("inf")
    best_k = 1.0
    best_x0 = max_spend * 0.5

    L_candidates = [max_rev * m for m in (1.0, 1.2, 1.5, 2.0)]
    k_candidates = [v / max(max_spend, 1.0) for v in (0.5, 1.0, 2.0, 4.0, 8.0)]
    x0_candidates = [max_spend * f for f in (0.2, 0.4, 0.5, 0.6, 0.8)]

    for L in L_candidates:
        for k in k_candidates:
            for x0 in x0_candidates:
                sse = 0.0
                for s, r in zip(spend, revenue):
                    exponent = -k * (s - x0)
                    exponent = max(-500.0, min(500.0, exponent))
                    predicted = L / (1.0 + math.exp(exponent))
                    sse += (predicted - r) ** 2
                if sse < best_sse:
                    best_sse = sse
                    best_k = k
                    best_x0 = x0

    inflection = best_x0
    saturation_budget = inflection + 3.0 / max(best_k, 1e-9)
    saturation_budget = max(saturation_budget, max_spend * 0.5)

    current_spend = spend[-1] if spend else 0.0
    sat_pct = min(1.0, current_spend / saturation_budget) if saturation_budget > 0 else 0.0

    return round(sat_pct, 4), round(saturation_budget, 2)


# ---------------------------------------------------------------------------
# 2. Autonomous Winner Pattern Replication
# ---------------------------------------------------------------------------

@dataclass
class ContentPattern:
    pattern_id: str
    content_type: str
    hook_style: str
    structure: str
    emotional_tone: str
    cta_type: str
    avg_engagement_rate: float
    avg_rpm: float
    avg_conversion_rate: float
    sample_size: int
    platforms_effective: list[str]
    best_time_slots: list[int]
    audience_resonance_score: float


@dataclass
class ReplicationPlan:
    source_pattern: ContentPattern
    target_platforms: list[str]
    recommended_variations: list[dict]
    estimated_revenue_impact: float
    confidence: float
    priority_score: float


def _pattern_key(item: dict) -> str:
    return "|".join([
        str(item.get("hook", "unknown")),
        str(item.get("structure", "unknown")),
        str(item.get("tone", "unknown")),
        str(item.get("cta", "unknown")),
    ])


def _t_stat(sample_mean: float, pop_mean: float, sample_std: float, n: int) -> float:
    """One-sample t-statistic."""
    if sample_std <= 0 or n <= 1:
        return 0.0
    return (sample_mean - pop_mean) / (sample_std / math.sqrt(n))


def _t_critical(df: int, alpha: float = 0.05) -> float:
    """Approximate one-tailed t critical value using the Wilson-Hilferty transform."""
    if df <= 0:
        return 2.0
    z = 1.645 if alpha == 0.05 else 1.96
    return z * (1.0 - 2.0 / (9.0 * max(df, 1))) + math.sqrt(2.0 / (9.0 * max(df, 1)))


def extract_winning_patterns(
    content_performances: list[dict],
    min_sample_size: int = 5,
) -> list[ContentPattern]:
    """Extract recurring patterns from top-performing content.

    Groups by (hook_style, structure, emotional_tone, cta_type), computes
    aggregate metrics, and identifies statistically significant winners
    using one-sample t-test vs the global baseline.
    """
    if not content_performances:
        return []

    groups: dict[str, list[dict]] = defaultdict(list)
    for item in content_performances:
        key = _pattern_key(item)
        groups[key].append(item)

    all_engagement = [float(i.get("engagement", 0)) for i in content_performances]
    all_rpm = [float(i.get("rpm", 0)) for i in content_performances]
    all_conversion = [float(i.get("conversion", 0)) for i in content_performances]
    global_eng = statistics.mean(all_engagement) if all_engagement else 0.0
    global_rpm = statistics.mean(all_rpm) if all_rpm else 0.0
    global_conv = statistics.mean(all_conversion) if all_conversion else 0.0

    patterns: list[ContentPattern] = []

    for key, items in groups.items():
        if len(items) < min_sample_size:
            continue

        parts = key.split("|")
        hook = parts[0] if len(parts) > 0 else "unknown"
        structure = parts[1] if len(parts) > 1 else "unknown"
        tone = parts[2] if len(parts) > 2 else "unknown"
        cta = parts[3] if len(parts) > 3 else "unknown"

        eng_vals = [float(i.get("engagement", 0)) for i in items]
        rpm_vals = [float(i.get("rpm", 0)) for i in items]
        conv_vals = [float(i.get("conversion", 0)) for i in items]

        avg_eng = statistics.mean(eng_vals)
        avg_rpm = statistics.mean(rpm_vals)
        avg_conv = statistics.mean(conv_vals)
        n = len(items)

        eng_std = statistics.stdev(eng_vals) if n > 1 else 0.0
        t_val = _t_stat(avg_eng, global_eng, eng_std, n)
        df = n - 1
        t_crit = _t_critical(df)

        is_winner = t_val > t_crit and avg_eng > global_eng

        if not is_winner:
            composite = (
                0.4 * (avg_eng / max(global_eng, 1e-9))
                + 0.35 * (avg_rpm / max(global_rpm, 1e-9))
                + 0.25 * (avg_conv / max(global_conv, 1e-9))
            )
            is_winner = composite > 1.3

        if not is_winner:
            continue

        platform_counts: dict[str, int] = defaultdict(int)
        hour_counts: dict[int, int] = defaultdict(int)
        for i in items:
            platform_counts[str(i.get("platform", "unknown"))] += 1
            ts = i.get("timestamp")
            if isinstance(ts, datetime):
                hour_counts[ts.hour] += 1
            elif isinstance(ts, str):
                try:
                    hour_counts[datetime.fromisoformat(ts).hour] += 1
                except (ValueError, TypeError):
                    pass

        platforms_effective = sorted(platform_counts, key=platform_counts.get, reverse=True)  # type: ignore[arg-type]

        sorted_hours = sorted(hour_counts, key=hour_counts.get, reverse=True)  # type: ignore[arg-type]
        best_hours = sorted_hours[:3] if sorted_hours else []

        resonance = min(1.0, (
            0.4 * (avg_eng / max(global_eng, 1e-9))
            + 0.3 * (avg_rpm / max(global_rpm, 1e-9))
            + 0.2 * (avg_conv / max(global_conv, 1e-9))
            + 0.1 * min(1.0, n / 50)
        ))

        content_types = [str(i.get("content_type", "post")) for i in items]
        most_common_type = max(set(content_types), key=content_types.count)

        pid = f"pat_{hook[:3]}_{structure[:3]}_{tone[:3]}_{cta[:3]}"
        patterns.append(ContentPattern(
            pattern_id=pid,
            content_type=most_common_type,
            hook_style=hook,
            structure=structure,
            emotional_tone=tone,
            cta_type=cta,
            avg_engagement_rate=round(avg_eng, 6),
            avg_rpm=round(avg_rpm, 2),
            avg_conversion_rate=round(avg_conv, 6),
            sample_size=n,
            platforms_effective=platforms_effective,
            best_time_slots=best_hours,
            audience_resonance_score=round(resonance, 4),
        ))

    patterns.sort(key=lambda p: p.audience_resonance_score, reverse=True)
    return patterns


def compute_variation_strategy(
    pattern: ContentPattern,
    existing_variations: int,
) -> list[dict]:
    """Generate variation strategies to prevent pattern fatigue."""
    strategies: list[dict] = []

    angle_variations = [
        {"variation_type": "angle_shift", "description": f"Same {pattern.structure} structure but lead with a contrarian take", "expected_lift": 0.05},
        {"variation_type": "audience_pivot", "description": f"Adapt {pattern.hook_style} hook for a beginner audience vs advanced", "expected_lift": 0.08},
        {"variation_type": "format_remix", "description": f"Convert {pattern.content_type} into a carousel or thread format", "expected_lift": 0.06},
    ]

    tone_variations = [
        {"variation_type": "tone_shift", "description": f"Keep {pattern.structure} but shift tone from {pattern.emotional_tone} to educational", "expected_lift": 0.04},
        {"variation_type": "storytelling_wrap", "description": f"Wrap the {pattern.hook_style} hook in a personal story intro", "expected_lift": 0.07},
    ]

    cta_variations = [
        {"variation_type": "cta_experiment", "description": f"Test soft CTA (engagement-first) vs direct {pattern.cta_type}", "expected_lift": 0.10},
        {"variation_type": "multi_cta", "description": f"Add secondary CTA alongside primary {pattern.cta_type}", "expected_lift": 0.03},
    ]

    platform_variations = [
        {"variation_type": "platform_native", "description": f"Adapt for {plat} native format and conventions", "expected_lift": 0.09}
        for plat in pattern.platforms_effective[:2]
    ]

    timing_variations = []
    if pattern.best_time_slots:
        alt_slot = (pattern.best_time_slots[0] + 12) % 24
        timing_variations.append({
            "variation_type": "timing_experiment",
            "description": f"Test posting at {alt_slot}:00 vs current best slot {pattern.best_time_slots[0]}:00",
            "expected_lift": 0.03,
        })

    all_options = angle_variations + tone_variations + cta_variations + platform_variations + timing_variations

    fatigue_factor = min(1.0, existing_variations / 10.0)
    if fatigue_factor > 0.7:
        for v in all_options:
            v["expected_lift"] *= max(0.3, 1.0 - fatigue_factor)
        strategies.append({
            "variation_type": "pattern_rest",
            "description": f"Pattern showing fatigue ({existing_variations} variations). Consider 1-2 week rest before new variations.",
            "expected_lift": 0.0,
        })

    all_options.sort(key=lambda x: x["expected_lift"], reverse=True)
    max_new = max(1, 5 - int(fatigue_factor * 3))
    strategies.extend(all_options[:max_new])

    for s in strategies:
        s["expected_lift"] = round(s["expected_lift"], 4)
    return strategies


def generate_replication_plans(
    winning_patterns: list[ContentPattern],
    available_platforms: list[str],
    current_content_mix: dict[str, int],
    daily_content_capacity: int,
) -> list[ReplicationPlan]:
    """Generate actionable replication plans from winning patterns.

    Prioritizes patterns by revenue per unit, current mix saturation,
    untapped platform potential, and room for variation.
    """
    if not winning_patterns or daily_content_capacity <= 0:
        return []

    plans: list[ReplicationPlan] = []
    capacity_remaining = daily_content_capacity

    for pattern in winning_patterns:
        if capacity_remaining <= 0:
            break

        existing_count = current_content_mix.get(pattern.pattern_id, 0)
        saturation = min(1.0, existing_count / max(daily_content_capacity * 3, 1))

        untapped_platforms = [
            p for p in available_platforms
            if p not in pattern.platforms_effective
        ]
        platform_potential = len(untapped_platforms) / max(len(available_platforms), 1)

        revenue_per_unit = pattern.avg_rpm * pattern.avg_engagement_rate
        variation_room = max(0.0, 1.0 - (existing_count / 20.0))

        priority = (
            0.35 * min(1.0, revenue_per_unit / 100.0)
            + 0.25 * (1.0 - saturation)
            + 0.20 * platform_potential
            + 0.20 * variation_room
        )

        target_platforms = untapped_platforms or pattern.platforms_effective[:2]

        confidence = min(1.0, (
            0.4 * min(1.0, pattern.sample_size / 30)
            + 0.3 * pattern.audience_resonance_score
            + 0.3 * (1.0 - saturation)
        ))

        variations = compute_variation_strategy(pattern, existing_count)

        base_daily_rev = revenue_per_unit * len(target_platforms)
        estimated_impact = base_daily_rev * 30 * confidence

        plans.append(ReplicationPlan(
            source_pattern=pattern,
            target_platforms=target_platforms,
            recommended_variations=variations,
            estimated_revenue_impact=round(estimated_impact, 2),
            confidence=round(confidence, 4),
            priority_score=round(priority, 4),
        ))
        capacity_remaining -= 1

    plans.sort(key=lambda p: p.priority_score, reverse=True)
    return plans


# ---------------------------------------------------------------------------
# 3. Audience Micro-Segmentation Engine
# ---------------------------------------------------------------------------

@dataclass
class UserBehavior:
    user_id: str
    engagement_events: list[dict]
    purchase_history: list[dict]
    content_preferences: dict[str, float]
    platform_activity: dict[str, float]
    recency_days: float
    frequency_per_week: float
    monetary_total: float


@dataclass
class MicroSegment:
    segment_id: str
    name: str
    description: str
    size: int
    avg_ltv: float
    avg_engagement_rate: float
    avg_conversion_rate: float
    top_content_types: list[str]
    top_offers: list[str]
    optimal_contact_frequency: float
    price_sensitivity: float
    growth_potential: float
    recommended_actions: list[str]


_SEGMENT_LABELS = {
    (5, 5, 5): ("Champions", "Highest value, most active and recent. Reward and retain."),
    (5, 5, 4): ("Champions", "Top tier, nearly maxed spend. Exclusive offers."),
    (5, 4, 5): ("Loyal High-Spenders", "Recent, regular, big spenders. VIP treatment."),
    (5, 4, 4): ("Loyal Regulars", "Consistently active. Upsell opportunities."),
    (5, 3, 5): ("Big Spenders - Warming", "High spend but moderate frequency. Increase touchpoints."),
    (4, 5, 5): ("Active Champions", "Very active, slightly less recent. Re-engage quickly."),
    (4, 4, 4): ("Solid Mid-Tier", "Reliable contributors. Cross-sell and nurture."),
    (5, 1, 1): ("New Visitors", "Just arrived, no purchasing history yet. Welcome sequence."),
    (5, 1, 2): ("New Visitors", "Fresh audience. Onboarding content."),
    (5, 2, 1): ("New Engaged", "New and showing interest. Nurture aggressively."),
    (4, 1, 1): ("Recent One-Timers", "Came recently but only once. Re-engagement campaign."),
    (3, 3, 3): ("Mid-Range", "Average across all dimensions. Identify growth levers."),
    (2, 4, 4): ("At Risk - Loyal", "Were loyal but fading. Urgent win-back campaign."),
    (2, 3, 4): ("At Risk - Valuable", "High-value users slipping away. Personal outreach."),
    (2, 2, 4): ("At Risk - Big Spender", "Big spender going cold. Priority re-engagement."),
    (1, 4, 4): ("Can't Lose Them", "Formerly best customers. Aggressive win-back."),
    (1, 3, 3): ("About to Hibernate", "Declining on all fronts. Last-chance offers."),
    (1, 2, 2): ("Hibernating", "Low activity across the board. Reactivation or sunset."),
    (1, 1, 2): ("Hibernating", "Nearly dormant. Low-cost re-engagement attempt."),
    (1, 1, 1): ("Lost", "Inactive on all fronts. Suppress or deep reactivation."),
}


def _assign_quintile(values: list[float], value: float) -> int:
    """Assign a 1-5 quintile score. 5 is best."""
    if not values:
        return 3
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    for q in range(1, 6):
        threshold_idx = min(int(n * q / 5), n - 1)
        if value <= sorted_vals[threshold_idx]:
            return q
    return 5


def _lookup_segment_label(r: int, f: int, m: int) -> tuple[str, str]:
    """Find the closest matching segment label."""
    key = (r, f, m)
    if key in _SEGMENT_LABELS:
        return _SEGMENT_LABELS[key]

    best_dist = float("inf")
    best_label = ("Mid-Range", "Average customer segment.")
    for (lr, lf, lm), (name, desc) in _SEGMENT_LABELS.items():
        dist = abs(r - lr) + abs(f - lf) + abs(m - lm)
        if dist < best_dist:
            best_dist = dist
            best_label = (name, desc)
    return best_label


def _segment_actions(name: str, r: int, f: int, m: int) -> list[str]:
    actions: list[str] = []
    if "Champion" in name:
        actions.extend([
            "Offer exclusive early-access content",
            "Launch referral program incentives",
            "Test premium upsell offers",
        ])
    elif "Loyal" in name:
        actions.extend([
            "Cross-sell complementary offers",
            "Increase engagement touchpoints",
            "Request testimonials and reviews",
        ])
    elif "At Risk" in name or "Can't Lose" in name:
        actions.extend([
            "Trigger urgent win-back email sequence",
            "Offer personalized discount or bonus",
            "Direct outreach from creator",
        ])
    elif "New" in name:
        actions.extend([
            "Send welcome sequence with best content",
            "Low-commitment CTA (free resource, quiz)",
            "Build trust before monetization",
        ])
    elif "Hibernating" in name or "Lost" in name:
        actions.extend([
            "Send reactivation campaign with compelling offer",
            "A/B test subject lines for re-engagement",
            "Consider suppression to protect deliverability",
        ])
    else:
        actions.extend([
            "Increase content frequency to boost engagement",
            "Test new offer angles for this segment",
            "Monitor for movement to higher-value segment",
        ])

    if r <= 2:
        actions.append("Prioritize recency: time-sensitive offer or content drop")
    if f <= 2:
        actions.append("Boost frequency: reminders, push notifications, series content")
    if m >= 4 and f <= 2:
        actions.append("High-value user with low frequency — personal outreach recommended")
    return actions


def segment_audience_rfm(
    behaviors: list[UserBehavior],
    n_segments: int = 5,
) -> list[MicroSegment]:
    """RFM-based audience segmentation.

    Scores each user on Recency, Frequency, Monetary using quintiles,
    groups into segments, and generates per-segment metrics and
    actionable recommendations.
    """
    if not behaviors:
        return []

    recency_vals = [b.recency_days for b in behaviors]
    freq_vals = [b.frequency_per_week for b in behaviors]
    monetary_vals = [b.monetary_total for b in behaviors]

    max_recency = max(recency_vals) if recency_vals else 1.0

    scored: list[tuple[UserBehavior, int, int, int]] = []
    for b in behaviors:
        inv_recency = max_recency - b.recency_days
        r = _assign_quintile([max_recency - v for v in recency_vals], inv_recency)
        f = _assign_quintile(freq_vals, b.frequency_per_week)
        m = _assign_quintile(monetary_vals, b.monetary_total)
        scored.append((b, r, f, m))

    seg_groups: dict[str, list[tuple[UserBehavior, int, int, int]]] = defaultdict(list)
    for entry in scored:
        b, r, f, m = entry
        label, _ = _lookup_segment_label(r, f, m)
        seg_groups[label].append(entry)

    segments: list[MicroSegment] = []

    for seg_name, members in seg_groups.items():
        if not members:
            continue

        users = [m[0] for m in members]
        r_avg = statistics.mean([m[1] for m in members])
        f_avg = statistics.mean([m[2] for m in members])
        m_avg = statistics.mean([m[3] for m in members])

        ltvs = [u.monetary_total for u in users]
        avg_ltv = statistics.mean(ltvs)

        eng_rates: list[float] = []
        conv_rates: list[float] = []
        content_pref_agg: dict[str, float] = defaultdict(float)
        offer_agg: dict[str, float] = defaultdict(float)

        for u in users:
            n_events = len(u.engagement_events)
            n_purchases = len(u.purchase_history)
            total_interactions = n_events + n_purchases
            if total_interactions > 0:
                eng_rates.append(n_events / max(total_interactions, 1))
                conv_rates.append(n_purchases / max(n_events, 1))
            for ct, aff in u.content_preferences.items():
                content_pref_agg[ct] += aff
            for ph in u.purchase_history:
                oid = str(ph.get("offer_id", "unknown"))
                offer_agg[oid] += float(ph.get("amount", 0))

        avg_eng = statistics.mean(eng_rates) if eng_rates else 0.0
        avg_conv = statistics.mean(conv_rates) if conv_rates else 0.0

        top_content = sorted(content_pref_agg, key=content_pref_agg.get, reverse=True)[:3]  # type: ignore[arg-type]
        top_offers = sorted(offer_agg, key=offer_agg.get, reverse=True)[:3]  # type: ignore[arg-type]

        freq_mean = statistics.mean([u.frequency_per_week for u in users])
        optimal_freq = min(7.0, max(1.0, freq_mean * 1.2))

        avg_monetary = statistics.mean([u.monetary_total for u in users])
        max_monetary = max(monetary_vals) if monetary_vals else 1.0
        price_sens = max(0.0, 1.0 - (avg_monetary / max(max_monetary, 1.0)))

        growth_potential = min(1.0, (
            0.3 * (r_avg / 5.0)
            + 0.3 * (1.0 - min(1.0, avg_conv))
            + 0.2 * (f_avg / 5.0)
            + 0.2 * min(1.0, len(members) / max(len(behaviors) * 0.3, 1))
        ))

        _, description = _lookup_segment_label(round(r_avg), round(f_avg), round(m_avg))
        actions = _segment_actions(seg_name, round(r_avg), round(f_avg), round(m_avg))

        sid = seg_name.lower().replace(" ", "_").replace("-", "_")
        segments.append(MicroSegment(
            segment_id=f"seg_{sid}",
            name=seg_name,
            description=description,
            size=len(members),
            avg_ltv=round(avg_ltv, 2),
            avg_engagement_rate=round(avg_eng, 6),
            avg_conversion_rate=round(avg_conv, 6),
            top_content_types=top_content,
            top_offers=top_offers,
            optimal_contact_frequency=round(optimal_freq, 1),
            price_sensitivity=round(price_sens, 4),
            growth_potential=round(growth_potential, 4),
            recommended_actions=actions,
        ))

    segments.sort(key=lambda s: s.avg_ltv, reverse=True)
    return segments


def compute_segment_value_matrix(
    segments: list[MicroSegment],
    offers: list[dict],
) -> list[dict]:
    """Cross-reference segments with offers for highest-value matches.

    For each (segment, offer) pair, estimates expected revenue per contact
    and ranks by total opportunity (expected_rev * segment_size).
    """
    if not segments or not offers:
        return []

    results: list[dict] = []

    for seg in segments:
        for offer in offers:
            offer_id = str(offer.get("offer_id", "unknown"))
            offer_name = str(offer.get("name", offer_id))
            offer_price = float(offer.get("price", 0))
            offer_commission_pct = float(offer.get("commission_pct", 0.5))
            offer_category = str(offer.get("category", "general"))

            category_match = 1.0 if offer_category in seg.top_content_types else 0.5
            offer_match = 1.2 if offer_id in seg.top_offers else 0.8

            price_fit = max(0.2, 1.0 - abs(seg.price_sensitivity - 0.5) * (offer_price / max(offer_price, 100)))
            price_fit = min(1.0, price_fit)

            conv_estimate = seg.avg_conversion_rate * category_match * offer_match * price_fit
            revenue_per_contact = conv_estimate * offer_price * offer_commission_pct
            total_opportunity = revenue_per_contact * seg.size

            confidence = min(1.0, (
                0.3 * (1.0 if offer_id in seg.top_offers else 0.4)
                + 0.3 * min(1.0, seg.size / 100)
                + 0.2 * category_match
                + 0.2 * (1.0 - seg.price_sensitivity)
            ))

            results.append({
                "segment_id": seg.segment_id,
                "segment_name": seg.name,
                "offer_id": offer_id,
                "offer_name": offer_name,
                "expected_revenue_per_contact": round(revenue_per_contact, 4),
                "total_opportunity": round(total_opportunity, 2),
                "estimated_conversion_rate": round(conv_estimate, 6),
                "confidence": round(confidence, 4),
                "price_fit": round(price_fit, 4),
                "recommended_frequency": round(
                    seg.optimal_contact_frequency * confidence, 1
                ),
            })

    results.sort(key=lambda r: r["total_opportunity"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# 4. Self-Healing Workflow Engine
# ---------------------------------------------------------------------------

@dataclass
class WorkflowHealth:
    workflow_id: str
    name: str
    status: str
    success_rate_24h: float
    avg_latency_ms: float
    error_count_24h: int
    last_error: str | None
    auto_recovery_attempts: int
    dependencies: list[str]
    bottleneck_step: str | None


@dataclass
class RecoveryAction:
    action_type: str
    target: str
    params: dict
    estimated_recovery_time_s: float
    confidence: float


_RETRYABLE_ERRORS = {
    "timeout", "rate_limit", "connection_reset", "temporary_unavailable",
    "429", "503", "504", "econnreset", "etimeout",
}


def _is_retryable(error: str) -> bool:
    lower = error.lower()
    return any(token in lower for token in _RETRYABLE_ERRORS)


def diagnose_workflow_health(
    execution_history: list[dict],
    dependency_health: dict[str, float],
) -> WorkflowHealth:
    """Diagnose workflow health from execution history.

    Analyzes step-level success rates, latency distribution, error
    clustering, and dependency impacts to produce a health report.
    """
    if not execution_history:
        return WorkflowHealth(
            workflow_id="unknown",
            name="unknown",
            status="healthy",
            success_rate_24h=1.0,
            avg_latency_ms=0.0,
            error_count_24h=0,
            last_error=None,
            auto_recovery_attempts=0,
            dependencies=list(dependency_health.keys()),
            bottleneck_step=None,
        )

    wf_id = str(execution_history[0].get("workflow_id", "unknown"))
    wf_name = str(execution_history[0].get("workflow_name", wf_id))

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    recent: list[dict] = []
    for ex in execution_history:
        ts = ex.get("timestamp")
        if isinstance(ts, datetime) and ts >= cutoff:
            recent.append(ex)
        elif isinstance(ts, str):
            try:
                if datetime.fromisoformat(ts) >= cutoff:
                    recent.append(ex)
            except (ValueError, TypeError):
                recent.append(ex)
        else:
            recent.append(ex)

    if not recent:
        recent = execution_history[-50:]

    total = len(recent)
    successes = sum(1 for e in recent if str(e.get("status", "")).lower() in ("success", "ok", "completed"))
    success_rate = successes / max(total, 1)

    latencies = [float(e.get("latency_ms", 0)) for e in recent if e.get("latency_ms") is not None]
    avg_latency = statistics.mean(latencies) if latencies else 0.0

    errors = [e for e in recent if str(e.get("status", "")).lower() in ("error", "failed", "failure")]
    error_count = len(errors)

    last_error_msg: str | None = None
    if errors:
        last_error_msg = str(errors[-1].get("error", "Unknown error"))

    step_errors: dict[str, int] = defaultdict(int)
    step_latencies: dict[str, list[float]] = defaultdict(list)
    for e in recent:
        step = str(e.get("step", "unknown"))
        if str(e.get("status", "")).lower() in ("error", "failed", "failure"):
            step_errors[step] += 1
        lat = e.get("latency_ms")
        if lat is not None:
            step_latencies[step].append(float(lat))

    bottleneck: str | None = None
    if step_errors:
        bottleneck = max(step_errors, key=step_errors.get)  # type: ignore[arg-type]
    elif step_latencies:
        step_avgs = {s: statistics.mean(lats) for s, lats in step_latencies.items() if lats}
        if step_avgs:
            slowest = max(step_avgs, key=step_avgs.get)  # type: ignore[arg-type]
            if step_avgs[slowest] > avg_latency * 2:
                bottleneck = slowest

    recovery_attempts = sum(
        1 for e in recent
        if str(e.get("status", "")).lower() == "retry"
        or e.get("is_retry", False)
    )

    dep_issues = [dep for dep, health in dependency_health.items() if health < 0.5]

    if success_rate >= 0.98 and not dep_issues:
        status = "healthy"
    elif success_rate >= 0.90:
        status = "degraded"
    elif error_count > 0 and recovery_attempts > 0 and success_rate >= 0.80:
        status = "recovered"
    else:
        status = "failing"

    if dep_issues and status == "healthy":
        status = "degraded"

    return WorkflowHealth(
        workflow_id=wf_id,
        name=wf_name,
        status=status,
        success_rate_24h=round(success_rate, 4),
        avg_latency_ms=round(avg_latency, 2),
        error_count_24h=error_count,
        last_error=last_error_msg,
        auto_recovery_attempts=recovery_attempts,
        dependencies=list(dependency_health.keys()),
        bottleneck_step=bottleneck,
    )


def generate_recovery_plan(
    health: WorkflowHealth,
    available_fallbacks: dict[str, str],
) -> list[RecoveryAction]:
    """Generate automatic recovery actions for unhealthy workflows.

    Decision tree:
    1. Single step failing with retryable error -> retry with exponential backoff
    2. Dependency down -> circuit break + fallback
    3. Latency spiking -> scale up workers
    4. Persistent failure -> alert + graceful degradation
    """
    if health.status == "healthy":
        return []

    actions: list[RecoveryAction] = []

    if health.last_error and _is_retryable(health.last_error):
        backoff_base = 2.0
        attempt = health.auto_recovery_attempts + 1
        delay = min(backoff_base ** attempt, 300.0)
        actions.append(RecoveryAction(
            action_type="retry",
            target=health.bottleneck_step or health.workflow_id,
            params={
                "max_retries": 3,
                "backoff_seconds": round(delay, 1),
                "backoff_strategy": "exponential",
                "jitter": True,
            },
            estimated_recovery_time_s=delay * 3,
            confidence=0.7 if attempt <= 2 else 0.4,
        ))

    for dep in health.dependencies:
        if health.last_error and dep.lower() in health.last_error.lower():
            fallback_target = available_fallbacks.get(dep)
            actions.append(RecoveryAction(
                action_type="circuit_break",
                target=dep,
                params={
                    "break_duration_s": 60,
                    "half_open_after_s": 30,
                    "failure_threshold": 5,
                },
                estimated_recovery_time_s=60.0,
                confidence=0.8,
            ))
            if fallback_target:
                actions.append(RecoveryAction(
                    action_type="fallback",
                    target=dep,
                    params={
                        "fallback_to": fallback_target,
                        "degraded_mode": True,
                    },
                    estimated_recovery_time_s=5.0,
                    confidence=0.85,
                ))

    if health.avg_latency_ms > 5000 and health.status == "degraded":
        scale_factor = min(4, max(2, int(health.avg_latency_ms / 2000)))
        actions.append(RecoveryAction(
            action_type="scale_up",
            target=health.bottleneck_step or health.workflow_id,
            params={
                "scale_factor": scale_factor,
                "cooldown_s": 300,
                "max_instances": scale_factor * 2,
            },
            estimated_recovery_time_s=30.0,
            confidence=0.6,
        ))

    if health.status == "failing" and health.success_rate_24h < 0.5:
        actions.append(RecoveryAction(
            action_type="alert",
            target=health.workflow_id,
            params={
                "severity": "critical",
                "message": (
                    f"Workflow '{health.name}' failing: "
                    f"{health.success_rate_24h:.0%} success rate, "
                    f"{health.error_count_24h} errors in 24h. "
                    f"Last error: {health.last_error or 'unknown'}"
                ),
                "channels": ["slack", "email", "pagerduty"],
            },
            estimated_recovery_time_s=0.0,
            confidence=1.0,
        ))

    if health.status == "failing" and health.auto_recovery_attempts >= 3:
        actions.append(RecoveryAction(
            action_type="circuit_break",
            target=health.workflow_id,
            params={
                "break_duration_s": 300,
                "reason": "persistent_failure_after_retries",
                "graceful_shutdown": True,
                "drain_queue": True,
            },
            estimated_recovery_time_s=300.0,
            confidence=0.9,
        ))

    if health.bottleneck_step and health.bottleneck_step in available_fallbacks:
        already_has_fallback = any(
            a.action_type == "fallback" and a.target == health.bottleneck_step
            for a in actions
        )
        if not already_has_fallback:
            actions.append(RecoveryAction(
                action_type="fallback",
                target=health.bottleneck_step,
                params={
                    "fallback_to": available_fallbacks[health.bottleneck_step],
                    "degraded_mode": True,
                },
                estimated_recovery_time_s=5.0,
                confidence=0.75,
            ))

    if not actions and health.status != "healthy":
        actions.append(RecoveryAction(
            action_type="alert",
            target=health.workflow_id,
            params={
                "severity": "warning",
                "message": (
                    f"Workflow '{health.name}' in '{health.status}' state "
                    f"but no automatic recovery available. Manual review needed."
                ),
                "channels": ["slack"],
            },
            estimated_recovery_time_s=0.0,
            confidence=1.0,
        ))

    actions.sort(key=lambda a: a.confidence, reverse=True)
    return actions

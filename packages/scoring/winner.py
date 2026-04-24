"""Winner detection and clone recommendation engine.

Identifies top-performing content and recommends cloning across
accounts/platforms. Deterministic, rules-based.
"""

from dataclasses import dataclass

FORMULA_VERSION = "v1"

WINNER_THRESHOLD_RPM = 10.0
WINNER_THRESHOLD_PROFIT = 50.0
WINNER_THRESHOLD_ENGAGEMENT = 0.05
LOSER_THRESHOLD_RPM = 2.0
LOSER_THRESHOLD_IMPRESSIONS = 1000


@dataclass
class ContentPerformance:
    content_id: str
    title: str
    impressions: int = 0
    revenue: float = 0.0
    profit: float = 0.0
    rpm: float = 0.0
    ctr: float = 0.0
    engagement_rate: float = 0.0
    conversion_rate: float = 0.0
    platform: str = ""
    account_id: str = ""


@dataclass
class WinnerSignal:
    content_id: str
    title: str
    is_winner: bool
    is_loser: bool
    win_score: float
    clone_recommended: bool
    clone_targets: list[str]
    explanation: str


def detect_winners(items: list[ContentPerformance], available_platforms: list[str] = None) -> list[WinnerSignal]:
    if not items:
        return []

    results = []
    for item in items:
        win_score = 0.0
        reasons = []

        if item.rpm >= WINNER_THRESHOLD_RPM:
            win_score += 0.3
            reasons.append(f"RPM ${item.rpm:.2f}")
        if item.profit >= WINNER_THRESHOLD_PROFIT:
            win_score += 0.3
            reasons.append(f"profit ${item.profit:.2f}")
        if item.engagement_rate >= WINNER_THRESHOLD_ENGAGEMENT:
            win_score += 0.2
            reasons.append(f"engagement {item.engagement_rate:.1%}")
        if item.ctr >= 0.03:
            win_score += 0.1
            reasons.append(f"CTR {item.ctr:.1%}")
        if item.conversion_rate >= 0.03:
            win_score += 0.1
            reasons.append(f"conversion {item.conversion_rate:.1%}")

        is_winner = win_score >= 0.5
        is_loser = (
            item.impressions >= LOSER_THRESHOLD_IMPRESSIONS
            and item.rpm < LOSER_THRESHOLD_RPM
            and item.engagement_rate < 0.01
        )

        clone_targets = []
        if is_winner and available_platforms:
            clone_targets = [p for p in available_platforms if p != item.platform]

        if is_winner:
            explanation = f"WINNER: {', '.join(reasons)}. Score {win_score:.2f}."
        elif is_loser:
            explanation = f"LOSER: {item.impressions} impressions but RPM ${item.rpm:.2f}, engagement {item.engagement_rate:.1%}. Consider suppression."
        else:
            explanation = f"Neutral: win_score {win_score:.2f}. Not enough signal to classify."

        results.append(
            WinnerSignal(
                content_id=item.content_id,
                title=item.title,
                is_winner=is_winner,
                is_loser=is_loser,
                win_score=round(win_score, 3),
                clone_recommended=is_winner and len(clone_targets) > 0,
                clone_targets=clone_targets,
                explanation=explanation,
            )
        )

    results.sort(key=lambda x: -x.win_score)
    return results

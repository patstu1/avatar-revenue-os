"""Similarity / repetition detection engine.

Compares content against existing library using keyword overlap.
Full embedding-based similarity requires AI provider credentials.
"""

from __future__ import annotations

from dataclasses import dataclass

SIMILARITY_THRESHOLD = 0.85
FORMULA_VERSION = "v1"


@dataclass
class SimilarityInput:
    new_keywords: list[str]
    new_title: str = ""
    existing_items: list[dict] = None

    def __post_init__(self):
        if self.existing_items is None:
            self.existing_items = []


@dataclass
class SimilarityResult:
    is_too_similar: bool
    max_similarity_score: float
    avg_similarity_score: float
    compared_against_count: int
    most_similar_id: str | None
    details: list[dict]
    threshold_used: float
    explanation: str
    formula_version: str = FORMULA_VERSION


def _keyword_jaccard(a: list[str], b: list[str]) -> float:
    set_a = {k.lower().strip() for k in a if k}
    set_b = {k.lower().strip() for k in b if k}
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _title_similarity(a: str, b: str) -> float:
    words_a = {w.lower().strip() for w in a.split() if len(w) > 2}
    words_b = {w.lower().strip() for w in b.split() if len(w) > 2}
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    return overlap / max(len(words_a), len(words_b))


def compute_similarity(inp: SimilarityInput) -> SimilarityResult:
    details = []
    scores = []

    for item in inp.existing_items:
        item_kw = item.get("keywords", [])
        item_title = item.get("title", "")
        item_id = item.get("id", "")

        kw_sim = _keyword_jaccard(inp.new_keywords, item_kw)
        title_sim = _title_similarity(inp.new_title, item_title)
        combined = 0.6 * kw_sim + 0.4 * title_sim

        scores.append(combined)
        details.append(
            {
                "content_id": item_id,
                "keyword_similarity": round(kw_sim, 4),
                "title_similarity": round(title_sim, 4),
                "combined_similarity": round(combined, 4),
            }
        )

    if not scores:
        return SimilarityResult(
            is_too_similar=False,
            max_similarity_score=0.0,
            avg_similarity_score=0.0,
            compared_against_count=0,
            most_similar_id=None,
            details=[],
            threshold_used=SIMILARITY_THRESHOLD,
            explanation="No existing content to compare against.",
        )

    max_score = max(scores)
    avg_score = sum(scores) / len(scores)
    most_similar_idx = scores.index(max_score)
    most_similar_id = details[most_similar_idx]["content_id"] if details else None
    is_too_similar = max_score >= SIMILARITY_THRESHOLD

    explanation = (
        f"Compared against {len(scores)} items. "
        f"Max similarity: {max_score:.3f}, avg: {avg_score:.3f}, threshold: {SIMILARITY_THRESHOLD}. "
    )
    if is_too_similar:
        explanation += "Content is TOO SIMILAR — recommend rewrite or different angle."
    else:
        explanation += "Originality check passed."

    return SimilarityResult(
        is_too_similar=is_too_similar,
        max_similarity_score=round(max_score, 4),
        avg_similarity_score=round(avg_score, 4),
        compared_against_count=len(scores),
        most_similar_id=most_similar_id,
        details=details,
        threshold_used=SIMILARITY_THRESHOLD,
        explanation=explanation,
    )

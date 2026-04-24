"""QA / compliance / originality scoring engine.

Evaluates content items across 6 quality dimensions. Returns decomposed scores,
blocking issues, and a recommended QA status (pass/fail/review).
"""

from dataclasses import dataclass

FORMULA_VERSION = "v1"

ORIGINALITY_THRESHOLD = 0.4
COMPLIANCE_THRESHOLD = 0.5
COMPOSITE_PASS_THRESHOLD = 0.6
COMPOSITE_REVIEW_THRESHOLD = 0.4


@dataclass
class QAInput:
    originality_score: float = 0.5
    compliance_score: float = 0.5
    brand_alignment_score: float = 0.5
    technical_quality_score: float = 0.5
    audio_quality_score: float = 0.5
    visual_quality_score: float = 0.5
    has_required_disclosures: bool = True
    has_sponsor_metadata: bool = True
    is_sponsored_content: bool = False
    word_count: int = 0
    duration_seconds: int = 0


@dataclass
class QAResult:
    qa_status: str
    composite_score: float
    originality_score: float
    compliance_score: float
    brand_alignment_score: float
    technical_quality_score: float
    audio_quality_score: float
    visual_quality_score: float
    issues: list[str]
    recommendations: list[str]
    automated_checks: dict
    explanation: str
    formula_version: str = FORMULA_VERSION


def compute_qa_score(inp: QAInput) -> QAResult:
    scores = {
        "originality": max(0.0, min(1.0, inp.originality_score)),
        "compliance": max(0.0, min(1.0, inp.compliance_score)),
        "brand_alignment": max(0.0, min(1.0, inp.brand_alignment_score)),
        "technical_quality": max(0.0, min(1.0, inp.technical_quality_score)),
        "audio_quality": max(0.0, min(1.0, inp.audio_quality_score)),
        "visual_quality": max(0.0, min(1.0, inp.visual_quality_score)),
    }

    composite = (
        0.20 * scores["originality"]
        + 0.20 * scores["compliance"]
        + 0.15 * scores["brand_alignment"]
        + 0.15 * scores["technical_quality"]
        + 0.15 * scores["audio_quality"]
        + 0.15 * scores["visual_quality"]
    )

    issues = []
    recommendations = []
    checks = {}

    checks["disclosures_present"] = inp.has_required_disclosures
    if not inp.has_required_disclosures:
        issues.append("Required disclosures missing — publication blocked")

    checks["sponsor_metadata_present"] = inp.has_sponsor_metadata or not inp.is_sponsored_content
    if inp.is_sponsored_content and not inp.has_sponsor_metadata:
        issues.append("Sponsor metadata missing for sponsored content — publication blocked")

    checks["originality_above_threshold"] = scores["originality"] >= ORIGINALITY_THRESHOLD
    if scores["originality"] < ORIGINALITY_THRESHOLD:
        issues.append(
            f"Originality {scores['originality']:.2f} below {ORIGINALITY_THRESHOLD} — force rewrite or guarded path"
        )
        recommendations.append("Rewrite with different angle to improve originality")

    checks["compliance_above_threshold"] = scores["compliance"] >= COMPLIANCE_THRESHOLD
    if scores["compliance"] < COMPLIANCE_THRESHOLD:
        issues.append(f"Compliance {scores['compliance']:.2f} below {COMPLIANCE_THRESHOLD}")
        recommendations.append("Review for regulatory compliance issues")

    if scores["technical_quality"] < 0.4:
        recommendations.append("Technical quality low — consider re-rendering")
    if scores["brand_alignment"] < 0.5:
        recommendations.append("Content may not align with brand voice guidelines")

    has_blocking_issues = not inp.has_required_disclosures or (
        inp.is_sponsored_content and not inp.has_sponsor_metadata
    )

    if has_blocking_issues:
        qa_status = "fail"
    elif scores["originality"] < ORIGINALITY_THRESHOLD:
        qa_status = "review"
    elif composite >= COMPOSITE_PASS_THRESHOLD:
        qa_status = "pass"
    elif composite >= COMPOSITE_REVIEW_THRESHOLD:
        qa_status = "review"
    else:
        qa_status = "fail"

    explanation = (
        f"QA {qa_status.upper()}: composite={composite:.3f}. "
        f"originality={scores['originality']:.2f}, compliance={scores['compliance']:.2f}, "
        f"brand={scores['brand_alignment']:.2f}, tech={scores['technical_quality']:.2f}."
    )
    if issues:
        explanation += f" Issues: {'; '.join(issues)}."

    return QAResult(
        qa_status=qa_status,
        composite_score=round(composite, 4),
        originality_score=scores["originality"],
        compliance_score=scores["compliance"],
        brand_alignment_score=scores["brand_alignment"],
        technical_quality_score=scores["technical_quality"],
        audio_quality_score=scores["audio_quality"],
        visual_quality_score=scores["visual_quality"],
        issues=issues,
        recommendations=recommendations,
        automated_checks=checks,
        explanation=explanation,
    )

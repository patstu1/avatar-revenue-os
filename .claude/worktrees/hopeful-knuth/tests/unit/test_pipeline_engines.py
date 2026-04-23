"""Unit tests for Phase 3 scoring engines: publish score, QA, similarity."""
import pytest
from packages.scoring.publish import PublishScoreInput, compute_publish_score, WEIGHTS
from packages.scoring.qa import QAInput, compute_qa_score
from packages.scoring.similarity import SimilarityInput, compute_similarity


class TestPublishScore:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_zero_input(self):
        result = compute_publish_score(PublishScoreInput())
        assert result.composite_score == 0.0
        assert not result.publish_ready

    def test_strong_content_passes(self):
        result = compute_publish_score(PublishScoreInput(
            hook_strength=0.8, monetization_fit=0.7, originality=0.8,
            compliance=0.9, retention_likelihood=0.7, cta_clarity=0.8,
            brand_consistency=0.7, thumbnail_ctr_prediction=0.6,
            expected_profit_score=0.7,
        ))
        assert result.composite_score > 0.6
        assert result.publish_ready
        assert result.confidence == "high"

    def test_low_compliance_blocks(self):
        result = compute_publish_score(PublishScoreInput(
            hook_strength=0.8, originality=0.8, compliance=0.3,
        ))
        assert not result.publish_ready
        assert any("Compliance" in b for b in result.blocking_issues)

    def test_low_originality_blocks(self):
        result = compute_publish_score(PublishScoreInput(
            hook_strength=0.8, compliance=0.9, originality=0.2,
        ))
        assert not result.publish_ready
        assert any("originality" in b.lower() for b in result.blocking_issues)

    def test_explanation_present(self):
        result = compute_publish_score(PublishScoreInput(hook_strength=0.5))
        assert "Publish score" in result.explanation


class TestQAScoring:
    def test_good_content_passes(self):
        result = compute_qa_score(QAInput(
            originality_score=0.8, compliance_score=0.9,
            brand_alignment_score=0.7, technical_quality_score=0.8,
        ))
        assert result.qa_status == "pass"
        assert result.composite_score > 0.6

    def test_missing_disclosures_fails(self):
        result = compute_qa_score(QAInput(has_required_disclosures=False))
        assert result.qa_status == "fail"
        assert any("disclosures" in i.lower() for i in result.issues)

    def test_missing_sponsor_metadata_fails(self):
        result = compute_qa_score(QAInput(
            is_sponsored_content=True, has_sponsor_metadata=False,
        ))
        assert result.qa_status == "fail"
        assert any("sponsor" in i.lower() for i in result.issues)

    def test_low_originality_routes_to_review(self):
        result = compute_qa_score(QAInput(
            originality_score=0.2, compliance_score=0.9,
            brand_alignment_score=0.7, technical_quality_score=0.7,
        ))
        assert result.qa_status == "review"

    def test_all_checks_recorded(self):
        result = compute_qa_score(QAInput())
        assert "disclosures_present" in result.automated_checks
        assert "originality_above_threshold" in result.automated_checks
        assert "compliance_above_threshold" in result.automated_checks

    def test_explanation_contains_scores(self):
        result = compute_qa_score(QAInput())
        assert "originality=" in result.explanation
        assert "compliance=" in result.explanation


class TestSimilarity:
    def test_no_existing_content(self):
        result = compute_similarity(SimilarityInput(new_keywords=["test"]))
        assert not result.is_too_similar
        assert result.compared_against_count == 0

    def test_identical_keywords_detected(self):
        result = compute_similarity(SimilarityInput(
            new_keywords=["budget", "savings", "money"],
            new_title="Budget Tips",
            existing_items=[
                {"id": "x1", "keywords": ["budget", "savings", "money"], "title": "Budget Tips"},
            ],
        ))
        assert result.max_similarity_score > 0.8
        assert result.is_too_similar

    def test_different_keywords_pass(self):
        result = compute_similarity(SimilarityInput(
            new_keywords=["investing", "stocks"],
            new_title="Stock Market Guide",
            existing_items=[
                {"id": "x1", "keywords": ["budget", "savings"], "title": "Budget Tips"},
            ],
        ))
        assert not result.is_too_similar
        assert result.max_similarity_score < 0.5

    def test_details_contain_per_item_scores(self):
        result = compute_similarity(SimilarityInput(
            new_keywords=["a", "b"],
            existing_items=[
                {"id": "1", "keywords": ["a"], "title": "T1"},
                {"id": "2", "keywords": ["c"], "title": "T2"},
            ],
        ))
        assert len(result.details) == 2
        assert "combined_similarity" in result.details[0]

    def test_explanation_present(self):
        result = compute_similarity(SimilarityInput(
            new_keywords=["test"],
            existing_items=[{"id": "1", "keywords": ["test"], "title": "Test"}],
        ))
        assert "Compared against" in result.explanation

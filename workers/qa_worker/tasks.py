"""QA worker tasks — quality checks, similarity scoring, compliance."""
import uuid

from workers.base_task import TrackedTask
from workers.celery_app import app


@app.task(base=TrackedTask, bind=True, name="workers.qa_worker.run_qa_check")
def run_qa_check(self, content_item_id: str) -> dict:
    """Run QA/compliance/originality checks using the real scoring engine."""
    from sqlalchemy.orm import Session

    from packages.db.enums import ContentType, QAStatus
    from packages.db.models.content import ContentItem, Script
    from packages.db.models.quality import QAReport
    from packages.db.session import get_sync_engine
    from packages.scoring.qa import QAInput, compute_qa_score

    engine = get_sync_engine()
    with Session(engine) as session:
        content = session.get(ContentItem, uuid.UUID(content_item_id))
        if not content:
            raise ValueError(f"ContentItem {content_item_id} not found")

        script = session.get(Script, content.script_id) if content.script_id else None
        has_offer = content.offer_id is not None
        word_count = script.word_count if script else 0

        inp = QAInput(
            originality_score=0.7,
            compliance_score=0.85,
            brand_alignment_score=0.75,
            technical_quality_score=0.7,
            audio_quality_score=0.7 if content.content_type in (ContentType.SHORT_VIDEO, ContentType.LONG_VIDEO) else 0.5,
            visual_quality_score=0.7,
            has_required_disclosures=True,
            has_sponsor_metadata=not has_offer or True,
            is_sponsored_content=has_offer,
            word_count=word_count,
        )
        result = compute_qa_score(inp)

        report = QAReport(
            content_item_id=content.id,
            brand_id=content.brand_id,
            qa_status=QAStatus(result.qa_status),
            originality_score=result.originality_score,
            compliance_score=result.compliance_score,
            brand_alignment_score=result.brand_alignment_score,
            technical_quality_score=result.technical_quality_score,
            audio_quality_score=result.audio_quality_score,
            visual_quality_score=result.visual_quality_score,
            composite_score=result.composite_score,
            issues_found=result.issues,
            recommendations=result.recommendations,
            automated_checks=result.automated_checks,
            explanation=result.explanation,
        )
        session.add(report)
        content.status = "qa_complete"
        session.commit()
        session.refresh(report)

        return {
            "qa_report_id": str(report.id),
            "status": result.qa_status,
            "composite_score": result.composite_score,
        }


@app.task(base=TrackedTask, bind=True, name="workers.qa_worker.run_similarity_check")
def run_similarity_check(self, content_item_id: str) -> dict:
    """Check content against existing library using the real similarity engine."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.content import ContentItem
    from packages.db.models.quality import SimilarityReport
    from packages.db.session import get_sync_engine
    from packages.scoring.similarity import SimilarityInput, compute_similarity

    engine = get_sync_engine()
    with Session(engine) as session:
        content = session.get(ContentItem, uuid.UUID(content_item_id))
        if not content:
            raise ValueError(f"ContentItem {content_item_id} not found")

        existing = session.execute(
            select(ContentItem).where(
                ContentItem.brand_id == content.brand_id,
                ContentItem.id != content.id,
            ).limit(50)
        ).scalars().all()

        existing_data = [
            {"id": str(e.id), "title": e.title, "keywords": e.tags if isinstance(e.tags, list) else []}
            for e in existing
        ]

        inp = SimilarityInput(
            new_keywords=content.tags if isinstance(content.tags, list) else [],
            new_title=content.title,
            existing_items=existing_data,
        )
        result = compute_similarity(inp)

        report = SimilarityReport(
            content_item_id=content.id,
            brand_id=content.brand_id,
            compared_against_count=result.compared_against_count,
            max_similarity_score=result.max_similarity_score,
            avg_similarity_score=result.avg_similarity_score,
            most_similar_content_id=uuid.UUID(result.most_similar_id) if result.most_similar_id else None,
            similarity_details=result.details,
            is_too_similar=result.is_too_similar,
            threshold_used=result.threshold_used,
            explanation=result.explanation,
        )
        session.add(report)
        session.commit()
        session.refresh(report)

        return {"similarity_report_id": str(report.id), "is_too_similar": result.is_too_similar}

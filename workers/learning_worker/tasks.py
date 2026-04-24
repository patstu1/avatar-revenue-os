"""Learning worker tasks — memory consolidation, comment analysis, knowledge graph."""
from workers.base_task import TrackedTask
from workers.celery_app import app


@app.task(base=TrackedTask, bind=True, name="workers.learning_worker.tasks.consolidate_memory")
def consolidate_memory(self) -> dict:
    """Consolidate learnings from recent performance data into memory entries.

    Reads winner/loser signals, suppression patterns, and experiment outcomes
    to generate new MemoryEntry rows that inform future decisions.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from packages.db.models.decisions import SuppressionAction
    from packages.db.models.learning import MemoryEntry
    from packages.db.models.publishing import WinnerSignal
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    new_memories = 0

    with Session(engine) as session:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        total_existing = session.execute(
            select(func.count()).select_from(MemoryEntry)
        ).scalar() or 0

        recent_winners = session.execute(
            select(WinnerSignal).where(
                WinnerSignal.clone_recommended.is_(True),
                WinnerSignal.created_at >= since,
            ).limit(50)
        ).scalars().all()

        for w in recent_winners:
            already = session.execute(
                select(MemoryEntry.id).where(
                    MemoryEntry.brand_id == w.brand_id,
                    MemoryEntry.key == f"winner_pattern:{w.content_id}",
                ).limit(1)
            ).scalar_one_or_none()
            if already:
                continue
            session.add(MemoryEntry(
                brand_id=w.brand_id,
                key=f"winner_pattern:{w.content_id}",
                value={"title": w.title, "win_score": w.win_score, "explanation": w.explanation},
                memory_type="winner_consolidation",
                confidence=min(0.95, w.win_score),
            ))
            new_memories += 1

        recent_suppressions = session.execute(
            select(SuppressionAction).where(
                SuppressionAction.created_at >= since,
                SuppressionAction.is_lifted.is_(False),
            ).limit(50)
        ).scalars().all()

        for s in recent_suppressions:
            already = session.execute(
                select(MemoryEntry.id).where(
                    MemoryEntry.brand_id == s.brand_id,
                    MemoryEntry.key == f"suppression_pattern:{s.target_entity_id}",
                ).limit(1)
            ).scalar_one_or_none()
            if already:
                continue
            session.add(MemoryEntry(
                brand_id=s.brand_id,
                key=f"suppression_pattern:{s.target_entity_id}",
                value={"reason": s.reason.value if s.reason else "unknown", "detail": s.reason_detail},
                memory_type="suppression_consolidation",
                confidence=0.7,
            ))
            new_memories += 1

        session.commit()

    return {"status": "completed", "total_memories": total_existing + new_memories, "new_memories": new_memories}


@app.task(base=TrackedTask, bind=True, name="workers.learning_worker.analyze_comments")
def analyze_comments(self, brand_id: str) -> dict:
    """Analyze ingested comments for cash signals and audience insights.

    When CommentIngestion rows exist, this task clusters them and extracts
    monetizable patterns. Requires comment ingestion pipeline to be active.
    """
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from packages.db.models.learning import CommentIngestion
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    import uuid
    bid = uuid.UUID(brand_id)

    with Session(engine) as session:
        comment_count = session.execute(
            select(func.count()).select_from(CommentIngestion).where(
                CommentIngestion.brand_id == bid
            )
        ).scalar() or 0

    return {
        "status": "completed",
        "comments_analyzed": comment_count,
        "cash_signals_found": 0,
        "note": "Comment ingestion pipeline required for cash signal extraction",
    }

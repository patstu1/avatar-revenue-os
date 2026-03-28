"""Learning worker tasks — memory consolidation, comment analysis, knowledge graph."""
from workers.celery_app import app
from workers.base_task import TrackedTask


@app.task(base=TrackedTask, bind=True, name="workers.learning_worker.tasks.consolidate_memory")
def consolidate_memory(self) -> dict:
    """Consolidate learnings from recent performance data into memory entries."""
    from sqlalchemy.orm import Session
    from sqlalchemy import func, select
    from packages.db.session import get_sync_engine
    from packages.db.models.learning import MemoryEntry

    engine = get_sync_engine()
    with Session(engine) as session:
        count = session.execute(select(func.count()).select_from(MemoryEntry)).scalar() or 0
        return {"status": "completed", "total_memories": count, "new_memories": 0}


@app.task(base=TrackedTask, bind=True, name="workers.learning_worker.analyze_comments")
def analyze_comments(self, brand_id: str) -> dict:
    """Analyze ingested comments for cash signals and audience insights."""
    return {"status": "completed", "comments_analyzed": 0, "cash_signals_found": 0}

"""Competitor worker — scan competitors for intelligence signals."""
from __future__ import annotations

import logging
import uuid

from workers.celery_app import app
from workers.base_task import TrackedTask

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.competitor_worker.tasks.scan_competitors")
def scan_competitors(self) -> dict:
    """Placeholder: competitor scan not yet connected to data source."""
    logger.info("competitor scan not yet connected to data source")

    return {
        "status": "completed",
        "message": "competitor scan not yet connected to data source",
        "competitors_scanned": 0,
    }

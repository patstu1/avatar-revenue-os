"""Publishing worker tasks — native-first publishing with aggregator fallback + express publish.

Flow:
1. publish_content: Single job dispatch via route_and_publish (native -> aggregator chain).
2. express_publish: Highest-priority task for trend-reactive content. Publishes to ALL
   active accounts simultaneously, bypassing the normal queue.

No artificial caps. No retry ceilings. System retries on next cycle if all methods fail.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from workers.celery_app import app
from workers.base_task import TrackedTask

import workers.publishing_worker.auto_publish  # noqa: F401
import workers.publishing_worker.measured_data_cascade  # noqa: F401


@app.task(base=TrackedTask, bind=True, name="workers.publishing_worker.publish_content")
def publish_content(self, publish_job_id: str) -> dict:
    """Execute a publish job via native-first routing with aggregator fallback.

    Routing order:
    1. Native platform API (YouTube, TikTok, Instagram, X) if OAuth tokens exist.
    2. Aggregator chain (Buffer -> Publer -> Ayrshare) as fallback.
    3. If all fail: emit event, system retries on next cycle.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.publishing import PublishJob
    from packages.db.models.content import ContentItem
    from packages.db.models.accounts import CreatorAccount
    from packages.db.enums import JobStatus
    from apps.api.services.event_bus import emit_event_sync

    engine = get_sync_engine()
    with Session(engine) as session:
        job = session.get(PublishJob, uuid.UUID(publish_job_id))
        if not job:
            raise ValueError(f"PublishJob {publish_job_id} not found")

        # ── Quality Governor gate ──────────────────────────────────────
        from packages.db.models.quality_governor import QualityGovernorReport
        if job.content_item_id:
            qg = session.query(QualityGovernorReport).filter(
                QualityGovernorReport.content_item_id == job.content_item_id,
                QualityGovernorReport.is_active.is_(True),
            ).order_by(QualityGovernorReport.created_at.desc()).first()
            if qg and not qg.publish_allowed:
                job.status = JobStatus.FAILED
                job.error_message = f"Quality Governor blocked: {qg.verdict} (score={qg.total_score:.2f})"
                session.commit()
                return {"publish_job_id": publish_job_id, "status": "quality_blocked", "reason": job.error_message}

        # ── Workflow gate ──────────────────────────────────────────────
        from packages.db.models.workflow_builder import WorkflowInstance
        if job.content_item_id:
            wf_inst = session.query(WorkflowInstance).filter(
                WorkflowInstance.resource_type == "content_item",
                WorkflowInstance.resource_id == job.content_item_id,
                WorkflowInstance.is_active.is_(True),
            ).order_by(WorkflowInstance.created_at.desc()).first()
            if wf_inst and wf_inst.status == "in_progress":
                job.status = JobStatus.FAILED
                job.error_message = f"Workflow pending: step {wf_inst.current_step_order} awaiting approval"
                session.commit()
                return {"publish_job_id": publish_job_id, "status": "workflow_pending", "reason": job.error_message}

        # ── Warmup capacity enforcement ─────────────────────────────
        if job.creator_account_id:
            acct_for_warmup = session.get(CreatorAccount, job.creator_account_id)
            if acct_for_warmup:
                try:
                    from packages.db.models.autonomous_phase_a import AccountWarmupPlan
                    from sqlalchemy import func as sqlfunc
                    warmup = session.query(AccountWarmupPlan).filter(
                        AccountWarmupPlan.account_id == job.creator_account_id,
                        AccountWarmupPlan.is_active.is_(True),
                    ).order_by(AccountWarmupPlan.created_at.desc()).first()
                    if warmup and warmup.warmup_phase and "warmup" in warmup.warmup_phase.lower():
                        max_per_day = warmup.current_posts_per_week // 7 if warmup.current_posts_per_week else 1
                        max_per_day = max(max_per_day, 1)
                        from datetime import datetime, timedelta, timezone as tz
                        today_start = datetime.now(tz.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                        published_today = session.query(sqlfunc.count()).select_from(PublishJob).filter(
                            PublishJob.creator_account_id == job.creator_account_id,
                            PublishJob.status == JobStatus.COMPLETED,
                            PublishJob.published_at >= today_start,
                        ).scalar() or 0
                        if published_today >= max_per_day:
                            job.status = JobStatus.FAILED
                            job.error_message = (
                                f"Warmup cap: {published_today}/{max_per_day} posts today "
                                f"(phase={warmup.warmup_phase}, {warmup.current_posts_per_week}/wk)"
                            )
                            session.commit()
                            logger.warning("publish.warmup_blocked",
                                           account_id=str(job.creator_account_id),
                                           published_today=published_today, cap=max_per_day)
                            return {"publish_job_id": publish_job_id, "status": "warmup_blocked",
                                    "reason": job.error_message}
                except Exception:
                    logger.debug("warmup_check_failed", exc_info=True)

        job.status = JobStatus.RUNNING
        session.commit()

        # ── Load related entities ──────────────────────────────────────
        content = session.get(ContentItem, job.content_item_id) if job.content_item_id else None
        account = session.get(CreatorAccount, job.creator_account_id) if job.creator_account_id else None

        # ── Resolve org_id ─────────────────────────────────────────────
        org_id = None
        if job.brand_id:
            from packages.db.models.core import Brand
            brand = session.get(Brand, job.brand_id)
            if brand:
                org_id = brand.organization_id

        # ── Route and publish via native-first dispatcher ──────────────
        from packages.clients.distributor_router import route_and_publish

        loop = asyncio.new_event_loop()
        try:
            publish_result = loop.run_until_complete(
                route_and_publish(session, job, content, account, org_id)
            )
        finally:
            loop.close()

        # ── Process result ─────────────────────────────────────────────
        platform_val = job.platform.value if hasattr(job.platform, "value") else str(job.platform)

        if publish_result.success:
            job.status = JobStatus.COMPLETED
            job.published_at = datetime.now(timezone.utc)
            job.error_message = None
            job.platform_post_id = publish_result.post_id
            job.platform_post_url = publish_result.post_url
            # Store publish method in job metadata
            job.publish_config = {
                **(job.publish_config or {}),
                "publish_method": publish_result.method,
                "methods_tried": publish_result.methods_tried,
                "published_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            if content:
                content.status = "published"
            session.commit()

            return {
                "publish_job_id": str(job.id),
                "status": "published",
                "method": publish_result.method,
                "methods_tried": publish_result.methods_tried,
                "platform": platform_val,
                "post_id": publish_result.post_id,
                "post_url": publish_result.post_url,
                "published_at": job.published_at.isoformat(),
            }
        else:
            job.status = JobStatus.FAILED
            job.error_message = publish_result.error
            job.retries = (job.retries or 0) + 1
            job.error_details = {
                **(job.error_details or {}),
                "methods_tried": publish_result.methods_tried,
                "last_method": publish_result.method,
                "failure_time": datetime.now(timezone.utc).isoformat(),
            }
            session.commit()

            # Emit event so system can retry on next cycle
            try:
                emit_event_sync(
                    session,
                    domain="publishing",
                    event_type="publish.all_methods_failed",
                    summary=f"All publish methods failed for job {publish_job_id} on {platform_val}: {publish_result.error}",
                    org_id=org_id,
                    brand_id=job.brand_id,
                    entity_type="publish_job",
                    entity_id=job.id,
                    severity="warning",
                    details={
                        "methods_tried": publish_result.methods_tried,
                        "error": publish_result.error,
                        "retries": job.retries,
                    },
                    requires_action=True,
                )
                session.commit()
            except Exception:
                pass  # Don't fail the task over event emission

            return {
                "publish_job_id": str(job.id),
                "status": "failed",
                "method": publish_result.method,
                "methods_tried": publish_result.methods_tried,
                "platform": platform_val,
                "error": job.error_message,
                "retries": job.retries,
            }


@app.task(
    base=TrackedTask,
    bind=True,
    name="workers.publishing_worker.express_publish",
    priority=9,  # Highest Celery priority (0=lowest, 9=highest)
    queue="publishing",
)
def express_publish(self, content_item_id: str, brand_id: str, reason: str = "trend_reactive") -> dict:
    """Express publish — highest priority, simultaneous multi-platform dispatch.

    For trend-reactive and time-sensitive content. Publishes to ALL active accounts
    for the brand simultaneously, bypassing the normal publishing queue.

    Args:
        content_item_id: UUID of the content item to publish.
        brand_id: UUID of the brand.
        reason: Why this is express ("trend_reactive", "time_sensitive", "breaking").
    """
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    from packages.db.session import get_sync_engine
    from packages.db.models.content import ContentItem
    from packages.db.models.core import Brand
    from packages.db.models.integration_registry import CreatorPlatformAccount
    from packages.db.models.accounts import CreatorAccount
    from packages.db.enums import JobStatus
    from packages.db.models.publishing import PublishJob
    from apps.api.services.event_bus import emit_event_sync

    engine = get_sync_engine()
    with Session(engine) as session:
        content = session.get(ContentItem, uuid.UUID(content_item_id))
        if not content:
            raise ValueError(f"ContentItem {content_item_id} not found")

        brand = session.get(Brand, uuid.UUID(brand_id))
        if not brand:
            raise ValueError(f"Brand {brand_id} not found")

        org_id = brand.organization_id

        # ── Find all active accounts for this brand ────────────────────
        accounts = session.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand.id,
                CreatorAccount.is_active.is_(True),
            )
        ).scalars().all()

        if not accounts:
            return {
                "content_item_id": content_item_id,
                "brand_id": brand_id,
                "status": "no_accounts",
                "reason": reason,
                "error": "No active accounts found for brand",
            }

        # ── Create publish jobs for each account ───────────────────────
        jobs = []
        for acct in accounts:
            platform = acct.platform
            pj = PublishJob(
                content_item_id=content.id,
                creator_account_id=acct.id,
                brand_id=brand.id,
                platform=platform,
                status=JobStatus.RUNNING,
                publish_config={"express": True, "reason": reason},
            )
            session.add(pj)
            jobs.append((pj, acct))
        session.flush()

        # ── Publish to all platforms simultaneously ────────────────────
        from packages.clients.distributor_router import route_and_publish

        async def _publish_all():
            tasks = []
            for pj, acct in jobs:
                tasks.append(route_and_publish(session, pj, content, acct, org_id))
            return await asyncio.gather(*tasks, return_exceptions=True)

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(_publish_all())
        finally:
            loop.close()

        # ── Process results ────────────────────────────────────────────
        successes = []
        failures = []

        for (pj, acct), result in zip(jobs, results):
            platform_val = pj.platform.value if hasattr(pj.platform, "value") else str(pj.platform)

            if isinstance(result, Exception):
                pj.status = JobStatus.FAILED
                pj.error_message = str(result)
                failures.append({"platform": platform_val, "error": str(result)})
            elif result.success:
                pj.status = JobStatus.COMPLETED
                pj.published_at = datetime.now(timezone.utc)
                pj.platform_post_id = result.post_id
                pj.platform_post_url = result.post_url
                pj.publish_config = {
                    **(pj.publish_config or {}),
                    "publish_method": result.method,
                    "methods_tried": result.methods_tried,
                }
                successes.append({
                    "platform": platform_val,
                    "method": result.method,
                    "post_id": result.post_id,
                    "post_url": result.post_url,
                })
            else:
                pj.status = JobStatus.FAILED
                pj.error_message = result.error
                pj.error_details = {
                    "methods_tried": result.methods_tried,
                    "last_method": result.method,
                }
                failures.append({
                    "platform": platform_val,
                    "error": result.error,
                    "methods_tried": result.methods_tried,
                })

        # Update content status if any succeeded
        if successes:
            content.status = "published"

        session.commit()

        # ── Emit event ─────────────────────────────────────────────────
        try:
            emit_event_sync(
                session,
                domain="publishing",
                event_type="publish.express_completed",
                summary=f"Express publish: {len(successes)} succeeded, {len(failures)} failed across {len(jobs)} platforms",
                org_id=org_id,
                brand_id=brand.id,
                entity_type="content_item",
                entity_id=content.id,
                severity="info" if successes else "warning",
                details={
                    "reason": reason,
                    "successes": successes,
                    "failures": failures,
                    "total_accounts": len(jobs),
                },
                requires_action=bool(failures),
            )
            session.commit()
        except Exception:
            pass

        return {
            "content_item_id": content_item_id,
            "brand_id": brand_id,
            "reason": reason,
            "status": "completed",
            "total_accounts": len(jobs),
            "successes": successes,
            "failures": failures,
            "success_count": len(successes),
            "failure_count": len(failures),
        }

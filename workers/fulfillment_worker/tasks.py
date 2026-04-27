"""Batch 9 — fulfillment worker tasks.

Four scheduled tasks that close the autonomous tail of the revenue
circle. All run via Celery beat; all are idempotent and tolerate
missed ticks.

Tasks:
  - drain_pending_production_jobs  (every 60s)
  - dispatch_due_followups         (every 15 min)
  - chase_unpaid_proposals_task    (every 6h)
  - reconcile_stripe_webhooks_task (every 10 min)

Each task runs inside a fresh DB session using the same
``run_async`` / async-session-factory pattern as the existing workers.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import socket
from datetime import datetime, timedelta, timezone

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from workers.base_task import TrackedTask


def _fresh_session_factory():
    """Build a fresh async_sessionmaker with a fresh engine inside the
    current thread's event loop.

    We do NOT reuse ``packages.db.session.get_async_session_factory``
    because it caches the engine globally; that engine's connection
    pool binds to the first event loop that opened a connection, and
    subsequent Celery task invocations (each in a fresh thread+loop)
    then crash with ``Future attached to a different loop``.
    """
    db_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(db_url, pool_pre_ping=True, pool_size=2, max_overflow=2)
    return async_sessionmaker(engine, expire_on_commit=False), engine


logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from sync Celery task context.

    Always runs inside a fresh ThreadPoolExecutor thread that owns its
    own event loop. This prevents "Future attached to a different loop"
    errors when the persistent Celery worker process invokes us
    repeatedly: each call gets a private loop, and the async session
    factory's engine binds fresh inside that thread instead of leaking
    across invocations.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


_WORKER_ID = f"fulfillment_worker@{socket.gethostname()}/{os.getpid()}"
STUCK_IN_PROGRESS_HOURS = 4


# ═══════════════════════════════════════════════════════════════════════════
#  1. drain_pending_production_jobs
# ═══════════════════════════════════════════════════════════════════════════


async def _drain_pending_production_jobs() -> dict:
    """Pick up queued production jobs, transition to in_progress, emit events.

    Also detects stuck in_progress jobs older than 4h and escalates to GM.
    """
    from apps.api.services.event_bus import emit_event
    from apps.api.services.stage_controller import mark_stage
    from packages.db.models.fulfillment import ProductionJob
    from packages.db.models.gm_control import GMEscalation

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        now = datetime.now(timezone.utc)

        # 1a. Pick up pending jobs.
        pending = (
            (
                await db.execute(
                    select(ProductionJob)
                    .where(
                        ProductionJob.status == "queued",
                        ProductionJob.is_active.is_(True),
                        ProductionJob.picked_up_at.is_(None),
                    )
                    .limit(25)
                )
            )
            .scalars()
            .all()
        )

        picked = 0
        for job in pending:
            job.status = "in_progress"
            job.picked_up_at = now
            job.worker_id = _WORKER_ID
            job.attempt_count = (job.attempt_count or 0) + 1
            job.started_at = job.started_at or now
            picked += 1

            await emit_event(
                db,
                domain="fulfillment",
                event_type="production.job.picked_up",
                summary=f"Production job picked up by fulfillment worker: {job.title[:80]}",
                org_id=job.org_id,
                entity_type="production_job",
                entity_id=job.id,
                previous_state="queued",
                new_state="in_progress",
                actor_type="system",
                actor_id=_WORKER_ID,
                details={
                    "production_job_id": str(job.id),
                    "worker_id": _WORKER_ID,
                    "attempt": job.attempt_count,
                    "avenue_slug": job.avenue_slug,
                },
            )
            try:
                await mark_stage(
                    db,
                    org_id=job.org_id,
                    entity_type="production_job",
                    entity_id=job.id,
                    stage="in_progress",
                )
            except Exception as stage_exc:
                logger.warning(
                    "production.mark_stage_failed",
                    job_id=str(job.id),
                    error=str(stage_exc)[:150],
                )
        await db.flush()

        # 1b. Detect stuck jobs.
        stuck_cutoff = now - timedelta(hours=STUCK_IN_PROGRESS_HOURS)
        stuck_jobs = (
            (
                await db.execute(
                    select(ProductionJob)
                    .where(
                        ProductionJob.status == "in_progress",
                        ProductionJob.is_active.is_(True),
                        ProductionJob.picked_up_at.isnot(None),
                        ProductionJob.picked_up_at < stuck_cutoff,
                    )
                    .limit(25)
                )
            )
            .scalars()
            .all()
        )

        escalated = 0
        for job in stuck_jobs:
            existing_esc = (
                await db.execute(
                    select(GMEscalation).where(
                        GMEscalation.entity_type == "production_job",
                        GMEscalation.entity_id == job.id,
                        GMEscalation.reason_code == "production_job_stuck",
                        GMEscalation.status == "open",
                    )
                )
            ).scalar_one_or_none()
            if existing_esc is not None:
                continue
            db.add(
                GMEscalation(
                    org_id=job.org_id,
                    reason_code="production_job_stuck",
                    entity_type="production_job",
                    entity_id=job.id,
                    title=f"Production job stuck in_progress: {job.title[:300]}",
                    description=(
                        f"Job {job.id} was picked up at {job.picked_up_at.isoformat()} "
                        f"and has been in_progress for >{STUCK_IN_PROGRESS_HOURS}h "
                        f"without completing. Operator must either call "
                        f"/gm/write/production/{{id}}/submit-output with a real "
                        f"deliverable URL or cancel the job."
                    ),
                    severity="warning",
                    status="open",
                    details_json={
                        "production_job_id": str(job.id),
                        "avenue_slug": job.avenue_slug,
                        "picked_up_at": job.picked_up_at.isoformat(),
                        "worker_id": job.worker_id,
                        "attempt_count": job.attempt_count,
                    },
                )
            )
            escalated += 1

        await db.commit()
        summary = {"picked": picked, "stuck_escalated": escalated}
        logger.info("fulfillment.drain_pending.done", **summary)
    await engine.dispose()
    return summary


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.drain_pending_production_jobs",
    queue="default",
)
def drain_pending_production_jobs():
    return _run_async(_drain_pending_production_jobs())


# ═══════════════════════════════════════════════════════════════════════════
#  2. dispatch_due_followups
# ═══════════════════════════════════════════════════════════════════════════


async def _dispatch_due_followups() -> dict:
    """Scan for deliveries with followup_scheduled_at <= now() and
    followup_sent_at IS NULL, send the follow-up email, mark sent.
    """
    from apps.api.services.event_bus import emit_event
    from packages.clients.email_templates import build_delivery_followup
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.clients import Client
    from packages.db.models.delivery import Delivery
    from packages.db.models.fulfillment import ClientProject

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        now = datetime.now(timezone.utc)
        rows = (
            (
                await db.execute(
                    select(Delivery)
                    .where(
                        Delivery.followup_sent_at.is_(None),
                        Delivery.followup_scheduled_at.isnot(None),
                        Delivery.followup_scheduled_at <= now,
                        Delivery.status == "sent",
                        Delivery.is_active.is_(True),
                    )
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

        sent = 0
        failed = 0
        skipped_no_smtp = 0

        for delivery in rows:
            client = (await db.execute(select(Client).where(Client.id == delivery.client_id))).scalar_one_or_none()
            project = (
                await db.execute(select(ClientProject).where(ClientProject.id == delivery.project_id))
            ).scalar_one_or_none()
            if client is None or project is None:
                delivery.followup_sent_at = now  # prevent retry loop
                failed += 1
                continue

            smtp = await SmtpEmailClient.from_db(db, delivery.org_id)
            if smtp is None:
                skipped_no_smtp += 1
                continue

            built = build_delivery_followup(
                display_name=client.display_name or client.primary_email,
                project_title=project.title,
                deliverable_url=delivery.deliverable_url,
            )
            result = await smtp.send_email(
                to_email=delivery.recipient_email or client.primary_email,
                subject=built["subject"],
                body_html=built["html"],
                body_text=built["text"],
            )
            if result.get("success"):
                delivery.followup_sent_at = now
                sent += 1
                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="followup.sent",
                    summary=f"Follow-up sent to {delivery.recipient_email} for {project.title[:80]}",
                    org_id=delivery.org_id,
                    entity_type="delivery",
                    entity_id=delivery.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={
                        "delivery_id": str(delivery.id),
                        "project_id": str(project.id),
                        "avenue_slug": delivery.avenue_slug,
                        "client_id": str(client.id),
                        "provider": result.get("provider", "smtp"),
                    },
                )
            else:
                failed += 1
                logger.warning(
                    "followup.send_failed",
                    delivery_id=str(delivery.id),
                    error=result.get("error"),
                )

        await db.commit()
        summary = {
            "candidates": len(rows),
            "sent": sent,
            "failed": failed,
            "skipped_no_smtp": skipped_no_smtp,
        }
        logger.info("fulfillment.dispatch_followups.done", **summary)
    await engine.dispose()
    return summary


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.dispatch_due_followups",
    queue="default",
)
def dispatch_due_followups():
    return _run_async(_dispatch_due_followups())


# ═══════════════════════════════════════════════════════════════════════════
#  3. chase_unpaid_proposals_task
# ═══════════════════════════════════════════════════════════════════════════


async def _chase_unpaid_proposals_task() -> dict:
    from apps.api.services.proposal_dunning_service import chase_unpaid_proposals

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await chase_unpaid_proposals(db)
    await engine.dispose()
    return result


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.chase_unpaid_proposals",
    queue="default",
)
def chase_unpaid_proposals_task():
    return _run_async(_chase_unpaid_proposals_task())


# ═══════════════════════════════════════════════════════════════════════════
#  4. reconcile_stripe_webhooks_task
# ═══════════════════════════════════════════════════════════════════════════


async def _reconcile_stripe_webhooks_task() -> dict:
    from apps.api.services.stripe_reconciliation_service import (
        reconcile_all_stripe_orgs,
    )

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await reconcile_all_stripe_orgs(db)
    await engine.dispose()
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  5. Batch 11 — retention state scanner
# ═══════════════════════════════════════════════════════════════════════════


async def _scan_retention_states_task() -> dict:
    """Every 6h: re-evaluate retention_state for every active client
    across every org. Emits client.retention_state.changed whenever a
    flip occurs so GM surfaces see candidates in real time.
    """
    from apps.api.services.retention_service import scan_all_retention_states

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await scan_all_retention_states(db)
        await db.commit()
    await engine.dispose()
    return result


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.scan_retention_states",
    queue="default",
)
def scan_retention_states():
    return _run_async(_scan_retention_states_task())


# ═══════════════════════════════════════════════════════════════════════════
#  6. Batch 13 — overdue invoice scanner
# ═══════════════════════════════════════════════════════════════════════════


async def _scan_overdue_invoices_task() -> dict:
    """Every 6h: flip sent → overdue for invoices whose due_date
    has passed, and open a GMEscalation for each so GM surfaces
    them."""
    from apps.api.services.invoice_service import scan_overdue_invoices

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        result = await scan_overdue_invoices(db)
    await engine.dispose()
    return result


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.scan_overdue_invoices",
    queue="default",
)
def scan_overdue_invoices_task():
    return _run_async(_scan_overdue_invoices_task())


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.reconcile_stripe_webhooks",
    queue="default",
)
def reconcile_stripe_webhooks_task():
    return _run_async(_reconcile_stripe_webhooks_task())


# ═══════════════════════════════════════════════════════════════════════════
#  7. execute_content_pack_jobs
#
#  Picks up in_progress content_pack ProductionJobs that have no output_url
#  yet, generates a real Markdown content pack via Anthropic from the
#  approved brief, uploads the artifact via MediaStorage (S3 or local
#  fallback), then calls submit_production_output() which triggers the
#  existing QA → delivery → followup chain automatically.
#
#  Beat: every 2 minutes.  Max 5 jobs per run.  One job failure never
#  kills the whole task.  Fully idempotent — skips jobs that already have
#  output_url or that are no longer in_progress.
# ═══════════════════════════════════════════════════════════════════════════

_CONTENT_PACK_MAX_PER_RUN = 5
_CONTENT_PACK_PROMPT = """\
You are a professional B2B content strategist producing a client-ready content pack.
Generate a complete, structured Markdown content pack based on the project brief below.

The output must be:
- Immediately usable by the client (no placeholders, no "fill in later" notes)
- Professionally written, clear, and actionable
- Formatted in clean Markdown with headings (##), bullet points, and numbered lists
- Between 600 and 1200 words

Structure the pack with these sections (adapt titles to the project):
1. **Overview** — what the pack covers and who it is for
2. **Key Messages** — 3–5 core messages or value propositions
3. **Content Calendar / Topics** — a list of specific content ideas or topics (at least 6)
4. **Sample Content** — one fully written example piece (email, post, or article intro)
5. **Next Steps** — 3 concrete actions the client should take after receiving this pack

Brief:
"""


_GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_ANTHROPIC_PREMIUM_MODEL = "claude-opus-4-5"

_PREMIUM_AVENUE_SLUGS = frozenset({"high_ticket", "sponsor_deals"})
_PREMIUM_TIER_KEYS = frozenset({"retainer", "enterprise", "premium", "high_ticket"})


def _select_content_pack_provider(job) -> tuple[str | None, str | None, str | None]:
    """Return (provider, model, api_key) based on job routing rules.

    Premium signals (→ Anthropic Opus):
      - avenue_slug in _PREMIUM_AVENUE_SLUGS
      - metadata_json.tier in _PREMIUM_TIER_KEYS

    Default: Anthropic Sonnet (confirmed working in production).
    Groq used only when GROQ_CONTENT_PACK_MODEL env var is explicitly set
    AND GROQ_API_KEY is non-empty (opt-in for quota-bearing accounts).

    Returns (None, None, error_msg) when the required key is missing.
    """
    meta = job.metadata_json or {}
    tier = str(meta.get("tier", "")).lower()
    is_premium = job.avenue_slug in _PREMIUM_AVENUE_SLUGS or tier in _PREMIUM_TIER_KEYS

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if is_premium:
        model = os.environ.get("ANTHROPIC_PREMIUM_MODEL", _ANTHROPIC_PREMIUM_MODEL)
        if not anthropic_key:
            return None, None, "ANTHROPIC_API_KEY not configured"
        return "anthropic", model, anthropic_key

    # Opt-in Groq: only use when explicitly configured with a quota-bearing key
    groq_key = os.environ.get("GROQ_API_KEY", "")
    groq_model_override = os.environ.get("GROQ_CONTENT_PACK_MODEL", "")
    if groq_key and groq_model_override:
        return "groq", groq_model_override, groq_key

    # Default: Anthropic Sonnet
    model = os.environ.get("ANTHROPIC_DEFAULT_MODEL", _ANTHROPIC_DEFAULT_MODEL)
    if not anthropic_key:
        return None, None, "ANTHROPIC_API_KEY not configured"
    return "anthropic", model, anthropic_key


async def _execute_content_pack_jobs() -> dict:
    """Generate content packs for in_progress jobs that have no output yet."""
    from apps.api.services.event_bus import emit_event
    from apps.api.services.qa_delivery_service import submit_production_output
    from packages.db.models.fulfillment import (
        ClientProject,  # noqa: F401
        ProductionJob,
    )
    from packages.db.models.gm_control import GMEscalation

    # Ensure FK-referenced models are in the mapper registry before any flush.
    # ClientProject.proposal_id references proposals.id — importing Proposal
    # here prevents NoReferencedTableError / PendingRollbackError mid-flush.
    from packages.db.models.proposals import Proposal  # noqa: F401
    from packages.media.storage import MediaStorage

    Session, engine = _fresh_session_factory()
    async with Session() as db:
        # ── 1. Find eligible jobs ──────────────────────────────────────────
        eligible = (
            (
                await db.execute(
                    select(ProductionJob)
                    .where(
                        ProductionJob.status == "in_progress",
                        ProductionJob.job_type == "content_pack",
                        ProductionJob.is_active.is_(True),
                        ProductionJob.output_url.is_(None),
                        ProductionJob.attempt_count <= ProductionJob.retry_limit,
                    )
                    .order_by(ProductionJob.picked_up_at.asc().nullslast())
                    .limit(_CONTENT_PACK_MAX_PER_RUN)
                )
            )
            .scalars()
            .all()
        )

        generated = 0
        failed = 0
        skipped = 0

        for job in eligible:
            # ── 2. Guard: skip if state changed since query ────────────────
            if job.status != "in_progress" or job.output_url:
                skipped += 1
                continue

            # ── 3. Load approved brief ────────────────────────────────────
            from packages.db.models.fulfillment import ProjectBrief as _PB

            brief = (
                await db.execute(
                    select(_PB).where(
                        _PB.id == job.brief_id,
                        _PB.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()

            if brief is None or brief.status != "approved":
                logger.warning(
                    "content_pack.no_approved_brief",
                    job_id=str(job.id),
                    brief_id=str(job.brief_id),
                    brief_status=brief.status if brief is not None else "missing",
                )
                skipped += 1
                continue

            # ── 4. Emit generation started ────────────────────────────────
            await emit_event(
                db,
                domain="fulfillment",
                event_type="content_pack.generation_started",
                summary=f"Content pack generation started: {job.title[:80]}",
                org_id=job.org_id,
                entity_type="production_job",
                entity_id=job.id,
                actor_type="system",
                actor_id=_WORKER_ID,
                details={
                    "production_job_id": str(job.id),
                    "brief_id": str(brief.id),
                    "avenue_slug": job.avenue_slug,
                },
            )
            await db.flush()

            # ── 5. Build brief context for LLM ───────────────────────────
            brief_text = "\n".join(
                filter(
                    None,
                    [
                        f"Title: {brief.title}",
                        f"Summary: {brief.summary}" if brief.summary else None,
                        f"Goals: {brief.goals}" if brief.goals else None,
                        f"Audience: {brief.audience}" if brief.audience else None,
                        f"Tone and voice: {brief.tone_and_voice}" if brief.tone_and_voice else None,
                        (f"Deliverables: {brief.deliverables_json}" if brief.deliverables_json else None),
                    ],
                )
            )

            # ── 6. Select provider and generate content ───────────────────
            generation_error: str | None = None
            markdown_content: str | None = None
            provider, model_slug, provider_key_or_err = _select_content_pack_provider(job)

            if provider is None:
                generation_error = provider_key_or_err or "No LLM provider available"
            else:
                try:
                    prompt_text = _CONTENT_PACK_PROMPT + brief_text
                    if provider == "groq":
                        from groq import Groq

                        client = Groq(api_key=provider_key_or_err)
                        completion = client.chat.completions.create(
                            model=model_slug,
                            max_tokens=2000,
                            messages=[{"role": "user", "content": prompt_text}],
                        )
                        markdown_content = completion.choices[0].message.content if completion.choices else None
                    elif provider == "anthropic":
                        import anthropic

                        client = anthropic.Anthropic(api_key=provider_key_or_err)
                        response = client.messages.create(
                            model=model_slug,
                            max_tokens=2000,
                            messages=[{"role": "user", "content": prompt_text}],
                        )
                        markdown_content = response.content[0].text if response.content else None
                    if not markdown_content or len(markdown_content.strip()) < 100:
                        generation_error = "LLM returned empty or too-short content"
                        markdown_content = None
                except Exception as llm_exc:
                    generation_error = f"LLM call failed ({provider}): {str(llm_exc)[:200]}"
                    logger.warning(
                        "content_pack.llm_failed",
                        job_id=str(job.id),
                        provider=provider,
                        model=model_slug,
                        error=generation_error,
                    )

            # ── 7. Handle generation failure ─────────────────────────────
            if generation_error or not markdown_content:
                failed += 1
                err_msg = generation_error or "No content returned from LLM"
                job.error_message = err_msg

                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="content_pack.generation_failed",
                    summary=f"Content pack generation failed: {job.title[:80]}",
                    org_id=job.org_id,
                    entity_type="production_job",
                    entity_id=job.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={
                        "production_job_id": str(job.id),
                        "error": err_msg,
                        "avenue_slug": job.avenue_slug,
                    },
                )

                # Escalate if not already open
                existing_esc = (
                    await db.execute(
                        select(GMEscalation).where(
                            GMEscalation.entity_type == "production_job",
                            GMEscalation.entity_id == job.id,
                            GMEscalation.reason_code == "content_pack_generation_failed",
                            GMEscalation.status == "open",
                        )
                    )
                ).scalar_one_or_none()
                if existing_esc is None:
                    db.add(
                        GMEscalation(
                            org_id=job.org_id,
                            reason_code="content_pack_generation_failed",
                            entity_type="production_job",
                            entity_id=job.id,
                            title=f"Content pack generation failed: {job.title[:300]}",
                            description=(
                                f"Job {job.id} failed to generate content: {err_msg}. "
                                f"Check provider API keys (GROQ_API_KEY / ANTHROPIC_API_KEY) "
                                f"or brief completeness. Job remains in_progress for retry "
                                f"(attempt {job.attempt_count} of {job.retry_limit})."
                            ),
                            severity="warning",
                            status="open",
                            details_json={
                                "production_job_id": str(job.id),
                                "avenue_slug": job.avenue_slug,
                                "error": err_msg,
                            },
                        )
                    )
                await db.flush()
                continue

            # ── 8. Upload artifact via MediaStorage ───────────────────────
            output_url: str | None = None
            try:
                storage = MediaStorage()
                key = f"content_packs/{job.id}.md"
                output_url = storage.upload_bytes(
                    data=markdown_content.encode("utf-8"),
                    key=key,
                    content_type="text/markdown; charset=utf-8",
                )
            except Exception as upload_exc:
                upload_error_msg = f"Storage upload failed: {str(upload_exc)[:200]}"
                logger.warning(
                    "content_pack.upload_failed",
                    job_id=str(job.id),
                    error=upload_error_msg,
                )
                failed += 1
                job.error_message = upload_error_msg

                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="content_pack.generation_failed",
                    summary=f"Content pack upload failed: {job.title[:80]}",
                    org_id=job.org_id,
                    entity_type="production_job",
                    entity_id=job.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={
                        "production_job_id": str(job.id),
                        "error": upload_error_msg,
                        "avenue_slug": job.avenue_slug,
                        "note": "Content was generated but could not be stored. Retry will regenerate.",
                    },
                )

                existing_esc = (
                    await db.execute(
                        select(GMEscalation).where(
                            GMEscalation.entity_type == "production_job",
                            GMEscalation.entity_id == job.id,
                            GMEscalation.reason_code == "content_pack_generation_failed",
                            GMEscalation.status == "open",
                        )
                    )
                ).scalar_one_or_none()
                if existing_esc is None:
                    db.add(
                        GMEscalation(
                            org_id=job.org_id,
                            reason_code="content_pack_generation_failed",
                            entity_type="production_job",
                            entity_id=job.id,
                            title=f"Content pack storage upload failed: {job.title[:300]}",
                            description=(
                                f"Job {job.id} generated content successfully but upload failed: "
                                f"{upload_error_msg}. "
                                f"Check S3_BUCKET / S3_ACCESS_KEY_ID / S3_SECRET_ACCESS_KEY env vars. "
                                f"Job remains in_progress for retry."
                            ),
                            severity="warning",
                            status="open",
                            details_json={
                                "production_job_id": str(job.id),
                                "avenue_slug": job.avenue_slug,
                                "error": upload_error_msg,
                            },
                        )
                    )
                await db.flush()
                # Do NOT call submit_production_output — no valid output_url exists.
                continue

            # ── 9. Submit output → triggers QA → delivery → followup ─────
            try:
                result = await submit_production_output(
                    db,
                    job=job,
                    output_url=output_url,
                    output_payload={
                        "format": "markdown",
                        "content": markdown_content,
                        "word_count": len(markdown_content.split()),
                        "generator": f"{provider}:{model_slug}",
                    },
                    auto_qa=True,
                    auto_dispatch=True,
                )
                generated += 1

                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="content_pack.generation_completed",
                    summary=f"Content pack generated and submitted: {job.title[:80]}",
                    org_id=job.org_id,
                    entity_type="production_job",
                    entity_id=job.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={
                        "production_job_id": str(job.id),
                        "output_url": output_url,
                        "word_count": len(markdown_content.split()),
                        "qa_result": (result.get("qa") or {}).get("result"),
                        "delivery_id": (result.get("delivery") or {}).get("delivery_id"),
                        "avenue_slug": job.avenue_slug,
                    },
                )
                logger.info(
                    "content_pack.generation_completed",
                    job_id=str(job.id),
                    output_url=output_url,
                    qa_result=(result.get("qa") or {}).get("result"),
                    delivery_id=(result.get("delivery") or {}).get("delivery_id"),
                )
            except Exception as submit_exc:
                failed += 1
                err = f"submit_production_output failed: {str(submit_exc)[:200]}"
                job.error_message = err
                logger.error("content_pack.submit_failed", job_id=str(job.id), error=err)
                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="content_pack.generation_failed",
                    summary=f"Content pack submit failed: {job.title[:80]}",
                    org_id=job.org_id,
                    entity_type="production_job",
                    entity_id=job.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={"production_job_id": str(job.id), "error": err},
                )

        await db.commit()
        summary = {
            "eligible": len(eligible),
            "generated": generated,
            "failed": failed,
            "skipped": skipped,
        }
        logger.info("fulfillment.execute_content_pack.done", **summary)
    await engine.dispose()
    return summary


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.execute_content_pack_jobs",
    queue="default",
)
def execute_content_pack_jobs():
    return _run_async(_execute_content_pack_jobs())


# ═══════════════════════════════════════════════════════════════════════════
#  8. execute_renewal_pipeline
#
#  Every 6h: for each org find clients in retention_state='renewal_due' or
#  'renewal_overdue', then for each client:
#    a) Ensure an open renewal proposal exists (create via trigger_renewal if not).
#    b) Ensure a Stripe payment link exists on that proposal.
#    c) Send one renewal email and flip proposal draft → sent.
#  Dunning (chase_unpaid_proposals) owns all subsequent follow-ups once
#  proposal.status == 'sent'.
#
#  Idempotency:
#   - Skips if open renewal proposal already exists for that client.
#   - Skips payment link creation if PaymentLink row already exists on proposal.
#   - Skips email send if proposal.status already 'sent'.
#   - trigger_renewal is debounced 24h inside retention_service.
#   - GMEscalation upserted by unique (org_id, entity_type, entity_id, reason_code).
# ═══════════════════════════════════════════════════════════════════════════

_RENEWAL_MAX_PER_ORG = 20


async def _upsert_gm_escalation(
    db,
    *,
    client,
    reason_code: str,
    title: str,
    details: dict,
) -> None:
    """Insert a GMEscalation if not already open; bump occurrence_count otherwise."""
    from packages.db.models.gm_control import GMEscalation

    now = datetime.now(timezone.utc)
    existing = (
        await db.execute(
            select(GMEscalation)
            .where(
                GMEscalation.org_id == client.org_id,
                GMEscalation.entity_type == "client",
                GMEscalation.entity_id == client.id,
                GMEscalation.reason_code == reason_code,
                GMEscalation.status == "open",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            GMEscalation(
                org_id=client.org_id,
                entity_type="client",
                entity_id=client.id,
                reason_code=reason_code,
                title=title,
                severity="warning",
                details_json=details,
                status="open",
                first_seen_at=now,
                last_seen_at=now,
                source_module="renewal_pipeline",
            )
        )
    else:
        existing.last_seen_at = now
        existing.occurrence_count = (existing.occurrence_count or 1) + 1
    await db.flush()


async def _execute_renewal_pipeline() -> dict:
    """Renewal pipeline — scanner, proposal creation, Stripe link, email send."""
    import uuid as _uuid

    from apps.api.services.event_bus import emit_event
    from apps.api.services.proposals_service import record_payment_link
    from apps.api.services.retention_service import detect_renewal_due, trigger_renewal
    from apps.api.services.stripe_billing_service import (
        create_payment_link as stripe_create_payment_link,
    )
    from apps.api.services.test_record_guard import is_test_or_synthetic_record
    from packages.clients.external_clients import SmtpEmailClient
    from packages.db.models.clients import Client
    from packages.db.models.proposals import PaymentLink, Proposal

    Session, engine = _fresh_session_factory()
    processed = linked = emailed = escalated = skipped = 0

    async with Session() as db:
        now = datetime.now(timezone.utc)

        # ── 1. Discover all orgs with eligible clients ──────────────────
        org_ids = list(
            (
                await db.execute(
                    select(Client.org_id)
                    .where(
                        Client.is_active.is_(True),
                        Client.retention_state.in_(("renewal_due", "renewal_overdue")),
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        for org_id in org_ids:
            clients = await detect_renewal_due(db, org_id=org_id, limit=_RENEWAL_MAX_PER_ORG)

            for client in clients:
                processed += 1

                # ── 2. Idempotency: find existing open renewal proposal ──
                open_proposal = (
                    await db.execute(
                        select(Proposal)
                        .where(
                            Proposal.extra_json["source_client_id"].astext == str(client.id),
                            Proposal.extra_json["retention_source"].astext == "renewal",
                            ~Proposal.status.in_(("paid", "cancelled", "rejected")),
                        )
                        .order_by(Proposal.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()

                if open_proposal is None:
                    # Determine renewal amount from the client's first (source) proposal.
                    renewal_cents = 0
                    if client.first_proposal_id:
                        src_prop = (
                            await db.execute(select(Proposal).where(Proposal.id == client.first_proposal_id))
                        ).scalar_one_or_none()
                        if src_prop:
                            renewal_cents = src_prop.total_amount_cents or 0

                    if renewal_cents <= 0:
                        escalated += 1
                        await _upsert_gm_escalation(
                            db,
                            client=client,
                            reason_code="renewal_amount_unknown",
                            title=f"Renewal amount unknown for {client.display_name or client.primary_email}",
                            details={
                                "client_id": str(client.id),
                                "first_proposal_id": str(client.first_proposal_id)
                                if client.first_proposal_id
                                else None,
                            },
                        )
                        continue

                    pkg = client.avenue_slug or "recurring_retainer"
                    trigger_result = await trigger_renewal(
                        db,
                        client=client,
                        package_slug=pkg,
                        line_items=[
                            {
                                "description": f"Renewal — {pkg}",
                                "unit_amount_cents": renewal_cents,
                                "quantity": 1,
                                "currency": "usd",
                                "position": 0,
                            }
                        ],
                        actor_type="system",
                        actor_id=_WORKER_ID,
                    )

                    pid = trigger_result.get("proposal_id")
                    if not pid:
                        # Debounced with no resolvable proposal — skip this tick
                        skipped += 1
                        continue

                    open_proposal = (
                        await db.execute(select(Proposal).where(Proposal.id == _uuid.UUID(pid)))
                    ).scalar_one_or_none()
                    if open_proposal is None:
                        skipped += 1
                        continue

                proposal = open_proposal

                # ── 3. Idempotency: find or create Stripe payment link ──
                # Re-check guard here as a defence-in-depth measure: even if
                # detect_renewal_due already filtered, verify again before any
                # money-touching operation.
                _guard_blocked, _guard_reason = is_test_or_synthetic_record(
                    email=client.primary_email or "",
                    source=client.avenue_slug,
                    metadata={"client_id": str(client.id)},
                )
                if _guard_blocked:
                    logger.warning(
                        "renewal_pipeline.guard_blocked",
                        client_id=str(client.id),
                        email=client.primary_email,
                        reason=_guard_reason,
                    )
                    skipped += 1
                    continue

                existing_link = (
                    await db.execute(
                        select(PaymentLink)
                        .where(
                            PaymentLink.proposal_id == proposal.id,
                            PaymentLink.status.in_(("active", "pending")),
                        )
                        .limit(1)
                    )
                ).scalar_one_or_none()

                payment_link_url: str | None = None
                if existing_link is not None:
                    payment_link_url = existing_link.url
                else:
                    stripe_meta = {
                        "source": "renewal",
                        "retention_source": "renewal",
                        "avenue_slug": "retainer_renewal",
                        "proposal_id": str(proposal.id),
                        "client_id": str(client.id),
                        "org_id": str(client.org_id),
                        "brand_id": str(client.brand_id) if client.brand_id else "",
                    }
                    stripe_result = await stripe_create_payment_link(
                        amount_cents=proposal.total_amount_cents,
                        currency="usd",
                        product_name=proposal.title or f"Renewal — {client.display_name or client.primary_email}",
                        metadata=stripe_meta,
                        db=db,
                        org_id=client.org_id,
                    )
                    if stripe_result.get("error") or not stripe_result.get("url"):
                        escalated += 1
                        await _upsert_gm_escalation(
                            db,
                            client=client,
                            reason_code="renewal_payment_link_failed",
                            title=f"Renewal Stripe link failed for {client.display_name or client.primary_email}",
                            details={
                                "client_id": str(client.id),
                                "proposal_id": str(proposal.id),
                                "stripe_error": stripe_result.get("error", "no_url_returned"),
                            },
                        )
                        continue

                    link_rec = await record_payment_link(
                        db,
                        org_id=client.org_id,
                        brand_id=client.brand_id,
                        proposal_id=proposal.id,
                        provider="stripe",
                        provider_link_id=stripe_result["id"],
                        url=stripe_result["url"],
                        amount_cents=proposal.total_amount_cents,
                        currency="usd",
                        source="renewal",
                        metadata=stripe_meta,
                    )
                    payment_link_url = link_rec.url
                    linked += 1

                # ── 4. Send initial renewal email (once only) ────────────
                if proposal.status == "sent":
                    # Already emailed — dunning owns follow-ups from here.
                    skipped += 1
                    continue

                smtp = await SmtpEmailClient.from_db(db, client.org_id)
                first_name = (client.display_name or client.primary_email or "").split(" ")[0] or "there"
                subject = f"Your renewal is ready — {proposal.title}"
                body_text = (
                    f"Hi {first_name},\n\n"
                    f"Your renewal is ready. Complete your payment here:\n\n"
                    f"{payment_link_url}\n\n"
                    f"Amount: ${proposal.total_amount_cents / 100:,.2f} USD\n\n"
                    f"Reply to this email with any questions.\n\nThank you!"
                )

                if smtp is None:
                    escalated += 1
                    await _upsert_gm_escalation(
                        db,
                        client=client,
                        reason_code="renewal_email_failed",
                        title=f"No SMTP — renewal email not sent to {client.primary_email}",
                        details={
                            "client_id": str(client.id),
                            "proposal_id": str(proposal.id),
                            "payment_link_url": payment_link_url,
                        },
                    )
                else:
                    send_res = await smtp.send_email(
                        to_email=client.primary_email,
                        subject=subject,
                        body_text=body_text,
                        body_html=f"<p>{body_text.replace(chr(10), '<br>')}</p>",
                    )
                    if send_res.get("success"):
                        emailed += 1
                    else:
                        logger.warning(
                            "renewal_pipeline.email_send_failed",
                            client_id=str(client.id),
                            error=send_res.get("error"),
                        )

                # ── 5. Transition proposal draft → sent ─────────────────
                proposal.status = "sent"
                proposal.sent_at = now
                await db.flush()

                await emit_event(
                    db,
                    domain="fulfillment",
                    event_type="client.retention.renewal_email_sent",
                    summary=f"Renewal email sent to {client.primary_email}: {proposal.title}",
                    org_id=client.org_id,
                    brand_id=client.brand_id,
                    entity_type="proposal",
                    entity_id=proposal.id,
                    actor_type="system",
                    actor_id=_WORKER_ID,
                    details={
                        "client_id": str(client.id),
                        "proposal_id": str(proposal.id),
                        "payment_link_url": payment_link_url,
                        "avenue_slug": client.avenue_slug,
                    },
                )
                logger.info(
                    "renewal_pipeline.proposal_sent",
                    client_id=str(client.id),
                    proposal_id=str(proposal.id),
                    avenue_slug=client.avenue_slug,
                )

        await db.commit()

    await engine.dispose()
    summary = {
        "processed": processed,
        "payment_links_created": linked,
        "emails_sent": emailed,
        "escalated": escalated,
        "skipped": skipped,
    }
    logger.info("renewal_pipeline.done", **summary)
    return summary


@shared_task(
    base=TrackedTask,
    name="workers.fulfillment_worker.tasks.execute_renewal_pipeline",
    queue="default",
)
def execute_renewal_pipeline():
    return _run_async(_execute_renewal_pipeline())

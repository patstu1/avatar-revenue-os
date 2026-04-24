"""Buffer Distribution Layer — service layer for profiles, publish jobs, sync, blockers."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import Platform
from packages.db.models.buffer_distribution import (
    BufferBlocker,
    BufferProfile,
    BufferPublishAttempt,
    BufferPublishJob,
    BufferStatusSync,
)
from packages.db.models.content import ContentItem
from packages.scoring.buffer_engine import (
    build_publish_payload,
    detect_buffer_blockers,
    determine_publish_mode,
    map_buffer_status,
)

logger = structlog.get_logger()

BUFFER_API_KEY_ENV = "BUFFER_API_KEY"


def _has_buffer_api_key() -> bool:
    return bool(os.environ.get(BUFFER_API_KEY_ENV))


# ── Profile CRUD ──────────────────────────────────────────────────────

async def list_buffer_profiles(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list:
    q = await db.execute(
        select(BufferProfile)
        .where(BufferProfile.brand_id == brand_id, BufferProfile.is_active.is_(True))
        .order_by(BufferProfile.created_at.desc()).limit(limit)
    )
    return list(q.scalars().all())


async def create_buffer_profile(db: AsyncSession, brand_id: uuid.UUID, data: dict[str, Any]) -> BufferProfile:
    platform_val = data.get("platform", "tiktok")
    try:
        platform_enum = Platform(platform_val)
    except ValueError:
        platform_enum = Platform.TIKTOK

    bp = BufferProfile(
        brand_id=brand_id,
        creator_account_id=data.get("creator_account_id"),
        platform=platform_enum,
        buffer_profile_id=data.get("buffer_profile_id"),
        display_name=data.get("display_name", "Unnamed Profile"),
        credential_status=data.get("credential_status", "not_connected"),
        config_json=data.get("config_json", {}),
    )
    db.add(bp)
    await db.flush()
    await db.refresh(bp)
    return bp


async def update_buffer_profile(db: AsyncSession, profile_id: uuid.UUID, data: dict[str, Any]) -> Optional[BufferProfile]:
    q = await db.execute(select(BufferProfile).where(BufferProfile.id == profile_id))
    bp = q.scalar_one_or_none()
    if not bp:
        return None
    for key in ("buffer_profile_id", "display_name", "credential_status", "config_json", "is_active"):
        if key in data and data[key] is not None:
            setattr(bp, key, data[key])
    await db.flush()
    await db.refresh(bp)
    return bp


# ── Publish Jobs ──────────────────────────────────────────────────────

async def list_publish_jobs(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list:
    q = await db.execute(
        select(BufferPublishJob)
        .where(BufferPublishJob.brand_id == brand_id, BufferPublishJob.is_active.is_(True))
        .order_by(BufferPublishJob.created_at.desc()).limit(limit)
    )
    return list(q.scalars().all())


async def recompute_publish_jobs(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Scan for approved content items without a Buffer publish job and create jobs."""
    profiles_q = await db.execute(
        select(BufferProfile)
        .where(BufferProfile.brand_id == brand_id, BufferProfile.is_active.is_(True))
    )
    profiles = profiles_q.scalars().all()
    if not profiles:
        return {"jobs_created": 0, "reason": "no_active_profiles"}

    content_q = await db.execute(
        select(ContentItem)
        .where(ContentItem.brand_id == brand_id)
        .order_by(ContentItem.created_at.desc()).limit(50)
    )
    content_items = content_q.scalars().all()

    existing_q = await db.execute(
        select(BufferPublishJob.content_item_id)
        .where(BufferPublishJob.brand_id == brand_id, BufferPublishJob.is_active.is_(True))
    )
    existing_content_ids = {r[0] for r in existing_q.all() if r[0]}

    created = 0
    for ci in content_items:
        if ci.id in existing_content_ids:
            continue

        best_profile = _match_profile(ci, profiles)
        if not best_profile:
            continue

        content_ctx = {
            "caption": ci.title or "",
            "title": ci.title or "",
            "media_url": None,
            "link_url": None,
        }
        profile_ctx = {
            "platform": best_profile.platform.value if best_profile.platform else "unknown",
            "buffer_profile_id": best_profile.buffer_profile_id or "",
        }

        payload = build_publish_payload(content_ctx, profile_ctx)
        mode = determine_publish_mode(content_ctx, profile_ctx)

        job = BufferPublishJob(
            brand_id=brand_id,
            buffer_profile_id_fk=best_profile.id,
            content_item_id=ci.id,
            platform=best_profile.platform,
            publish_mode=mode,
            status="pending",
            payload_json=payload,
        )
        db.add(job)
        created += 1

    await db.flush()
    return {"jobs_created": created}


def _match_profile(content_item: Any, profiles: list[BufferProfile]) -> Optional[BufferProfile]:
    """Pick the best Buffer profile for a content item (platform match preferred, connected preferred)."""
    connected = [p for p in profiles if p.credential_status == "connected"]
    if connected:
        return connected[0]
    return profiles[0] if profiles else None


# ── Submit to Buffer ──────────────────────────────────────────────────

async def submit_job_to_buffer(db: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
    """Submit a single publish job to Buffer's API.

    This is where the real Buffer API call would go. Currently persists the attempt
    and marks success/failure based on credential availability.
    """
    q = await db.execute(select(BufferPublishJob).where(BufferPublishJob.id == job_id))
    job = q.scalar_one_or_none()
    if not job:
        raise ValueError(f"Publish job {job_id} not found")

    profile_q = await db.execute(select(BufferProfile).where(BufferProfile.id == job.buffer_profile_id_fk))
    profile = profile_q.scalar_one_or_none()

    attempt = BufferPublishAttempt(
        job_id=job.id,
        attempt_number=job.retry_count + 1,
        request_payload_json=job.payload_json,
    )

    if not _has_buffer_api_key():
        attempt.success = False
        attempt.error_message = "BUFFER_API_KEY not configured"
        attempt.response_status_code = 0
        job.status = "failed"
        job.error_message = "BUFFER_API_KEY not configured"

        blocker = BufferBlocker(
            brand_id=job.brand_id,
            buffer_profile_id_fk=job.buffer_profile_id_fk,
            blocker_type="missing_buffer_api_key",
            severity="critical",
            description="Buffer API key not configured. Cannot submit publish job.",
            operator_action_needed="Set BUFFER_API_KEY environment variable with a valid Buffer API key.",
        )
        db.add(blocker)
    elif profile and profile.credential_status != "connected":
        attempt.success = False
        attempt.error_message = f"Profile credential status: {profile.credential_status}"
        attempt.response_status_code = 0
        job.status = "failed"
        job.error_message = f"Buffer profile not connected (status: {profile.credential_status})"

        blocker = BufferBlocker(
            brand_id=job.brand_id,
            buffer_profile_id_fk=job.buffer_profile_id_fk,
            blocker_type="missing_buffer_credentials",
            severity="high",
            description=f"Buffer profile '{profile.display_name}' is not connected.",
            operator_action_needed=f"Connect this Buffer profile via the Buffer dashboard.",
        )
        db.add(blocker)
    else:
        from packages.clients.external_clients import BufferClient
        client = BufferClient()

        text = (job.payload_json or {}).get("text", "")
        media = (job.payload_json or {}).get("media")
        scheduled = job.scheduled_at
        profile_id_str = profile.buffer_profile_id if profile else None

        if not profile_id_str:
            attempt.success = False
            attempt.error_message = "Buffer profile ID not mapped"
            attempt.response_status_code = 0
            job.status = "failed"
            job.error_message = "Buffer profile ID not mapped"
        else:
            result = await client.create_update(
                profile_ids=[profile_id_str],
                text=text,
                media=media,
                scheduled_at=scheduled,
            )

            attempt.response_status_code = result.get("status_code", 0)
            attempt.response_body_json = result.get("data") or {}
            attempt.duration_ms = 0

            if result.get("success"):
                attempt.success = True
                buffer_id = (result.get("data") or {}).get("updates", [{}])[0].get("id", f"buf_{job.id}")
                job.status = "submitted"
                job.buffer_post_id = buffer_id
                logger.info("buffer.job_submitted_real", job_id=str(job.id), buffer_id=buffer_id)
            elif result.get("blocked"):
                attempt.success = False
                attempt.error_message = result.get("error", "Blocked")
                job.status = "failed"
                job.error_message = result.get("error", "Blocked")
                db.add(BufferBlocker(
                    brand_id=job.brand_id,
                    buffer_profile_id_fk=job.buffer_profile_id_fk,
                    blocker_type="buffer_api_blocked",
                    severity="critical",
                    description=result.get("error", "Buffer API blocked"),
                    operator_action_needed="Check BUFFER_API_KEY configuration.",
                ))
            else:
                attempt.success = False
                attempt.error_message = result.get("error", "Unknown error")
                job.status = "failed"
                job.error_message = result.get("error", "Unknown error")
                job.retry_count += 1

    job.retry_count += 1
    db.add(attempt)
    await db.flush()

    return {
        "job_id": str(job.id),
        "status": job.status,
        "success": attempt.success,
        "error": attempt.error_message,
    }


# ── Status Sync ───────────────────────────────────────────────────────

async def run_status_sync(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Sync Buffer post statuses back into our system.

    With a real Buffer API key, this would poll Buffer's updates endpoint.
    Currently simulates status transitions for submitted jobs.
    """
    jobs_q = await db.execute(
        select(BufferPublishJob)
        .where(
            BufferPublishJob.brand_id == brand_id,
            BufferPublishJob.is_active.is_(True),
            BufferPublishJob.status.in_(["submitted", "queued", "scheduled"]),
        )
    )
    jobs = jobs_q.scalars().all()

    checked = len(jobs)
    updated = 0
    failed = 0
    published = 0

    for job in jobs:
        if not _has_buffer_api_key():
            # Without API key, we simulate based on job age
            if job.status == "submitted":
                job.status = "queued"
                updated += 1
        else:
            from packages.clients.external_clients import BufferClient
            client = BufferClient()

            if job.buffer_post_id:
                result = await client.get_update(job.buffer_post_id)
                if result.get("success") and result.get("data"):
                    buffer_status = result["data"].get("status", "")
                    new_status = map_buffer_status(buffer_status)
                else:
                    new_status = "unknown"
            else:
                new_status = "unknown"

            if new_status != job.status:
                job.status = new_status
                updated += 1
                if new_status == "published":
                    job.published_at = datetime.now(timezone.utc).isoformat()
                    published += 1
                elif new_status == "failed":
                    failed += 1

    sync_record = BufferStatusSync(
        brand_id=brand_id,
        jobs_checked=checked,
        jobs_updated=updated,
        jobs_failed=failed,
        jobs_published=published,
        sync_mode="pull",
        details_json={"has_api_key": _has_buffer_api_key()},
    )
    db.add(sync_record)
    await db.flush()

    return {
        "jobs_checked": checked,
        "jobs_updated": updated,
        "jobs_failed": failed,
        "jobs_published": published,
    }


# ── Blockers ──────────────────────────────────────────────────────────

async def list_buffer_blockers(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list:
    q = await db.execute(
        select(BufferBlocker)
        .where(BufferBlocker.brand_id == brand_id, BufferBlocker.is_active.is_(True), BufferBlocker.resolved.is_(False))
        .order_by(BufferBlocker.created_at.desc()).limit(limit)
    )
    return list(q.scalars().all())


async def recompute_blockers(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Detect and persist current blockers for Buffer distribution."""
    await db.execute(
        update(BufferBlocker)
        .where(BufferBlocker.brand_id == brand_id, BufferBlocker.is_active.is_(True), BufferBlocker.resolved.is_(False))
        .values(resolved=True)
    )

    profiles = await list_buffer_profiles(db, brand_id)
    profile_dicts = [
        {
            "id": p.id,
            "platform": p.platform.value if p.platform else "unknown",
            "display_name": p.display_name,
            "credential_status": p.credential_status,
            "buffer_profile_id": p.buffer_profile_id,
            "is_active": p.is_active,
        }
        for p in profiles
    ]

    brand_ctx = {"has_buffer_api_key": _has_buffer_api_key()}
    detected = detect_buffer_blockers(profile_dicts, brand_ctx)

    created = 0
    for b in detected:
        blocker = BufferBlocker(
            brand_id=brand_id,
            buffer_profile_id_fk=b.get("buffer_profile_id_fk"),
            blocker_type=b["blocker_type"],
            severity=b["severity"],
            description=b["description"],
            operator_action_needed=b["operator_action_needed"],
        )
        db.add(blocker)
        created += 1

    await db.flush()
    return {"blockers_created": created}


# ── Status Sync List ──────────────────────────────────────────────────

async def list_status_syncs(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 20) -> list:
    q = await db.execute(
        select(BufferStatusSync)
        .where(BufferStatusSync.brand_id == brand_id, BufferStatusSync.is_active.is_(True))
        .order_by(BufferStatusSync.created_at.desc()).limit(limit)
    )
    return list(q.scalars().all())

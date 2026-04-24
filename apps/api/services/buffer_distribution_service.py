"""Buffer Distribution Layer — service layer for profiles, publish jobs, sync, blockers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

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


async def _resolve_buffer_api_key(db: AsyncSession, organization_id: uuid.UUID) -> str:
    """Resolve Buffer API key from the integration_providers table (dashboard-managed).

    All credentials are stored encrypted in the DB and managed via the
    Integrations dashboard.  No .env fallback — if the key isn't in the DB,
    the operator needs to configure it through Settings > Integrations.
    """
    from apps.api.services.integration_manager import get_credential

    return await get_credential(db, organization_id, "buffer") or ""


# ── Profile CRUD ──────────────────────────────────────────────────────


async def list_buffer_profiles(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list:
    q = await db.execute(
        select(BufferProfile)
        .where(BufferProfile.brand_id == brand_id, BufferProfile.is_active.is_(True))
        .order_by(BufferProfile.created_at.desc())
        .limit(limit)
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


async def update_buffer_profile(db: AsyncSession, profile_id: uuid.UUID, data: dict[str, Any]) -> BufferProfile | None:
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
        .order_by(BufferPublishJob.created_at.desc())
        .limit(limit)
    )
    return list(q.scalars().all())


async def recompute_publish_jobs(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Scan for approved content items without a Buffer publish job and create jobs.

    Requires:
      - brand is still active
      - brand has >=1 active, connected buffer profile
      - content item status == 'approved' (not draft/qa_passed/published/failed)
    """
    # Verify brand is still active
    from packages.db.models.core import Brand

    brand_q = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.is_active.is_(True)))
    brand = brand_q.scalar_one_or_none()
    if not brand:
        return {"jobs_created": 0, "reason": "brand_inactive_or_missing"}

    profiles_q = await db.execute(
        select(BufferProfile).where(BufferProfile.brand_id == brand_id, BufferProfile.is_active.is_(True))
    )
    profiles = profiles_q.scalars().all()
    if not profiles:
        return {"jobs_created": 0, "reason": "no_active_profiles"}

    # Only materialize jobs for content that's actually approved for publishing.
    content_q = await db.execute(
        select(ContentItem)
        .where(
            ContentItem.brand_id == brand_id,
            ContentItem.status == "approved",
        )
        .order_by(ContentItem.created_at.desc())
        .limit(50)
    )
    content_items = content_q.scalars().all()
    if not content_items:
        return {"jobs_created": 0, "reason": "no_approved_content"}

    existing_q = await db.execute(
        select(BufferPublishJob.content_item_id).where(
            BufferPublishJob.brand_id == brand_id, BufferPublishJob.is_active.is_(True)
        )
    )
    existing_content_ids = {r[0] for r in existing_q.all() if r[0]}

    # Resolve all video and thumbnail assets in one batch to keep queries bounded
    from packages.db.models.content import Asset

    asset_ids: set[uuid.UUID] = set()
    for ci in content_items:
        if ci.video_asset_id:
            asset_ids.add(ci.video_asset_id)
        if ci.thumbnail_asset_id:
            asset_ids.add(ci.thumbnail_asset_id)
    asset_lookup: dict[uuid.UUID, Asset] = {}
    if asset_ids:
        asset_rows = (await db.execute(select(Asset).where(Asset.id.in_(asset_ids)))).scalars().all()
        asset_lookup = {a.id: a for a in asset_rows}

    def _resolve_media_url(ci) -> str | None:
        """Resolve a usable public media URL from ContentItem -> Asset.

        Prefers video, falls back to thumbnail. Only returns URLs that look
        like real HTTP(S) resources so Buffer can fetch them.
        """
        for asset_id in (ci.video_asset_id, ci.thumbnail_asset_id):
            if not asset_id:
                continue
            a = asset_lookup.get(asset_id)
            if not a:
                continue
            path = a.file_path or ""
            if path.startswith("http://") or path.startswith("https://"):
                return path
        return None

    from apps.api.services.publish_readiness import check_publish_readiness
    from packages.db.models.offers import Offer

    # Batch-resolve offer URLs for content items that have offer_id
    offer_ids: set[uuid.UUID] = {ci.offer_id for ci in content_items if ci.offer_id}
    offer_lookup: dict[uuid.UUID, Offer] = {}
    if offer_ids:
        offer_rows = (await db.execute(select(Offer).where(Offer.id.in_(offer_ids)))).scalars().all()
        offer_lookup = {o.id: o for o in offer_rows}

    created = 0
    blocked_missing_media = 0
    blocked_reasons: dict[str, int] = {}

    for ci in content_items:
        if ci.id in existing_content_ids:
            continue

        best_profile = _match_profile(ci, profiles)
        if not best_profile:
            continue

        # Readiness re-check — second line of defense. Even if an item is in
        # `approved` state, we do NOT materialize a Buffer job unless it
        # actually satisfies the publish-readiness contract for the current
        # platform target. This is the fail-closed gate.
        readiness = await check_publish_readiness(db, ci)
        if not readiness.ok:
            blocked_missing_media += 1
            blocked_reasons[readiness.reason] = blocked_reasons.get(readiness.reason, 0) + 1
            # Park the item so the operator sees the honest state
            ci.status = "pending_media"
            logger.warning(
                "buffer.recompute.readiness_blocked",
                content_item_id=str(ci.id),
                reason=readiness.reason,
                detail=readiness.detail,
            )
            continue

        media_url = _resolve_media_url(ci)
        # Build caption: prefer description, fallback to title
        caption = getattr(ci, "description", None) or ci.title or ""

        # Resolve offer URL → link_url so it gets appended to published caption
        link_url = None
        if ci.offer_id and ci.offer_id in offer_lookup:
            offer = offer_lookup[ci.offer_id]
            link_url = offer.offer_url or None

        content_ctx = {
            "caption": caption,
            "title": ci.title or "",
            "description": getattr(ci, "description", None),
            "content_type": ci.content_type.value if ci.content_type else None,
            "media_url": media_url,
            "link_url": link_url,
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
    return {
        "jobs_created": created,
        "blocked_pending_media": blocked_missing_media,
        "blocked_reasons": blocked_reasons,
    }


def _match_profile(content_item: Any, profiles: list[BufferProfile]) -> BufferProfile | None:
    """Pick the best Buffer profile for a content item (platform match preferred, connected preferred)."""
    connected = [p for p in profiles if p.credential_status == "connected"]
    if connected:
        return connected[0]
    return profiles[0] if profiles else None


# ── Submit to Buffer ──────────────────────────────────────────────────


async def submit_job_to_buffer(db: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
    """Submit a single publish job to Buffer's API.

    Resolves the Buffer API key from DB (dashboard-saved) first, then env var fallback.
    """
    q = await db.execute(select(BufferPublishJob).where(BufferPublishJob.id == job_id))
    job = q.scalar_one_or_none()
    if not job:
        raise ValueError(f"Publish job {job_id} not found")

    profile_q = await db.execute(select(BufferProfile).where(BufferProfile.id == job.buffer_profile_id_fk))
    profile = profile_q.scalar_one_or_none()

    # Resolve API key: DB first (dashboard), env fallback
    from packages.db.models.core import Brand

    brand_q = await db.execute(select(Brand).where(Brand.id == job.brand_id))
    brand = brand_q.scalar_one_or_none()
    org_id = brand.organization_id if brand else None
    buffer_api_key = await _resolve_buffer_api_key(db, org_id) if org_id else ""

    attempt = BufferPublishAttempt(
        job_id=job.id,
        attempt_number=job.retry_count + 1,
        request_payload_json=job.payload_json,
    )

    if not buffer_api_key:
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
            operator_action_needed="Connect this Buffer profile via the Buffer dashboard.",
        )
        db.add(blocker)
    else:
        from packages.clients.external_clients import BufferClient
        from packages.scoring.buffer_engine import validate_publish_payload

        client = BufferClient(api_key=buffer_api_key)

        payload = job.payload_json or {}
        text = payload.get("text", "")
        assets = payload.get("assets")
        metadata = payload.get("metadata")
        media = payload.get("media")  # legacy — used only if `assets` is missing
        scheduled = job.scheduled_at
        profile_id_str = profile.buffer_profile_id if profile else None
        platform_value = profile.platform.value if (profile and profile.platform) else "unknown"

        # Pre-submit validation — fail closed with an honest reason before calling Buffer
        validation = validate_publish_payload(payload, platform_value)

        if not profile_id_str:
            attempt.success = False
            attempt.error_message = "Buffer profile ID not mapped"
            attempt.response_status_code = 0
            job.status = "failed"
            job.error_message = "Buffer profile ID not mapped"
        elif not validation["ok"]:
            attempt.success = False
            attempt.error_message = f"pre_submit_validation_failed: {validation['reason']}"
            attempt.response_status_code = 0
            job.status = "failed"
            job.error_message = f"pre_submit_validation_failed: {validation['reason']}"
            logger.warning(
                "buffer.pre_submit_validation_failed",
                job_id=str(job.id),
                reason=validation["reason"],
                platform=platform_value,
            )
        else:
            result = await client.create_update(
                profile_ids=[profile_id_str],
                text=text,
                media=media,
                assets=assets,
                metadata=metadata,
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
                db.add(
                    BufferBlocker(
                        brand_id=job.brand_id,
                        buffer_profile_id_fk=job.buffer_profile_id_fk,
                        blocker_type="buffer_api_blocked",
                        severity="critical",
                        description=result.get("error", "Buffer API blocked"),
                        operator_action_needed="Check BUFFER_API_KEY configuration.",
                    )
                )
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


async def sync_published_posts_from_buffer(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    """Pull all posts from Buffer's GraphQL API and write external links + status back into DB.

    This is the bridge that ingests real destination URLs (x.com/..., instagram.com/...)
    into publish_jobs and content_items, turning "queued" into "verified published".
    """
    from sqlalchemy import select
    from sqlalchemy import update as sa_update

    from packages.clients.external_clients import BufferClient
    from packages.db.models.content import ContentItem
    from packages.db.models.publishing import PublishJob

    api_key = await _resolve_buffer_api_key(db, organization_id)
    if not api_key:
        return {"synced": 0, "error": "no_api_key"}

    client = BufferClient(api_key=api_key)

    # Get Buffer organization id
    org_result = await client.get_organizations()
    if not org_result.get("success"):
        return {"synced": 0, "error": "org_fetch_failed"}
    orgs = (org_result.get("data") or {}).get("account", {}).get("organizations", [])
    if not orgs:
        return {"synced": 0, "error": "no_orgs"}
    buffer_org_id = orgs[0]["id"]

    # Fetch all posts
    list_result = await client._graphql(
        """query($input: PostsInput!) {
            posts(input: $input) {
                edges { node { id status sentAt externalLink channelId channelService } }
            }
        }""",
        {"input": {"organizationId": buffer_org_id}},
    )
    if not list_result.get("success"):
        return {"synced": 0, "error": "list_failed"}

    edges = (list_result.get("data") or {}).get("posts", {}).get("edges", []) or []

    synced = 0
    for edge in edges:
        node = edge.get("node") or {}
        buf_id = node.get("id")
        ext_link = node.get("externalLink")
        sent_at = node.get("sentAt")
        status = node.get("status")

        if not buf_id or not ext_link:
            continue

        # Find matching BufferPublishJob
        bpj_q = await db.execute(select(BufferPublishJob).where(BufferPublishJob.buffer_post_id == buf_id))
        bpj = bpj_q.scalar_one_or_none()
        if not bpj:
            continue

        # Update buffer job
        bpj.status = "published" if status == "sent" else (status or "sent")
        existing_payload = bpj.payload_json or {}
        existing_payload["external_link"] = ext_link
        existing_payload["sent_at"] = sent_at
        bpj.payload_json = existing_payload

        # Update publish_jobs via content_item_id
        if bpj.content_item_id:
            await db.execute(
                sa_update(PublishJob)
                .where(PublishJob.content_item_id == bpj.content_item_id)
                .values(
                    platform_post_url=ext_link,
                    status="COMPLETED",
                )
            )
            await db.execute(
                sa_update(ContentItem).where(ContentItem.id == bpj.content_item_id).values(status="published")
            )
        synced += 1

    await db.flush()
    logger.info("buffer.sync_published_posts", org_id=str(organization_id), synced=synced, total_posts=len(edges))
    return {"synced": synced, "total_posts_in_buffer": len(edges)}


async def run_status_sync(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    """Sync Buffer post statuses back into our system.

    With a real Buffer API key, this would poll Buffer's updates endpoint.
    Currently simulates status transitions for submitted jobs.
    """
    jobs_q = await db.execute(
        select(BufferPublishJob).where(
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

    # Resolve org to check for DB-stored Buffer API key
    from packages.db.models.core import Brand

    brand_row = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    _org_id = brand_row.organization_id if brand_row else None
    _buffer_key = await _resolve_buffer_api_key(db, _org_id) if _org_id else ""

    for job in jobs:
        if not _buffer_key:
            # Without API key, we simulate based on job age
            if job.status == "submitted":
                job.status = "queued"
                updated += 1
        else:
            from packages.clients.external_clients import BufferClient

            client = BufferClient(api_key=_buffer_key)

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
        details_json={"has_api_key": bool(_buffer_key)},
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
        .order_by(BufferBlocker.created_at.desc())
        .limit(limit)
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

    # Resolve org to check for DB-stored Buffer API key
    from packages.db.models.core import Brand as _Brand

    _brand_row = (await db.execute(select(_Brand).where(_Brand.id == brand_id))).scalar_one_or_none()
    _org_id = _brand_row.organization_id if _brand_row else None
    _has_key = bool(await _resolve_buffer_api_key(db, _org_id)) if _org_id else False

    brand_ctx = {"has_buffer_api_key": _has_key}
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
        .order_by(BufferStatusSync.created_at.desc())
        .limit(limit)
    )
    return list(q.scalars().all())

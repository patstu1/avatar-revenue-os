"""Auto-publish bridge: approved content → native-first publishing with aggregator fallback.

Scans for approved content items, checks readiness and warmup constraints,
publishes via the distributor router (native API first, then Buffer/Publer/Ayrshare failover).
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task
from sqlalchemy import func, select

from packages.db.models.accounts import CreatorAccount
from packages.db.models.buffer_distribution import BufferProfile, BufferPublishJob
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.session import get_async_session_factory
from packages.scoring.buffer_engine import build_publish_payload, determine_publish_mode

logger = logging.getLogger(__name__)


async def _auto_publish_for_brand(brand_id):
    """Publish approved content via the multi-distributor router with failover."""
    from packages.clients.distributor_router import PublishRequest, any_distributor_configured, publish_with_failover

    async with get_async_session_factory()() as db:
        # Load aggregator credentials from encrypted DB
        agg_creds = {}
        brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
        org_id = brand.organization_id if brand else None
        if org_id:
            try:
                from apps.api.services import secrets_service
                from apps.api.services.integration_manager import get_credential
                for prov_key in ("buffer", "publer", "ayrshare"):
                    # Check integration_providers first, then provider_secrets
                    key = await get_credential(db, org_id, prov_key)
                    if not key:
                        key = await secrets_service.get_key(db, org_id, prov_key)
                    if key:
                        agg_creds[prov_key] = key
            except Exception as e:
                logger.warning("auto_publish_cred_load_failed", error=str(e))

        if not any_distributor_configured(creds=agg_creds):
            return {"brand_id": str(brand_id), "skipped": True, "reason": "No publishing service configured - add API keys in Settings > Integrations"}

        try:
            from apps.api.services.permission_enforcement import PermissionDenied, enforce_permission
            if org_id:
                await enforce_permission(db, org_id, "auto_publish")
        except PermissionDenied as e:
            return {"brand_id": str(brand_id), "skipped": True, "reason": f"permission_denied: {e.mode}"}
        except Exception:
            pass

        profiles = list((await db.execute(
            select(BufferProfile).where(
                BufferProfile.brand_id == brand_id,
                BufferProfile.is_active.is_(True),
            )
        )).scalars().all())

        connected = [p for p in profiles if p.credential_status == "connected"] or profiles

        approved_items = list((await db.execute(
            select(ContentItem).where(
                ContentItem.brand_id == brand_id,
                ContentItem.status == "approved",
            ).order_by(ContentItem.created_at.desc()).limit(50)
        )).scalars().all())
        # NOTE: auto_publish worker picks up ALL approved items including
        # auto_approved ones from the publish policy engine. The Approval
        # record tracks whether it was auto or manual.

        existing_ids = set(r[0] for r in (await db.execute(
            select(BufferPublishJob.content_item_id).where(
                BufferPublishJob.brand_id == brand_id,
                BufferPublishJob.is_active.is_(True),
            )
        )).all() if r[0])

        accounts = {str(a.id): a for a in (await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            )
        )).scalars().all()}

        created = 0
        published_direct = 0
        skipped_health = 0
        skipped_existing = 0
        skipped_warmup = 0
        skipped_no_offer = 0
        failed = 0

        # Brand-level override: if explicitly set, allow unmonetized publishing.
        # This is an escape hatch, NOT the default behavior. The default is
        # hard-block: content without an attached offer does not publish.
        brand_guidelines = brand.brand_guidelines or {} if brand else {}
        allow_unmonetized = brand_guidelines.get("allow_unmonetized_publishing", False)

        for ci in approved_items:
            if ci.id in existing_ids:
                skipped_existing += 1
                continue

            # ── HARD-BLOCK: content MUST have an offer attached ──────────
            # The auto_attach_offers task (every 3m) ensures this is populated
            # before the 10m publish cycle runs. If an item still has no offer,
            # either the brand has no active offers or attach is lagging.
            # Either way, do NOT publish unmonetized content.
            if not ci.offer_id and not allow_unmonetized:
                skipped_no_offer += 1
                logger.warning(
                    "auto_publish.hard_block_no_offer",
                    content_id=str(ci.id),
                    brand_id=str(brand_id),
                    title=ci.title[:60] if ci.title else "",
                )
                continue

            acct = accounts.get(str(ci.creator_account_id)) if ci.creator_account_id else None
            if acct:
                health = getattr(acct.account_health, "value", str(acct.account_health)) if acct.account_health else "healthy"
                if health in ("critical", "suspended"):
                    skipped_health += 1
                    continue
                fatigue = float(acct.fatigue_score or 0)
                if fatigue > 0.8:
                    skipped_health += 1
                    continue

                try:
                    from datetime import datetime, timezone

                    from packages.scoring.warmup_engine import can_post_now
                    created_at = acct.created_at if acct.created_at else datetime.now(timezone.utc)
                    posts_today_count = (await db.execute(
                        select(func.count(BufferPublishJob.id)).where(
                            BufferPublishJob.brand_id == brand_id,
                            BufferPublishJob.is_active.is_(True),
                            func.date(BufferPublishJob.created_at) == func.current_date(),
                        )
                    )).scalar() or 0
                    platform_str = getattr(acct.platform, 'value', str(acct.platform)) if acct.platform else "youtube"
                    warmup_check = can_post_now(created_at, platform_str, posts_today_count)
                    if not warmup_check.get("allowed"):
                        skipped_warmup += 1
                        continue
                except Exception as warmup_err:
                    logger.warning("Warmup check failed for account %s, BLOCKING post as safety measure: %s", acct.id, warmup_err)
                    skipped_warmup += 1
                    continue

            try:
                from apps.api.services.disclosure_injection_service import check_and_inject_disclosure
                disc_result = await check_and_inject_disclosure(db, ci.id)
                if disc_result.get("injected"):
                    logger.info("disclosure injected for content %s: %s", ci.id, disc_result.get("disclosure_type"))
            except Exception:
                pass

            platform = ci.platform or "youtube"
            text = ci.description or ci.title or ""
            offer_link = None
            if ci.offer_id:
                from packages.db.models.core import Offer
                offer = (await db.execute(select(Offer).where(Offer.id == ci.offer_id))).scalar_one_or_none()
                if offer:
                    offer_link = getattr(offer, "offer_url", None) or getattr(offer, "landing_url", None) or None

            if not offer_link:
                try:
                    from packages.scoring.affiliate_link_engine import generate_tracking_id, select_best_product
                    acct = accounts.get(str(ci.creator_account_id)) if ci.creator_account_id else None
                    niche = acct.niche_focus if acct and acct.niche_focus else "general"
                    tid = generate_tracking_id(str(ci.id), str(ci.creator_account_id or ""), platform)
                    product = select_best_product(niche, ci.title, tid)
                    if product.get("link"):
                        offer_link = product["link"]
                except Exception:
                    pass

            profile_ids = []
            if connected:
                best = connected[0]
                for p in connected:
                    plat = getattr(p.platform, "value", str(p.platform)) if p.platform else ""
                    if plat == platform:
                        best = p
                        break
                if best.buffer_profile_id:
                    profile_ids = [best.buffer_profile_id]

            media_urls = []
            from packages.db.models.content import Asset
            if ci.video_asset_id:
                video_asset = (await db.execute(select(Asset).where(Asset.id == ci.video_asset_id))).scalar_one_or_none()
                if video_asset and video_asset.file_path and video_asset.file_path.startswith("http"):
                    media_urls.append(video_asset.file_path)
            if ci.thumbnail_asset_id and not media_urls:
                thumb_asset = (await db.execute(select(Asset).where(Asset.id == ci.thumbnail_asset_id))).scalar_one_or_none()
                if thumb_asset and thumb_asset.file_path and thumb_asset.file_path.startswith("http"):
                    media_urls.append(thumb_asset.file_path)

            request = PublishRequest(
                text=text, platform=platform,
                profile_ids=profile_ids,
                media_urls=media_urls or None, link_url=offer_link,
            )

            result = await publish_with_failover(request, creds=agg_creds)

            content_ctx = {"caption": ci.title or "", "title": ci.title or "", "media_url": None, "link_url": None}
            profile_ctx = {"platform": platform, "buffer_profile_id": profile_ids[0] if profile_ids else ""}
            payload = build_publish_payload(content_ctx, profile_ctx)
            mode = determine_publish_mode(content_ctx, profile_ctx)

            if connected:
                db.add(BufferPublishJob(
                    brand_id=brand_id,
                    buffer_profile_id_fk=connected[0].id,
                    content_item_id=ci.id,
                    platform=connected[0].platform,
                    publish_mode=mode,
                    status="published" if result.success else "failed",
                    distributor_name=result.method or "unknown",
                    distributor_post_id=result.post_id if result.success else None,
                    buffer_post_id=result.post_id if result.success else None,
                    error_message=result.error if not result.success else None,
                    payload_json={
                        **payload,
                        "publish_method": result.method,
                        "methods_tried": result.methods_tried,
                    },
                ))

            if result.success:
                ci.status = "published"
                published_direct += 1

                # Event-driven chain: schedule per-item metrics ingest 5 min
                # from now so the platform API has time to count. The ingest
                # task chains to causal attribution on success.
                try:
                    from workers.analytics_ingestion_worker.tasks import ingest_metrics_for_content_item
                    acct_id = str(ci.creator_account_id) if ci.creator_account_id else str(acct.id) if acct else ""
                    if acct_id:
                        ingest_metrics_for_content_item.apply_async(
                            args=[str(ci.id), acct_id],
                            countdown=300,  # 5-minute delay
                            queue="analytics",
                        )
                except Exception:
                    logger.debug("event_chain.schedule_failed content_id=%s", ci.id, exc_info=True)
            else:
                failed += 1
                logger.warning("publish failed for content %s: %s (tried: %s)", ci.id, result.error, result.methods_tried)

            created += 1

        await db.commit()
        return {
            "brand_id": str(brand_id),
            "jobs_created": created,
            "published_direct": published_direct,
            "failed": failed,
            "skipped_health": skipped_health,
            "skipped_existing": skipped_existing,
            "skipped_warmup": skipped_warmup,
            "skipped_no_offer": skipped_no_offer,
        }


async def _run_auto_publish():
    async with get_async_session_factory()() as db:
        brand_ids = [r[0] for r in (await db.execute(select(Brand.id).where(Brand.is_active.is_(True)))).all()]

    total_created = 0
    total_published = 0
    for bid in brand_ids:
        try:
            result = await _auto_publish_for_brand(bid)
            total_created += result.get("jobs_created", 0)
            total_published += result.get("published_direct", 0)
            if result.get("jobs_created"):
                logger.info("auto_publish.completed brand=%s published=%s failed=%s warmup_skipped=%s",
                            result["brand_id"], result.get("published_direct", 0),
                            result.get("failed", 0), result.get("skipped_warmup", 0))
        except Exception:
            logger.exception("auto_publish.failed brand_id=%s", str(bid))

    return {"total_jobs_created": total_created, "total_published": total_published, "brands_processed": len(brand_ids)}


@shared_task(name="workers.publishing_worker.tasks.auto_publish_approved_content")
def auto_publish_approved_content():
    import packages.db.session as db_session_mod

    # Reset cached async engine so a fresh one binds to the new loop.
    # Celery fork workers reuse processes — each task needs its own loop+engine.
    if db_session_mod._async_engine is not None:
        db_session_mod._async_engine.sync_engine.dispose()
        db_session_mod._async_engine = None
        db_session_mod._async_session_factory = None

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run_auto_publish())
    finally:
        loop.close()

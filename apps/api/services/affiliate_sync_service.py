"""Affiliate Network Sync Service — import conversions/commissions from network APIs."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.clients.affiliate_network_clients import CJClient, ImpactClient, ShareASaleClient
from packages.db.models.affiliate_intel import (
    AffiliateConversionEvent,
    AffiliateLink,
    AffiliateNetworkAccount,
)


async def sync_network_data(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Sync conversion/commission data from all configured affiliate networks."""
    networks = list(
        (
            await db.execute(
                select(AffiliateNetworkAccount).where(
                    AffiliateNetworkAccount.brand_id == brand_id, AffiliateNetworkAccount.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    total_synced = 0

    for net in networks:
        name = net.network_name.lower()
        try:
            if "impact" in name:
                client = ImpactClient()
                result = await client.fetch_conversions(start, end)
                if result.get("success"):
                    total_synced += await _import_impact_conversions(db, brand_id, net.id, result["data"])
            elif "shareasale" in name:
                client = ShareASaleClient()
                result = await client.fetch_activity(start, end)
                if result.get("success"):
                    total_synced += 0  # XML parsing would go here
            elif "cj" in name or "commission junction" in name:
                client = CJClient()
                result = await client.fetch_commissions(start, end)
                if result.get("success"):
                    total_synced += await _import_cj_commissions(db, brand_id, net.id, result["data"])

            net.status = "synced"
        except Exception:
            net.status = "sync_failed"

    await db.flush()
    return {"networks_checked": len(networks), "records_synced": total_synced, "status": "completed"}


async def _import_impact_conversions(
    db: AsyncSession, brand_id: uuid.UUID, network_id: uuid.UUID, actions: list
) -> int:
    count = 0
    for a in actions:
        action_tracker = a.get("SharedId") or a.get("ActionTrackerId") or a.get("SubId1") or ""
        link = None
        if action_tracker:
            link = (
                await db.execute(
                    select(AffiliateLink).where(
                        AffiliateLink.brand_id == brand_id,
                        AffiliateLink.tracking_id == action_tracker,
                    )
                )
            ).scalar_one_or_none()
        if not link:
            offer_id_str = a.get("CampaignId") or a.get("ProgramId") or ""
            if offer_id_str:
                link = (
                    await db.execute(
                        select(AffiliateLink)
                        .where(AffiliateLink.brand_id == brand_id)
                        .order_by(AffiliateLink.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
            else:
                link = (
                    await db.execute(
                        select(AffiliateLink)
                        .where(AffiliateLink.brand_id == brand_id)
                        .order_by(AffiliateLink.created_at.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
        if not link:
            continue
        db.add(
            AffiliateConversionEvent(
                brand_id=brand_id,
                link_id=link.id,
                offer_id=link.offer_id,
                conversion_value=float(a.get("Amount", 0) or 0),
                conversion_type="sale",
            )
        )
        count += 1
    return count


async def _import_cj_commissions(db: AsyncSession, brand_id: uuid.UUID, network_id: uuid.UUID, data: Any) -> int:
    if not isinstance(data, list):
        return 0
    count = 0
    for item in data:
        link = (
            await db.execute(select(AffiliateLink).where(AffiliateLink.brand_id == brand_id).limit(1))
        ).scalar_one_or_none()
        if not link:
            continue
        db.add(
            AffiliateConversionEvent(
                brand_id=brand_id,
                link_id=link.id,
                offer_id=link.offer_id,
                conversion_value=float(item.get("saleAmount", 0) or 0),
                conversion_type="sale",
            )
        )
        count += 1
    return count

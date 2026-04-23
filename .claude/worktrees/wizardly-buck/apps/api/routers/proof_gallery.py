"""Proof Gallery — public-facing endpoint for B2B outbound.

Returns proof videos, offer packages, and cluster capabilities.
No auth required — this is what you send to prospects.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import DBSession
from packages.db.models.content import Asset, ContentItem
from packages.db.models.offers import Offer
from packages.db.models.core import Brand

router = APIRouter(tags=["proof-gallery"])


class ProofAsset(BaseModel):
    id: str
    cluster: str
    title: str
    video_url: str
    cover_url: Optional[str] = None
    duration_seconds: float
    resolution: str = "1920x1080"

    model_config = {"from_attributes": True}


class OfferPackage(BaseModel):
    id: str
    name: str
    description: str
    price: float
    cluster: str

    model_config = {"from_attributes": True}


class ClusterInfo(BaseModel):
    name: str
    brand: str
    niche: str
    revenue_role: str
    channels: int
    proof_count: int
    offers: list[OfferPackage]


class ProofGalleryResponse(BaseModel):
    clusters: list[ClusterInfo]
    proof_assets: list[ProofAsset]
    offers: list[OfferPackage]
    total_proof_videos: int
    total_offers: int


@router.get("/proof-gallery", response_model=ProofGalleryResponse)
async def proof_gallery(db: DBSession, cluster: Optional[str] = None):
    """Public proof gallery — videos, offers, and cluster info for outbound pitches."""

    # Get proof assets
    q = select(ContentItem, Asset).join(Asset, Asset.id == ContentItem.video_asset_id).where(
        ContentItem.status == "proof_ready",
    )
    if cluster:
        q = q.where(ContentItem.tags.contains([cluster]))
    q = q.order_by(desc(ContentItem.created_at)).limit(50)
    rows = (await db.execute(q)).all()

    proof_assets = []
    for ci, asset in rows:
        meta = asset.metadata_blob or {}
        proof_assets.append(ProofAsset(
            id=str(ci.id),
            cluster=meta.get("cluster", "general"),
            title=ci.title.replace("[PROOF] ", ""),
            video_url=asset.file_path,
            cover_url=meta.get("cover_url"),
            duration_seconds=asset.duration_seconds or 0,
        ))

    # Get B2B offers
    oq = select(Offer).where(Offer.is_active.is_(True), Offer.payout_amount > 0).order_by(Offer.payout_amount)
    offer_rows = (await db.execute(oq)).scalars().all()

    offers = []
    brand_cache = {}
    for o in offer_rows:
        if o.brand_id not in brand_cache:
            b = (await db.execute(select(Brand).where(Brand.id == o.brand_id))).scalar_one_or_none()
            brand_cache[o.brand_id] = b
        brand = brand_cache.get(o.brand_id)
        offers.append(OfferPackage(
            id=str(o.id),
            name=o.name,
            description=o.description or "",
            price=o.payout_amount,
            cluster=brand.niche if brand else "general",
        ))

    # Get cluster info
    brands = (await db.execute(
        select(Brand).where(Brand.is_active.is_(True))
    )).scalars().all()

    REVENUE_ROLES = {
        "beauty": "B2B proof + affiliate",
        "fitness_health": "B2B proof + newsletter",
        "AI tools": "affiliate + B2B proof",
        "celebrity culture": "authority + content",
        "personal finance": "affiliate + lead gen",
    }

    from packages.db.models.buffer_distribution import BufferProfile
    clusters = []
    for b in brands:
        channel_count = (await db.execute(
            select(BufferProfile).where(BufferProfile.brand_id == b.id, BufferProfile.is_active.is_(True))
        )).scalars().all()
        proof_count = len([p for p in proof_assets if any(
            t in (b.niche or "").lower() or t in b.name.lower().replace(" ", "_")
            for t in [p.cluster]
        )])
        brand_offers = [o for o in offers if o.cluster == b.niche]

        clusters.append(ClusterInfo(
            name=b.name,
            brand=b.name,
            niche=b.niche or "general",
            revenue_role=REVENUE_ROLES.get(b.niche, "content production"),
            channels=len(channel_count),
            proof_count=proof_count,
            offers=brand_offers,
        ))

    return ProofGalleryResponse(
        clusters=clusters,
        proof_assets=proof_assets,
        offers=offers,
        total_proof_videos=len(proof_assets),
        total_offers=len(offers),
    )


@router.get("/proof-gallery/{cluster_name}", response_model=ProofGalleryResponse)
async def proof_gallery_by_cluster(cluster_name: str, db: DBSession):
    """Filtered proof gallery for a specific cluster."""
    return await proof_gallery(db, cluster=cluster_name)

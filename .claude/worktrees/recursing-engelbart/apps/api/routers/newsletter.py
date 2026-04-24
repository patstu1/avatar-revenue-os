"""Newsletter integration endpoints — Beehiiv connections and campaign sync."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional

from apps.api.deps import CurrentUser, DBSession
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.core import Brand
from packages.db.models.newsletter import NewsletterConnection, NewsletterCampaign
from packages.clients.beehiiv_client import BeehiivClient, BeehiivError

router = APIRouter()
conn_service = CRUDService(NewsletterConnection)
campaign_service = CRUDService(NewsletterCampaign)
brand_service = CRUDService(Brand)


class ConnectionCreate(BaseModel):
    brand_id: uuid.UUID
    api_key: str
    publication_id: str
    publication_name: Optional[str] = None


class ConnectionResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    provider: str
    publication_id: str
    publication_name: Optional[str] = None
    subscriber_count: int
    last_synced_at: Optional[str] = None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class CampaignResponse(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    brand_id: uuid.UUID
    external_campaign_id: str
    subject: Optional[str] = None
    status: str
    sent_at: Optional[str] = None
    open_rate: float
    click_rate: float
    unsubscribe_count: int
    revenue: float
    created_at: datetime
    model_config = {"from_attributes": True}


@router.post("/connections", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(body: ConnectionCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Verify API key works
    client = BeehiivClient(body.api_key)
    try:
        count = await client.get_subscriber_count(body.publication_id)
    except BeehiivError as e:
        raise HTTPException(status_code=400, detail=f"Beehiiv API error: {e}")

    conn = await conn_service.create(
        db,
        brand_id=body.brand_id,
        provider="beehiiv",
        publication_id=body.publication_id,
        publication_name=body.publication_name,
        api_key_encrypted=body.api_key,  # TODO: encrypt at rest
        subscriber_count=count,
        last_synced_at=datetime.now(timezone.utc),
    )
    await log_action(
        db, "newsletter.connected",
        organization_id=current_user.organization_id, brand_id=body.brand_id,
        user_id=current_user.id, actor_type="human",
        entity_type="newsletter_connection", entity_id=conn.id,
    )
    return conn


@router.get("/connections", response_model=list[ConnectionResponse])
async def list_connections(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await conn_service.list(db, filters={"brand_id": brand_id})
    return result["items"]


@router.post("/connections/{connection_id}/sync")
async def sync_connection(connection_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        conn = await conn_service.get_or_404(db, connection_id)
    except ValueError:
        raise HTTPException(status_code=404)
    brand = await brand_service.get(db, conn.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    client = BeehiivClient(conn.api_key_encrypted)

    # Sync subscriber count
    try:
        count = await client.get_subscriber_count(conn.publication_id)
        conn.subscriber_count = count
        conn.last_synced_at = datetime.now(timezone.utc)
    except BeehiivError as e:
        raise HTTPException(status_code=502, detail=f"Beehiiv sync failed: {e}")

    # Sync campaigns
    try:
        posts_data = await client.list_posts(conn.publication_id, limit=50, status="confirmed")
        posts = posts_data.get("data", [])
        synced = 0
        for post in posts:
            ext_id = post.get("id", "")
            if not ext_id:
                continue
            # Check if already exists
            existing = await campaign_service.list(db, filters={"external_campaign_id": ext_id}, page_size=1)
            stats = post.get("stats", {})
            campaign_data = {
                "connection_id": conn.id,
                "brand_id": conn.brand_id,
                "external_campaign_id": ext_id,
                "subject": post.get("title") or post.get("subject_line"),
                "status": post.get("status", "confirmed"),
                "sent_at": post.get("publish_date"),
                "open_rate": stats.get("open_rate", 0) or 0,
                "click_rate": stats.get("click_rate", 0) or 0,
                "unsubscribe_count": stats.get("unsubscribes", 0) or 0,
                "revenue": 0,
                "raw_stats": stats,
            }
            if existing["items"]:
                item = existing["items"][0]
                for k, v in campaign_data.items():
                    if k not in ("connection_id", "brand_id", "external_campaign_id"):
                        setattr(item, k, v)
            else:
                await campaign_service.create(db, **campaign_data)
            synced += 1
    except BeehiivError as e:
        raise HTTPException(status_code=502, detail=f"Campaign sync failed: {e}")

    await db.flush()
    return {"subscriber_count": count, "campaigns_synced": synced}


@router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await campaign_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        conn = await conn_service.get_or_404(db, connection_id)
    except ValueError:
        raise HTTPException(status_code=404)
    brand = await brand_service.get(db, conn.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    await conn_service.delete(db, connection_id)

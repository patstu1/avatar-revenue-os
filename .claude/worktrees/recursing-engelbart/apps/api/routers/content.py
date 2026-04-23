"""Content pipeline endpoints — briefs, scripts, content items."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.core import ContentBriefCreate, ContentBriefResponse
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.content import ContentBrief, ContentItem, Script
from packages.db.models.core import Brand

router = APIRouter()
brief_service = CRUDService(ContentBrief)
script_service = CRUDService(Script)
content_service = CRUDService(ContentItem)
brand_service = CRUDService(Brand)


@router.post("/briefs", response_model=ContentBriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(body: ContentBriefCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    brief = await brief_service.create(db, **body.model_dump())
    await log_action(
        db, "content_brief.created",
        brand_id=body.brand_id, user_id=current_user.id,
        actor_type="human", entity_type="content_brief", entity_id=brief.id,
    )
    return brief


@router.get("/briefs", response_model=list[ContentBriefResponse])
async def list_briefs(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await brief_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.get("/briefs/{brief_id}", response_model=ContentBriefResponse)
async def get_brief(brief_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await brief_service.get_or_404(db, brief_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Brief not found")


@router.get("/items")
async def list_content_items(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return await content_service.list(db, filters={"brand_id": brand_id}, page=page)

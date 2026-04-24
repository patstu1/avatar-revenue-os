"""Content pipeline endpoints — briefs, scripts, content items."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from apps.api.deps import CurrentUser, DBSession, OperatorUser
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


class GenerateBatchRequest(BaseModel):
    brand_id: uuid.UUID
    platform: str = "tiktok"
    topic: str
    count: int = 5


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


@router.post("/generate-batch")
async def generate_batch(body: GenerateBatchRequest, current_user: OperatorUser, db: DBSession):
    """Create briefs and kick off content generation for a batch of content pieces.

    Creates one brief per item with the given topic and platform, then triggers
    the generation pipeline for each brief asynchronously.
    """
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not found or access denied")

    count = min(body.count, 25)  # Cap at 25
    created_briefs = []

    for i in range(count):
        title = f"{body.topic}" if count == 1 else f"{body.topic} ({i + 1}/{count})"
        brief = await brief_service.create(
            db,
            brand_id=body.brand_id,
            title=title,
            content_type="short_video",
            target_platform=body.platform,
            hook=f"Hook for: {body.topic}",
            angle=body.topic,
            status="draft",
        )
        created_briefs.append(brief)

    await db.flush()

    # Trigger async generation for each brief
    results = []
    for brief in created_briefs:
        try:
            from apps.api.services.content_generation_service import generate_content_from_brief
            gen_result = await generate_content_from_brief(db, brief.id)
            results.append({
                "brief_id": str(brief.id),
                "title": brief.title,
                "success": gen_result.get("success", False),
                "content_item_id": gen_result.get("content_item_id"),
                "error": gen_result.get("error"),
            })
        except Exception as e:
            results.append({
                "brief_id": str(brief.id),
                "title": brief.title,
                "success": False,
                "error": str(e),
            })

    await log_action(
        db, "content.batch_generated",
        brand_id=body.brand_id, user_id=current_user.id,
        actor_type="human", entity_type="content_batch",
        details={"count": count, "topic": body.topic, "platform": body.platform},
    )

    successful = sum(1 for r in results if r["success"])
    return {
        "total": count,
        "successful": successful,
        "failed": count - successful,
        "results": results,
    }

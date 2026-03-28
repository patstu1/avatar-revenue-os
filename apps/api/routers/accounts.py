"""Creator account management endpoints."""
import uuid

from fastapi import APIRouter, HTTPException, Query, status

from apps.api.deps import CurrentUser, DBSession
from apps.api.schemas.core import CreatorAccountCreate, CreatorAccountResponse
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand

router = APIRouter()
account_service = CRUDService(CreatorAccount)
brand_service = CRUDService(Brand)


@router.post("/", response_model=CreatorAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: CreatorAccountCreate, current_user: CurrentUser, db: DBSession):
    brand = await brand_service.get(db, body.brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    account = await account_service.create(db, **body.model_dump())
    await log_action(
        db, "creator_account.created",
        brand_id=body.brand_id, user_id=current_user.id,
        actor_type="human", entity_type="creator_account", entity_id=account.id,
    )
    return account


@router.get("/", response_model=list[CreatorAccountResponse])
async def list_accounts(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    result = await account_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.get("/{account_id}", response_model=CreatorAccountResponse)
async def get_account(account_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        return await account_service.get_or_404(db, account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Account not found")

"""Creator account management endpoints with RBAC."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from apps.api.deps import CurrentUser, DBSession, OperatorUser
from apps.api.schemas.core import CreatorAccountCreate, CreatorAccountResponse, CreatorAccountUpdate
from apps.api.services.audit_service import log_action
from apps.api.services.crud_service import CRUDService
from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand

logger = logging.getLogger(__name__)

router = APIRouter()
account_service = CRUDService(CreatorAccount)
brand_service = CRUDService(Brand)


async def _verify_brand_access(brand_id: uuid.UUID, user, db):
    brand = await brand_service.get(db, brand_id)
    if not brand or brand.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    return brand


@router.post("/", response_model=CreatorAccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: CreatorAccountCreate, current_user: OperatorUser, db: DBSession):
    await _verify_brand_access(body.brand_id, current_user, db)
    account = await account_service.create(db, **body.model_dump())
    await log_action(
        db, "creator_account.created",
        organization_id=current_user.organization_id,
        brand_id=body.brand_id, user_id=current_user.id,
        actor_type="human", entity_type="creator_account", entity_id=account.id,
    )
    return account


@router.get("/", response_model=list[CreatorAccountResponse])
async def list_accounts(
    brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession, page: int = Query(1, ge=1)
):
    await _verify_brand_access(brand_id, current_user, db)
    result = await account_service.list(db, filters={"brand_id": brand_id}, page=page)
    return result["items"]


@router.get("/{account_id}", response_model=CreatorAccountResponse)
async def get_account(account_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    try:
        acct = await account_service.get_or_404(db, account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Account not found")
    await _verify_brand_access(acct.brand_id, current_user, db)
    return acct


@router.patch("/{account_id}", response_model=CreatorAccountResponse)
async def update_account(account_id: uuid.UUID, body: CreatorAccountUpdate, current_user: OperatorUser, db: DBSession):
    try:
        acct = await account_service.get_or_404(db, account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Account not found")
    await _verify_brand_access(acct.brand_id, current_user, db)
    updated = await account_service.update(db, account_id, **body.model_dump(exclude_unset=True))
    await log_action(
        db, "creator_account.updated",
        organization_id=current_user.organization_id,
        brand_id=acct.brand_id, user_id=current_user.id, actor_type="human",
        entity_type="creator_account", entity_id=account_id,
    )
    return updated


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    try:
        acct = await account_service.get_or_404(db, account_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Account not found")
    await _verify_brand_access(acct.brand_id, current_user, db)
    await account_service.delete(db, account_id)
    await log_action(
        db, "creator_account.deleted",
        organization_id=current_user.organization_id,
        brand_id=acct.brand_id, user_id=current_user.id, actor_type="human",
        entity_type="creator_account", entity_id=account_id,
    )


class CredentialUpdate(BaseModel):
    platform_access_token: str
    platform_refresh_token: Optional[str] = None
    platform_external_id: Optional[str] = None
    platform_token_expires_at: Optional[str] = None


@router.put("/{account_id}/credentials")
async def update_credentials(account_id: uuid.UUID, body: CredentialUpdate, current_user: OperatorUser, db: DBSession):
    """Store platform API credentials for an account."""
    from sqlalchemy import select
    acct = (await db.execute(select(CreatorAccount).where(CreatorAccount.id == account_id))).scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    await _verify_brand_access(acct.brand_id, current_user, db)

    acct.platform_access_token = body.platform_access_token
    if body.platform_refresh_token is not None:
        acct.platform_refresh_token = body.platform_refresh_token
    if body.platform_external_id is not None:
        acct.platform_external_id = body.platform_external_id
    if body.platform_token_expires_at:
        try:
            acct.platform_token_expires_at = datetime.fromisoformat(body.platform_token_expires_at)
        except (ValueError, TypeError) as exc:
            logger.warning("Invalid token expiry date %r for account %s: %s", body.platform_token_expires_at, account_id, exc)
    acct.credential_status = "connected"
    await db.flush()
    await db.refresh(acct)

    await log_action(
        db, "creator_account.credentials_updated",
        organization_id=current_user.organization_id,
        brand_id=acct.brand_id, user_id=current_user.id, actor_type="human",
        entity_type="creator_account", entity_id=account_id,
    )
    return {
        "account_id": str(acct.id),
        "credential_status": acct.credential_status,
        "platform_external_id": acct.platform_external_id,
    }


@router.post("/{account_id}/sync")
async def trigger_sync(account_id: uuid.UUID, current_user: OperatorUser, db: DBSession):
    """Trigger a manual analytics sync for an account."""
    from sqlalchemy import select
    acct = (await db.execute(select(CreatorAccount).where(CreatorAccount.id == account_id))).scalar_one_or_none()
    if not acct:
        raise HTTPException(status_code=404, detail="Account not found")
    await _verify_brand_access(acct.brand_id, current_user, db)

    if not acct.platform_access_token:
        raise HTTPException(status_code=400, detail="No platform credentials stored. Connect the account first.")

    platform_val = acct.platform.value if hasattr(acct.platform, 'value') else str(acct.platform)

    sync_result = {"account_id": str(acct.id), "platform": platform_val, "status": "completed", "metrics_synced": 0}

    if platform_val == "youtube":
        from apps.api.services.youtube_sync_service import sync_youtube_account
        sync_result = await sync_youtube_account(db, acct)
    else:
        sync_result["status"] = "unsupported"
        sync_result["message"] = f"Manual sync not yet supported for {platform_val}. YouTube is currently supported."

    acct.last_synced_at = datetime.now(timezone.utc)
    await db.flush()

    await log_action(
        db, "creator_account.sync_triggered",
        organization_id=current_user.organization_id,
        brand_id=acct.brand_id, user_id=current_user.id, actor_type="human",
        entity_type="creator_account", entity_id=account_id,
    )
    return sync_result

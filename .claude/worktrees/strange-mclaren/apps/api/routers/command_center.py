"""System Command Center API."""
import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from apps.api.deps import CurrentUser, DBSession
from apps.api.services.command_center_service import get_command_center_data
from packages.db.models.core import Brand

router = APIRouter()


@router.get("/{brand_id}/command-center")
async def command_center(brand_id: uuid.UUID, current_user: CurrentUser, db: DBSession):
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand or brand.organization_id != current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brand not accessible")
    try:
        return await get_command_center_data(db, brand_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error processing request")

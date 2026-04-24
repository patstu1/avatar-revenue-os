"""Cinema Studio endpoints — projects, scenes, characters, styles, generations."""

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from apps.api.deps import CurrentUser, DBSession, OperatorUser, require_brand_access
from apps.api.schemas.cinema_studio import (
    CharacterBibleCreate,
    CharacterBibleResponse,
    CharacterBibleUpdate,
    GenerationTrigger,
    StudioDashboardStats,
    StudioGenerationResponse,
    StudioProjectCreate,
    StudioProjectResponse,
    StudioProjectUpdate,
    StudioSceneCreate,
    StudioSceneResponse,
    StudioSceneUpdate,
    StylePresetCreate,
    StylePresetResponse,
    StylePresetUpdate,
)
from apps.api.services import cinema_studio_service as svc
from apps.api.services.audit_service import log_action

router = APIRouter()


def _raise_for_svc_error(e: ValueError) -> None:
    """Map service exceptions to correct HTTP status codes."""
    if isinstance(e, svc.NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, svc.AccessDeniedError):
        raise HTTPException(status_code=403, detail=str(e))
    raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/studio/projects", response_model=list[StudioProjectResponse])
async def list_projects(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_projects(db, brand_id, status=status, page=page)


@router.post("/{brand_id}/studio/projects", response_model=StudioProjectResponse, status_code=201)
async def create_project(
    brand_id: uuid.UUID,
    body: StudioProjectCreate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    project = await svc.create_project(db, brand_id, **body.model_dump())
    await log_action(
        db,
        "studio_project.created",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_project",
        entity_id=project.id,
    )
    return project


@router.get("/{brand_id}/studio/projects/{project_id}", response_model=StudioProjectResponse)
async def get_project(
    brand_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        return await svc.get_project(db, project_id, brand_id=brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)


@router.put("/{brand_id}/studio/projects/{project_id}", response_model=StudioProjectResponse)
async def update_project(
    brand_id: uuid.UUID,
    project_id: uuid.UUID,
    body: StudioProjectUpdate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        project = await svc.update_project(db, project_id, brand_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_project.updated",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_project",
        entity_id=project.id,
    )
    return project


@router.delete("/{brand_id}/studio/projects/{project_id}", status_code=204)
async def delete_project(
    brand_id: uuid.UUID,
    project_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        await svc.delete_project(db, project_id, brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_project.deleted",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_project",
        entity_id=project_id,
    )


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/studio/scenes", response_model=list[StudioSceneResponse])
async def list_scenes(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    project_id: Optional[uuid.UUID] = None,
    page: int = Query(1, ge=1),
):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_scenes(db, brand_id, project_id=project_id, page=page)


@router.post("/{brand_id}/studio/scenes", response_model=StudioSceneResponse, status_code=201)
async def create_scene(
    brand_id: uuid.UUID,
    body: StudioSceneCreate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    scene = await svc.create_scene(db, brand_id, **body.model_dump())
    await log_action(
        db,
        "studio_scene.created",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_scene",
        entity_id=scene.id,
    )
    return scene


@router.get("/{brand_id}/studio/scenes/{scene_id}", response_model=StudioSceneResponse)
async def get_scene(
    brand_id: uuid.UUID,
    scene_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        return await svc.get_scene(db, scene_id, brand_id=brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)


@router.put("/{brand_id}/studio/scenes/{scene_id}", response_model=StudioSceneResponse)
async def update_scene(
    brand_id: uuid.UUID,
    scene_id: uuid.UUID,
    body: StudioSceneUpdate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        scene = await svc.update_scene(db, scene_id, brand_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_scene.updated",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_scene",
        entity_id=scene.id,
    )
    return scene


@router.delete("/{brand_id}/studio/scenes/{scene_id}", status_code=204)
async def delete_scene(
    brand_id: uuid.UUID,
    scene_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        await svc.delete_scene(db, scene_id, brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_scene.deleted",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_scene",
        entity_id=scene_id,
    )


@router.post(
    "/{brand_id}/studio/scenes/{scene_id}/generate",
    response_model=StudioGenerationResponse,
    status_code=201,
)
async def generate_from_scene(
    brand_id: uuid.UUID,
    scene_id: uuid.UUID,
    body: GenerationTrigger,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        gen = await svc.trigger_generation(
            db,
            brand_id,
            scene_id,
            model=body.model,
            seed=body.seed,
            steps=body.steps,
            guidance=body.guidance,
        )
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except svc.AccessDeniedError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await log_action(
        db,
        "studio_generation.triggered",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="studio_generation",
        entity_id=gen.id,
    )
    return gen


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/studio/characters", response_model=list[CharacterBibleResponse])
async def list_characters(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_characters(db, brand_id, page=page)


@router.post("/{brand_id}/studio/characters", response_model=CharacterBibleResponse, status_code=201)
async def create_character(
    brand_id: uuid.UUID,
    body: CharacterBibleCreate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    char = await svc.create_character(db, brand_id, **body.model_dump())
    await log_action(
        db,
        "studio_character.created",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="character_bible",
        entity_id=char.id,
    )
    return char


@router.get("/{brand_id}/studio/characters/{character_id}", response_model=CharacterBibleResponse)
async def get_character(
    brand_id: uuid.UUID,
    character_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        return await svc.get_character(db, character_id, brand_id=brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)


@router.put("/{brand_id}/studio/characters/{character_id}", response_model=CharacterBibleResponse)
async def update_character(
    brand_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterBibleUpdate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        char = await svc.update_character(db, character_id, brand_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_character.updated",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="character_bible",
        entity_id=char.id,
    )
    return char


@router.delete("/{brand_id}/studio/characters/{character_id}", status_code=204)
async def delete_character(
    brand_id: uuid.UUID,
    character_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        await svc.delete_character(db, character_id, brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_character.deleted",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="character_bible",
        entity_id=character_id,
    )


# ---------------------------------------------------------------------------
# Style Presets
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/studio/styles", response_model=list[StylePresetResponse])
async def list_styles(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    category: Optional[str] = None,
):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_styles(db, brand_id, category=category)


@router.post("/{brand_id}/studio/styles", response_model=StylePresetResponse, status_code=201)
async def create_style(
    brand_id: uuid.UUID,
    body: StylePresetCreate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    style = await svc.create_style(db, brand_id, **body.model_dump())
    await log_action(
        db,
        "studio_style.created",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="style_preset",
        entity_id=style.id,
    )
    return style


@router.put("/{brand_id}/studio/styles/{style_id}", response_model=StylePresetResponse)
async def update_style(
    brand_id: uuid.UUID,
    style_id: uuid.UUID,
    body: StylePresetUpdate,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        style = await svc.update_style(db, style_id, brand_id, **body.model_dump(exclude_unset=True))
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_style.updated",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="style_preset",
        entity_id=style.id,
    )
    return style


@router.delete("/{brand_id}/studio/styles/{style_id}", status_code=204)
async def delete_style(
    brand_id: uuid.UUID,
    style_id: uuid.UUID,
    current_user: OperatorUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        await svc.delete_style(db, style_id, brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)
    await log_action(
        db,
        "studio_style.deleted",
        organization_id=current_user.organization_id,
        brand_id=brand_id,
        user_id=current_user.id,
        actor_type="human",
        entity_type="style_preset",
        entity_id=style_id,
    )


# ---------------------------------------------------------------------------
# Generations
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/studio/generations", response_model=list[StudioGenerationResponse])
async def list_generations(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    scene_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    await require_brand_access(brand_id, current_user, db)
    return await svc.list_generations(db, brand_id, scene_id=scene_id, status=status, page=page)


@router.get("/{brand_id}/studio/generations/{generation_id}", response_model=StudioGenerationResponse)
async def get_generation(
    brand_id: uuid.UUID,
    generation_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    try:
        return await svc.get_generation(db, generation_id, brand_id=brand_id)
    except ValueError as e:
        _raise_for_svc_error(e)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@router.get("/{brand_id}/studio/dashboard-stats", response_model=StudioDashboardStats)
async def studio_dashboard(
    brand_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    await require_brand_access(brand_id, current_user, db)
    return await svc.dashboard_stats(db, brand_id)

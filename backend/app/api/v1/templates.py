"""Server Template Catalog API endpoints.

Provides CRUD operations for server templates that pre-fill the
multi-step server builder wizard with sensible defaults.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.template import ServerTemplate
from app.schemas.template import (
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=TemplateListResponse)
async def list_templates(
    include_inactive: bool = Query(
        False, description="Include inactive templates (admin use)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List server templates, sorted by sort_order then name.

    By default only active templates are returned. Pass
    ``include_inactive=true`` to include deactivated templates
    (intended for admin views).
    """
    query = select(ServerTemplate)
    count_query = select(func.count(ServerTemplate.id))

    if not include_inactive:
        query = query.where(ServerTemplate.is_active.is_(True))
        count_query = count_query.where(ServerTemplate.is_active.is_(True))

    query = (
        query.order_by(ServerTemplate.sort_order, ServerTemplate.name)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    templates = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return TemplateListResponse(templates=templates, total=total)


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single server template by ID."""
    result = await db.execute(
        select(ServerTemplate).where(ServerTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    return template


@router.post("/", response_model=TemplateResponse, status_code=201)
async def create_template(
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new server template.

    .. note:: This endpoint will be restricted to admins once RBAC is wired up.
    """
    # Check for duplicate name
    existing = await db.execute(
        select(ServerTemplate).where(ServerTemplate.name == payload.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A template with name '{payload.name}' already exists",
        )

    template = ServerTemplate(
        id=uuid.uuid4(),
        **payload.model_dump(),
    )

    db.add(template)
    await db.flush()
    await db.refresh(template)

    logger.info("Created template: %s (%s)", template.name, template.id)
    return template


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing template (partial update).

    Only fields included in the request body are modified.

    .. note:: This endpoint will be restricted to admins once RBAC is wired up.
    """
    result = await db.execute(
        select(ServerTemplate).where(ServerTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If renaming, check for conflicts
    if "name" in update_data and update_data["name"] != template.name:
        existing = await db.execute(
            select(ServerTemplate).where(
                ServerTemplate.name == update_data["name"]
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"A template with name '{update_data['name']}' already exists",
            )

    for field, value in update_data.items():
        setattr(template, field, value)

    await db.flush()
    await db.refresh(template)

    logger.info("Updated template: %s (%s)", template.name, template.id)
    return template


@router.delete("/{template_id}", response_model=TemplateResponse)
async def delete_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a template by setting is_active to False.

    The template remains in the database for historical reference but
    will no longer appear in the default template listing.

    .. note:: This endpoint will be restricted to admins once RBAC is wired up.
    """
    result = await db.execute(
        select(ServerTemplate).where(ServerTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    if not template.is_active:
        raise HTTPException(
            status_code=400,
            detail="Template is already inactive",
        )

    template.is_active = False
    await db.flush()
    await db.refresh(template)

    logger.info("Soft-deleted template: %s (%s)", template.name, template.id)
    return template

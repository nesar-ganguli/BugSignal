from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.schemas.project_schema import ProjectCreate, ProjectListResponse, ProjectRead
from app.services.tenant_service import (
    TenantContext,
    require_admin_context,
    require_tenant_context,
)


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_tenant_context),
) -> ProjectListResponse:
    projects = db.scalars(
        select(Project)
        .where(Project.organization_id == tenant.organization_id)
        .order_by(Project.name.asc(), Project.id.asc())
    ).all()
    return ProjectListResponse(
        items=[
            ProjectRead(
                id=project.id,
                organization_id=project.organization_id,
                name=project.name,
                slug=project.slug,
                role=tenant.role,
            )
            for project in projects
        ]
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(require_admin_context),
) -> ProjectRead:
    project = Project(
        organization_id=tenant.organization_id,
        name=request.name.strip(),
        slug=request.slug,
    )
    db.add(project)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A project with this slug already exists.") from exc
    db.refresh(project)
    return ProjectRead(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        role=tenant.role,
    )

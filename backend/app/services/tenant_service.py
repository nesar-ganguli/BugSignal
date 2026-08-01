from dataclasses import dataclass
from datetime import datetime

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Organization, OrganizationMembership, Project, User
from app.services.auth_service import AuthPrincipal, require_principal


@dataclass(frozen=True)
class TenantContext:
    user_id: int
    organization_id: int
    project_id: int
    role: str


def require_tenant_context(
    principal: AuthPrincipal = Depends(require_principal),
    db: Session = Depends(get_db),
    x_project_id: int | None = Header(default=None, alias="X-Project-ID"),
) -> TenantContext:
    user = db.scalar(
        select(User).where(User.issuer == principal.issuer, User.subject == principal.subject)
    )
    if user is None:
        user = User(
            issuer=principal.issuer,
            subject=principal.subject,
            email=principal.email,
            display_name=principal.display_name,
        )
        db.add(user)
        db.flush()
    else:
        user.email = principal.email or user.email
        user.display_name = principal.display_name or user.display_name
        user.updated_at = datetime.utcnow()

    organization = db.scalar(
        select(Organization).where(
            Organization.external_id == principal.organization_external_id
        )
    )
    organization_created = organization is None
    if organization is None:
        organization = Organization(
            external_id=principal.organization_external_id,
            name=principal.organization_external_id,
        )
        db.add(organization)
        db.flush()

    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == user.id,
        )
    )
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="owner" if organization_created else _principal_role(principal),
        )
        db.add(membership)
        db.flush()

    project = None
    if x_project_id is not None:
        project = db.scalar(
            select(Project).where(
                Project.id == x_project_id,
                Project.organization_id == organization.id,
            )
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found.")
    else:
        project = db.scalar(
            select(Project)
            .where(Project.organization_id == organization.id)
            .order_by(Project.id.asc())
            .limit(1)
        )
        if project is None:
            project = Project(
                organization_id=organization.id,
                name="Default Project",
                slug="default",
            )
            db.add(project)
            db.flush()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tenant provisioning conflict. Retry request.")
    return TenantContext(user.id, organization.id, project.id, membership.role)


def _principal_role(principal: AuthPrincipal) -> str:
    for role in ("owner", "admin", "member", "viewer"):
        if role in principal.roles:
            return role
    return "member"


def require_editor_context(
    tenant: TenantContext = Depends(require_tenant_context),
) -> TenantContext:
    if tenant.role not in {"owner", "admin", "member"}:
        raise HTTPException(status_code=403, detail="Project write access is required.")
    return tenant


def require_admin_context(
    tenant: TenantContext = Depends(require_tenant_context),
) -> TenantContext:
    if tenant.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Organization administrator access is required.")
    return tenant

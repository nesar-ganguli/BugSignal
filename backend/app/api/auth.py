from fastapi import APIRouter, Depends

from app.schemas.auth_schema import CurrentUserResponse
from app.services.auth_service import AuthPrincipal, require_principal
from app.services.tenant_service import TenantContext, require_tenant_context


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(
    principal: AuthPrincipal = Depends(require_principal),
    tenant: TenantContext = Depends(require_tenant_context),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        subject=principal.subject,
        email=principal.email,
        display_name=principal.display_name,
        organization_external_id=principal.organization_external_id,
        roles=list(principal.roles),
        user_id=tenant.user_id,
        organization_id=tenant.organization_id,
        project_id=tenant.project_id,
        project_role=tenant.role,
    )

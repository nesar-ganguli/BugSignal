from fastapi import APIRouter, Depends

from app.schemas.auth_schema import CurrentUserResponse
from app.services.auth_service import AuthPrincipal, require_principal


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(
    principal: AuthPrincipal = Depends(require_principal),
) -> CurrentUserResponse:
    return CurrentUserResponse(
        subject=principal.subject,
        email=principal.email,
        display_name=principal.display_name,
        organization_external_id=principal.organization_external_id,
        roles=list(principal.roles),
    )

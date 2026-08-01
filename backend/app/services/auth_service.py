from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthPrincipal:
    issuer: str
    subject: str
    email: str | None
    display_name: str | None
    organization_external_id: str
    roles: tuple[str, ...]
    claims: dict[str, Any]


def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> AuthPrincipal:
    if not settings.oidc_enabled:
        return AuthPrincipal(
            issuer="bugsignal-development",
            subject="local-developer",
            email="developer@localhost",
            display_name="Local Developer",
            organization_external_id="local-development",
            roles=("owner",),
            claims={},
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("A bearer access token is required.")
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(status_code=503, detail="OIDC is enabled but not fully configured.")

    try:
        signing_key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(
            credentials.credentials
        )
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=[value.strip() for value in settings.oidc_algorithms.split(",")],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("The access token is invalid or expired.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise _unauthorized("The access token has no valid subject.")
    organization = claims.get(settings.oidc_organization_claim) or f"personal:{subject}"
    roles_claim = claims.get(settings.oidc_roles_claim, [])
    roles = tuple(roles_claim) if isinstance(roles_claim, list) else ()
    return AuthPrincipal(
        issuer=settings.oidc_issuer,
        subject=subject,
        email=_optional_string(claims.get("email")),
        display_name=_optional_string(claims.get("name")),
        organization_external_id=str(organization),
        roles=roles,
        claims=claims,
    )


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

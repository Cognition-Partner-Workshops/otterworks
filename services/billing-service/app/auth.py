from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

AUDIENCE = "otterworks-billing"
SERVICE_SCOPE = "billing:service"

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: UUID | None
    is_service: bool

    def may_act_for(self, tenant_id: UUID) -> bool:
        return self.is_service or self.tenant_id == tenant_id


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="a valid bearer token is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def authenticate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None:
        raise _unauthenticated()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.auth_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
        tenant_id = UUID(claims["tenant_id"]) if "tenant_id" in claims else None
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError) as error:
        raise _unauthenticated() from error
    scopes = str(claims.get("scope", "")).split()
    return Principal(str(claims["sub"]), tenant_id, SERVICE_SCOPE in scopes)


def authorize_tenant(
    tenant_id: Annotated[UUID, Path()],
    principal: Annotated[Principal, Depends(authenticate)],
) -> Principal:
    if not principal.may_act_for(tenant_id):
        raise HTTPException(status_code=403, detail="caller may not act for this tenant")
    return principal


def require_service(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    if not principal.is_service:
        raise HTTPException(status_code=403, detail="service scope is required")
    return principal

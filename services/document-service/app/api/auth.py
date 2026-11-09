"""Caller identity for the document API.

Identity comes from the Authorization JWT. When no ``JWT_SECRET`` is configured
the service trusts the ``X-User-ID`` header forwarded by api-gateway instead.
"""

import os
from uuid import UUID

import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.services.document_service import DocumentAccessError


def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "")


def extract_user_id(request: Request) -> UUID | None:
    """Extract user ID from the Authorization JWT."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :]
        secret = get_jwt_secret()
        if secret:
            try:
                payload = jwt.decode(token, secret, algorithms=["HS256", "HS384"])
                user_id_str = payload.get("user_id") or payload.get("sub")
                if user_id_str:
                    return UUID(str(user_id_str))
            except (jwt.PyJWTError, ValueError):
                pass
        else:
            forwarded_user_id = request.headers.get("X-User-ID")
            if forwarded_user_id:
                try:
                    return UUID(str(forwarded_user_id))
                except ValueError:
                    pass

    return None


def require_user_id(request: Request) -> UUID:
    """FastAPI dependency: the authenticated user, or 401."""
    user_id = extract_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def document_access_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DocumentAccessError):
        raise exc
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

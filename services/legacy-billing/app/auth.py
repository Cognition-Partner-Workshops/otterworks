import os
import uuid
from dataclasses import dataclass
from functools import wraps

import jwt
from flask import abort, g, jsonify, request

AUDIENCE = "otterworks-billing"
SERVICE_SCOPE = "billing:service"
MIN_SECRET_LENGTH = 32
OPEN_ENDPOINTS = frozenset({"health"})


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: uuid.UUID | None
    is_service: bool

    def may_act_for(self, tenant_id):
        if self.is_service:
            return True
        try:
            return self.tenant_id is not None and self.tenant_id == uuid.UUID(str(tenant_id))
        except ValueError:
            return False


def signing_secret():
    secret = os.getenv("BILLING_AUTH_SECRET", "")
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"BILLING_AUTH_SECRET must be set to at least {MIN_SECRET_LENGTH} characters"
        )
    return secret


def _unauthenticated():
    response = jsonify(detail="a valid bearer token is required")
    response.status_code = 401
    response.headers["WWW-Authenticate"] = "Bearer"
    return response


def _principal(secret):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=AUDIENCE,
            options={"require": ["exp", "sub", "aud"]},
        )
        tenant_id = uuid.UUID(claims["tenant_id"]) if "tenant_id" in claims else None
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        return None
    scopes = str(claims.get("scope", "")).split()
    return Principal(str(claims["sub"]), tenant_id, SERVICE_SCOPE in scopes)


def authorize_tenant(tenant_id):
    if not g.principal.may_act_for(tenant_id):
        abort(403, description="caller may not act for this tenant")


def service_only(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.principal.is_service:
            abort(403, description="service scope is required")
        return view(*args, **kwargs)

    return wrapper


def init_auth(app):
    secret = signing_secret()

    @app.before_request
    def authenticate():
        if request.endpoint in OPEN_ENDPOINTS:
            return None
        g.principal = _principal(secret)
        if g.principal is None:
            return _unauthenticated()
        if "tenant_id" in (request.view_args or {}):
            authorize_tenant(request.view_args["tenant_id"])
        return None

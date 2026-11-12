from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).parents[1] / "app"))
os.environ.setdefault("BILLING_AUTH_SECRET", "unit-test-signing-key-not-used-anywhere-else")

AUDIENCE = "otterworks-billing"
SERVICE_SCOPE = "billing:service"


def bearer(*, tenant=None, service=False, secret=None, **overrides):
    now = datetime.now(UTC)
    claims = {"sub": "pytest", "aud": AUDIENCE, "iat": now, "exp": now + timedelta(minutes=5)}
    if tenant is not None:
        claims["tenant_id"] = str(tenant)
    if service:
        claims["scope"] = SERVICE_SCOPE
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    token = jwt.encode(claims, secret or os.environ["BILLING_AUTH_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

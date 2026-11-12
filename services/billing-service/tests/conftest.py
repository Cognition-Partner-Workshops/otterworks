from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))
os.environ.setdefault(
    "BILLING_SVC_DATABASE_URL",
    "postgresql://billing_svc:billing_svc@localhost:56432/billing_svc_dev",
)
os.environ.setdefault("BILLING_SVC_AUTH_SECRET", "unit-test-signing-key-not-used-anywhere-else")

from datetime import UTC, datetime, timedelta  # noqa: E402
from uuid import UUID  # noqa: E402

import jwt  # noqa: E402

AUDIENCE = "otterworks-billing"
SERVICE_SCOPE = "billing:service"


def bearer(
    *,
    tenant: UUID | None = None,
    service: bool = False,
    secret: str | None = None,
    **overrides: object,
) -> dict[str, str]:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": "pytest",
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    if tenant is not None:
        claims["tenant_id"] = str(tenant)
    if service:
        claims["scope"] = SERVICE_SCOPE
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    token = jwt.encode(claims, secret or os.environ["BILLING_SVC_AUTH_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}

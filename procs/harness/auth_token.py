from __future__ import annotations

import argparse
import os
import sys
import time
import uuid

import jwt

AUDIENCE = "otterworks-billing"
SERVICE_SCOPE = "billing:service"
MIN_SECRET_LENGTH = 32
SECRET_ENV = "PROCS_AUTH_SECRET"


class AuthConfigError(ValueError):
    pass


def mint(
    secret: str,
    *,
    tenant_id: str | None = None,
    service: bool = False,
    ttl_seconds: int = 300,
    subject: str = "procs-harness",
) -> str:
    if len(secret) < MIN_SECRET_LENGTH:
        raise AuthConfigError(
            f"{SECRET_ENV} must be set to the stack's signing secret "
            f"(at least {MIN_SECRET_LENGTH} characters); make procs-up NS=<ns> generates it"
        )
    if service == (tenant_id is not None):
        raise AuthConfigError("a token names either one tenant or the service scope")
    now = int(time.time())
    claims: dict[str, object] = {
        "sub": subject,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    if service:
        claims["scope"] = SERVICE_SCOPE
    else:
        try:
            claims["tenant_id"] = str(uuid.UUID(str(tenant_id)))
        except ValueError as error:
            raise AuthConfigError(f"tenant id {tenant_id!r} is not a UUID") from error
    return jwt.encode(claims, secret, algorithm="HS256")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a bearer token for the procs billing stack")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--tenant", help="tenant UUID the token may act for")
    scope.add_argument("--service", action="store_true", help="token may act for every tenant")
    parser.add_argument("--ttl", type=int, default=3600, help="lifetime in seconds")
    args = parser.parse_args()
    try:
        token = mint(
            os.getenv(SECRET_ENV, ""),
            tenant_id=args.tenant,
            service=args.service,
            ttl_seconds=args.ttl,
            subject="procs-token",
        )
    except AuthConfigError as error:
        print(error, file=sys.stderr)
        return 2
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""JWT helpers shared by the API tests."""

import uuid

import jwt

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-pad32"  # noqa: S105


def make_jwt(user_id: str | uuid.UUID, roles: list[str] | None = None) -> str:
    claims: dict[str, object] = {"user_id": str(user_id)}
    if roles is not None:
        claims["roles"] = roles
    return jwt.encode(claims, TEST_JWT_SECRET, algorithm="HS256")


def auth_headers(user_id: str | uuid.UUID, roles: list[str] | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_jwt(user_id, roles)}"}

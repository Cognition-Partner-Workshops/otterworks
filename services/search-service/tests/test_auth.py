"""The backend must authenticate callers even when they bypass the gateway."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import jwt
import pytest
from flask import jsonify, request

from app.config import AuthConfig
from app.main import create_app

SECRET = "unit-test-signing-key-not-a-deployment-secret"
PEER_SECRET = "unit-test-peer-signing-key-not-a-deployment-secret"
SERVICE_TOKEN = "unit-test-internal-service-token"
USER_ID = str(uuid4())


@pytest.fixture()
def auth_client(app_config, mock_meilisearch_client):
    config = replace(app_config, auth=AuthConfig(
        jwt_secret=SECRET, jwt_peer_secret=PEER_SECRET, service_token=SERVICE_TOKEN))
    with patch("app.services.meilisearch_client.meilisearch.Client") as mock:
        mock.return_value = mock_meilisearch_client
        app = create_app(config)

        @app.get("/identity")
        def identity():
            return jsonify(user_id=request.headers.get("X-User-ID"))

        yield app.test_client()


def access_token(**overrides):
    claims = {"sub": USER_ID, "type": "access",
              "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS384")


@pytest.mark.parametrize("headers", [{}, {"X-User-ID": USER_ID},
                                    {"Authorization": "Bearer garbage", "X-User-ID": USER_ID}])
def test_rejects_unsigned_identity(auth_client, headers):
    assert auth_client.get("/api/v1/search/?q=test", headers=headers).status_code == 401


def test_signed_subject_overrides_spoofed_header(auth_client):
    response = auth_client.get("/identity", headers={
        "Authorization": f"Bearer {access_token()}", "X-User-ID": str(uuid4())})
    assert response.status_code == 200
    assert response.json["user_id"] == USER_ID


@pytest.mark.parametrize("overrides", [
    {"exp": datetime.now(timezone.utc) - timedelta(hours=1)},
    {"type": "refresh"}, {"sub": "not-a-uuid"},
])
def test_rejects_invalid_claims(auth_client, overrides):
    assert auth_client.get("/identity", headers={
        "Authorization": f"Bearer {access_token(**overrides)}"}).status_code == 401


def test_rejects_wrong_signature(auth_client):
    token = jwt.encode({"sub": USER_ID, "type": "access", "exp": 4102444800},
                       "a-different-signing-key", algorithm="HS256")
    assert auth_client.get("/identity", headers={
        "Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("claims", [
    {"sub": USER_ID, "type": "access"},
    {"exp": 4102444800, "type": "access"},
])
def test_rejects_missing_required_claims(auth_client, claims):
    token = jwt.encode(claims, SECRET, algorithm="HS256")
    assert auth_client.get("/identity", headers={
        "Authorization": f"Bearer {token}"}).status_code == 401


def test_preserves_peer_and_internal_service_auth(auth_client):
    token = jwt.encode({"sub": USER_ID, "type": "access", "exp": 4102444800},
                       PEER_SECRET, algorithm="HS512")
    assert auth_client.get("/identity", headers={
        "Authorization": f"Bearer {token}"}).json["user_id"] == USER_ID
    assert auth_client.get("/identity", headers={
        "Authorization": f"Bearer {SERVICE_TOKEN}"}).status_code == 200


def test_health_and_metrics_stay_internal_scrapable(auth_client):
    assert auth_client.get("/health/live").status_code != 401
    assert auth_client.get("/metrics").status_code == 200
    assert auth_client.get("/metrics-evil").status_code == 401

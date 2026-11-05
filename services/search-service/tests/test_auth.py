from dataclasses import replace
from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.config import AuthConfig
from app.main import create_app

SECRET = "search-jwt-test-secret"
USER = "00000000-0000-4000-8000-000000000101"


@pytest.fixture()
def secured(app_config):
    config = replace(app_config, auth=AuthConfig(jwt_secret=SECRET, jwt_peer_secret="peer-secret", service_token="", require_auth=True))
    with patch("app.main.MeiliSearchService"):
        app = create_app(config)
    app.config["SEARCH_SERVICE"].search.return_value.to_dict.return_value = {}
    app.config["SEARCH_SERVICE"].advanced_search.return_value.to_dict.return_value = {}
    return app


def headers(claims=None, secret=SECRET, algorithm="HS256", **extra):
    token = jwt.encode({"sub": USER} if claims is None else claims, secret, algorithm=algorithm)
    return {"Authorization": f"Bearer {token}", **extra}


@pytest.mark.parametrize("path,method", [("/?q=test", "get"), ("/advanced", "post")])
def test_verified_identity_scopes_search(secured, path, method):
    client = secured.test_client()
    url = "/api/v1/search" + path
    call = getattr(client, method)
    body = {"json": {"q": "test"}} if method == "post" else {}
    assert call(url, headers={"X-User-ID": USER}, **body).status_code == 401
    assert call(url, headers=headers(**{"X-User-ID": "forged"}), **body).status_code == 403
    assert call(url, headers=headers(**{"X-User-ID": USER}), **body).status_code == 200
    service = secured.config["SEARCH_SERVICE"]
    search = service.search if method == "get" else service.advanced_search
    assert search.call_count == 1
    assert search.call_args.kwargs["owner_id"] == USER


@pytest.mark.parametrize("claims,secret,algorithm", [
    ({"sub": USER}, SECRET, "HS256"),
    ({"sub": USER}, SECRET, "HS384"),
    ({"sub": USER}, "peer-secret", "HS512"),
    ({"user_id": USER}, SECRET, "HS256"),
    ({"sub": USER, "user_id": "other"}, SECRET, "HS256"),
    ({"sub": "", "user_id": USER}, SECRET, "HS256"),
    ({"sub": USER, "aud": "otterworks", "iat": 4102444800}, SECRET, "HS256"),
])
def test_gateway_compatible_claims_and_keys(secured, claims, secret, algorithm):
    response = secured.test_client().get("/api/v1/search/?q=test", headers=headers(claims, secret, algorithm))
    assert response.status_code == 200
    assert secured.config["SEARCH_SERVICE"].search.call_args.kwargs["owner_id"] == USER


@pytest.mark.parametrize("credential", [
    {},
    {"Authorization": "Bearer malformed"},
    headers(secret="wrong-secret"),
    headers(claims={}),
    headers(claims={"sub": ""}),
    headers(claims={"sub": USER, "exp": 1}),
    headers(claims={"sub": USER, "nbf": 4102444800}),
    headers(algorithm="none", secret=None),
])
def test_invalid_credentials_fail_closed(secured, credential):
    response = secured.test_client().get("/api/v1/search/?q=test", headers=credential)
    assert response.status_code == 401
    secured.config["SEARCH_SERVICE"].search.assert_not_called()


def test_empty_keys_do_not_validate_tokens(app_config):
    config = replace(app_config, auth=AuthConfig(jwt_secret="", jwt_peer_secret="", service_token="", require_auth=True))
    with patch("app.main.MeiliSearchService"):
        app = create_app(config)
    assert app.test_client().get("/api/v1/search/?q=test", headers=headers()).status_code == 401


def test_unverified_header_is_ignored_even_with_auth_disabled(app):
    app.config["SEARCH_SERVICE"] = MagicMock()
    app.config["SEARCH_SERVICE"].search.return_value.to_dict.return_value = {}
    response = app.test_client().get("/api/v1/search/?q=test", headers={"X-User-ID": "forged"})
    assert response.status_code == 200
    assert app.config["SEARCH_SERVICE"].search.call_args.kwargs["owner_id"] is None

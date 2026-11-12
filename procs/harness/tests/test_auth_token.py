from __future__ import annotations

import http.server
import sys
import threading
from pathlib import Path

import jwt
import pytest

sys.path.insert(0, str(Path(__file__).parents[3]))

import procs.harness.replay as replay
from procs.harness.auth_token import AUDIENCE, SERVICE_SCOPE, AuthConfigError, mint

SECRET = "unit-test-signing-key-not-used-anywhere-else"
TENANT = "00000000-0000-0000-0000-000000000001"


def decode(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"], audience=AUDIENCE)


def test_service_token_carries_the_service_scope_and_expires() -> None:
    claims = decode(mint(SECRET, service=True, ttl_seconds=60))

    assert claims["scope"] == SERVICE_SCOPE
    assert "tenant_id" not in claims
    assert claims["exp"] - claims["iat"] == 60


def test_tenant_token_is_scoped_to_one_tenant() -> None:
    claims = decode(mint(SECRET, tenant_id=TENANT))

    assert claims["tenant_id"] == TENANT
    assert "scope" not in claims


@pytest.mark.parametrize("secret", ["", "too-short"])
def test_missing_or_short_secret_is_refused(secret) -> None:
    with pytest.raises(AuthConfigError):
        mint(secret, service=True)


def test_token_must_name_a_tenant_or_the_service_scope() -> None:
    with pytest.raises(AuthConfigError):
        mint(SECRET)
    with pytest.raises(AuthConfigError):
        mint(SECRET, tenant_id="not-a-uuid")


@pytest.fixture
def target():
    seen: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            seen.append(self.headers.get("Authorization"))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            return None

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", seen
    server.shutdown()
    server.server_close()


def test_replay_requests_carry_a_service_token(target) -> None:
    base_url, seen = target

    assert replay.reset_target(base_url) == (True, "")
    scheme, token = seen[0].split(" ")
    assert scheme == "Bearer"
    assert decode(token)["scope"] == SERVICE_SCOPE


def test_replay_stops_before_any_request_without_a_signing_secret(monkeypatch, target, capsys) -> None:
    base_url, seen = target
    monkeypatch.delenv("PROCS_AUTH_SECRET", raising=False)
    monkeypatch.setattr("sys.argv", ["replay.py", "--base-url", base_url])

    assert replay.main() == replay.AUTH_MISSING
    assert "PROCS_AUTH_SECRET" in capsys.readouterr().err
    assert seen == []


@pytest.mark.parametrize("status", [401, 403])
def test_reset_refused_for_credentials_names_the_secret(monkeypatch, status) -> None:
    monkeypatch.setattr(replay, "request_json", lambda *_args: (status, {"detail": "denied"}))

    ok, message = replay.reset_target("http://target")

    assert not ok
    assert "PROCS_AUTH_SECRET" in message

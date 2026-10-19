"""Incident scenarios at the unit level: chaos flags gate the incident code paths.

`cache-leak` (chaos:document-service:render_cache) and the `slow_queries` chaos
flag are exercised through the real FastAPI app with an in-memory database.
"""

import secrets
import uuid

import jwt
import pytest
from httpx import AsyncClient

from app import chaos
from app.api import documents as documents_api
from app.services.render_cache import render_cache
from app.telemetry import RENDER_CACHE_ENTRIES, SERVICE


@pytest.fixture
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = secrets.token_hex(32)
    monkeypatch.setenv("JWT_SECRET", secret)
    return secret


@pytest.fixture(autouse=True)
def empty_render_cache():
    render_cache.clear()
    yield
    render_cache.clear()


def _headers(secret: str, user_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode({"sub": str(user_id), "user_id": str(user_id)}, secret, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _flags_on(monkeypatch: pytest.MonkeyPatch, *keys: str) -> None:
    monkeypatch.setattr(documents_api, "flag_active", lambda key: key in keys)


async def _create(client: AsyncClient, headers: dict[str, str], title: str = "Leak") -> str:
    resp = await client.post(
        "/api/v1/documents/", headers=headers, json={"title": title, "content": "body " * 50}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _cache_gauge() -> float:
    return RENDER_CACHE_ENTRIES.labels(SERVICE)._value.get()


def test_scenario_flag_keys_are_namespaced_per_service() -> None:
    assert chaos.FLAG_RENDER_CACHE == "chaos:document-service:render_cache"
    assert chaos.FLAG_REQUEST_LOG == "chaos:document-service:request_log"
    assert chaos.FLAG_SLOW_QUERIES.startswith("chaos:document-service:")


@pytest.mark.asyncio
async def test_export_bypasses_render_cache_when_flag_off(
    client: AsyncClient, jwt_secret: str
) -> None:
    headers = _headers(jwt_secret, uuid.uuid4())
    doc_id = await _create(client, headers)
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export", params={"format": "html"}, headers=headers
    )
    assert resp.status_code == 200
    assert len(render_cache) == 0


@pytest.mark.asyncio
async def test_export_populates_and_serves_render_cache_when_flag_on(
    client: AsyncClient, jwt_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _flags_on(monkeypatch, chaos.FLAG_RENDER_CACHE)
    headers = _headers(jwt_secret, uuid.uuid4())
    doc_id = await _create(client, headers)
    url = f"/api/v1/documents/{doc_id}/export"
    first = await client.get(url, params={"format": "html"}, headers=headers)
    second = await client.get(url, params={"format": "html"}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.text == second.text
    assert len(render_cache) == 1
    assert _cache_gauge() == 1
    await client.get(url, params={"format": "markdown"}, headers=headers)
    assert len(render_cache) == 2


@pytest.mark.asyncio
async def test_export_cache_is_owner_checked(
    client: AsyncClient, jwt_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _flags_on(monkeypatch, chaos.FLAG_RENDER_CACHE)
    owner = _headers(jwt_secret, uuid.uuid4())
    doc_id = await _create(client, owner)
    url = f"/api/v1/documents/{doc_id}/export"
    assert (await client.get(url, params={"format": "html"}, headers=owner)).status_code == 200
    other = _headers(jwt_secret, uuid.uuid4())
    assert (await client.get(url, params={"format": "html"}, headers=other)).status_code == 403


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    reason="[PLANTED] incident/scenarios.yaml cache-leak: render_cache is unbounded and keeps "
    "one entry (plus the full source) per document version, so edit+export grows RSS "
    "until DocumentServiceMemoryHigh pages",
)
async def test_render_cache_is_bounded_across_versions(
    client: AsyncClient, jwt_secret: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _flags_on(monkeypatch, chaos.FLAG_RENDER_CACHE)
    headers = _headers(jwt_secret, uuid.uuid4())
    doc_id = await _create(client, headers)
    for i in range(10):
        resp = await client.patch(
            f"/api/v1/documents/{doc_id}", headers=headers, json={"content": f"edit {i}"}
        )
        assert resp.status_code == 200, resp.text
        await client.get(
            f"/api/v1/documents/{doc_id}/export", params={"format": "html"}, headers=headers
        )
    assert len(render_cache) <= 1


@pytest.mark.asyncio
async def test_slow_queries_flag_injects_latency_on_list(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(documents_api.asyncio, "sleep", fake_sleep)
    owner_id = uuid.uuid4()
    assert (await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})).status_code
    assert slept == []
    _flags_on(monkeypatch, chaos.FLAG_SLOW_QUERIES)
    await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert len(slept) == 1 and 3.0 <= slept[0] <= 5.0

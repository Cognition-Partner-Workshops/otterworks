"""Document endpoints exercised as an authenticated owner (and as other callers)."""

import uuid

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.api import documents as documents_api
from app.chaos import FLAG_RENDER_CACHE, FLAG_SLOW_QUERIES
from app.services.document_query_repository import DocumentQueryRepository
from app.services.render_cache import render_cache
from app.services.share_link import ShareLinkService

SECRET = "authenticated-api-tests-secret-pad32"  # noqa: S105
BASE = "/api/v1/documents"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", SECRET)


@pytest.fixture(autouse=True)
def empty_render_cache():
    render_cache.clear()
    yield
    render_cache.clear()


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode({"user_id": str(user_id)}, SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def _create(client: AsyncClient, owner_id: uuid.UUID, **fields) -> dict:
    payload = {"title": "Doc", "content": "Body text", "owner_id": str(owner_id)}
    payload.update(fields)
    resp = await client.post(f"{BASE}/", json=payload)
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_owner_can_read_update_patch_and_delete(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, title="Original")
    headers = _auth(owner_id)

    got = await client.get(f"{BASE}/{doc['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["title"] == "Original"

    put = await client.put(
        f"{BASE}/{doc['id']}", json={"title": "Replaced", "content": "a b c"}, headers=headers
    )
    assert put.status_code == 200
    assert put.json()["version"] == 2
    assert put.json()["word_count"] == 3

    patched = await client.patch(
        f"{BASE}/{doc['id']}", json={"content_type": "text/html"}, headers=headers
    )
    assert patched.status_code == 200
    assert patched.json()["content_type"] == "text/html"
    assert patched.json()["title"] == "Replaced"
    assert patched.json()["version"] == 3

    deleted = await client.delete(f"{BASE}/{doc['id']}", headers=headers)
    assert deleted.status_code == 204
    gone = await client.get(f"{BASE}/{doc['id']}", headers=headers)
    assert gone.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PUT", "", {"title": "x"}),
        ("PATCH", "", {"title": "x"}),
        ("DELETE", "", None),
        ("GET", "/versions", None),
        ("POST", "/share", None),
        ("GET", "/export", None),
    ],
)
async def test_non_owner_is_denied(
    client: AsyncClient, owner_id: uuid.UUID, method: str, suffix: str, body: dict | None
):
    doc = await _create(client, owner_id)
    resp = await client.request(
        method, f"{BASE}/{doc['id']}{suffix}", json=body, headers=_auth(uuid.uuid4())
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PUT", "", {"title": "x"}),
        ("PATCH", "", {"title": "x"}),
        ("DELETE", "", None),
        ("GET", "/versions", None),
        ("POST", f"/versions/{uuid.uuid4()}/restore", None),
        ("POST", "/share", None),
        ("GET", "/export", None),
    ],
)
async def test_missing_document_is_404_for_authenticated_caller(
    client: AsyncClient, method: str, suffix: str, body: dict | None
):
    resp = await client.request(
        method, f"{BASE}/{uuid.uuid4()}{suffix}", json=body, headers=_auth(uuid.uuid4())
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_versions_and_restore_as_owner(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, title="First", content="one")
    headers = _auth(owner_id)
    await client.put(
        f"{BASE}/{doc['id']}", json={"title": "Second", "content": "two"}, headers=headers
    )

    versions = await client.get(f"{BASE}/{doc['id']}/versions", headers=headers)
    assert versions.status_code == 200
    numbers = [v["version_number"] for v in versions.json()]
    assert numbers == [1, 2]
    first_id = versions.json()[0]["id"]

    restored = await client.post(f"{BASE}/{doc['id']}/versions/{first_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["title"] == "First"
    assert restored.json()["content"] == "one"
    assert restored.json()["version"] == 3


@pytest.mark.asyncio
async def test_restore_unknown_version_is_404(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.post(
        f"{BASE}/{doc['id']}/versions/{uuid.uuid4()}/restore", headers=_auth(owner_id)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_other_owners_document_is_denied(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.post(
        f"{BASE}/{doc['id']}/versions/{uuid.uuid4()}/restore", headers=_auth(uuid.uuid4())
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fmt", "media_type", "marker"),
    [
        ("html", "text/html", "<h1>Title &amp; more</h1>"),
        ("markdown", "text/markdown", "# Title & more"),
        ("pdf", "application/pdf", "TITLE: Title & more"),
    ],
)
async def test_export_as_owner(
    client: AsyncClient, owner_id: uuid.UUID, fmt: str, media_type: str, marker: str
):
    doc = await _create(client, owner_id, title="Title & more")
    resp = await client.get(
        f"{BASE}/{doc['id']}/export", params={"format": fmt}, headers=_auth(owner_id)
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(media_type)
    assert marker in resp.text


@pytest.mark.asyncio
async def test_export_rejects_unknown_format(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.get(
        f"{BASE}/{doc['id']}/export", params={"format": "docx"}, headers=_auth(owner_id)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_without_render_cache_flag_leaves_cache_empty(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc = await _create(client, owner_id)
    resp = await client.get(f"{BASE}/{doc['id']}/export", headers=_auth(owner_id))
    assert resp.status_code == 200
    assert len(render_cache) == 0


@pytest.mark.asyncio
async def test_export_with_render_cache_flag_reuses_render_until_new_version(
    client: AsyncClient, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(documents_api, "flag_active", lambda key: key == FLAG_RENDER_CACHE)
    doc = await _create(client, owner_id, title="Cached")
    headers = _auth(owner_id)
    url = f"{BASE}/{doc['id']}/export"

    first = await client.get(url, params={"format": "html"}, headers=headers)
    assert first.status_code == 200
    assert len(render_cache) == 1

    def fail_render(*_args, **_kwargs):
        raise AssertionError("a cached export must not be re-rendered")

    with monkeypatch.context() as m:
        m.setattr(documents_api.DocumentService, "export_document", fail_render)
        second = await client.get(url, params={"format": "html"}, headers=headers)
    assert second.status_code == 200
    assert second.text == first.text
    assert second.headers["content-type"] == first.headers["content-type"]

    await client.patch(f"{BASE}/{doc['id']}", json={"title": "Renamed"}, headers=headers)
    third = await client.get(url, params={"format": "html"}, headers=headers)
    assert "<h1>Renamed</h1>" in third.text


@pytest.mark.asyncio
async def test_share_link_mint_requires_auth(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.post(f"{BASE}/{doc['id']}/share")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_shared_link_for_missing_document_is_404(client: AsyncClient):
    doc_id = str(uuid.uuid4())
    token = ShareLinkService().mint_token(doc_id)
    resp = await client.get(f"{BASE}/shared", params={"document_id": doc_id, "token": token})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_invalid_or_wrongly_signed_jwt_is_unauthenticated(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc = await _create(client, owner_id)
    forged = jwt.encode(
        {"user_id": str(owner_id)}, "some-other-secret-value-pad32", algorithm="HS256"
    )
    for header in (f"Bearer {forged}", "Bearer not-a-jwt", "Basic abc"):
        resp = await client.get(f"{BASE}/{doc['id']}", headers={"Authorization": header})
        assert resp.status_code == 401, header


@pytest.mark.asyncio
async def test_jwt_without_user_claim_or_with_bad_uuid_is_unauthenticated(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc = await _create(client, owner_id)
    for claims in ({"role": "user"}, {"sub": "not-a-uuid"}):
        token = jwt.encode(claims, SECRET, algorithm="HS256")
        resp = await client.get(f"{BASE}/{doc['id']}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401, claims


@pytest.mark.asyncio
async def test_forwarded_user_id_is_used_only_without_jwt_secret(
    client: AsyncClient, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
):
    doc = await _create(client, owner_id)
    forwarded = {"Authorization": "Bearer opaque", "X-User-ID": str(owner_id)}

    with_secret = await client.get(f"{BASE}/{doc['id']}", headers=forwarded)
    assert with_secret.status_code == 401

    monkeypatch.delenv("JWT_SECRET")
    without_secret = await client.get(f"{BASE}/{doc['id']}", headers=forwarded)
    assert without_secret.status_code == 200

    bad = await client.get(
        f"{BASE}/{doc['id']}", headers={"Authorization": "Bearer opaque", "X-User-ID": "nope"}
    )
    assert bad.status_code == 401

    no_bearer = await client.get(f"{BASE}/{doc['id']}", headers={"X-User-ID": str(owner_id)})
    assert no_bearer.status_code == 401


@pytest.mark.asyncio
async def test_create_without_trailing_slash(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(BASE, json={"title": "No slash", "owner_id": str(owner_id)})
    assert resp.status_code == 201
    assert resp.json()["title"] == "No slash"


@pytest.mark.asyncio
async def test_list_without_trailing_slash_uses_jwt_owner(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, title="Mine")
    await _create(client, uuid.uuid4(), title="Theirs")

    resp = await client.get(BASE, headers=_auth(owner_id))
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Mine"]


@pytest.mark.asyncio
async def test_filtered_list_without_trailing_slash(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, title="Alpha report")
    await _create(client, owner_id, title="Beta notes")

    resp = await client.get(BASE, params={"title": "report"})
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alpha report"]


@pytest.mark.asyncio
async def test_non_default_sort_alone_takes_the_filter_path(
    client: AsyncClient, owner_id: uuid.UUID
):
    await _create(client, owner_id, title="Bravo")
    await _create(client, owner_id, title="Alpha")

    resp = await client.get(f"{BASE}/", params={"sort": "title", "direction": "asc"})
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alpha", "Bravo"]


@pytest.mark.asyncio
async def test_filter_database_error_is_reported_as_400(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    async def broken_count(self, **_filters):
        raise SQLAlchemyError("boom")

    monkeypatch.setattr(DocumentQueryRepository, "count_documents", broken_count)
    resp = await client.get(f"{BASE}/", params={"title": "anything"})
    assert resp.status_code == 400
    assert resp.json()["detail"].startswith("Invalid filter")


@pytest.mark.asyncio
async def test_search_paginates(client: AsyncClient, owner_id: uuid.UUID):
    for index in range(3):
        await _create(client, owner_id, title=f"Needle {index}")
    await _create(client, owner_id, title="Haystack", content="nothing here")

    resp = await client.get(f"{BASE}/search", params={"q": "needle", "size": 2, "page": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_search_requires_a_query(client: AsyncClient):
    resp = await client.get(f"{BASE}/search")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_slow_queries_flag_injects_latency(
    client: AsyncClient, owner_id: uuid.UUID, monkeypatch: pytest.MonkeyPatch
):
    delays: list[float] = []

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(documents_api, "flag_active", lambda key: key == FLAG_SLOW_QUERIES)
    monkeypatch.setattr(documents_api.asyncio, "sleep", record_sleep)
    monkeypatch.setattr(documents_api.random, "uniform", lambda low, high: 4.0)

    resp = await client.get(f"{BASE}/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 200
    assert delays == [4.0]

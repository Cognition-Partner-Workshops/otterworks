"""QA pyramid (docs area): document lifecycle, templates, comments, versions.

Tests that expose a known defect are marked ``xfail(strict=True)`` with the bug
label so the suite stays green while the defect exists and flips red once fixed.
"""

import secrets
import uuid

import jwt
import pytest
from httpx import AsyncClient

REAL_OWNER_PARAM = "[REAL] list honours ?owner_id= from any caller (cross-user listing)"
REAL_SEARCH_SCOPE = "[REAL] /documents/search is not owner-scoped"
REAL_COMMENT_AUTHZ = "[REAL] comment routes have no authn/authz and trust body author_id"
REAL_BODY_OWNER = "[REAL] create / from-template trust body owner_id over the JWT subject"
REAL_PAGE_SIZE = "[REAL] client sends pageSize but the service only reads size"


@pytest.fixture
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    secret = secrets.token_hex(32)
    monkeypatch.setenv("JWT_SECRET", secret)
    return secret


@pytest.fixture
def make_headers(jwt_secret: str):
    def _make(user_id: uuid.UUID) -> dict[str, str]:
        token = jwt.encode({"sub": str(user_id)}, jwt_secret, algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def alice() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def bob() -> uuid.UUID:
    return uuid.uuid4()


async def _create(
    client: AsyncClient, headers: dict, title: str = "Doc", content: str = ""
) -> dict:
    resp = await client.post(
        "/api/v1/documents/", json={"title": title, "content": content}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_create_get_with_jwt_owner(client: AsyncClient, make_headers, alice):
    doc = await _create(client, make_headers(alice), "Plan", "one two three")
    assert doc["owner_id"] == str(alice)
    assert doc["word_count"] == 3
    assert doc["version"] == 1
    resp = await client.get(f"/api/v1/documents/{doc['id']}", headers=make_headers(alice))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Plan"


@pytest.mark.asyncio
async def test_create_rejects_empty_title(client: AsyncClient, make_headers, alice):
    resp = await client.post("/api/v1/documents/", json={"title": ""}, headers=make_headers(alice))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_without_trailing_slash(client: AsyncClient, make_headers, alice):
    resp = await client.post(
        "/api/v1/documents", json={"title": "No slash"}, headers=make_headers(alice)
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_requires_auth(client: AsyncClient, make_headers, alice):
    doc = await _create(client, make_headers(alice))
    resp = await client.get(f"/api/v1/documents/{doc['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_other_user_cannot_read_update_or_delete(
    client: AsyncClient, make_headers, alice, bob
):
    doc = await _create(client, make_headers(alice))
    bob_h = make_headers(bob)
    assert (await client.get(f"/api/v1/documents/{doc['id']}", headers=bob_h)).status_code == 403
    assert (
        await client.patch(f"/api/v1/documents/{doc['id']}", json={"title": "x"}, headers=bob_h)
    ).status_code == 403
    assert (
        await client.put(f"/api/v1/documents/{doc['id']}", json={"title": "x"}, headers=bob_h)
    ).status_code == 403
    assert (await client.delete(f"/api/v1/documents/{doc['id']}", headers=bob_h)).status_code == 403
    assert (
        await client.get(f"/api/v1/documents/{doc['id']}/versions", headers=bob_h)
    ).status_code == 403


@pytest.mark.asyncio
async def test_edit_title_and_content_bumps_version(client: AsyncClient, make_headers, alice):
    h = make_headers(alice)
    doc = await _create(client, h, "Draft", "v1 body")
    r = await client.patch(f"/api/v1/documents/{doc['id']}", json={"title": "Renamed"}, headers=h)
    assert r.status_code == 200
    assert r.json()["title"] == "Renamed"
    r = await client.put(
        f"/api/v1/documents/{doc['id']}", json={"title": "Final", "content": "a b c d"}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["version"] == 3
    assert r.json()["word_count"] == 4


@pytest.mark.asyncio
async def test_patch_rejects_null_title(client: AsyncClient, make_headers, alice):
    h = make_headers(alice)
    doc = await _create(client, h)
    r = await client.patch(f"/api/v1/documents/{doc['id']}", json={"title": None}, headers=h)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_versions_history_and_restore(client: AsyncClient, make_headers, alice):
    h = make_headers(alice)
    doc = await _create(client, h, "Hist", "original")
    await client.patch(f"/api/v1/documents/{doc['id']}", json={"content": "second"}, headers=h)
    await client.patch(f"/api/v1/documents/{doc['id']}", json={"content": "third"}, headers=h)
    versions = (await client.get(f"/api/v1/documents/{doc['id']}/versions", headers=h)).json()
    assert [v["version_number"] for v in versions] == [1, 2, 3]
    assert versions[0]["content"] == "original"
    r = await client.post(
        f"/api/v1/documents/{doc['id']}/versions/{versions[0]['id']}/restore", headers=h
    )
    assert r.status_code == 200
    assert r.json()["content"] == "original"
    assert r.json()["version"] == 4


@pytest.mark.asyncio
async def test_restore_unknown_version_404(client: AsyncClient, make_headers, alice):
    h = make_headers(alice)
    doc = await _create(client, h)
    r = await client.post(
        f"/api/v1/documents/{doc['id']}/versions/{uuid.uuid4()}/restore", headers=h
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_soft_delete_hides_document(client: AsyncClient, make_headers, alice):
    h = make_headers(alice)
    doc = await _create(client, h, "Doomed")
    assert (await client.delete(f"/api/v1/documents/{doc['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/api/v1/documents/{doc['id']}", headers=h)).status_code == 404
    listing = (await client.get("/api/v1/documents/", headers=h)).json()
    assert all(item["id"] != doc["id"] for item in listing["items"])
    assert (await client.delete(f"/api/v1/documents/{doc['id']}", headers=h)).status_code == 404


@pytest.mark.asyncio
async def test_list_scoped_to_caller_and_paginated(client: AsyncClient, make_headers, alice, bob):
    h = make_headers(alice)
    for i in range(25):
        await _create(client, h, f"Doc {i}")
    await _create(client, make_headers(bob), "Bob doc")
    page1 = (
        await client.get("/api/v1/documents/", params={"page": 1, "size": 20}, headers=h)
    ).json()
    page2 = (
        await client.get("/api/v1/documents/", params={"page": 2, "size": 20}, headers=h)
    ).json()
    assert page1["total"] == 25
    assert page1["pages"] == 2
    assert len(page1["items"]) == 20
    assert len(page2["items"]) == 5
    ids = {d["id"] for d in page1["items"]} | {d["id"] for d in page2["items"]}
    assert len(ids) == 25
    assert all(d["owner_id"] == str(alice) for d in page1["items"] + page2["items"])


@pytest.mark.asyncio
async def test_list_rejects_out_of_range_size(client: AsyncClient, make_headers, alice):
    r = await client.get("/api/v1/documents/", params={"size": 101}, headers=make_headers(alice))
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.xfail(reason=REAL_PAGE_SIZE, strict=True)
async def test_list_honours_page_size_alias(client: AsyncClient, make_headers, alice):
    h = make_headers(alice)
    for i in range(25):
        await _create(client, h, f"Doc {i}")
    r = await client.get("/api/v1/documents/", params={"page": 1, "pageSize": 50}, headers=h)
    assert len(r.json()["items"]) == 25


@pytest.mark.asyncio
@pytest.mark.xfail(reason=REAL_OWNER_PARAM, strict=True)
async def test_list_ignores_foreign_owner_id_param(client: AsyncClient, make_headers, alice, bob):
    await _create(client, make_headers(alice), "Alice private")
    r = await client.get(
        "/api/v1/documents/", params={"owner_id": str(alice)}, headers=make_headers(bob)
    )
    assert all(d["owner_id"] == str(bob) for d in r.json()["items"])


@pytest.mark.asyncio
@pytest.mark.xfail(reason=REAL_SEARCH_SCOPE, strict=True)
async def test_search_scoped_to_caller(client: AsyncClient, make_headers, alice, bob):
    await _create(client, make_headers(alice), "Alice secret roadmap")
    r = await client.get(
        "/api/v1/documents/search", params={"q": "secret"}, headers=make_headers(bob)
    )
    assert r.json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.xfail(reason=REAL_BODY_OWNER, strict=True)
async def test_create_ignores_body_owner_for_authenticated_caller(
    client: AsyncClient, make_headers, alice, bob
):
    r = await client.post(
        "/api/v1/documents/",
        json={"title": "Planted", "owner_id": str(alice)},
        headers=make_headers(bob),
    )
    assert r.json()["owner_id"] == str(bob)


@pytest.mark.asyncio
async def test_template_create_list_and_instantiate(client: AsyncClient, alice):
    r = await client.post(
        "/api/v1/templates/",
        json={"name": "Meeting", "content": "## Agenda\n- item", "created_by": str(alice)},
    )
    assert r.status_code == 201
    template = r.json()
    names = [t["name"] for t in (await client.get("/api/v1/templates/")).json()]
    assert "Meeting" in names
    r = await client.post(
        f"/api/v1/documents/from-template/{template['id']}",
        json={"title": "Monday sync", "owner_id": str(alice)},
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["content"] == "## Agenda\n- item"
    assert doc["title"] == "Monday sync"
    assert doc["is_template"] is False


@pytest.mark.asyncio
async def test_from_unknown_template_404(client: AsyncClient, alice):
    r = await client.post(
        f"/api/v1/documents/from-template/{uuid.uuid4()}",
        json={"title": "x", "owner_id": str(alice)},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_template_requires_name(client: AsyncClient, alice):
    r = await client.post("/api/v1/templates/", json={"name": "", "created_by": str(alice)})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_comments_add_list_delete(client: AsyncClient, make_headers, alice):
    doc = await _create(client, make_headers(alice))
    r = await client.post(
        f"/api/v1/documents/{doc['id']}/comments",
        json={"author_id": str(alice), "content": "LGTM"},
    )
    assert r.status_code == 201
    comment = r.json()
    listed = (await client.get(f"/api/v1/documents/{doc['id']}/comments")).json()
    assert [c["content"] for c in listed] == ["LGTM"]
    assert (
        await client.delete(f"/api/v1/documents/{doc['id']}/comments/{comment['id']}")
    ).status_code == 204
    assert (await client.get(f"/api/v1/documents/{doc['id']}/comments")).json() == []
    assert (
        await client.delete(f"/api/v1/documents/{doc['id']}/comments/{comment['id']}")
    ).status_code == 404


@pytest.mark.asyncio
async def test_comment_rejects_empty_content(client: AsyncClient, make_headers, alice):
    doc = await _create(client, make_headers(alice))
    r = await client.post(
        f"/api/v1/documents/{doc['id']}/comments", json={"author_id": str(alice), "content": ""}
    )
    assert r.status_code == 422


@pytest.mark.asyncio
@pytest.mark.xfail(reason=REAL_COMMENT_AUTHZ, strict=True)
async def test_comment_on_foreign_document_forbidden(client: AsyncClient, make_headers, alice, bob):
    doc = await _create(client, make_headers(alice))
    r = await client.post(
        f"/api/v1/documents/{doc['id']}/comments",
        json={"author_id": str(alice), "content": "spoofed"},
        headers=make_headers(bob),
    )
    assert r.status_code in (401, 403)

"""Object-level authorization: callers only reach their own documents and comments."""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


async def _create(client: AsyncClient, user_id: uuid.UUID, title: str, content: str = "body"):
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": title, "content": content},
        headers=auth_header(user_id),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _template(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/templates/",
        json={"name": "Spec", "content": "Spec body", "created_by": str(uuid.uuid4())},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---- list: ?owner_id= cannot widen the caller's scope ----


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{}, {"title": "Private"}])
async def test_list_owner_id_of_another_user_is_denied(client: AsyncClient, params):
    victim, intruder = uuid.uuid4(), uuid.uuid4()
    await _create(client, victim, "Private")
    for path in ("/api/v1/documents/", "/api/v1/documents"):
        resp = await client.get(
            path, params={"owner_id": str(victim), **params}, headers=auth_header(intruder)
        )
        assert resp.status_code == 403
        assert "Private" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{}, {"title": "Mine"}])
async def test_list_returns_only_the_callers_documents(client: AsyncClient, params):
    me, other = uuid.uuid4(), uuid.uuid4()
    await _create(client, me, "Mine")
    await _create(client, other, "Mine too, but not yours")
    for extra in ({}, {"owner_id": str(me)}):
        resp = await client.get(
            "/api/v1/documents/", params={**params, **extra}, headers=auth_header(me)
        )
        assert resp.status_code == 200
        assert [item["title"] for item in resp.json()["items"]] == ["Mine"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{}, {"title": "x"}])
async def test_list_requires_authentication(client: AsyncClient, params):
    await _create(client, uuid.uuid4(), "x")
    resp = await client.get("/api/v1/documents/", params=params)
    assert resp.status_code == 401


# ---- search ----


@pytest.mark.asyncio
async def test_search_does_not_return_other_users_documents(client: AsyncClient):
    victim, intruder = uuid.uuid4(), uuid.uuid4()
    await _create(client, victim, "Merger plan", "confidential")
    resp = await client.get(
        "/api/v1/documents/search", params={"q": "Merger"}, headers=auth_header(intruder)
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_search_returns_the_callers_matches(client: AsyncClient):
    me, other = uuid.uuid4(), uuid.uuid4()
    mine = await _create(client, me, "Merger plan")
    await _create(client, other, "Merger plan")
    resp = await client.get(
        "/api/v1/documents/search", params={"q": "Merger"}, headers=auth_header(me)
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [mine["id"]]


@pytest.mark.asyncio
async def test_search_requires_authentication(client: AsyncClient):
    resp = await client.get("/api/v1/documents/search", params={"q": "anything"})
    assert resp.status_code == 401


# ---- create / create-from-template: owner comes from the token ----


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
async def test_create_with_another_users_owner_id_is_denied(client: AsyncClient, path):
    victim, attacker = uuid.uuid4(), uuid.uuid4()
    resp = await client.post(
        path,
        json={"title": "Planted", "owner_id": str(victim)},
        headers=auth_header(attacker),
    )
    assert resp.status_code == 403
    listing = await client.get("/api/v1/documents/", headers=auth_header(victim))
    assert listing.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_with_own_owner_id_is_allowed(client: AsyncClient):
    me = uuid.uuid4()
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Mine", "owner_id": str(me)},
        headers=auth_header(me),
    )
    assert resp.status_code == 201
    assert resp.json()["owner_id"] == str(me)


@pytest.mark.asyncio
async def test_create_with_owner_id_but_no_authentication_is_rejected(client: AsyncClient):
    resp = await client.post(
        "/api/v1/documents/", json={"title": "Anon", "owner_id": str(uuid.uuid4())}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_from_template_with_another_users_owner_id_is_denied(client: AsyncClient):
    victim, attacker = uuid.uuid4(), uuid.uuid4()
    template_id = await _template(client)
    resp = await client.post(
        f"/api/v1/documents/from-template/{template_id}",
        json={"title": "Planted", "owner_id": str(victim)},
        headers=auth_header(attacker),
    )
    assert resp.status_code == 403
    listing = await client.get("/api/v1/documents/", headers=auth_header(victim))
    assert listing.json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("send_owner", [True, False])
async def test_from_template_is_owned_by_the_caller(client: AsyncClient, send_owner: bool):
    me = uuid.uuid4()
    template_id = await _template(client)
    body = {"title": "From spec", **({"owner_id": str(me)} if send_owner else {})}
    resp = await client.post(
        f"/api/v1/documents/from-template/{template_id}", json=body, headers=auth_header(me)
    )
    assert resp.status_code == 201
    assert resp.json()["owner_id"] == str(me)
    assert resp.json()["content"] == "Spec body"


@pytest.mark.asyncio
async def test_from_template_requires_authentication(client: AsyncClient):
    template_id = await _template(client)
    resp = await client.post(
        f"/api/v1/documents/from-template/{template_id}",
        json={"title": "Anon", "owner_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 401


# ---- comments ----


@pytest.mark.asyncio
async def test_comments_require_authentication(client: AsyncClient):
    owner = uuid.uuid4()
    doc = await _create(client, owner, "Doc")
    base = f"/api/v1/documents/{doc['id']}/comments"
    assert (await client.get(base)).status_code == 401
    assert (await client.post(base, json={"content": "hi"})).status_code == 401
    assert (await client.delete(f"{base}/{uuid.uuid4()}")).status_code == 401


@pytest.mark.asyncio
async def test_non_owner_cannot_list_or_add_comments(client: AsyncClient):
    owner, intruder = uuid.uuid4(), uuid.uuid4()
    doc = await _create(client, owner, "Doc")
    base = f"/api/v1/documents/{doc['id']}/comments"
    await client.post(base, json={"content": "private note"}, headers=auth_header(owner))

    listed = await client.get(base, headers=auth_header(intruder))
    assert listed.status_code == 403
    assert "private note" not in listed.text
    added = await client.post(base, json={"content": "spam"}, headers=auth_header(intruder))
    assert added.status_code == 403

    remaining = await client.get(base, headers=auth_header(owner))
    assert [c["content"] for c in remaining.json()] == ["private note"]


@pytest.mark.asyncio
async def test_comment_author_comes_from_the_token(client: AsyncClient):
    owner = uuid.uuid4()
    doc = await _create(client, owner, "Doc")
    base = f"/api/v1/documents/{doc['id']}/comments"

    spoofed = await client.post(
        base,
        json={"author_id": str(uuid.uuid4()), "content": "impersonated"},
        headers=auth_header(owner),
    )
    assert spoofed.status_code == 403

    created = await client.post(base, json={"content": "mine"}, headers=auth_header(owner))
    assert created.status_code == 201
    assert created.json()["author_id"] == str(owner)


@pytest.mark.asyncio
async def test_only_the_author_can_delete_a_comment(client: AsyncClient):
    owner, intruder = uuid.uuid4(), uuid.uuid4()
    doc = await _create(client, owner, "Doc")
    base = f"/api/v1/documents/{doc['id']}/comments"
    comment = (
        await client.post(base, json={"content": "keep"}, headers=auth_header(owner))
    ).json()

    denied = await client.delete(f"{base}/{comment['id']}", headers=auth_header(intruder))
    assert denied.status_code == 403
    assert len((await client.get(base, headers=auth_header(owner))).json()) == 1

    allowed = await client.delete(f"{base}/{comment['id']}", headers=auth_header(owner))
    assert allowed.status_code == 204
    assert (await client.get(base, headers=auth_header(owner))).json() == []


@pytest.mark.asyncio
async def test_comment_on_unknown_document_is_404(client: AsyncClient):
    resp = await client.post(
        f"/api/v1/documents/{uuid.uuid4()}/comments",
        json={"content": "orphan"},
        headers=auth_header(uuid.uuid4()),
    )
    assert resp.status_code == 404

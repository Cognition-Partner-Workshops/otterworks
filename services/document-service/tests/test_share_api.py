"""Unit tests for document share links: minting authz and the read-only shared route."""

import hashlib
import uuid

import pytest
from httpx import AsyncClient

from app.services.share_link import TOKEN_LENGTH, ShareLinkService

DOC_A = "11111111-1111-4111-8111-111111111111"
DOC_B = "22222222-2222-4222-8222-222222222222"


@pytest.fixture(autouse=True)
def header_identity(monkeypatch):
    # Same reasoning as test_share_link.py: use the X-User-ID identity path regardless
    # of whether test_documents_api.py set JWT_SECRET earlier in the session.
    monkeypatch.delenv("JWT_SECRET", raising=False)


def _headers(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": "Bearer token", "X-User-ID": str(user_id)}


async def _create(client: AsyncClient, owner_id: uuid.UUID, title: str = "Shared") -> str:
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": title, "content": "secret body", "owner_id": str(owner_id)},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── ShareLinkService ────────────────────────────────────────────────────


def test_token_has_fixed_length_hex():
    token = ShareLinkService(salt="s").mint_token(DOC_A)
    assert len(token) == TOKEN_LENGTH
    int(token, 16)


def test_salt_changes_token():
    assert ShareLinkService(salt="one").mint_token(DOC_A) != ShareLinkService(
        salt="two"
    ).mint_token(DOC_A)


def test_token_from_other_salt_is_rejected():
    token = ShareLinkService(salt="one").mint_token(DOC_A)
    assert ShareLinkService(salt="two").verify_token(DOC_A, token) is False


def test_salt_read_from_environment(monkeypatch):
    monkeypatch.setenv("SHARE_LINK_SALT", "env-salt")
    assert ShareLinkService().mint_token(DOC_A) == ShareLinkService(salt="env-salt").mint_token(
        DOC_A
    )


def test_distinct_documents_get_distinct_tokens():
    svc = ShareLinkService(salt="s")
    assert svc.mint_token(DOC_A) != svc.mint_token(DOC_B)


def test_empty_and_truncated_tokens_rejected():
    svc = ShareLinkService(salt="s")
    token = svc.mint_token(DOC_A)
    assert svc.verify_token(DOC_A, "") is False
    assert svc.verify_token(DOC_A, token[:-1]) is False
    assert svc.verify_token(DOC_A, token + "0") is False


@pytest.mark.xfail(
    strict=True,
    reason="[PLANTED] OW-SEC-403: share tokens are unkeyed MD5 over a source-visible salt "
    "(security/equivalence/findings.yaml). Passes once the keyed-MAC refactor lands.",
)
def test_token_cannot_be_derived_offline_from_default_salt(monkeypatch):
    monkeypatch.delenv("SHARE_LINK_SALT", raising=False)
    forged = hashlib.md5(f"{DOC_A}:otterworks-share".encode()).hexdigest()[:TOKEN_LENGTH]  # noqa: S324
    assert ShareLinkService().verify_token(DOC_A, forged) is False


# ── POST /api/v1/documents/{id}/share ──────────────────────────────────


@pytest.mark.asyncio
async def test_mint_requires_authentication(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    resp = await client.post(f"/api/v1/documents/{doc_id}/share")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_mint_by_non_owner_is_forbidden(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    resp = await client.post(f"/api/v1/documents/{doc_id}/share", headers=_headers(uuid.uuid4()))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mint_for_missing_document_is_404(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(f"/api/v1/documents/{uuid.uuid4()}/share", headers=_headers(owner_id))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_mint_rejects_non_uuid_id(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post("/api/v1/documents/not-a-uuid/share", headers=_headers(owner_id))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_mint_returns_document_id_and_token(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    resp = await client.post(f"/api/v1/documents/{doc_id}/share", headers=_headers(owner_id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == doc_id
    assert len(body["token"]) == TOKEN_LENGTH


@pytest.mark.asyncio
async def test_mint_is_stable_for_same_document(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    first = await client.post(f"/api/v1/documents/{doc_id}/share", headers=_headers(owner_id))
    second = await client.post(f"/api/v1/documents/{doc_id}/share", headers=_headers(owner_id))
    assert first.json()["token"] == second.json()["token"]


# ── GET /api/v1/documents/shared ───────────────────────────────────────


async def _mint(client: AsyncClient, owner_id: uuid.UUID, doc_id: str) -> str:
    resp = await client.post(f"/api/v1/documents/{doc_id}/share", headers=_headers(owner_id))
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


@pytest.mark.asyncio
async def test_shared_route_opens_document_for_another_user(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_id = await _create(client, owner_id, title="Link doc")
    token = await _mint(client, owner_id, doc_id)
    resp = await client.get(
        "/api/v1/documents/shared",
        params={"document_id": doc_id, "token": token},
        headers=_headers(uuid.uuid4()),
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Link doc"
    assert resp.json()["content"] == "secret body"


@pytest.mark.asyncio
async def test_token_for_one_document_does_not_open_another(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc_a = await _create(client, owner_id, title="A")
    doc_b = await _create(client, owner_id, title="B")
    token_a = await _mint(client, owner_id, doc_a)
    resp = await client.get(
        "/api/v1/documents/shared", params={"document_id": doc_b, "token": token_a}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_shared_route_requires_token(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    resp = await client.get("/api/v1/documents/shared", params={"document_id": doc_id})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shared_route_rejects_empty_token(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    resp = await client.get("/api/v1/documents/shared", params={"document_id": doc_id, "token": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_shared_route_valid_token_for_deleted_document_is_404(
    client: AsyncClient, owner_id: uuid.UUID
):
    deleted_doc = "00000000-0000-4000-8000-00000000dead"
    token = ShareLinkService().mint_token(deleted_doc)
    resp = await client.get(
        "/api/v1/documents/shared", params={"document_id": deleted_doc, "token": token}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_share_link_does_not_grant_direct_access(client: AsyncClient, owner_id: uuid.UUID):
    doc_id = await _create(client, owner_id)
    await _mint(client, owner_id, doc_id)
    stranger = uuid.uuid4()
    direct = await client.get(f"/api/v1/documents/{doc_id}", headers=_headers(stranger))
    assert direct.status_code == 403
    edit = await client.patch(
        f"/api/v1/documents/{doc_id}", json={"title": "pwned"}, headers=_headers(stranger)
    )
    assert edit.status_code == 403

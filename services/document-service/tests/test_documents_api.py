"""Tests for document API endpoints."""

import uuid

import jwt
import pytest
from httpx import AsyncClient

from tests.auth_helpers import TEST_JWT_SECRET, auth_headers, make_jwt


@pytest.mark.asyncio
async def test_create_document(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(
        "/api/v1/documents/",
        json={
            "title": "Test Document",
            "content": "Hello world",
            "owner_id": str(owner_id),
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Document"
    assert data["content"] == "Hello world"
    assert data["word_count"] == 2
    assert data["version"] == 1
    assert data["owner_id"] == str(owner_id)


@pytest.mark.asyncio
async def test_get_document(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Doc", "content": "Body", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient, headers: dict[str, str]):
    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_documents(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    for i in range(3):
        await client.post(
            "/api/v1/documents/",
            json={"title": f"Doc {i}", "content": "", "owner_id": str(owner_id)},
        )
    resp = await client.get("/api/v1/documents/", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_documents_pagination(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    for i in range(5):
        await client.post(
            "/api/v1/documents/",
            json={"title": f"Doc {i}", "content": "", "owner_id": str(owner_id)},
        )
    resp = await client.get(
        "/api/v1/documents/", headers=headers, params={"page": 1, "size": 2}
    )
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["pages"] == 3


@pytest.mark.asyncio
async def test_update_document(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Original", "content": "Old body", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"title": "Updated", "content": "New body"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Updated"
    assert data["content"] == "New body"
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_patch_document(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Original", "content": "Body", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"title": "Patched Title"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Patched Title"
    assert data["content"] == "Body"  # unchanged
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_delete_document(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "To Delete", "content": "", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_document_versions(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Versioned", "content": "v1", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    await client.put(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"title": "Versioned", "content": "v2"},
    )

    resp = await client.get(f"/api/v1/documents/{doc_id}/versions", headers=headers)
    assert resp.status_code == 200
    versions = resp.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1


@pytest.mark.asyncio
async def test_restore_version(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Restore Me", "content": "Original", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    await client.put(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"title": "Changed", "content": "Changed body"},
    )

    versions_resp = await client.get(f"/api/v1/documents/{doc_id}/versions", headers=headers)
    v1_id = versions_resp.json()[-1]["id"]  # first version

    resp = await client.post(
        f"/api/v1/documents/{doc_id}/versions/{v1_id}/restore", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Restore Me"
    assert data["content"] == "Original"
    assert data["version"] == 3


@pytest.mark.asyncio
async def test_search_documents(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    await client.post(
        "/api/v1/documents/",
        json={"title": "Python Guide", "content": "Learn Python", "owner_id": str(owner_id)},
    )
    await client.post(
        "/api/v1/documents/",
        json={"title": "Rust Guide", "content": "Learn Rust", "owner_id": str(owner_id)},
    )

    resp = await client.get("/api/v1/documents/search", headers=headers, params={"q": "Python"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Python Guide"


@pytest.mark.asyncio
async def test_export_document_html(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Export", "content": "Content here", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export", headers=headers, params={"format": "html"}
    )
    assert resp.status_code == 200
    assert "<h1>Export</h1>" in resp.text


@pytest.mark.asyncio
async def test_export_document_markdown(
    client: AsyncClient, owner_id: uuid.UUID, headers: dict[str, str]
):
    create_resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Export MD", "content": "MD content", "owner_id": str(owner_id)},
    )
    doc_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export", headers=headers, params={"format": "markdown"}
    )
    assert resp.status_code == 200
    assert "# Export MD" in resp.text


@pytest.mark.asyncio
async def test_create_document_via_jwt(client: AsyncClient):
    """Create a document without owner_id in the body, using JWT instead."""
    user_id = uuid.uuid4()
    token = make_jwt(str(user_id))
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "JWT Doc", "content": "Created via JWT"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "JWT Doc"
    assert data["owner_id"] == str(user_id)


@pytest.mark.asyncio
async def test_create_document_via_jwt_hs384(client: AsyncClient):
    """Create a document using an HS384-signed JWT (matches auth-service algorithm)."""
    user_id = uuid.uuid4()
    token = jwt.encode({"sub": str(user_id)}, TEST_JWT_SECRET, algorithm="HS384")
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "HS384 Doc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["owner_id"] == str(user_id)


@pytest.mark.asyncio
async def test_create_document_x_user_id_header_ignored(client: AsyncClient):
    """X-User-Id header alone is not trusted (prevents identity spoofing)."""
    user_id = uuid.uuid4()
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "Header Doc"},
        headers={"X-User-Id": str(user_id)},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_document_no_auth_returns_401(client: AsyncClient):
    """Creating a document without owner_id and without auth returns 401."""
    resp = await client.post(
        "/api/v1/documents/",
        json={"title": "No Auth Doc"},
    )
    assert resp.status_code == 401


async def _create_for(client: AsyncClient, owner: uuid.UUID, title: str, content: str) -> str:
    resp = await client.post(
        "/api/v1/documents/",
        headers=auth_headers(owner),
        json={"title": title, "content": content},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# --- Owner scoping: search and list must never return another user's documents ---


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/documents/search", params={"q": "anything"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_only_returns_callers_documents(client: AsyncClient):
    alice, mallory = uuid.uuid4(), uuid.uuid4()
    alice_doc = await _create_for(client, alice, "Q4 layoffs", "confidential plan")
    mallory_doc = await _create_for(client, mallory, "My layoffs memo", "public")

    resp = await client.get(
        "/api/v1/documents/search", headers=auth_headers(mallory), params={"q": "layoffs"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [mallory_doc]
    assert alice_doc not in resp.text
    assert "confidential plan" not in resp.text

    resp = await client.get(
        "/api/v1/documents/search", headers=auth_headers(alice), params={"q": "layoffs"}
    )
    assert [item["id"] for item in resp.json()["items"]] == [alice_doc]


@pytest.mark.asyncio
async def test_list_requires_auth(client: AsyncClient, owner_id: uuid.UUID):
    await _create_for(client, owner_id, "Private", "body")
    resp = await client.get("/api/v1/documents/")
    assert resp.status_code == 401
    resp = await client.get("/api/v1/documents/", params={"owner_id": str(owner_id)})
    assert resp.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/v1/documents/", "/api/v1/documents"])
async def test_list_ignores_foreign_owner_id(client: AsyncClient, path: str):
    alice, mallory = uuid.uuid4(), uuid.uuid4()
    alice_doc = await _create_for(client, alice, "Alice private", "alice secret")
    mallory_doc = await _create_for(client, mallory, "Mallory own", "mine")

    resp = await client.get(
        path, headers=auth_headers(mallory), params={"owner_id": str(alice)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert [item["id"] for item in data["items"]] == [mallory_doc]
    assert alice_doc not in resp.text
    assert "alice secret" not in resp.text


@pytest.mark.asyncio
async def test_filtered_list_ignores_foreign_owner_id(client: AsyncClient):
    alice, mallory = uuid.uuid4(), uuid.uuid4()
    alice_doc = await _create_for(client, alice, "Quarterly report", "alice secret")
    mallory_doc = await _create_for(client, mallory, "Quarterly notes", "mine")

    resp = await client.get(
        "/api/v1/documents/",
        headers=auth_headers(mallory),
        params={"owner_id": str(alice), "title": "quarterly"},
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [mallory_doc]
    assert alice_doc not in resp.text


@pytest.mark.asyncio
async def test_list_own_owner_id_still_accepted(client: AsyncClient, owner_id: uuid.UUID):
    """Existing clients send their own id; that keeps working."""
    doc_id = await _create_for(client, owner_id, "Mine", "body")
    resp = await client.get(
        "/api/v1/documents/", headers=auth_headers(owner_id), params={"owner_id": str(owner_id)}
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [doc_id]


@pytest.mark.asyncio
async def test_list_admin_may_target_another_owner(client: AsyncClient):
    alice, admin = uuid.uuid4(), uuid.uuid4()
    alice_doc = await _create_for(client, alice, "Alice doc", "body")
    await _create_for(client, admin, "Admin doc", "body")

    resp = await client.get(
        "/api/v1/documents/",
        headers=auth_headers(admin, roles=["ADMIN", "USER"]),
        params={"owner_id": str(alice)},
    )
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()["items"]] == [alice_doc]

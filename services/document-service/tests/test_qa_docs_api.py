"""QA (docs area): document API behaviour through the ASGI app with JWT identities."""

import uuid

import jwt
import pytest
from httpx import AsyncClient

QA_JWT_SECRET = "qa-docs-jwt-secret-for-unit-tests-32b"  # noqa: S105
BASE = "/api/v1/documents"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("JWT_SECRET", QA_JWT_SECRET)
    return QA_JWT_SECRET


def auth_headers(user_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode({"user_id": str(user_id)}, QA_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def alice() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def bob() -> uuid.UUID:
    return uuid.uuid4()


async def create_doc(
    client: AsyncClient, user_id: uuid.UUID, title: str = "QA Doc", content: str = "one two three"
) -> dict:
    resp = await client.post(
        f"{BASE}/", headers=auth_headers(user_id), json={"title": title, "content": content}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---- create ----


@pytest.mark.asyncio
async def test_create_uses_jwt_identity_as_owner(client, alice):
    doc = await create_doc(client, alice)
    assert doc["owner_id"] == str(alice)
    assert doc["version"] == 1
    assert doc["word_count"] == 3
    assert doc["is_deleted"] is False
    assert doc["content_type"] == "text/markdown"


@pytest.mark.asyncio
async def test_create_without_trailing_slash(client, alice):
    resp = await client.post(BASE, headers=auth_headers(alice), json={"title": "No slash"})
    assert resp.status_code == 201
    assert resp.json()["content"] == ""
    assert resp.json()["word_count"] == 0


@pytest.mark.asyncio
async def test_create_rejects_empty_title(client, alice):
    resp = await client.post(f"{BASE}/", headers=auth_headers(alice), json={"title": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_overlong_title(client, alice):
    resp = await client.post(f"{BASE}/", headers=auth_headers(alice), json={"title": "x" * 501})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_accepts_max_length_title(client, alice):
    resp = await client.post(f"{BASE}/", headers=auth_headers(alice), json={"title": "x" * 500})
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_create_without_identity_is_401(client):
    resp = await client.post(f"{BASE}/", json={"title": "anon"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_with_forged_jwt_is_401(client):
    forged = jwt.encode(
        {"user_id": str(uuid.uuid4())}, "wrong-secret-wrong-secret-wrong-32", algorithm="HS256"
    )
    resp = await client.post(
        f"{BASE}/", headers={"Authorization": f"Bearer {forged}"}, json={"title": "forged"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_stores_rich_text_html_verbatim(client, alice):
    html = "<h1>Heading</h1><p><strong>bold</strong> and <em>italic</em></p><ul><li>item</li></ul>"
    doc = await create_doc(client, alice, content=html)
    got = await client.get(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    assert got.json()["content"] == html


# ---- open / read ----


@pytest.mark.asyncio
async def test_get_requires_auth(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.get(f"{BASE}/{doc['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_other_users_document_is_403(client, alice, bob):
    doc = await create_doc(client, alice)
    resp = await client.get(f"{BASE}/{doc['id']}", headers=auth_headers(bob))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_get_unknown_document_is_404(client, alice):
    resp = await client.get(f"{BASE}/{uuid.uuid4()}", headers=auth_headers(alice))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_malformed_id_is_422(client, alice):
    resp = await client.get(f"{BASE}/not-a-uuid", headers=auth_headers(alice))
    assert resp.status_code == 422


# ---- edit / autosave (PATCH) ----


@pytest.mark.asyncio
async def test_patch_content_bumps_version_and_word_count(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"content": "<p>a b c d e</p>"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == 2
    assert body["title"] == doc["title"]


@pytest.mark.asyncio
async def test_patch_rename_only_keeps_content(client, alice):
    doc = await create_doc(client, alice, content="keep me")
    resp = await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"title": "Renamed"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"
    assert resp.json()["content"] == "keep me"


@pytest.mark.asyncio
async def test_patch_empty_body_does_not_bump_version(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.patch(f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={})
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


@pytest.mark.asyncio
async def test_patch_null_title_is_rejected(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"title": None}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_empty_title_is_rejected(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"title": ""}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_clearing_content_sets_word_count_zero(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"content": ""}
    )
    assert resp.status_code == 200
    assert resp.json()["word_count"] == 0
    assert resp.json()["content"] == ""


@pytest.mark.asyncio
async def test_patch_by_other_user_is_403_and_unchanged(client, alice, bob):
    doc = await create_doc(client, alice, content="original")
    resp = await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(bob), json={"content": "hijack"}
    )
    assert resp.status_code == 403
    got = await client.get(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    assert got.json()["content"] == "original"


@pytest.mark.asyncio
async def test_sequential_autosaves_persist_latest(client, alice):
    doc = await create_doc(client, alice, content="")
    for i in range(1, 6):
        await client.patch(
            f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"content": f"draft {i}"}
        )
    got = (await client.get(f"{BASE}/{doc['id']}", headers=auth_headers(alice))).json()
    assert got["content"] == "draft 5"
    assert got["version"] == 6


# ---- full replace (PUT) ----


@pytest.mark.asyncio
async def test_put_replaces_title_and_content(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.put(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"title": "T2", "content": "x y"}
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "T2"
    assert resp.json()["word_count"] == 2
    assert resp.json()["version"] == 2


@pytest.mark.asyncio
async def test_put_requires_title(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.put(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"content": "x"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_unknown_is_404(client, alice):
    resp = await client.put(
        f"{BASE}/{uuid.uuid4()}", headers=auth_headers(alice), json={"title": "x"}
    )
    assert resp.status_code == 404


# ---- delete ----


@pytest.mark.asyncio
async def test_delete_then_get_is_404(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.delete(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    assert resp.status_code == 204
    got = await client.get(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    assert got.status_code == 404


@pytest.mark.asyncio
async def test_delete_twice_is_404(client, alice):
    doc = await create_doc(client, alice)
    await client.delete(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    resp = await client.delete(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_by_other_user_is_403(client, alice, bob):
    doc = await create_doc(client, alice)
    resp = await client.delete(f"{BASE}/{doc['id']}", headers=auth_headers(bob))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_deleted_document_disappears_from_list(client, alice):
    keep = await create_doc(client, alice, title="Keep")
    gone = await create_doc(client, alice, title="Gone")
    await client.delete(f"{BASE}/{gone['id']}", headers=auth_headers(alice))
    listed = (await client.get(f"{BASE}/", headers=auth_headers(alice))).json()
    ids = [d["id"] for d in listed["items"]]
    assert keep["id"] in ids
    assert gone["id"] not in ids
    assert listed["total"] == 1


# ---- list ----


@pytest.mark.asyncio
async def test_list_is_scoped_to_jwt_user(client, alice, bob):
    await create_doc(client, alice, title="A doc")
    await create_doc(client, bob, title="B doc")
    listed = (await client.get(f"{BASE}/", headers=auth_headers(alice))).json()
    assert {d["owner_id"] for d in listed["items"]} == {str(alice)}


@pytest.mark.asyncio
async def test_list_cannot_read_other_owner_via_query_param(client, alice, bob):
    await create_doc(client, alice, title="Alice private")
    listed = await client.get(
        f"{BASE}/", headers=auth_headers(bob), params={"owner_id": str(alice)}
    )
    items = listed.json().get("items", []) if listed.status_code == 200 else []
    assert all(
        d["owner_id"] == str(bob) for d in items
    ), "owner_id query param leaks another user's documents"


@pytest.mark.asyncio
async def test_list_without_auth_does_not_return_everyone(client, alice, bob):
    await create_doc(client, alice)
    await create_doc(client, bob)
    resp = await client.get(f"{BASE}/")
    items = resp.json().get("items", []) if resp.status_code == 200 else []
    assert items == [], "unauthenticated list returns all users' documents"


@pytest.mark.asyncio
async def test_list_orders_most_recently_updated_first(client, alice):
    first = await create_doc(client, alice, title="First")
    second = await create_doc(client, alice, title="Second")
    await client.patch(
        f"{BASE}/{first['id']}", headers=auth_headers(alice), json={"content": "touch"}
    )
    listed = (await client.get(f"{BASE}/", headers=auth_headers(alice))).json()
    assert [d["id"] for d in listed["items"]][:2] == [first["id"], second["id"]]


@pytest.mark.asyncio
async def test_list_pagination_math(client, alice):
    for i in range(5):
        await create_doc(client, alice, title=f"Doc {i}")
    listed = (
        await client.get(f"{BASE}/", headers=auth_headers(alice), params={"page": 2, "size": 2})
    ).json()
    assert listed["total"] == 5
    assert listed["pages"] == 3
    assert listed["page"] == 2
    assert len(listed["items"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"page": 0}, {"size": 0}, {"size": 101}])
async def test_list_rejects_bad_pagination(client, alice, params):
    resp = await client.get(f"{BASE}/", headers=auth_headers(alice), params=params)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_title_filter_with_quote_is_treated_as_literal(client, alice):
    await create_doc(client, alice, title="Otter's guide")
    resp = await client.get(f"{BASE}/", headers=auth_headers(alice), params={"title": "Otter's"})
    assert resp.status_code == 200, resp.text
    assert [d["title"] for d in resp.json()["items"]] == ["Otter's guide"]


@pytest.mark.asyncio
async def test_title_filter_cannot_widen_to_other_owners(client, alice, bob):
    await create_doc(client, alice, title="Alice secret")
    resp = await client.get(
        f"{BASE}/", headers=auth_headers(bob), params={"title": "x') OR ('1'='1"}
    )
    items = resp.json().get("items", []) if resp.status_code == 200 else []
    assert all(d["owner_id"] == str(bob) for d in items), "title filter is SQL-injectable"


@pytest.mark.asyncio
async def test_sort_by_unknown_column_is_client_error(client, alice):
    await create_doc(client, alice)
    resp = await client.get(f"{BASE}/", headers=auth_headers(alice), params={"sort": "nope_column"})
    assert resp.status_code in (400, 422)


# ---- versions / history ----


@pytest.mark.asyncio
async def test_versions_track_each_save(client, alice):
    doc = await create_doc(client, alice, content="v1")
    await client.patch(f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"content": "v2"})
    await client.patch(
        f"{BASE}/{doc['id']}", headers=auth_headers(alice), json={"title": "Renamed"}
    )
    versions = (
        await client.get(f"{BASE}/{doc['id']}/versions", headers=auth_headers(alice))
    ).json()
    assert [v["version_number"] for v in versions] == [1, 2, 3]
    assert [v["content"] for v in versions] == ["v1", "v2", "v2"]
    assert versions[-1]["title"] == "Renamed"


@pytest.mark.asyncio
async def test_versions_of_other_user_is_403(client, alice, bob):
    doc = await create_doc(client, alice)
    resp = await client.get(f"{BASE}/{doc['id']}/versions", headers=auth_headers(bob))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_restore_version_creates_new_version(client, alice):
    doc = await create_doc(client, alice, title="Orig", content="first body")
    await client.put(
        f"{BASE}/{doc['id']}",
        headers=auth_headers(alice),
        json={"title": "New", "content": "second"},
    )
    versions = (
        await client.get(f"{BASE}/{doc['id']}/versions", headers=auth_headers(alice))
    ).json()
    resp = await client.post(
        f"{BASE}/{doc['id']}/versions/{versions[0]['id']}/restore", headers=auth_headers(alice)
    )
    assert resp.status_code == 200
    restored = resp.json()
    assert restored["title"] == "Orig"
    assert restored["content"] == "first body"
    assert restored["version"] == 3
    assert restored["word_count"] == 2


@pytest.mark.asyncio
async def test_restore_version_of_another_document_is_404(client, alice):
    a = await create_doc(client, alice, title="A")
    b = await create_doc(client, alice, title="B")
    b_versions = (
        await client.get(f"{BASE}/{b['id']}/versions", headers=auth_headers(alice))
    ).json()
    resp = await client.post(
        f"{BASE}/{a['id']}/versions/{b_versions[0]['id']}/restore", headers=auth_headers(alice)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_by_other_user_is_403(client, alice, bob):
    doc = await create_doc(client, alice)
    versions = (
        await client.get(f"{BASE}/{doc['id']}/versions", headers=auth_headers(alice))
    ).json()
    resp = await client.post(
        f"{BASE}/{doc['id']}/versions/{versions[0]['id']}/restore", headers=auth_headers(bob)
    )
    assert resp.status_code == 403


# ---- export ----


@pytest.mark.asyncio
async def test_export_html_escapes_markup(client, alice):
    doc = await create_doc(
        client, alice, title="<script>x</script>", content="<img src=x onerror=alert(1)>"
    )
    resp = await client.get(
        f"{BASE}/{doc['id']}/export", headers=auth_headers(alice), params={"format": "html"}
    )
    assert resp.status_code == 200
    assert "<script>" not in resp.text
    assert "&lt;img" in resp.text


@pytest.mark.asyncio
async def test_export_markdown(client, alice):
    doc = await create_doc(client, alice, title="MD", content="body")
    resp = await client.get(
        f"{BASE}/{doc['id']}/export", headers=auth_headers(alice), params={"format": "markdown"}
    )
    assert resp.status_code == 200
    assert resp.text == "# MD\n\nbody"
    assert resp.headers["content-type"].startswith("text/markdown")


@pytest.mark.asyncio
async def test_export_rejects_unknown_format(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.get(
        f"{BASE}/{doc['id']}/export", headers=auth_headers(alice), params={"format": "docx"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_other_user_is_403(client, alice, bob):
    doc = await create_doc(client, alice)
    resp = await client.get(f"{BASE}/{doc['id']}/export", headers=auth_headers(bob))
    assert resp.status_code == 403


# ---- search ----


@pytest.mark.asyncio
async def test_search_does_not_leak_other_users_documents(client, alice, bob):
    await create_doc(client, alice, title="Alice confidential plan", content="secret")
    resp = await client.get(
        f"{BASE}/search", headers=auth_headers(bob), params={"q": "confidential"}
    )
    items = resp.json().get("items", []) if resp.status_code == 200 else []
    assert items == [], "document search returns other users' documents"


# ---- share ----


@pytest.mark.asyncio
async def test_share_link_round_trip(client, alice):
    doc = await create_doc(client, alice, content="shared body")
    minted = await client.post(f"{BASE}/{doc['id']}/share", headers=auth_headers(alice))
    assert minted.status_code == 200
    token = minted.json()["token"]
    resp = await client.get(f"{BASE}/shared", params={"document_id": doc["id"], "token": token})
    assert resp.status_code == 200
    assert resp.json()["content"] == "shared body"


@pytest.mark.asyncio
async def test_share_by_other_user_is_403(client, alice, bob):
    doc = await create_doc(client, alice)
    resp = await client.post(f"{BASE}/{doc['id']}/share", headers=auth_headers(bob))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_shared_rejects_bad_token(client, alice):
    doc = await create_doc(client, alice)
    resp = await client.get(
        f"{BASE}/shared", params={"document_id": doc["id"], "token": "deadbeefdeadbeef"}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_shared_deleted_document_is_404(client, alice):
    doc = await create_doc(client, alice)
    token = (await client.post(f"{BASE}/{doc['id']}/share", headers=auth_headers(alice))).json()[
        "token"
    ]
    await client.delete(f"{BASE}/{doc['id']}", headers=auth_headers(alice))
    resp = await client.get(f"{BASE}/shared", params={"document_id": doc["id"], "token": token})
    assert resp.status_code == 404

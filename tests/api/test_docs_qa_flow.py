"""QA pyramid (docs area): black-box document-service flows through the gateway.

Known defects are ``xfail(strict=True)`` with a [REAL] or [PLANTED] label so the
suite stays green while they exist and flips red once they are fixed.
"""

import uuid

import pytest

pytestmark = pytest.mark.api_flow

DOCS = "/api/v1/documents/"


def _create(api_client, user, title, content=""):
    return api_client.create_document(user, title, content)


def test_document_lifecycle_create_edit_delete(api_client):
    user = api_client.register_user("docs-qa-life")
    h = user.auth_headers
    doc = _create(api_client, user, f"QA lifecycle {api_client.run_id}", "one two")
    assert doc["owner_id"] == user.id and doc["version"] == 1

    r = api_client.client.patch(f"{DOCS}{doc['id']}", headers=h, json={"title": "Renamed"})
    assert r.status_code == 200 and r.json()["title"] == "Renamed"
    r = api_client.client.patch(f"{DOCS}{doc['id']}", headers=h, json={"content": "<p>a b c</p>"})
    assert r.status_code == 200 and r.json()["version"] == 3

    r = api_client.client.get(f"{DOCS}{doc['id']}", headers=h)
    assert r.json()["content"] == "<p>a b c</p>"

    assert api_client.client.delete(f"{DOCS}{doc['id']}", headers=h).status_code == 204
    assert api_client.client.get(f"{DOCS}{doc['id']}", headers=h).status_code == 404
    listing = api_client.client.get(DOCS, headers=h).json()
    assert all(item["id"] != doc["id"] for item in listing["items"])


def test_documents_require_authentication(api_client):
    assert api_client.client.get(DOCS).status_code == 401
    r = api_client.client.post(DOCS, json={"title": "anon"})
    assert r.status_code == 401


def test_create_validates_title(api_client):
    user = api_client.register_user("docs-qa-valid")
    r = api_client.client.post(DOCS, headers=user.auth_headers, json={"title": ""})
    assert r.status_code == 422


def test_cross_user_document_access_denied(api_client):
    alice = api_client.register_user("docs-qa-alice")
    bob = api_client.register_user("docs-qa-bob")
    doc = _create(api_client, alice, "Alice only")
    b = bob.auth_headers
    assert api_client.client.get(f"{DOCS}{doc['id']}", headers=b).status_code == 403
    r = api_client.client.patch(f"{DOCS}{doc['id']}", headers=b, json={"title": "x"})
    assert r.status_code == 403
    assert api_client.client.delete(f"{DOCS}{doc['id']}", headers=b).status_code == 403
    assert api_client.client.get(f"{DOCS}{doc['id']}/versions", headers=b).status_code == 403
    assert api_client.client.post(f"{DOCS}{doc['id']}/share", headers=b).status_code == 403


def test_versions_history_and_restore(api_client):
    user = api_client.register_user("docs-qa-ver")
    h = user.auth_headers
    doc = _create(api_client, user, "History", "first draft")
    api_client.client.patch(f"{DOCS}{doc['id']}", headers=h, json={"content": "second draft"})
    versions = api_client.client.get(f"{DOCS}{doc['id']}/versions", headers=h).json()
    assert [v["version_number"] for v in versions] == [1, 2]
    r = api_client.client.post(
        f"{DOCS}{doc['id']}/versions/{versions[0]['id']}/restore", headers=h
    )
    assert r.status_code == 200
    assert r.json()["content"] == "first draft" and r.json()["version"] == 3
    r = api_client.client.post(f"{DOCS}{doc['id']}/versions/{uuid.uuid4()}/restore", headers=h)
    assert r.status_code == 404


def test_list_pagination_with_size(api_client):
    user = api_client.register_user("docs-qa-page")
    for i in range(23):
        _create(api_client, user, f"Paged {i}")
    h = user.auth_headers
    p1 = api_client.client.get(DOCS, headers=h, params={"page": 1, "size": 20}).json()
    p2 = api_client.client.get(DOCS, headers=h, params={"page": 2, "size": 20}).json()
    assert p1["total"] == 23 and p1["pages"] == 2
    assert len(p1["items"]) == 20 and len(p2["items"]) == 3
    assert not {d["id"] for d in p1["items"]} & {d["id"] for d in p2["items"]}


def test_list_title_filter(api_client):
    user = api_client.register_user("docs-qa-filter")
    _create(api_client, user, "Quarterly report")
    _create(api_client, user, "Grocery list")
    r = api_client.client.get(DOCS, headers=user.auth_headers, params={"title": "report"})
    assert r.status_code == 200
    assert [d["title"] for d in r.json()["items"]] == ["Quarterly report"]


def test_templates_create_list_and_instantiate(api_client):
    user = api_client.register_user("docs-qa-tmpl")
    h = user.auth_headers
    name = f"QA template {api_client.run_id}-{uuid.uuid4().hex[:6]}"
    r = api_client.client.post(
        "/api/v1/templates/",
        headers=h,
        json={"name": name, "content": "## Agenda", "created_by": user.id},
    )
    assert r.status_code == 201, r.text
    template = r.json()
    names = [t["name"] for t in api_client.client.get("/api/v1/templates/", headers=h).json()]
    assert name in names
    r = api_client.client.post(
        f"{DOCS}from-template/{template['id']}",
        headers=h,
        json={"title": "From template", "owner_id": user.id},
    )
    assert r.status_code == 201, r.text
    api_client.created_documents.append(r.json()["id"])
    assert r.json()["content"] == "## Agenda"


def test_comments_add_list_delete(api_client):
    user = api_client.register_user("docs-qa-cmt")
    h = user.auth_headers
    doc = _create(api_client, user, "Commented")
    r = api_client.client.post(
        f"{DOCS}{doc['id']}/comments", headers=h, json={"author_id": user.id, "content": "LGTM"}
    )
    assert r.status_code == 201
    comment = r.json()
    listed = api_client.client.get(f"{DOCS}{doc['id']}/comments", headers=h).json()
    assert [c["content"] for c in listed] == ["LGTM"]
    r = api_client.client.delete(f"{DOCS}{doc['id']}/comments/{comment['id']}", headers=h)
    assert r.status_code == 204
    assert api_client.client.get(f"{DOCS}{doc['id']}/comments", headers=h).json() == []


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[REAL] client sends pageSize but document-service reads size",
    strict=True,
)
def test_list_honours_client_page_size_param(api_client):
    user = api_client.register_user("docs-qa-pagesize")
    for i in range(22):
        _create(api_client, user, f"Bulk {i}")
    r = api_client.client.get(DOCS, headers=user.auth_headers, params={"page": 1, "pageSize": 50})
    assert len(r.json()["items"]) == 22


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[REAL] list honours ?owner_id= from any caller",
    strict=True,
)
def test_list_owner_id_param_cannot_read_other_users(api_client):
    alice = api_client.register_user("docs-qa-own-a")
    bob = api_client.register_user("docs-qa-own-b")
    _create(api_client, alice, "Alice private list")
    r = api_client.client.get(DOCS, headers=bob.auth_headers, params={"owner_id": alice.id})
    assert all(d["owner_id"] == bob.id for d in r.json()["items"])


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[REAL] /documents/search is not owner-scoped",
    strict=True,
)
def test_search_is_owner_scoped(api_client):
    alice = api_client.register_user("docs-qa-srch-a")
    bob = api_client.register_user("docs-qa-srch-b")
    marker = f"zz{uuid.uuid4().hex[:10]}"
    _create(api_client, alice, f"Secret {marker}")
    r = api_client.client.get(f"{DOCS}search", headers=bob.auth_headers, params={"q": marker})
    assert r.status_code == 200 and r.json()["total"] == 0


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[REAL] create trusts body owner_id over JWT subject",
    strict=True,
)
def test_create_cannot_assign_other_owner(api_client):
    alice = api_client.register_user("docs-qa-body-a")
    bob = api_client.register_user("docs-qa-body-b")
    r = api_client.client.post(
        DOCS, headers=bob.auth_headers, json={"title": "planted", "owner_id": alice.id}
    )
    api_client.created_documents.append(r.json()["id"])
    assert r.json()["owner_id"] == bob.id


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[REAL] comment routes have no authz and trust body author_id",
    strict=True,
)
def test_comment_on_foreign_document_forbidden(api_client):
    alice = api_client.register_user("docs-qa-cm-a")
    bob = api_client.register_user("docs-qa-cm-b")
    doc = _create(api_client, alice, "Alice comments")
    r = api_client.client.post(
        f"{DOCS}{doc['id']}/comments",
        headers=bob.auth_headers,
        json={"author_id": alice.id, "content": "spoofed"},
    )
    assert r.status_code in (401, 403)


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[PLANTED] OW-SEC-401 SQL injection in list title filter",
    strict=True,
)
def test_title_filter_is_not_injectable(api_client):
    user = api_client.register_user("docs-qa-sqli")
    r = api_client.client.get(DOCS, headers=user.auth_headers, params={"title": "'"})
    assert r.status_code == 200 and r.json()["total"] == 0


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[PLANTED] OW-SEC-402 path traversal in /documents/exports",
    strict=True,
)
def test_export_archive_rejects_traversal(api_client):
    user = api_client.register_user("docs-qa-trav")
    r = api_client.client.get(
        f"{DOCS}exports", headers=user.auth_headers, params={"name": "../../../../etc/hostname"}
    )
    assert r.status_code == 404


@pytest.mark.gap_revealer
@pytest.mark.xfail(
    reason="[PLANTED] OW-SEC-403 share token is a short unkeyed MD5 digest",
    strict=True,
)
def test_share_token_is_not_a_short_digest(api_client):
    user = api_client.register_user("docs-qa-share")
    doc = _create(api_client, user, "Shared")
    r = api_client.client.post(f"{DOCS}{doc['id']}/share", headers=user.auth_headers)
    assert r.status_code == 200
    assert len(r.json()["token"]) >= 32

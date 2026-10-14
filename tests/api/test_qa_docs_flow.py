"""QA black-box API checks for the docs area, run through the API gateway."""

import hashlib
import uuid

import pytest

pytestmark = pytest.mark.api_flow

DOCS = "/api/v1/documents"


def _get(api_client, user, document_id):
    return api_client.client.get(f"{DOCS}/{document_id}", headers=user.auth_headers)


def _list_ids(api_client, user, **params):
    response = api_client.client.get(
        f"{DOCS}/", headers=user.auth_headers, params={"size": 100, **params}
    )
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_create_open_and_list_document(api_client):
    user = api_client.register_user("qa-docs-create")
    doc = api_client.create_document(user, f"QA Create {api_client.run_id}", "alpha beta")

    assert doc["owner_id"] == user.id
    assert doc["version"] == 1
    assert doc["word_count"] == 2
    assert doc["is_deleted"] is False

    opened = _get(api_client, user, doc["id"])
    assert opened.status_code == 200, opened.text
    assert opened.json()["content"] == "alpha beta"
    assert doc["id"] in _list_ids(api_client, user)


def test_rich_text_html_autosave_round_trips(api_client):
    user = api_client.register_user("qa-docs-autosave")
    doc = api_client.create_document(user, "QA Autosave", "")
    html = "<h1>Heading</h1><p><strong>bold</strong> and <em>italic</em></p><ul><li>item</li></ul>"

    saved = api_client.client.patch(
        f"{DOCS}/{doc['id']}", headers=user.auth_headers, json={"content": html}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == 2

    reopened = _get(api_client, user, doc["id"]).json()
    assert reopened["content"] == html
    assert reopened["title"] == "QA Autosave"


def test_rename_keeps_content_and_records_version(api_client):
    user = api_client.register_user("qa-docs-rename")
    doc = api_client.create_document(user, "Before Rename", "keep me")

    renamed = api_client.client.patch(
        f"{DOCS}/{doc['id']}", headers=user.auth_headers, json={"title": "After Rename"}
    )
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body["title"] == "After Rename"
    assert body["content"] == "keep me"

    versions = api_client.client.get(
        f"{DOCS}/{doc['id']}/versions", headers=user.auth_headers
    ).json()
    assert [v["title"] for v in versions][-1] == "After Rename"


def test_blank_title_rename_is_rejected(api_client):
    user = api_client.register_user("qa-docs-blank")
    doc = api_client.create_document(user, "Has Title", "x")

    response = api_client.client.patch(
        f"{DOCS}/{doc['id']}", headers=user.auth_headers, json={"title": ""}
    )
    assert response.status_code == 422, response.text
    assert _get(api_client, user, doc["id"]).json()["title"] == "Has Title"


def test_version_history_and_restore(api_client):
    user = api_client.register_user("qa-docs-history")
    doc = api_client.create_document(user, "QA History", "first draft")
    for content in ("second draft", "third draft"):
        response = api_client.client.patch(
            f"{DOCS}/{doc['id']}", headers=user.auth_headers, json={"content": content}
        )
        assert response.status_code == 200, response.text

    versions = api_client.client.get(f"{DOCS}/{doc['id']}/versions", headers=user.auth_headers)
    assert versions.status_code == 200, versions.text
    history = versions.json()
    assert [v["version_number"] for v in history] == [1, 2, 3]
    first = history[0]

    restored = api_client.client.post(
        f"{DOCS}/{doc['id']}/versions/{first['id']}/restore", headers=user.auth_headers
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["content"] == "first draft"
    assert restored.json()["version"] == 4


def test_delete_removes_from_open_and_list(api_client):
    user = api_client.register_user("qa-docs-delete")
    doc = api_client.create_document(user, "QA Delete Me", "bye")

    deleted = api_client.client.delete(f"{DOCS}/{doc['id']}", headers=user.auth_headers)
    assert deleted.status_code in (200, 204), deleted.text
    assert _get(api_client, user, doc["id"]).status_code == 404
    assert doc["id"] not in _list_ids(api_client, user)


def test_list_sort_and_pagination(api_client):
    user = api_client.register_user("qa-docs-list")
    for title in ("Bravo", "Alpha", "Charlie"):
        api_client.create_document(user, title, "x")

    response = api_client.client.get(
        f"{DOCS}/",
        headers=user.auth_headers,
        params={"sort": "title", "direction": "asc", "page": 1, "size": 2},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["pages"] == 2
    assert [item["title"] for item in body["items"]] == ["Alpha", "Bravo"]


def test_title_filter_is_case_insensitive(api_client):
    user = api_client.register_user("qa-docs-filter")
    api_client.create_document(user, "Quarterly Roadmap", "x")
    api_client.create_document(user, "Standup Notes", "x")

    response = api_client.client.get(
        f"{DOCS}/", headers=user.auth_headers, params={"title": "ROADMAP"}
    )
    assert response.status_code == 200, response.text
    assert [item["title"] for item in response.json()["items"]] == ["Quarterly Roadmap"]


def test_title_filter_with_apostrophe_is_literal(api_client):
    user = api_client.register_user("qa-docs-quote")
    api_client.create_document(user, "Otter's Guide", "x")

    response = api_client.client.get(
        f"{DOCS}/", headers=user.auth_headers, params={"title": "Otter's"}
    )
    assert response.status_code == 200, response.text
    assert [item["title"] for item in response.json()["items"]] == ["Otter's Guide"]


def test_title_filter_cannot_be_used_for_sql_injection(api_client):
    victim = api_client.register_user("qa-docs-sqli-victim")
    api_client.create_document(victim, f"Victim Secret {api_client.run_id}", "classified")
    attacker = api_client.register_user("qa-docs-sqli-attacker")

    response = api_client.client.get(
        f"{DOCS}/",
        headers=attacker.auth_headers,
        params={"title": "zzz') OR ('1'='1"},
    )
    titles = [item["title"] for item in response.json().get("items", [])]
    assert f"Victim Secret {api_client.run_id}" not in titles, "title filter is injectable"


def test_other_user_cannot_open_edit_or_delete(api_client):
    owner = api_client.register_user("qa-docs-owner")
    intruder = api_client.register_user("qa-docs-intruder")
    doc = api_client.create_document(owner, "Private", "owner only")
    path = f"{DOCS}/{doc['id']}"

    assert api_client.client.get(path, headers=intruder.auth_headers).status_code in (403, 404)
    patch = api_client.client.patch(path, headers=intruder.auth_headers, json={"title": "pwn"})
    assert patch.status_code in (403, 404)
    delete = api_client.client.delete(path, headers=intruder.auth_headers)
    assert delete.status_code in (403, 404)
    assert _get(api_client, owner, doc["id"]).json()["title"] == "Private"


def test_unauthenticated_document_access_is_rejected(api_client):
    owner = api_client.register_user("qa-docs-anon")
    doc = api_client.create_document(owner, "Anon Check", "x")

    assert api_client.client.get(f"{DOCS}/{doc['id']}").status_code == 401
    assert api_client.client.get(f"{DOCS}/").status_code == 401


def test_list_owner_id_param_cannot_read_other_users_documents(api_client):
    owner = api_client.register_user("qa-docs-list-owner")
    other = api_client.register_user("qa-docs-list-other")
    doc = api_client.create_document(owner, "Owner Only List", "x")

    leaked = _list_ids(api_client, other, owner_id=owner.id)
    assert doc["id"] not in leaked, "owner_id query param bypasses ownership"


def test_search_finds_own_document_but_not_others(api_client):
    owner = api_client.register_user("qa-docs-search-owner")
    other = api_client.register_user("qa-docs-search-other")
    marker = f"qamarker{uuid.uuid4().hex[:8]}"
    doc = api_client.create_document(owner, f"Search {marker}", "body")

    own = api_client.client.get(f"{DOCS}/search", headers=owner.auth_headers, params={"q": marker})
    assert own.status_code == 200, own.text
    assert doc["id"] in [item["id"] for item in own.json()["items"]]

    foreign = api_client.client.get(
        f"{DOCS}/search", headers=other.auth_headers, params={"q": marker}
    )
    assert doc["id"] not in [item["id"] for item in foreign.json()["items"]], (
        "search returns other users' documents"
    )


def test_search_percent_is_literal(api_client):
    user = api_client.register_user("qa-docs-search-pct")
    marker = uuid.uuid4().hex[:8]
    api_client.create_document(user, f"100% done {marker}", "x")
    api_client.create_document(user, f"1000 done {marker}", "x")

    response = api_client.client.get(
        f"{DOCS}/search", headers=user.auth_headers, params={"q": f"0% done {marker}"}
    )
    assert response.status_code == 200, response.text
    assert [item["title"] for item in response.json()["items"]] == [f"100% done {marker}"]


@pytest.mark.parametrize("fmt,needle", [("html", "<"), ("markdown", "QA Export")])
def test_export_formats(api_client, fmt, needle):
    user = api_client.register_user(f"qa-docs-export-{fmt}")
    doc = api_client.create_document(user, "QA Export", "exported body")

    response = api_client.client.get(
        f"{DOCS}/{doc['id']}/export", headers=user.auth_headers, params={"format": fmt}
    )
    assert response.status_code == 200, response.text
    assert needle in response.text
    assert "exported body" in response.text


def test_share_link_grants_read_access_to_another_user(api_client):
    owner = api_client.register_user("qa-docs-share")
    recipient = api_client.register_user("qa-docs-share-recipient")
    doc = api_client.create_document(owner, "QA Share", "shared body")

    minted = api_client.client.post(f"{DOCS}/{doc['id']}/share", headers=owner.auth_headers)
    assert minted.status_code == 200, minted.text
    token = minted.json()["token"]

    shared = api_client.client.get(
        f"{DOCS}/shared",
        headers=recipient.auth_headers,
        params={"document_id": doc["id"], "token": token},
    )
    assert shared.status_code == 200, shared.text
    assert shared.json()["content"] == "shared body"

    bad = api_client.client.get(
        f"{DOCS}/shared",
        headers=recipient.auth_headers,
        params={"document_id": doc["id"], "token": "nope"},
    )
    assert bad.status_code == 403


@pytest.mark.gap_revealer
def test_share_link_works_without_login(api_client):
    owner = api_client.register_user("qa-docs-share-anon")
    doc = api_client.create_document(owner, "QA Share Anon", "public body")
    token = api_client.client.post(f"{DOCS}/{doc['id']}/share", headers=owner.auth_headers).json()[
        "token"
    ]

    shared = api_client.client.get(
        f"{DOCS}/shared", params={"document_id": doc["id"], "token": token}
    )
    assert shared.status_code == 200, shared.text


def test_share_token_is_not_forgeable_from_document_id(api_client):
    owner = api_client.register_user("qa-docs-share-forge")
    attacker = api_client.register_user("qa-docs-share-attacker")
    doc = api_client.create_document(owner, "QA Forge", "secret body")

    forged = hashlib.md5(f"{doc['id']}:otterworks-share".encode()).hexdigest()[:16]
    response = api_client.client.get(
        f"{DOCS}/shared",
        headers=attacker.auth_headers,
        params={"document_id": doc["id"], "token": forged},
    )
    assert response.status_code == 403, "share token is md5(id + default salt) and forgeable"


def test_export_archive_rejects_path_traversal(api_client):
    user = api_client.register_user("qa-docs-export-archive")
    response = api_client.client.get(
        f"{DOCS}/exports",
        headers=user.auth_headers,
        params={"name": "../../../../etc/passwd"},
    )
    assert "root:" not in response.text, "export archive reads arbitrary files"


def test_margins_endpoint_returns_rows(api_client):
    user = api_client.register_user("qa-docs-margins")
    response = api_client.client.get("/api/v1/analytics/margins", headers=user.auth_headers)
    api_client.assert_gateway_route_available(response, "/api/v1/analytics/margins")
    assert response.status_code == 200, response.text
    body = response.json()
    assert {"as_of_date", "kpis", "rows"} <= body.keys()
    assert isinstance(body["rows"], list)
    assert body["rows"], "margins page would render empty"

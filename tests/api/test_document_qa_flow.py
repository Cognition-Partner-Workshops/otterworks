"""Docs-area QA flows through the API gateway.

Planted security labs (OW-SEC-401 SQL injection, OW-SEC-402 path traversal) are
non-strict xfail so remediation branches are not blocked. ``gap_revealer`` tests
marked [REAL] expose genuine defects and are left failing.
"""

import pytest


pytestmark = pytest.mark.api_flow

PLANTED_SQLI = "[PLANTED] OW-SEC-401: document filter SQL is string-interpolated"
PLANTED_TRAVERSAL = "[PLANTED] OW-SEC-402: export archive path is not contained"


def _doc_url(document_id: str, suffix: str = "") -> str:
    return f"/api/v1/documents/{document_id}{suffix}"


def _list(api_client, user, **params):
    response = api_client.client.get("/api/v1/documents", headers=user.auth_headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_editor_journey_create_autosave_rename_reload_delete(api_client):
    user = api_client.register_user("docs-qa-editor")
    headers = user.auth_headers

    created = api_client.client.post(
        "/api/v1/documents",
        headers=headers,
        json={"title": "Untitled document", "parentId": None},
    )
    assert created.status_code == 201, created.text
    document = created.json()
    api_client.created_documents.append(document["id"])
    assert document["owner_id"] == user.id
    assert document["content"] == ""

    drafts = ["<p>Otter</p>", "<p>Otter notes</p>", "<p>Otter notes autosaved</p>"]
    for expected_version, draft in enumerate(drafts, start=2):
        saved = api_client.client.patch(
            _doc_url(document["id"]), headers=headers, json={"content": draft}
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["version"] == expected_version

    renamed = api_client.client.patch(
        _doc_url(document["id"]), headers=headers, json={"title": f"QA Notes {api_client.run_id}"}
    )
    assert renamed.status_code == 200, renamed.text

    reloaded = api_client.client.get(_doc_url(document["id"]), headers=headers).json()
    assert reloaded["title"] == f"QA Notes {api_client.run_id}"
    assert reloaded["content"] == drafts[-1]
    assert reloaded["word_count"] == 3
    assert reloaded["version"] == 5

    versions = api_client.client.get(_doc_url(document["id"], "/versions"), headers=headers)
    assert [v["version_number"] for v in versions.json()] == [1, 2, 3, 4, 5]

    listing = _list(api_client, user)
    assert listing["items"][0]["id"] == document["id"]
    assert listing["items"][0]["title"] == reloaded["title"]

    deleted = api_client.client.delete(_doc_url(document["id"]), headers=headers)
    assert deleted.status_code == 204
    assert all(item["id"] != document["id"] for item in _list(api_client, user)["items"])
    assert api_client.client.get(_doc_url(document["id"]), headers=headers).status_code == 404


def test_list_is_scoped_to_caller_and_ordered_by_recent_edit(api_client):
    owner = api_client.register_user("docs-qa-list-a")
    other = api_client.register_user("docs-qa-list-b")
    first = api_client.create_document(owner, "First", "a")
    second = api_client.create_document(owner, "Second", "b")
    api_client.create_document(other, "Not mine", "c")

    items = _list(api_client, owner)["items"]
    assert [item["id"] for item in items] == [second["id"], first["id"]]

    api_client.client.patch(_doc_url(first["id"]), headers=owner.auth_headers, json={"content": "z"})
    items = _list(api_client, owner)["items"]
    assert [item["id"] for item in items] == [first["id"], second["id"]]


def test_list_filters_and_sorting_legit_path(api_client):
    user = api_client.register_user("docs-qa-filter")
    for title in ["Roadmap Bravo", "Roadmap Alpha", "Minutes"]:
        api_client.create_document(user, title, "body")

    filtered = _list(api_client, user, title="roadmap", sort="title", direction="asc")
    assert [item["title"] for item in filtered["items"]] == ["Roadmap Alpha", "Roadmap Bravo"]
    assert filtered["total"] == 2

    paged = _list(api_client, user, page=2, size=2)
    assert paged["pages"] == 2
    assert len(paged["items"]) == 1


def test_export_formats(api_client):
    user = api_client.register_user("docs-qa-export")
    document = api_client.create_document(user, "Export <b>me</b>", "line & more")
    cases = {
        "markdown": ("text/markdown", "# Export <b>me</b>\n\nline & more"),
        "pdf": ("application/pdf", "TITLE: Export <b>me</b>\n\nline & more"),
    }
    for fmt, (content_type, body) in cases.items():
        response = api_client.client.get(
            _doc_url(document["id"], "/export"), headers=user.auth_headers, params={"format": fmt}
        )
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(content_type)
        assert response.text == body

    html = api_client.client.get(
        _doc_url(document["id"], "/export"), headers=user.auth_headers, params={"format": "html"}
    )
    assert html.status_code == 200
    assert "<b>" not in html.text
    assert "&lt;b&gt;me&lt;/b&gt;" in html.text


def test_templates_list_and_instantiate(api_client):
    user = api_client.register_user("docs-qa-template")
    name = f"QA Template {api_client.run_id}"
    template = api_client.client.post(
        "/api/v1/templates/",
        headers=user.auth_headers,
        json={"name": name, "content": "## Agenda", "created_by": user.id},
    )
    assert template.status_code == 201, template.text
    template_id = template.json()["id"]

    templates = api_client.client.get("/api/v1/templates/", headers=user.auth_headers)
    assert templates.status_code == 200
    assert any(t["id"] == template_id for t in templates.json())

    created = api_client.client.post(
        f"/api/v1/documents/from-template/{template_id}",
        headers=user.auth_headers,
        json={"title": "Weekly sync", "owner_id": user.id},
    )
    assert created.status_code == 201, created.text
    document = created.json()
    api_client.created_documents.append(document["id"])
    assert document["content"] == "## Agenda"
    assert any(item["id"] == document["id"] for item in _list(api_client, user)["items"])

    missing = api_client.client.post(
        "/api/v1/documents/from-template/00000000-0000-0000-0000-000000000000",
        headers=user.auth_headers,
        json={"title": "x", "owner_id": user.id},
    )
    assert missing.status_code == 404


def test_cross_user_writes_are_forbidden(api_client):
    owner = api_client.register_user("docs-qa-owner")
    intruder = api_client.register_user("docs-qa-intruder")
    document = api_client.create_document(owner, "Owner only", "private")
    attempts = [
        ("PUT", "", {"title": "pwned", "content": ""}),
        ("PATCH", "", {"title": "pwned"}),
        ("DELETE", "", None),
        ("GET", "/versions", None),
        ("GET", "/export", None),
        ("POST", "/share", None),
    ]
    for method, suffix, body in attempts:
        response = api_client.client.request(
            method, _doc_url(document["id"], suffix), headers=intruder.auth_headers, json=body
        )
        assert response.status_code == 403, f"{method} {suffix}: {response.status_code}"

    unchanged = api_client.client.get(_doc_url(document["id"]), headers=owner.auth_headers).json()
    assert unchanged["title"] == "Owner only"


def test_document_routes_require_authentication(api_client):
    user = api_client.register_user("docs-qa-unauth")
    document = api_client.create_document(user, "Locked", "x")
    for method, path in [
        ("GET", "/api/v1/documents"),
        ("GET", _doc_url(document["id"])),
        ("PATCH", _doc_url(document["id"])),
        ("DELETE", _doc_url(document["id"])),
        ("GET", "/api/v1/templates/"),
    ]:
        response = api_client.client.request(method, path, json={} if method == "PATCH" else None)
        assert response.status_code == 401, f"{method} {path}: {response.status_code}"


def test_search_matches_wildcards_literally(api_client):
    user = api_client.register_user("docs-qa-wild")
    token = api_client.run_id
    hit = api_client.create_document(user, f"{token} 100% done", "x")
    api_client.create_document(user, f"{token} 1000 done", "x")
    response = api_client.client.get(
        "/api/v1/documents/search", headers=user.auth_headers, params={"q": f"{token} 100%"}
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [hit["id"]]


@pytest.mark.xfail(reason=PLANTED_SQLI, strict=False)
def test_title_filter_quote_is_not_interpreted_as_sql(api_client):
    user = api_client.register_user("docs-qa-sqli")
    api_client.create_document(user, "O'Brien notes", "x")
    response = api_client.client.get(
        "/api/v1/documents", headers=user.auth_headers, params={"title": "O'Brien"}
    )
    assert response.status_code == 200, response.text
    assert [item["title"] for item in response.json()["items"]] == ["O'Brien notes"]


@pytest.mark.xfail(reason=PLANTED_SQLI, strict=False)
def test_filter_errors_do_not_leak_sql(api_client):
    user = api_client.register_user("docs-qa-sqli-err")
    response = api_client.client.get(
        "/api/v1/documents", headers=user.auth_headers, params={"title": "'"}
    )
    assert "SELECT" not in response.text
    assert "asyncpg" not in response.text


@pytest.mark.xfail(reason=PLANTED_TRAVERSAL, strict=False)
def test_exports_endpoint_does_not_serve_files_outside_archive(api_client):
    user = api_client.register_user("docs-qa-traversal")
    response = api_client.client.get(
        "/api/v1/documents/exports",
        headers=user.auth_headers,
        params={"name": "../../../../etc/passwd"},
    )
    assert response.status_code in {400, 403, 404}
    assert "root:" not in response.text


@pytest.mark.gap_revealer
def test_owner_id_param_cannot_list_another_users_documents(api_client):
    """[REAL] ?owner_id= overrides the caller's JWT identity on the list endpoint."""
    owner = api_client.register_user("docs-qa-idor-a")
    intruder = api_client.register_user("docs-qa-idor-b")
    document = api_client.create_document(owner, "Payroll draft", "salary data")
    response = api_client.client.get(
        "/api/v1/documents", headers=intruder.auth_headers, params={"owner_id": owner.id}
    )
    assert response.status_code in {200, 403}
    if response.status_code == 200:
        assert all(item["id"] != document["id"] for item in response.json()["items"])


@pytest.mark.gap_revealer
def test_search_does_not_return_other_users_documents(api_client):
    """[REAL] /documents/search ignores ownership and returns every user's matches."""
    owner = api_client.register_user("docs-qa-search-a")
    intruder = api_client.register_user("docs-qa-search-b")
    marker = f"confidential-{api_client.run_id}"
    document = api_client.create_document(owner, marker, "secret")
    response = api_client.client.get(
        "/api/v1/documents/search", headers=intruder.auth_headers, params={"q": marker}
    )
    assert response.status_code == 200
    assert all(item["id"] != document["id"] for item in response.json()["items"])


@pytest.mark.gap_revealer
def test_client_page_size_param_is_honoured(api_client):
    """[REAL] the web client sends pageSize=50 but the service only reads size (default 20)."""
    user = api_client.register_user("docs-qa-pagesize")
    for i in range(21):
        api_client.create_document(user, f"Doc {i:02d}", "")
    data = _list(api_client, user, page=1, pageSize=50)
    assert data["total"] == 21
    assert len(data["items"]) == 21

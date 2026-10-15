"""QA coverage for the document lifecycle: authenticated CRUD, autosave, rename,
delete, listing, templates and export.

Tests that exercise a planted security lab (see security/equivalence/findings.yaml)
are marked non-strict ``xfail`` so they never block a remediation branch.
Docstrings starting with ``[REAL]`` mark genuine defects that are left failing.
"""

import os
import uuid

import jwt
import pytest
from httpx import AsyncClient

from app.services.document_service import DocumentService, _word_count
from app.services.export_archive import ExportArchive

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-pad32"  # noqa: S105
os.environ.setdefault("JWT_SECRET", TEST_JWT_SECRET)

PLANTED_SQLI = "[PLANTED] OW-SEC-401: document filter SQL is string-interpolated"
PLANTED_TRAVERSAL = "[PLANTED] OW-SEC-402: export archive path is not contained"


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    token = jwt.encode({"user_id": str(user_id)}, os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


async def _create(
    client: AsyncClient, user_id: uuid.UUID, title: str = "Doc", content: str = "", **extra
):
    resp = await client.post(
        "/api/v1/documents/",
        headers=_auth(user_id),
        json={"title": title, "content": content, **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---- helpers ----


@pytest.mark.parametrize(
    ("text", "expected"),
    [("", 0), ("one", 1), ("  two   words ", 2), ("line\nbreak\ttab", 3)],
)
def test_word_count(text: str, expected: int):
    assert _word_count(text) == expected


@pytest.mark.parametrize(
    ("total", "page", "size", "expected"),
    [(0, 1, 20, 1), (20, 1, 20, 1), (21, 1, 20, 2), (5, 1, 2, 3), (5, 1, 0, 1)],
)
def test_paginate(total: int, page: int, size: int, expected: int):
    assert DocumentService.paginate(total, page, size) == expected


# ---- create ----


@pytest.mark.asyncio
async def test_create_owner_comes_from_jwt(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Owned", "hello there")
    assert doc["owner_id"] == str(owner_id)
    assert doc["version"] == 1
    assert doc["word_count"] == 2
    assert doc["content_type"] == "text/markdown"
    assert doc["is_deleted"] is False


@pytest.mark.asyncio
async def test_create_without_trailing_slash_accepts_frontend_payload(
    client: AsyncClient, owner_id: uuid.UUID
):
    resp = await client.post(
        "/api/v1/documents",
        headers=_auth(owner_id),
        json={"title": "Untitled document", "parentId": None},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["content"] == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("title", ["", "x" * 501])
async def test_create_rejects_invalid_title(client: AsyncClient, owner_id: uuid.UUID, title: str):
    resp = await client.post("/api/v1/documents/", headers=_auth(owner_id), json={"title": title})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_accepts_max_length_title(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "x" * 500)
    assert len(doc["title"]) == 500


@pytest.mark.asyncio
async def test_create_rejects_invalid_jwt(client: AsyncClient):
    bad = jwt.encode(
        {"user_id": str(uuid.uuid4())}, "wrong-secret-wrong-secret-wrong-secret", algorithm="HS256"
    )
    resp = await client.post(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {bad}"},
        json={"title": "Nope"},
    )
    assert resp.status_code == 401


# ---- read / ownership ----


@pytest.mark.asyncio
async def test_get_requires_auth(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.get(f"/api/v1/documents/{doc['id']}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_owner_can_get(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Mine", "body")
    resp = await client.get(f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id))
    assert resp.status_code == 200
    assert resp.json()["title"] == "Mine"


@pytest.mark.asyncio
async def test_get_unknown_document_is_404(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}", headers=_auth(owner_id))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_malformed_id_is_422(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.get("/api/v1/documents/not-a-uuid", headers=_auth(owner_id))
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path_suffix", "body"),
    [
        ("GET", "", None),
        ("PUT", "", {"title": "Hijack", "content": "x"}),
        ("PATCH", "", {"title": "Hijack"}),
        ("DELETE", "", None),
        ("GET", "/versions", None),
        ("GET", "/export?format=markdown", None),
        ("POST", "/share", None),
    ],
)
async def test_non_owner_is_forbidden(
    client: AsyncClient, owner_id: uuid.UUID, method: str, path_suffix: str, body
):
    doc = await _create(client, owner_id, "Private", "secret")
    intruder = uuid.uuid4()
    resp = await client.request(
        method,
        f"/api/v1/documents/{doc['id']}{path_suffix}",
        headers=_auth(intruder),
        json=body,
    )
    assert resp.status_code == 403

    still_there = await client.get(f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id))
    assert still_there.json()["title"] == "Private"


# ---- edit / autosave / rename ----


@pytest.mark.asyncio
async def test_autosave_patches_bump_version_and_word_count(
    client: AsyncClient, owner_id: uuid.UUID
):
    doc = await _create(client, owner_id, "Draft")
    headers = _auth(owner_id)
    for i, content in enumerate(["<p>one</p>", "<p>one two</p>", "<p>one two three</p>"], start=2):
        resp = await client.patch(
            f"/api/v1/documents/{doc['id']}", headers=headers, json={"content": content}
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == i
        assert resp.json()["content"] == content
    assert resp.json()["word_count"] == 3

    versions = await client.get(f"/api/v1/documents/{doc['id']}/versions", headers=headers)
    assert [v["version_number"] for v in versions.json()] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_rename_keeps_content(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Old name", "keep me")
    resp = await client.patch(
        f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id), json={"title": "New name"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New name"
    assert data["content"] == "keep me"
    assert data["word_count"] == 2
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_empty_patch_does_not_create_version(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Stable")
    resp = await client.patch(f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id), json={})
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["title", "content", "content_type"])
async def test_patch_rejects_null_for_required_fields(
    client: AsyncClient, owner_id: uuid.UUID, field: str
):
    doc = await _create(client, owner_id)
    resp = await client.patch(
        f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id), json={field: None}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_rejects_empty_title(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.patch(
        f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id), json={"title": ""}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_clearing_content_resets_word_count(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Doc", "some words here")
    resp = await client.patch(
        f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id), json={"content": ""}
    )
    assert resp.json()["word_count"] == 0


@pytest.mark.asyncio
async def test_put_replaces_document_and_resets_omitted_fields(
    client: AsyncClient, owner_id: uuid.UUID, folder_id: uuid.UUID
):
    doc = await _create(
        client, owner_id, "Doc", "a", content_type="text/html", folder_id=str(folder_id)
    )
    resp = await client.put(
        f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id), json={"title": "Replaced"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Replaced"
    assert data["content"] == ""
    assert data["content_type"] == "text/markdown"
    assert data["folder_id"] is None
    assert data["version"] == 2


@pytest.mark.asyncio
async def test_restore_unknown_version_is_404(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.post(
        f"/api/v1/documents/{doc['id']}/versions/{uuid.uuid4()}/restore",
        headers=_auth(owner_id),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_appends_new_version(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "V1 title", "v1 body")
    headers = _auth(owner_id)
    await client.patch(
        f"/api/v1/documents/{doc['id']}", headers=headers, json={"title": "V2", "content": "v2"}
    )
    versions = (await client.get(f"/api/v1/documents/{doc['id']}/versions", headers=headers)).json()
    resp = await client.post(
        f"/api/v1/documents/{doc['id']}/versions/{versions[0]['id']}/restore", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert (data["title"], data["content"], data["version"]) == ("V1 title", "v1 body", 3)


# ---- delete ----


@pytest.mark.asyncio
async def test_delete_is_soft_and_hides_document(client: AsyncClient, owner_id: uuid.UUID):
    keep = await _create(client, owner_id, "Keep")
    gone = await _create(client, owner_id, "Gone")
    headers = _auth(owner_id)

    resp = await client.delete(f"/api/v1/documents/{gone['id']}", headers=headers)
    assert resp.status_code == 204

    assert (await client.get(f"/api/v1/documents/{gone['id']}", headers=headers)).status_code == 404
    assert (
        await client.delete(f"/api/v1/documents/{gone['id']}", headers=headers)
    ).status_code == 404
    listing = (await client.get("/api/v1/documents/", headers=headers)).json()
    assert [item["id"] for item in listing["items"]] == [keep["id"]]


@pytest.mark.asyncio
async def test_delete_requires_auth(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    assert (await client.delete(f"/api/v1/documents/{doc['id']}")).status_code == 401


# ---- list ----


@pytest.mark.asyncio
async def test_list_defaults_to_callers_documents(client: AsyncClient, owner_id: uuid.UUID):
    other = uuid.uuid4()
    await _create(client, owner_id, "Mine")
    await _create(client, other, "Theirs")
    resp = await client.get("/api/v1/documents", headers=_auth(owner_id))
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Mine"]


@pytest.mark.asyncio
async def test_list_is_newest_first(client: AsyncClient, owner_id: uuid.UUID):
    first = await _create(client, owner_id, "First")
    await _create(client, owner_id, "Second")
    await client.patch(
        f"/api/v1/documents/{first['id']}", headers=_auth(owner_id), json={"content": "touched"}
    )
    items = (await client.get("/api/v1/documents/", headers=_auth(owner_id))).json()["items"]
    assert items[0]["id"] == first["id"]


@pytest.mark.asyncio
async def test_list_filters_by_folder(
    client: AsyncClient, owner_id: uuid.UUID, folder_id: uuid.UUID
):
    await _create(client, owner_id, "In folder", folder_id=str(folder_id))
    await _create(client, owner_id, "Root")
    resp = await client.get(
        "/api/v1/documents/", headers=_auth(owner_id), params={"folder_id": str(folder_id)}
    )
    assert [item["title"] for item in resp.json()["items"]] == ["In folder"]


@pytest.mark.asyncio
async def test_list_excludes_template_backed_rows(
    client: AsyncClient, owner_id: uuid.UUID, db_session
):
    from app.models.document import Document

    db_session.add(Document(title="tmpl", content="", owner_id=owner_id, is_template=True))
    await db_session.commit()
    await _create(client, owner_id, "Real")
    items = (await client.get("/api/v1/documents/", headers=_auth(owner_id))).json()["items"]
    assert [item["title"] for item in items] == ["Real"]


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [0, 101])
async def test_list_rejects_out_of_range_page_size(
    client: AsyncClient, owner_id: uuid.UUID, size: int
):
    resp = await client.get("/api/v1/documents/", headers=_auth(owner_id), params={"size": size})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_sort_by_title_ascending(client: AsyncClient, owner_id: uuid.UUID):
    for title in ["Bravo", "Alpha", "Charlie"]:
        await _create(client, owner_id, title)
    resp = await client.get("/api/v1/documents/", params={"sort": "title", "direction": "asc"})
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["Alpha", "Bravo", "Charlie"]


@pytest.mark.asyncio
async def test_list_owner_id_param_cannot_read_another_users_documents(
    client: AsyncClient, owner_id: uuid.UUID
):
    """[REAL] ?owner_id= overrides the JWT identity, so any user can list anyone's documents."""
    await _create(client, owner_id, "Private", "secret body")
    intruder = uuid.uuid4()
    resp = await client.get(
        "/api/v1/documents/", headers=_auth(intruder), params={"owner_id": str(owner_id)}
    )
    assert resp.status_code in {200, 403}
    if resp.status_code == 200:
        assert resp.json()["items"] == []


# ---- search ----


@pytest.mark.asyncio
async def test_search_excludes_deleted(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Findable")
    await client.delete(f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id))
    resp = await client.get("/api/v1/documents/search", params={"q": "Findable"})
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_search_requires_query(client: AsyncClient):
    assert (await client.get("/api/v1/documents/search")).status_code == 422


# ---- export ----


@pytest.mark.asyncio
async def test_export_html_escapes_markup(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "<script>t</script>", "<img src=x onerror=alert(1)>")
    resp = await client.get(
        f"/api/v1/documents/{doc['id']}/export", headers=_auth(owner_id), params={"format": "html"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "<script>" not in resp.text
    assert "<img" not in resp.text
    assert "&lt;script&gt;" in resp.text


@pytest.mark.asyncio
async def test_export_pdf_returns_text_representation(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Report", "body")
    resp = await client.get(
        f"/api/v1/documents/{doc['id']}/export", headers=_auth(owner_id), params={"format": "pdf"}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/pdf")
    assert resp.text == "TITLE: Report\n\nbody"


@pytest.mark.asyncio
async def test_export_defaults_to_markdown(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id, "Notes", "- item")
    resp = await client.get(f"/api/v1/documents/{doc['id']}/export", headers=_auth(owner_id))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert resp.text == "# Notes\n\n- item"


@pytest.mark.asyncio
async def test_export_rejects_unknown_format(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    resp = await client.get(
        f"/api/v1/documents/{doc['id']}/export", headers=_auth(owner_id), params={"format": "docx"}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_of_deleted_document_is_404(client: AsyncClient, owner_id: uuid.UUID):
    doc = await _create(client, owner_id)
    await client.delete(f"/api/v1/documents/{doc['id']}", headers=_auth(owner_id))
    resp = await client.get(f"/api/v1/documents/{doc['id']}/export", headers=_auth(owner_id))
    assert resp.status_code == 404


# ---- templates ----


async def _template(client: AsyncClient, created_by: uuid.UUID, name: str, **extra):
    resp = await client.post(
        "/api/v1/templates/",
        json={"name": name, "content": f"{name} body", "created_by": str(created_by), **extra},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_templates_listed_by_name(client: AsyncClient, owner_id: uuid.UUID):
    for name in ["Weekly", "Agenda", "Retro"]:
        await _template(client, owner_id, name)
    resp = await client.get("/api/v1/templates/")
    assert [t["name"] for t in resp.json()] == ["Agenda", "Retro", "Weekly"]


@pytest.mark.asyncio
async def test_template_requires_name(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post("/api/v1/templates/", json={"name": "", "created_by": str(owner_id)})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_document_from_template_copies_content_and_type(
    client: AsyncClient, owner_id: uuid.UUID, folder_id: uuid.UUID
):
    tmpl = await _template(client, owner_id, "Spec", content_type="text/html")
    resp = await client.post(
        f"/api/v1/documents/from-template/{tmpl['id']}",
        json={"title": "My spec", "owner_id": str(owner_id), "folder_id": str(folder_id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert (data["title"], data["content"], data["content_type"]) == (
        "My spec",
        "Spec body",
        "text/html",
    )
    assert data["folder_id"] == str(folder_id)
    assert data["is_template"] is False

    listing = (await client.get("/api/v1/documents/", headers=_auth(owner_id))).json()
    assert [item["id"] for item in listing["items"]] == [data["id"]]


@pytest.mark.asyncio
async def test_document_from_unknown_template_is_404(client: AsyncClient, owner_id: uuid.UUID):
    resp = await client.post(
        f"/api/v1/documents/from-template/{uuid.uuid4()}",
        json={"title": "x", "owner_id": str(owner_id)},
    )
    assert resp.status_code == 404


# ---- planted security labs (OW-SEC-401 / OW-SEC-402) ----


@pytest.mark.asyncio
async def test_title_filter_with_quote_matches_literally(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "Plain")
    resp = await client.get("/api/v1/documents/", params={"title": "Plain"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PLANTED_SQLI, strict=False)
async def test_title_filter_quote_is_not_sql(client: AsyncClient, owner_id: uuid.UUID):
    await _create(client, owner_id, "O'Brien notes")
    resp = await client.get("/api/v1/documents/", params={"title": "O'Brien"})
    assert resp.status_code == 200
    assert [item["title"] for item in resp.json()["items"]] == ["O'Brien notes"]


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PLANTED_SQLI, strict=False)
async def test_title_filter_tautology_does_not_widen_results(
    client: AsyncClient, owner_id: uuid.UUID
):
    await _create(client, owner_id, "Visible")
    resp = await client.get("/api/v1/documents/", params={"title": "zzz%') OR 1=1 --"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PLANTED_SQLI, strict=False)
async def test_invalid_sort_is_rejected_without_leaking_sql(client: AsyncClient):
    resp = await client.get("/api/v1/documents/", params={"sort": "nope;--"})
    assert resp.status_code in {400, 422}
    assert "SELECT" not in resp.text


def test_export_archive_reads_nested_export(tmp_path):
    (tmp_path / "team").mkdir()
    (tmp_path / "team" / "plan.md").write_text("plan", encoding="utf-8")
    assert ExportArchive(base_dir=str(tmp_path)).read_export("team/plan.md") == "plan"


@pytest.mark.xfail(reason=PLANTED_TRAVERSAL, strict=False)
def test_export_archive_rejects_parent_traversal(tmp_path):
    root = tmp_path / "exports"
    root.mkdir()
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
    with pytest.raises((OSError, ValueError, PermissionError)):
        ExportArchive(base_dir=str(root)).read_export("../outside.txt")


@pytest.mark.asyncio
@pytest.mark.xfail(reason=PLANTED_TRAVERSAL, strict=False)
async def test_exports_endpoint_rejects_absolute_path(client: AsyncClient, tmp_path, monkeypatch):
    monkeypatch.setenv("EXPORT_ARCHIVE_DIR", str(tmp_path))
    secret = tmp_path.parent / "qa-outside-secret.txt"
    secret.write_text("outside", encoding="utf-8")
    resp = await client.get("/api/v1/documents/exports", params={"name": str(secret)})
    assert resp.status_code == 404

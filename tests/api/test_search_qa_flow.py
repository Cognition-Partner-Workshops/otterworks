"""Search area QA: indexing side effects, filters, scoping and known gaps.

Tests that expose a known defect are xfail with a [PLANTED]/[REAL] tag.
"""

import shutil
import subprocess
import uuid

import pytest

pytestmark = pytest.mark.api_flow

CHAOS_KEY = "chaos:search-service:suggest_500"


def _search(api_client, user, q, **params):
    response = api_client.client.get(
        "/api/v1/search/", headers=user.auth_headers, params={"q": q, **params}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _wait_total(api_client, user, q, predicate, description, **params):
    return api_client.poll_until(
        lambda: _search(api_client, user, q, **params),
        lambda body: predicate(body["total"]),
        description=description,
    )


def _upload(api_client, user, name):
    response = api_client.client.post(
        "/api/v1/files/upload", headers=user.auth_headers, files={"file": (name, b"otter")}
    )
    assert response.status_code == 201, response.text
    file_id = response.json()["file"]["id"]
    api_client.created_files.append(file_id)
    return file_id


def test_search_requires_authentication(api_client):
    response = api_client.client.get("/api/v1/search/", params={"q": "otter"})
    assert response.status_code == 401


def test_document_create_update_delete_reflected_in_search(api_client):
    user = api_client.register_user("search-qa-doc")
    tag = uuid.uuid4().hex[:10]
    document = api_client.create_document(user, f"Kelp Report {tag}", f"forecast {tag}")

    body = _wait_total(api_client, user, tag, lambda t: t >= 1, "document indexed")
    hit = body["results"][0]
    assert hit["id"] == document["id"]
    assert hit["type"] == "document"
    assert "<em>" in hit["content_snippet"]

    response = api_client.client.put(
        f"/api/v1/documents/{document['id']}",
        headers=user.auth_headers,
        json={"title": f"Seaweed Review {tag}", "content": f"updated {tag}"},
    )
    assert response.status_code == 200, response.text
    _wait_total(api_client, user, f"Seaweed {tag}", lambda t: t >= 1, "document reindexed")

    response = api_client.client.delete(f"/api/v1/documents/{document['id']}", headers=user.auth_headers)
    assert response.status_code == 204, response.text
    api_client.created_documents.remove(document["id"])
    _wait_total(api_client, user, tag, lambda t: t == 0, "document removed from index")


def test_file_upload_trash_restore_rename_delete_reflected_in_search(api_client):
    user = api_client.register_user("search-qa-file")
    tag = uuid.uuid4().hex[:10]
    file_id = _upload(api_client, user, f"otterfile-{tag}.txt")

    body = _wait_total(api_client, user, f"otterfile-{tag}", lambda t: t >= 1, "file indexed")
    assert body["results"][0]["type"] == "file"
    assert body["results"][0]["mime_type"] == "text/plain"

    assert api_client.client.post(f"/api/v1/files/{file_id}/trash", headers=user.auth_headers).status_code == 200
    _wait_total(api_client, user, f"otterfile-{tag}", lambda t: t == 0, "trashed file removed")

    assert api_client.client.post(f"/api/v1/files/{file_id}/restore", headers=user.auth_headers).status_code == 200
    _wait_total(api_client, user, f"otterfile-{tag}", lambda t: t >= 1, "restored file reindexed")

    response = api_client.client.patch(
        f"/api/v1/files/{file_id}/rename", headers=user.auth_headers, json={"name": f"renamed-{tag}.txt"}
    )
    assert response.status_code == 200, response.text
    _wait_total(api_client, user, f"renamed-{tag}", lambda t: t >= 1, "renamed file reindexed")

    assert api_client.client.delete(f"/api/v1/files/{file_id}", headers=user.auth_headers).status_code == 204
    api_client.created_files.remove(file_id)
    _wait_total(api_client, user, f"renamed-{tag}", lambda t: t == 0, "deleted file removed")


def test_type_filter_and_pagination(api_client):
    user = api_client.register_user("search-qa-filter")
    tag = uuid.uuid4().hex[:10]
    api_client.create_document(user, f"Filter Doc {tag}", "body")
    _upload(api_client, user, f"filter-{tag}.txt")
    _wait_total(api_client, user, tag, lambda t: t >= 2, "doc and file indexed")

    docs = _search(api_client, user, tag, type="document")
    files = _search(api_client, user, tag, type="file")
    assert {r["type"] for r in docs["results"]} == {"document"}
    assert {r["type"] for r in files["results"]} == {"file"}

    paged = _search(api_client, user, tag, page=1, size=1)
    assert paged["page_size"] == 1
    assert len(paged["results"]) == 1
    assert paged["total"] >= 2


def test_search_results_are_owner_scoped(api_client):
    owner = api_client.register_user("search-qa-owner")
    other = api_client.register_user("search-qa-other")
    tag = uuid.uuid4().hex[:10]
    api_client.create_document(owner, f"Private Plan {tag}", "secret")
    _wait_total(api_client, owner, tag, lambda t: t >= 1, "owner doc indexed")

    assert _search(api_client, other, tag)["total"] == 0
    assert _search(api_client, other, tag, owner_id=owner.id)["total"] == 0
    advanced = api_client.client.post(
        "/api/v1/search/advanced", headers=other.auth_headers, json={"q": tag, "owner_id": owner.id}
    )
    assert advanced.status_code == 200
    assert advanced.json()["total"] == 0


def test_suggest_returns_own_titles(api_client):
    user = api_client.register_user("search-qa-suggest")
    tag = uuid.uuid4().hex[:10]
    _upload(api_client, user, f"zq{tag}.txt")
    _wait_total(api_client, user, f"zq{tag}", lambda t: t >= 1, "file indexed")
    response = api_client.client.get("/api/v1/search/suggest", headers=user.auth_headers, params={"q": f"zq{tag}"})
    assert response.status_code == 200
    assert f"zq{tag}.txt" in response.json()["suggestions"]


@pytest.mark.xfail(strict=True, reason="[REAL] /suggest is not owner-scoped; leaks other users' titles")
def test_suggest_does_not_leak_other_users_titles(api_client):
    owner = api_client.register_user("search-qa-leak")
    other = api_client.register_user("search-qa-snoop")
    tag = uuid.uuid4().hex[:10]
    _upload(api_client, owner, f"leak{tag}.txt")
    _wait_total(api_client, owner, f"leak{tag}", lambda t: t >= 1, "file indexed")
    response = api_client.client.get("/api/v1/search/suggest", headers=other.auth_headers, params={"q": f"leak{tag}"})
    assert response.status_code == 200
    assert response.json()["suggestions"] == []


@pytest.mark.xfail(strict=True, reason="[REAL] /index/document trusts body owner_id (can plant results in another user's search)")
def test_index_document_cannot_target_another_owner(api_client):
    attacker = api_client.register_user("search-qa-attacker")
    victim = api_client.register_user("search-qa-victim")
    doc_id = str(uuid.uuid4())
    response = api_client.client.post(
        "/api/v1/search/index/document",
        headers=attacker.auth_headers,
        json={"id": doc_id, "title": f"Phish {doc_id}", "owner_id": victim.id},
    )
    if response.status_code == 201:
        api_client.indexed_documents.append(doc_id)
    assert response.status_code in (400, 403)


@pytest.mark.xfail(strict=True, reason="[REAL] DELETE /index/<type>/<id> has no ownership check")
def test_cannot_delete_another_users_index_entry(api_client):
    owner = api_client.register_user("search-qa-owner2")
    attacker = api_client.register_user("search-qa-attacker2")
    tag = uuid.uuid4().hex[:10]
    file_id = _upload(api_client, owner, f"keep-{tag}.txt")
    _wait_total(api_client, owner, f"keep-{tag}", lambda t: t >= 1, "file indexed")
    response = api_client.client.delete(f"/api/v1/search/index/file/{file_id}", headers=attacker.auth_headers)
    assert response.status_code in (403, 404)
    assert _search(api_client, owner, f"keep-{tag}")["total"] >= 1


@pytest.mark.xfail(strict=True, reason="[REAL] folders are never indexed; the UI Folders filter is always empty")
def test_new_folder_is_searchable(api_client):
    user = api_client.register_user("search-qa-folder")
    tag = uuid.uuid4().hex[:10]
    response = api_client.client.post(
        "/api/v1/folders", headers=user.auth_headers, json={"name": f"Folder{tag}", "owner_id": user.id}
    )
    assert response.status_code == 201, response.text
    api_client.created_folders.append(response.json()["id"])
    api_client.poll_until(
        lambda: _search(api_client, user, f"Folder{tag}")["total"],
        lambda total: total >= 1,
        timeout_seconds=8,
        description="folder indexed",
    )


def _redis(*args):
    return subprocess.run(
        ["docker", "exec", "otterworks-redis", "redis-cli", *args], capture_output=True, text=True, check=False
    )


@pytest.mark.xfail(strict=True, reason="[PLANTED] chaos flag search-suggest-500")
def test_suggest_survives_chaos_flag(api_client):
    if not shutil.which("docker") or _redis("PING").returncode != 0:
        pytest.skip("local otterworks-redis container not reachable")
    user = api_client.register_user("search-qa-chaos")
    _redis("SET", CHAOS_KEY, "1", "EX", "60")
    try:
        response = api_client.client.get("/api/v1/search/suggest", headers=user.auth_headers, params={"q": "ot"})
    finally:
        _redis("DEL", CHAOS_KEY)
    assert response.status_code == 200

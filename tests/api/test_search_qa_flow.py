"""Search QA (middle layer): gateway-level search journeys.

[REAL] failures are left failing on purpose and named in each docstring.
"""

from __future__ import annotations

import uuid


def _search(api_client, user, q, **params):
    response = api_client.client.get("/api/v1/search/", headers=user.auth_headers, params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def _ids(body):
    return [hit["id"] for hit in body["results"]]


def _index_document(api_client, user, **fields):
    doc = {"id": str(uuid.uuid4()), "owner_id": user.id, "content": "", **fields}
    response = api_client.client.post("/api/v1/search/index/document", headers=user.auth_headers, json=doc)
    assert response.status_code == 201, response.text
    api_client.indexed_documents.append(doc["id"])
    return doc


def _index_file(api_client, user, **fields):
    doc = {"id": str(uuid.uuid4()), "owner_id": user.id, "mime_type": "text/plain", **fields}
    response = api_client.client.post("/api/v1/search/index/file", headers=user.auth_headers, json=doc)
    assert response.status_code == 201, response.text
    api_client.indexed_files.append(doc["id"])
    return doc


def _token(api_client, label):
    return f"qa{label}{api_client.run_id}{uuid.uuid4().hex[:6]}".lower()


def test_new_document_is_full_text_searchable_by_owner_only(api_client):
    owner = api_client.register_user("search-qa-owner")
    other = api_client.register_user("search-qa-other")
    word = _token(api_client, "doc")
    document = api_client.create_document(owner, f"QA Search {word}", f"body mentions {word} once")

    found = api_client.poll_until(
        lambda: _search(api_client, owner, word),
        lambda body: document["id"] in _ids(body),
        description="new document to be searchable",
    )
    assert found["results"][0]["type"] == "document"
    assert _search(api_client, other, word)["total"] == 0


def test_uploaded_file_is_searchable_by_name_and_type_filter(api_client):
    owner = api_client.register_user("search-qa-upload")
    word = _token(api_client, "file")
    upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=owner.auth_headers,
        files={"file": (f"{word}.txt", b"qa search upload", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["file"]["id"]
    api_client.created_files.append(file_id)

    api_client.poll_until(
        lambda: _search(api_client, owner, word, type="file"),
        lambda body: file_id in _ids(body),
        description="uploaded file to be searchable",
    )
    assert file_id not in _ids(_search(api_client, owner, word, type="document"))


def test_type_filter_separates_documents_and_files(api_client):
    user = api_client.register_user("search-qa-type")
    word = _token(api_client, "type")
    doc = _index_document(api_client, user, title=f"Doc {word}")
    file = _index_file(api_client, user, name=f"{word}.csv")

    assert set(_ids(_search(api_client, user, word))) == {doc["id"], file["id"]}
    assert _ids(_search(api_client, user, word, type="document")) == [doc["id"]]
    assert _ids(_search(api_client, user, word, type="file")) == [file["id"]]


def test_folder_type_filter_finds_created_folder(api_client):
    """[REAL] the UI offers a 'Folders' filter but folders are never indexed, so it is always empty."""
    user = api_client.register_user("search-qa-folder")
    word = _token(api_client, "folder")
    folder = api_client.client.post(
        "/api/v1/folders", headers=user.auth_headers, json={"name": f"Folder {word}", "owner_id": user.id}
    )
    assert folder.status_code == 201, folder.text
    api_client.created_folders.append(folder.json()["id"])

    api_client.poll_until(
        lambda: _search(api_client, user, word, type="folder"),
        lambda body: folder.json()["id"] in _ids(body),
        timeout_seconds=10,
        description="folder to be searchable",
    )


def test_gibberish_query_returns_empty_results(api_client):
    user = api_client.register_user("search-qa-empty")
    body = _search(api_client, user, f"zzxq{uuid.uuid4().hex}")
    assert body["results"] == []
    assert body["total"] == 0


def test_missing_query_and_bad_paging_are_clean_400s(api_client):
    user = api_client.register_user("search-qa-400")
    for params in ({}, {"q": ""}, {"q": "x", "page": "abc"}):
        response = api_client.client.get("/api/v1/search/", headers=user.auth_headers, params=params)
        assert response.status_code == 400, params
        api_client.assert_json_error(response)


def test_search_requires_authentication(api_client):
    response = api_client.client.get("/api/v1/search/", params={"q": "anything"})
    assert response.status_code == 401


def test_pagination_splits_results(api_client):
    user = api_client.register_user("search-qa-page")
    word = _token(api_client, "page")
    ids = {_index_document(api_client, user, title=f"Page {word} {n}")["id"] for n in range(3)}

    first = _search(api_client, user, word, size=2, page=1)
    second = _search(api_client, user, word, size=2, page=2)
    assert first["total"] == 3
    assert len(first["results"]) == 2 and len(second["results"]) == 1
    assert set(_ids(first)) | set(_ids(second)) == ids


def test_advanced_search_tag_filter(api_client):
    user = api_client.register_user("search-qa-tags")
    word = _token(api_client, "tags")
    finance = _index_document(api_client, user, title=f"Budget {word}", tags=["finance"])
    _index_document(api_client, user, title=f"Offsite {word}", tags=["travel"])

    response = api_client.client.post(
        "/api/v1/search/advanced", headers=user.auth_headers, json={"query": word, "tags": ["finance"]}
    )
    assert response.status_code == 200, response.text
    assert _ids(response.json()) == [finance["id"]]


def test_reindexing_same_document_updates_search(api_client):
    """[REAL] intermittent: once the index has seen deletes, re-indexing an existing document id
    fails with MeiliSearch MDB_KEYEXIST (500); index_document lacks the retry index_file has."""
    user = api_client.register_user("search-qa-update")
    old, new = _token(api_client, "old"), _token(api_client, "new")
    doc = _index_document(api_client, user, title=f"Draft {old}")

    response = api_client.client.post(
        "/api/v1/search/index/document",
        headers=user.auth_headers,
        json={**doc, "title": f"Final {new}"},
    )
    assert response.status_code == 201, response.text
    assert _ids(_search(api_client, user, new)) == [doc["id"]]
    assert _search(api_client, user, old)["total"] == 0


def test_removed_document_disappears_from_search(api_client):
    user = api_client.register_user("search-qa-remove")
    word = _token(api_client, "rm")
    doc = _index_document(api_client, user, title=f"Remove {word}")
    assert _ids(_search(api_client, user, word)) == [doc["id"]]

    response = api_client.client.delete(f"/api/v1/search/index/document/{doc['id']}", headers=user.auth_headers)
    assert response.status_code == 200, response.text
    assert _search(api_client, user, word)["total"] == 0


def test_suggest_returns_prefix_matches(api_client):
    user = api_client.register_user("search-qa-suggest")
    word = _token(api_client, "sug")
    _index_document(api_client, user, title=f"{word} roadmap")
    response = api_client.client.get("/api/v1/search/suggest", headers=user.auth_headers, params={"q": word[:-2]})
    assert response.status_code == 200, response.text
    assert f"{word} roadmap" in response.json()["suggestions"]


def test_suggest_does_not_leak_other_users_titles(api_client):
    """[REAL] /suggest is not owner-scoped: any user can autocomplete another tenant's titles."""
    owner = api_client.register_user("search-qa-sug-owner")
    other = api_client.register_user("search-qa-sug-other")
    word = _token(api_client, "secret")
    _index_document(api_client, owner, title=f"{word} acquisition plan")
    response = api_client.client.get("/api/v1/search/suggest", headers=other.auth_headers, params={"q": word[:-2]})
    assert response.status_code == 200, response.text
    assert f"{word} acquisition plan" not in response.json()["suggestions"]


def test_index_cannot_plant_documents_in_another_users_results(api_client):
    """[REAL] POST /index/document trusts body owner_id, so a user can inject results into another tenant."""
    attacker = api_client.register_user("search-qa-attacker")
    victim = api_client.register_user("search-qa-victim")
    word = _token(api_client, "spoof")
    response = api_client.client.post(
        "/api/v1/search/index/document",
        headers=attacker.auth_headers,
        json={"id": str(uuid.uuid4()), "title": f"Reset password {word}", "owner_id": victim.id},
    )
    if response.status_code == 201:
        api_client.indexed_documents.append(response.json()["id"])
    assert _search(api_client, victim, word)["total"] == 0


def test_index_entries_cannot_be_deleted_by_another_user(api_client):
    """[REAL] DELETE /index/{type}/{id} has no ownership check; any user can remove another's entries."""
    owner = api_client.register_user("search-qa-del-owner")
    other = api_client.register_user("search-qa-del-other")
    word = _token(api_client, "keep")
    file = _index_file(api_client, owner, name=f"{word}.pdf")

    api_client.client.delete(f"/api/v1/search/index/file/{file['id']}", headers=other.auth_headers)
    assert _ids(_search(api_client, owner, word)) == [file["id"]]


def test_reindex_is_not_available_to_regular_users(api_client):
    """[REAL] POST /reindex ("admin operation") is accepted from any signed-in user."""
    user = api_client.register_user("search-qa-reindex")
    response = api_client.client.post("/api/v1/search/reindex", headers=user.auth_headers)
    assert response.status_code in (401, 403), response.text

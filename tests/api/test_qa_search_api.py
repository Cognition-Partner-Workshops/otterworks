"""QA integration tests for search (gateway -> search-service -> MeiliSearch)."""

import random
import string
import uuid

import pytest

pytestmark = pytest.mark.api_flow

SEARCH = "/api/v1/search/"


def word(prefix: str = "qa") -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase, k=10))


def index_doc(api, user, *, title, content="", tags=None, doc_id=None, created_at=None):
    doc_id = doc_id or str(uuid.uuid4())
    response = api.client.post(
        "/api/v1/search/index/document",
        headers=user.auth_headers,
        json={
            "id": doc_id,
            "title": title,
            "content": content,
            "owner_id": user.id,
            "tags": tags or [],
            "created_at": created_at or api.iso_time(),
            "updated_at": created_at or api.iso_time(),
        },
    )
    assert response.status_code == 201, response.text
    if doc_id not in api.indexed_documents:
        api.indexed_documents.append(doc_id)
    return doc_id


def index_file(api, user, *, name, mime_type="text/plain", file_id=None):
    file_id = file_id or str(uuid.uuid4())
    response = api.client.post(
        "/api/v1/search/index/file",
        headers=user.auth_headers,
        json={
            "id": file_id,
            "name": name,
            "mime_type": mime_type,
            "owner_id": user.id,
            "size": 123,
            "created_at": api.iso_time(),
            "updated_at": api.iso_time(),
        },
    )
    assert response.status_code == 201, response.text
    api.indexed_files.append(file_id)
    return file_id


def search(api, user, q, **params):
    response = api.client.get(SEARCH, headers=user.auth_headers, params={"q": q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def ids(body):
    return [r["id"] for r in body["results"]]


def test_indexed_document_is_found_by_content_with_highlighted_snippet(api_client):
    user = api_client.register_user("qa-search-content")
    term = word()
    doc_id = index_doc(api_client, user, title="Quarterly plan", content=f"the {term} migration notes")

    body = search(api_client, user, term)
    assert doc_id in ids(body)
    hit = next(r for r in body["results"] if r["id"] == doc_id)
    assert hit["type"] == "document"
    assert hit["title"] == "Quarterly plan"
    assert f"<em>{term}</em>" in hit["content_snippet"]
    assert "content" in hit["highlights"]
    assert body["query"] == term


def test_title_search_is_typo_tolerant(api_client):
    user = api_client.register_user("qa-search-typo")
    term = word("typo")
    doc_id = index_doc(api_client, user, title=f"Handbook {term}")
    typo = term[:-1] + ("x" if term[-1] != "x" else "y")
    assert doc_id in ids(search(api_client, user, typo))


def test_type_filter_separates_documents_and_files(api_client):
    user = api_client.register_user("qa-search-type")
    term = word("type")
    doc_id = index_doc(api_client, user, title=f"{term} doc")
    file_id = index_file(api_client, user, name=f"{term}.txt")

    all_body = search(api_client, user, term)
    assert {doc_id, file_id} <= set(ids(all_body))
    assert all_body["total"] == 2

    docs = search(api_client, user, term, type="document")
    assert ids(docs) == [doc_id]
    files = search(api_client, user, term, type="file")
    assert ids(files) == [file_id]
    assert files["results"][0]["mime_type"] == "text/plain"


def test_no_results_state_for_unknown_term(api_client):
    user = api_client.register_user("qa-search-empty")
    body = search(api_client, user, word("nothing"))
    assert body["results"] == []
    assert body["total"] == 0


def test_results_are_scoped_to_the_caller(api_client):
    owner = api_client.register_user("qa-search-owner")
    other = api_client.register_user("qa-search-other")
    term = word("secret")
    doc_id = index_doc(api_client, owner, title=f"Private {term}", content=term)

    assert doc_id in ids(search(api_client, owner, term))
    assert ids(search(api_client, other, term, owner_id=owner.id)) == []

    adv = api_client.client.post(
        "/api/v1/search/advanced",
        headers=other.auth_headers,
        json={"q": term, "owner_id": owner.id},
    )
    assert adv.status_code == 200, adv.text
    assert adv.json()["results"] == []


def test_suggest_returns_own_titles_for_prefix(api_client):
    user = api_client.register_user("qa-search-suggest")
    term = word("sugg")
    title = f"{term} roadmap"
    index_doc(api_client, user, title=title)

    response = api_client.client.get(
        "/api/v1/search/suggest", headers=user.auth_headers, params={"q": term[:6]}
    )
    assert response.status_code == 200, response.text
    assert title in response.json()["suggestions"]


def test_suggest_does_not_leak_other_users_titles(api_client):
    owner = api_client.register_user("qa-suggest-owner")
    other = api_client.register_user("qa-suggest-other")
    term = word("leak")
    title = f"{term} confidential board minutes"
    index_doc(api_client, owner, title=title)

    response = api_client.client.get(
        "/api/v1/search/suggest", headers=other.auth_headers, params={"q": term}
    )
    assert response.status_code == 200, response.text
    assert title not in response.json()["suggestions"], (
        "suggest exposes another tenant's document title"
    )


def test_pagination_returns_disjoint_pages(api_client):
    user = api_client.register_user("qa-search-pages")
    term = word("page")
    created = {index_doc(api_client, user, title=f"{term} item {i}") for i in range(5)}

    seen: list[str] = []
    for page in (1, 2, 3):
        body = search(api_client, user, term, page=page, size=2)
        assert body["total"] == 5
        assert body["page"] == page and body["page_size"] == 2
        seen.extend(ids(body))
    assert len(seen) == 5
    assert set(seen) == created


def test_reindexing_same_id_updates_document(api_client):
    user = api_client.register_user("qa-search-upsert")
    old, new = word("old"), word("new")
    doc_id = index_doc(api_client, user, title=f"Doc {old}")
    index_doc(api_client, user, title=f"Doc {new}", doc_id=doc_id)

    assert doc_id in ids(search(api_client, user, new))
    assert doc_id not in ids(search(api_client, user, old))


def test_remove_from_index_then_not_found(api_client):
    user = api_client.register_user("qa-search-remove")
    term = word("gone")
    doc_id = index_doc(api_client, user, title=f"{term} temp")
    assert doc_id in ids(search(api_client, user, term))

    first = api_client.client.delete(f"/api/v1/search/index/document/{doc_id}", headers=user.auth_headers)
    assert first.status_code == 200, first.text
    api_client.indexed_documents.remove(doc_id)
    assert doc_id not in ids(search(api_client, user, term))

    second = api_client.client.delete(f"/api/v1/search/index/document/{doc_id}", headers=user.auth_headers)
    assert second.status_code == 404


def test_advanced_search_tag_filter(api_client):
    user = api_client.register_user("qa-search-tags")
    term = word("tag")
    tagged = index_doc(api_client, user, title=f"{term} a", tags=["finance"])
    untagged = index_doc(api_client, user, title=f"{term} b", tags=["hr"])

    response = api_client.client.post(
        "/api/v1/search/advanced",
        headers=user.auth_headers,
        json={"q": term, "tags": ["finance"]},
    )
    assert response.status_code == 200, response.text
    result_ids = ids(response.json())
    assert tagged in result_ids
    assert untagged not in result_ids


def test_advanced_search_date_range_filter(api_client):
    user = api_client.register_user("qa-search-dates")
    term = word("date")
    doc_id = index_doc(api_client, user, title=f"{term} dated", created_at="2026-03-15T00:00:00+00:00")

    response = api_client.client.post(
        "/api/v1/search/advanced",
        headers=user.auth_headers,
        json={"q": term, "date_from": "2026-03-01T00:00:00+00:00", "date_to": "2026-03-31T00:00:00+00:00"},
    )
    assert response.status_code == 200, response.text
    assert doc_id in ids(response.json())


def test_search_requires_authentication(api_client):
    response = api_client.client.get(SEARCH, params={"q": "anything"})
    assert response.status_code == 401, response.text


@pytest.mark.side_effect
def test_document_created_via_document_service_is_searchable_and_navigable(api_client):
    user = api_client.register_user("qa-search-fanout")
    term = word("fan")
    document = api_client.create_document(user, title=f"Fanout {term}", content=f"body {term}")

    results = api_client.poll_until(
        lambda: search(api_client, user, term)["results"],
        lambda rs: any(r["id"] == document["id"] for r in rs),
        description="new document to be indexed",
    )
    hit = next(r for r in results if r["id"] == document["id"])
    assert hit["type"] == "document"
    fetched = api_client.client.get(f"/api/v1/documents/{document['id']}", headers=user.auth_headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["title"] == f"Fanout {term}"


@pytest.mark.side_effect
def test_uploaded_file_is_searchable_by_name(api_client):
    user = api_client.register_user("qa-search-upload")
    term = word("upl")
    upload = api_client.client.post(
        "/api/v1/files/upload",
        headers=user.auth_headers,
        files={"file": (f"{term}.txt", b"hello search", "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    file_id = upload.json()["file"]["id"]
    api_client.created_files.append(file_id)

    api_client.poll_until(
        lambda: ids(search(api_client, user, term, type="file")),
        lambda found: file_id in found,
        description="uploaded file to be indexed",
    )

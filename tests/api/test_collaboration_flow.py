import pytest


pytestmark = pytest.mark.api_flow


def test_collaboration_presence_endpoints(api_client):
    user = api_client.register_user("collab-flow")
    document_response = api_client.client.post(
        "/api/v1/documents/",
        headers=user.auth_headers,
        json={"title": f"Collab Doc {api_client.run_id}", "content": "collab body"},
    )
    assert document_response.status_code == 201, document_response.text
    document_id = document_response.json()["id"]

    active_documents_response = api_client.client.get(
        "/api/v1/collab/documents",
        headers=user.auth_headers,
    )
    assert active_documents_response.status_code == 200, active_documents_response.text
    active_documents = active_documents_response.json()
    assert "documents" in active_documents
    assert "count" in active_documents
    # Listing is scoped to documents the caller is a live participant of; this user
    # has not joined any collab session, so nothing (and no other tenant's IDs) is exposed.
    assert active_documents == {"documents": [], "count": 0}

    # Presence is only readable by a participant of the document; the owner has not
    # joined the collab session, so the request is forbidden rather than leaking state.
    presence_response = api_client.client.get(
        f"/api/v1/collab/documents/{document_id}/presence",
        headers=user.auth_headers,
    )
    assert presence_response.status_code == 403, presence_response.text


def test_collaboration_presence_requires_authentication(api_client):
    response = api_client.client.get("/api/v1/collab/documents")
    assert response.status_code == 401, response.text


def test_collaboration_invalid_document_presence_is_stable(api_client):
    user = api_client.register_user("collab-validation")

    presence_response = api_client.client.get(
        "/api/v1/collab/documents/not-a-real-document/presence",
        headers=user.auth_headers,
    )
    assert presence_response.status_code in {400, 403, 404}, presence_response.text

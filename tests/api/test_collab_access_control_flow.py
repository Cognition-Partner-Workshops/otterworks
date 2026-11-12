"""Collab-service must only expose a document to callers document-service lets see it."""

import os
import time

import pytest
import socketio


pytestmark = [pytest.mark.api_flow, pytest.mark.websocket]


def _collab_url(base_url: str) -> str:
    return os.getenv("OTTERWORKS_COLLAB_WS_URL", base_url.replace("http://", "ws://").replace("https://", "wss://"))


def _connect(base_url: str, token: str) -> socketio.Client:
    client = socketio.Client(reconnection=False, request_timeout=5)
    client.connect(_collab_url(base_url), auth={"token": token}, transports=["websocket"])
    return client


@pytest.fixture
def owner_and_outsider(api_client):
    owner = api_client.register_user("collab-owner")
    outsider = api_client.register_user("collab-outsider")
    document = api_client.create_document(
        owner,
        title=f"Private Collab Document {api_client.run_id}",
        content="owner only",
    )
    return owner, outsider, document["id"]


def test_socketio_outsider_cannot_join_read_or_write_document(owner_and_outsider, base_url):
    owner, outsider, document_id = owner_and_outsider
    owner_updates: list[dict] = []
    outsider_events: dict[str, list] = {"sync-document": [], "document-history": []}

    owner_socket = _connect(base_url, owner.access_token)
    owner_socket.on("document-update", lambda data: owner_updates.append(data))
    outsider_socket = _connect(base_url, outsider.access_token)
    for event, received in outsider_events.items():
        outsider_socket.on(event, lambda data, received=received: received.append(data))

    try:
        assert owner_socket.call("join-document", {"documentId": document_id}, timeout=5) == {"success": True}

        join = outsider_socket.call("join-document", {"documentId": document_id}, timeout=5)
        assert join["success"] is False, join

        outsider_socket.emit("request-history", {"documentId": document_id})
        outsider_socket.emit("document-update", {"documentId": document_id, "update": {"text": "overwritten"}})
        time.sleep(1.0)

        assert outsider_events["sync-document"] == []
        assert outsider_events["document-history"] == []
        assert owner_updates == []
    finally:
        owner_socket.disconnect()
        outsider_socket.disconnect()


def test_active_documents_listing_and_presence_are_scoped_to_the_caller(owner_and_outsider, api_client, base_url):
    owner, outsider, document_id = owner_and_outsider
    owner_socket = _connect(base_url, owner.access_token)
    try:
        assert owner_socket.call("join-document", {"documentId": document_id}, timeout=5) == {"success": True}

        outsider_listing = api_client.client.get("/api/v1/collab/documents", headers=outsider.auth_headers)
        assert outsider_listing.status_code == 200, outsider_listing.text
        assert document_id not in {d["documentId"] for d in outsider_listing.json()["documents"]}

        owner_listing = api_client.client.get("/api/v1/collab/documents", headers=owner.auth_headers)
        assert owner_listing.status_code == 200, owner_listing.text
        assert document_id in {d["documentId"] for d in owner_listing.json()["documents"]}

        outsider_presence = api_client.client.get(
            f"/api/v1/collab/documents/{document_id}/presence", headers=outsider.auth_headers
        )
        assert outsider_presence.status_code in {403, 404}, outsider_presence.text
        assert owner.email not in outsider_presence.text

        owner_presence = api_client.client.get(
            f"/api/v1/collab/documents/{document_id}/presence", headers=owner.auth_headers
        )
        assert owner_presence.status_code == 200, owner_presence.text
        assert owner_presence.json()["count"] == 1
    finally:
        owner_socket.disconnect()

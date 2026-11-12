import os
import time

import pytest
import socketio


pytestmark = [pytest.mark.api_flow, pytest.mark.websocket]


def _collab_url(base_url: str) -> str:
    return os.getenv("OTTERWORKS_COLLAB_WS_URL", base_url.replace("http://", "ws://").replace("https://", "wss://"))


def test_socketio_rejects_missing_or_invalid_token(base_url):
    sio = socketio.Client(reconnection=False, request_timeout=3)
    with pytest.raises(socketio.exceptions.ConnectionError):
        sio.connect(_collab_url(base_url), transports=["websocket"])

    invalid = socketio.Client(reconnection=False, request_timeout=3)
    with pytest.raises(socketio.exceptions.ConnectionError):
        invalid.connect(
            _collab_url(base_url),
            auth={"token": "not-a-valid-token"},
            transports=["websocket"],
        )


def _connect(base_url: str, token: str) -> socketio.Client:
    client = socketio.Client(reconnection=False, request_timeout=5)
    client.connect(_collab_url(base_url), auth={"token": token}, transports=["websocket"])
    return client


def _disconnect(*clients: socketio.Client) -> None:
    for client in clients:
        if client.connected:
            client.disconnect()


def test_socketio_owner_sessions_join_same_document_and_presence_updates(api_client, base_url):
    owner = api_client.register_user("ws-owner")
    document = api_client.create_document(
        owner,
        title=f"WebSocket Document {api_client.run_id}",
        content="collaboration body",
    )
    document_id = document["id"]
    received_by_second: list[dict] = []

    first = _connect(base_url, owner.access_token)
    second = _connect(base_url, owner.access_token)
    second.on("document-update", received_by_second.append)

    try:
        assert first.call("join-document", {"documentId": document_id}) == {"success": True}
        assert second.call("join-document", {"documentId": document_id}) == {"success": True}

        presence_response = api_client.client.get(
            f"/api/v1/collab/documents/{document_id}/presence",
            headers=owner.auth_headers,
        )
        assert presence_response.status_code == 200, presence_response.text
        assert presence_response.json()["count"] == 2

        first.emit(
            "document-update",
            {"documentId": document_id, "update": {"text": f"hello {api_client.run_id}"}},
        )

        api_client.poll_until(
            lambda: received_by_second,
            lambda updates: len(updates) >= 1,
            timeout_seconds=10,
            interval_seconds=0.25,
            description="collaboration update fanout to second socket client",
        )
    finally:
        _disconnect(first, second)


def test_socketio_other_user_cannot_join_or_change_document(api_client, base_url):
    owner = api_client.register_user("ws-owner")
    intruder = api_client.register_user("ws-intruder")
    document = api_client.create_document(
        owner,
        title=f"Private Document {api_client.run_id}",
        content="private body",
    )
    document_id = document["id"]
    received_by_owner: list[tuple[str, dict]] = []
    received_by_intruder: list[tuple[str, dict]] = []

    owner_client = _connect(base_url, owner.access_token)
    intruder_client = _connect(base_url, intruder.access_token)
    for event in ("document-update", "comment-added", "user-joined"):
        owner_client.on(event, lambda data, event=event: received_by_owner.append((event, data)))
    for event in ("sync-document", "presence-update", "document-history"):
        intruder_client.on(event, lambda data, event=event: received_by_intruder.append((event, data)))

    try:
        assert owner_client.call("join-document", {"documentId": document_id}) == {"success": True}

        join_result = intruder_client.call("join-document", {"documentId": document_id})
        assert join_result == {"success": False, "error": "Access denied"}

        intruder_client.emit(
            "document-update",
            {"documentId": document_id, "update": {"text": "tampered"}},
        )
        intruder_client.emit(
            "comment-add",
            {
                "documentId": document_id,
                "comment": {"id": "c1", "threadId": "t1", "content": "x", "rangeStart": 0, "rangeEnd": 1},
            },
        )
        intruder_client.emit("request-history", {"documentId": document_id})
        time.sleep(1.5)

        assert received_by_owner == []
        assert received_by_intruder == []
    finally:
        _disconnect(owner_client, intruder_client)


def test_collaboration_endpoints_hide_other_users_documents(api_client, base_url):
    owner = api_client.register_user("collab-owner")
    intruder = api_client.register_user("collab-intruder")
    document = api_client.create_document(
        owner,
        title=f"Private Collab Doc {api_client.run_id}",
        content="private body",
    )
    document_id = document["id"]

    client = _connect(base_url, owner.access_token)
    try:
        assert client.call("join-document", {"documentId": document_id}) == {"success": True}

        owner_listing = api_client.client.get("/api/v1/collab/documents", headers=owner.auth_headers)
        assert owner_listing.status_code == 200, owner_listing.text
        assert document_id in [entry["documentId"] for entry in owner_listing.json()["documents"]]

        intruder_listing = api_client.client.get("/api/v1/collab/documents", headers=intruder.auth_headers)
        assert intruder_listing.status_code == 200, intruder_listing.text
        assert document_id not in intruder_listing.text

        intruder_presence = api_client.client.get(
            f"/api/v1/collab/documents/{document_id}/presence",
            headers=intruder.auth_headers,
        )
        assert intruder_presence.status_code == 404, intruder_presence.text
        assert owner.email not in intruder_presence.text
    finally:
        _disconnect(client)

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


def test_socketio_fans_out_updates_to_the_owner_and_denies_other_users(api_client, base_url):
    user_a = api_client.register_user("ws-user-a")
    user_b = api_client.register_user("ws-user-b")
    document = api_client.create_document(
        user_a,
        title=f"WebSocket Document {api_client.run_id}",
        content="collaboration body",
    )
    document_id = document["id"]
    received_by_a2: list[dict] = []
    received_by_b: list[dict] = []
    denied_for_b: list[dict] = []

    client_a = socketio.Client(reconnection=False, request_timeout=5)
    client_a2 = socketio.Client(reconnection=False, request_timeout=5)
    client_b = socketio.Client(reconnection=False, request_timeout=5)

    @client_a2.on("document-update")
    def on_document_update_a2(data):
        received_by_a2.append(data)

    @client_b.on("document-update")
    def on_document_update_b(data):
        received_by_b.append(data)

    @client_b.on("access-denied")
    def on_access_denied(data):
        denied_for_b.append(data)

    try:
        for client, user in ((client_a, user_a), (client_a2, user_a), (client_b, user_b)):
            client.connect(_collab_url(base_url), auth={"token": user.access_token}, transports=["websocket"])

        # Only the document owner may join its collaboration room.
        assert client_a.call("join-document", {"documentId": document_id}, timeout=5) == {"success": True}
        assert client_a2.call("join-document", {"documentId": document_id}, timeout=5) == {"success": True}
        join_b = client_b.call("join-document", {"documentId": document_id}, timeout=5)
        assert join_b == {"success": False, "error": "Access denied"}, join_b
        time.sleep(0.5)

        presence_response = api_client.client.get(
            f"/api/v1/collab/documents/{document_id}/presence",
            headers=user_a.auth_headers,
        )
        assert presence_response.status_code == 200, presence_response.text
        assert {u["userId"] for u in presence_response.json()["users"]} == {user_a.id}

        # The non-owner cannot push edits into the room either.
        client_b.emit("document-update", {"documentId": document_id, "update": {"text": "tampered"}})

        client_a.emit(
            "document-update",
            {"documentId": document_id, "update": {"text": f"hello {api_client.run_id}"}},
        )

        api_client.poll_until(
            lambda: received_by_a2,
            lambda updates: len(updates) >= 1,
            timeout_seconds=10,
            interval_seconds=0.25,
            description="collaboration update fanout to the owner's second socket client",
        )
        assert received_by_b == []
        assert any(d.get("event") == "join-document" for d in denied_for_b), denied_for_b
        assert any(d.get("event") == "document-update" for d in denied_for_b), denied_for_b
    finally:
        for client in (client_a, client_a2, client_b):
            if client.connected:
                client.disconnect()

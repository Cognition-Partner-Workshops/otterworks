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


def test_socketio_owner_and_share_link_viewer_join_same_document(api_client, base_url):
    """The owner edits; a second user may only follow along through a share link the owner minted."""
    user_a = api_client.register_user("ws-user-a")
    user_b = api_client.register_user("ws-user-b")
    document = api_client.create_document(
        user_a,
        title=f"WebSocket Document {api_client.run_id}",
        content="collaboration body",
    )
    document_id = document["id"]
    share = api_client.client.post(f"/api/v1/documents/{document_id}/share", headers=user_a.auth_headers)
    assert share.status_code == 200, share.text
    share_token = share.json()["token"]
    received_by_b: list[dict] = []
    errors_for_b: list[dict] = []

    client_a = socketio.Client(reconnection=False, request_timeout=5)
    client_b = socketio.Client(reconnection=False, request_timeout=5)

    @client_b.on("document-update")
    def on_document_update(data):
        received_by_b.append(data)

    @client_b.on("document-update-error")
    def on_document_update_error(data):
        errors_for_b.append(data)

    try:
        client_a.connect(_collab_url(base_url), auth={"token": user_a.access_token}, transports=["websocket"])
        client_b.connect(_collab_url(base_url), auth={"token": user_b.access_token}, transports=["websocket"])

        assert client_a.call("join-document", {"documentId": document_id}, timeout=5) == {"success": True}
        assert client_b.call(
            "join-document", {"documentId": document_id, "shareToken": share_token}, timeout=5
        ) == {"success": True}

        presence_response = api_client.client.get(
            f"/api/v1/collab/documents/{document_id}/presence",
            headers=user_a.auth_headers,
        )
        assert presence_response.status_code == 200, presence_response.text
        assert presence_response.json()["count"] == 2

        client_a.emit(
            "document-update",
            {"documentId": document_id, "update": {"text": f"hello {api_client.run_id}"}},
        )

        api_client.poll_until(
            lambda: received_by_b,
            lambda updates: len(updates) >= 1,
            timeout_seconds=10,
            interval_seconds=0.25,
            description="collaboration update fanout to second socket client",
        )

        # A share-link viewer is read-only: its edits are refused and never reach the owner.
        client_b.emit("document-update", {"documentId": document_id, "update": {"text": "viewer edit"}})
        api_client.poll_until(
            lambda: errors_for_b,
            lambda errors: len(errors) >= 1,
            timeout_seconds=10,
            interval_seconds=0.25,
            description="viewer edit rejected",
        )
    finally:
        if client_a.connected:
            client_a.disconnect()
        if client_b.connected:
            client_b.disconnect()

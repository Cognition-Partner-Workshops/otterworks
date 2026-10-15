"""Two-user real-time collaboration flows against the running stack.

Socket.IO goes through the gateway (the same route the existing websocket suite uses);
y-websocket (what the web editor actually uses) is served by collab-service directly.
"""

import base64
import time
import uuid

import httpx
import pycrdt
import pytest
import websocket

from collab_helpers import RecordingSocket, YjsClient, collab_http_url, socketio_url, wait_for, yjs_ws_url


pytestmark = [pytest.mark.api_flow, pytest.mark.websocket]


@pytest.fixture
def two_users(api_client):
    owner = api_client.register_user("collab-owner")
    peer = api_client.register_user("collab-peer")
    document = api_client.create_document(owner, title=f"Collab {api_client.run_id}", content="seed")
    return owner, peer, document["id"]


@pytest.fixture
def sockets(base_url):
    opened: list = []

    def open_socket(user) -> RecordingSocket:
        sock = RecordingSocket(socketio_url(base_url), user.access_token).connect()
        opened.append(sock)
        return sock

    yield open_socket
    for sock in opened:
        sock.close()


@pytest.fixture
def yjs_clients(base_url):
    opened: list[YjsClient] = []

    def open_client(document_id: str, token: str | None) -> YjsClient:
        client = YjsClient(yjs_ws_url(base_url), f"document-{document_id}", token).connect()
        opened.append(client)
        return client

    yield open_client
    for client in opened:
        client.close()


def _yjs_update(text: str) -> str:
    doc = pycrdt.Doc()
    doc["content"] = pycrdt.Text(text)
    return base64.b64encode(doc.get_update()).decode()


# ── Socket.IO: presence, cursors, typing, comments, snapshots ────────────────


def test_join_returns_success_and_initial_presence(two_users, sockets):
    owner, peer, document_id = two_users
    a = sockets(owner)
    ack = a.join(document_id)
    assert ack == {"success": True}
    presence = a.wait_for_event("presence-update", lambda d: d["documentId"] == document_id)
    assert presence["count"] == 1
    assert presence["users"][0]["userId"] == owner.id
    assert a.wait_for_event("sync-document")["documentId"] == document_id


def test_second_user_joining_notifies_first_and_presence_endpoint_lists_both(api_client, two_users, sockets):
    owner, peer, document_id = two_users
    a = sockets(owner)
    a.join(document_id)
    b = sockets(peer)
    b.join(document_id)

    joined = a.wait_for_event("user-joined", lambda d: d["userId"] == peer.id)
    assert joined["displayName"] == peer.display_name
    a.wait_for_event("presence-update", lambda d: d["count"] == 2)

    response = api_client.client.get(f"/api/v1/collab/documents/{document_id}/presence", headers=owner.auth_headers)
    assert response.status_code == 200, response.text
    assert {u["userId"] for u in response.json()["users"]} == {owner.id, peer.id}


def test_cursor_selection_and_typing_are_relayed_to_peer(two_users, sockets):
    owner, peer, document_id = two_users
    a, b = sockets(owner), sockets(peer)
    a.join(document_id)
    b.join(document_id)

    a.emit(
        "cursor-update",
        {"documentId": document_id, "cursor": {"index": 3, "length": 0}, "selection": {"index": 1, "length": 2}},
    )
    a.emit("typing-indicator", {"documentId": document_id, "isTyping": True})

    cursor = b.wait_for_event("cursor-update", lambda d: d["userId"] == owner.id)
    assert cursor["cursor"] == {"index": 3, "length": 0}
    assert cursor["selection"] == {"index": 1, "length": 2}
    assert cursor["color"].startswith("#")
    typing = b.wait_for_event("typing-indicator", lambda d: d["userId"] == owner.id)
    assert typing["isTyping"] is True
    assert not a.received("cursor-update"), "cursor updates must not echo to the sender"


def test_yjs_update_over_socketio_reaches_peer_and_late_joiner_gets_state(api_client, two_users, sockets):
    owner, peer, document_id = two_users
    a, b = sockets(owner), sockets(peer)
    a.join(document_id)
    b.join(document_id)

    update = _yjs_update(f"hello {api_client.run_id}")
    a.emit("document-update", {"documentId": document_id, "update": update})
    assert b.wait_for_event("document-update")["update"] == update

    late = sockets(api_client.register_user("collab-late"))
    late.join(document_id)
    state = late.wait_for_event("sync-document")["state"]
    doc = pycrdt.Doc()
    doc.apply_update(base64.b64decode(state))
    assert str(doc.get("content", type=pycrdt.Text)) == f"hello {api_client.run_id}"


def test_comment_lifecycle_fans_out_with_server_stamped_author(two_users, sockets):
    owner, peer, document_id = two_users
    a, b = sockets(owner), sockets(peer)
    a.join(document_id)
    b.join(document_id)
    comment_id = f"c-{uuid.uuid4().hex[:8]}"

    b.emit(
        "comment-add",
        {
            "documentId": document_id,
            "comment": {"id": comment_id, "threadId": "t-1", "content": "nice", "author": {"userId": owner.id}},
        },
    )
    added = a.wait_for_event("comment-added", lambda d: d["id"] == comment_id)
    assert added["author"]["userId"] == peer.id, "author must come from the JWT, not the payload"
    b.wait_for_event("comment-added", lambda d: d["id"] == comment_id)

    b.emit("comment-update", {"documentId": document_id, "commentId": comment_id, "content": "nicer"})
    updated = a.wait_for_event("comment-updated", lambda d: d["commentId"] == comment_id)
    assert updated["content"] == "nicer"

    b.emit("comment-delete", {"documentId": document_id, "commentId": comment_id})
    assert a.wait_for_event("comment-deleted", lambda d: d["commentId"] == comment_id)["deletedBy"] == peer.id


def test_snapshot_and_history(two_users, sockets):
    owner, _, document_id = two_users
    a = sockets(owner)
    a.join(document_id)
    a.emit("request-snapshot", {"documentId": document_id, "label": "qa-checkpoint"})
    snapshot = a.wait_for_event("snapshot-created", lambda d: d["label"] == "qa-checkpoint")
    assert snapshot["createdBy"] == owner.id

    a.emit("request-history", {"documentId": document_id, "limit": 5})
    history = a.wait_for_event("document-history", lambda d: d["documentId"] == document_id)
    assert snapshot["id"] in [s["id"] for s in history["snapshots"]]


def test_leave_and_disconnect_emit_user_left(two_users, sockets):
    owner, peer, document_id = two_users
    a, b = sockets(owner), sockets(peer)
    a.join(document_id)
    b.join(document_id)
    b.close()
    left = a.wait_for_event("user-left", lambda d: d["userId"] == peer.id)
    assert left["socketId"]
    a.wait_for_event("presence-update", lambda d: d["count"] == 1)


def test_socketio_reconnect_rejoins_with_persisted_state(api_client, two_users, sockets):
    owner, _, document_id = two_users
    a = sockets(owner)
    a.join(document_id)
    a.emit("document-update", {"documentId": document_id, "update": _yjs_update("survives reconnect")})
    time.sleep(0.5)
    a.close()
    time.sleep(0.5)

    again = sockets(owner)
    again.join(document_id)
    doc = pycrdt.Doc()
    doc.apply_update(base64.b64decode(again.wait_for_event("sync-document")["state"]))
    assert str(doc.get("content", type=pycrdt.Text)) == "survives reconnect"


# ── y-websocket: the transport the web editor uses ───────────────────────────


def test_yjs_websocket_rejects_missing_and_invalid_tokens(base_url):
    for suffix in ("", "?token=not-a-jwt"):
        with pytest.raises(websocket.WebSocketBadStatusException) as exc:
            websocket.create_connection(f"{yjs_ws_url(base_url)}/document-{uuid.uuid4()}{suffix}", timeout=5)
        assert exc.value.status_code == 401


def test_yjs_two_sessions_sync_both_directions(two_users, yjs_clients):
    owner, _, document_id = two_users
    first = yjs_clients(document_id, owner.access_token)
    second = yjs_clients(document_id, owner.access_token)

    first.insert("hello")
    wait_for(lambda: second.value() == "hello", description="first -> second sync")
    second.insert(" world")
    wait_for(lambda: first.value() == "hello world", description="second -> first sync")


def test_yjs_concurrent_edits_converge(two_users, yjs_clients):
    owner, _, document_id = two_users
    first = yjs_clients(document_id, owner.access_token)
    second = yjs_clients(document_id, owner.access_token)
    first.insert("base")
    wait_for(lambda: second.value() == "base", description="baseline sync")

    with first.doc.transaction():
        first.text.insert(0, "A")
    with second.doc.transaction():
        second.text.insert(len(second.text), "B")

    wait_for(lambda: first.value() == second.value() == "AbaseB", description="convergence after concurrent edits")


def test_yjs_reconnect_and_persistence_after_all_clients_leave(two_users, yjs_clients):
    owner, _, document_id = two_users
    first = yjs_clients(document_id, owner.access_token)
    first.insert("persist me")
    second = yjs_clients(document_id, owner.access_token)
    wait_for(lambda: second.value() == "persist me", description="initial sync")

    second.close()
    first.insert("!")
    reconnected = yjs_clients(document_id, owner.access_token)
    wait_for(lambda: reconnected.value() == "persist me!", description="state after reconnect")

    first.close()
    reconnected.close()
    time.sleep(1.0)
    fresh = yjs_clients(document_id, owner.access_token)
    wait_for(lambda: fresh.value() == "persist me!", description="state after every client disconnected")


# ── Authorization boundaries ─────────────────────────────────────────────────


@pytest.mark.gap_revealer
def test_presence_endpoint_requires_auth_via_gateway(api_client, two_users):
    _, _, document_id = two_users
    assert api_client.client.get(f"/api/v1/collab/documents/{document_id}/presence").status_code == 401


@pytest.mark.gap_revealer
def test_unshared_user_cannot_read_document_over_yjs_websocket(api_client, two_users, yjs_clients):
    """[REAL] collab-service never checks document ownership: a user who gets 403 from
    document-service can still open the y-websocket room and read (and write) live content."""
    owner, outsider, document_id = two_users
    assert api_client.client.get(f"/api/v1/documents/{document_id}", headers=outsider.auth_headers).status_code == 403

    writer = yjs_clients(document_id, owner.access_token)
    writer.insert("owner-only secret")
    try:
        intruder = YjsClient(yjs_ws_url(str(api_client.client.base_url)), f"document-{document_id}", outsider.access_token)
        intruder.connect()
    except (websocket.WebSocketBadStatusException, AssertionError):
        return
    try:
        time.sleep(0.5)
        assert intruder.value() == "", f"unshared user read owner content: {intruder.value()!r}"
    finally:
        intruder.close()


@pytest.mark.gap_revealer
def test_unshared_user_cannot_join_document_room_over_socketio(api_client, two_users, sockets):
    """[REAL] join-document admits any authenticated user to any document room."""
    owner, outsider, document_id = two_users
    assert api_client.client.get(f"/api/v1/documents/{document_id}", headers=outsider.auth_headers).status_code == 403
    ack = sockets(outsider).join(document_id)
    assert ack.get("success") is not True, "unshared user was admitted to the collaboration room"


@pytest.mark.gap_revealer
def test_direct_collab_presence_requires_auth(base_url, two_users):
    """[REAL] collab-service's own /presence HTTP endpoint is unauthenticated (gateway is not)."""
    _, _, document_id = two_users
    try:
        response = httpx.get(f"{collab_http_url(base_url)}/api/v1/collab/documents/{document_id}/presence", timeout=5)
    except httpx.HTTPError as exc:
        pytest.skip(f"collab-service not directly reachable: {exc}")
    assert response.status_code in (401, 403), response.text

"""Collaboration area QA: Socket.IO co-editing, presence, comments, history,
reconnect, and the y-websocket endpoint the TipTap editor uses.

Tests marked ``xfail(strict=True)`` document genuine (non-planted) defects;
they flip to XPASS (and fail the run) once the defect is fixed.
"""

import base64
import os
import shutil
import subprocess
import threading
import time
import uuid

import pytest
import socketio
import websocket

pytestmark = [pytest.mark.api_flow, pytest.mark.websocket]

# Yjs updates generated with yjs 13 (Y.Text "qa" inserts by clientIDs 4242 / 4343).
YJS_UPDATE_HELLO = "AQGSIQAEAQJxYQ9oZWxsby1jb2xsYWItcWEA"
YJS_UPDATE_SECOND = "AQH3IQAEAQJxYQtzZWNvbmQtZWRpdAA="
HELLO_TEXT = b"hello-collab-qa"
SECOND_TEXT = b"second-edit"

REAL_NO_DOC_AUTHZ = (
    "[REAL] collab-service has no per-document authorization: any valid JWT can "
    "join, read and write any document room"
)


def _socketio_url(base_url: str) -> str:
    return os.getenv(
        "OTTERWORKS_COLLAB_WS_URL",
        base_url.replace("http://", "ws://").replace("https://", "wss://"),
    )


def _ywebsocket_base() -> str:
    return os.getenv("OTTERWORKS_COLLAB_YWS_URL", "ws://localhost:8084")


class Recorder:
    """Socket.IO client that records every event it receives."""

    def __init__(self, url: str, token: str):
        self.events: dict[str, list] = {}
        self._lock = threading.Lock()
        self.client = socketio.Client(reconnection=False, request_timeout=5)
        self.client.on("*", self._record)
        self.client.connect(url, auth={"token": token}, transports=["websocket"])

    def _record(self, event, data=None):
        with self._lock:
            self.events.setdefault(event, []).append(data)

    def got(self, event: str) -> list:
        with self._lock:
            return list(self.events.get(event, []))

    def wait_for(self, event: str, predicate=lambda _d: True, timeout: float = 8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for data in self.got(event):
                if predicate(data):
                    return data
            time.sleep(0.1)
        raise AssertionError(f"did not receive {event!r}; received={list(self.events)}")

    def join(self, document_id: str) -> dict:
        ack = self.client.call("join-document", {"documentId": document_id}, timeout=5)
        assert ack == {"success": True}, ack
        return self.wait_for("sync-document", lambda d: d["documentId"] == document_id)

    def close(self) -> None:
        if self.client.connected:
            self.client.disconnect()


@pytest.fixture
def sockets(base_url):
    opened: list[Recorder] = []

    def open_socket(token: str) -> Recorder:
        recorder = Recorder(_socketio_url(base_url), token)
        opened.append(recorder)
        return recorder

    yield open_socket
    for recorder in opened:
        recorder.close()


def _presence(api_client, user, document_id):
    response = api_client.client.get(
        f"/api/v1/collab/documents/{document_id}/presence", headers=user.auth_headers
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- y-websocket protocol helpers -------------------------------------------------


def _varuint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    out.append(value)
    return bytes(out)


def _sync_update_message(update: bytes) -> bytes:
    return b"\x00\x02" + _varuint(len(update)) + update


SYNC_STEP1_EMPTY = b"\x00\x00\x01\x00"


def _yws_connect(room: str, token: str | None):
    url = f"{_ywebsocket_base()}/{room}"
    if token is not None:
        url += f"?token={token}"
    return websocket.create_connection(url, timeout=5)


def _yws_collect(ws, needle: bytes, timeout: float = 6.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            frame = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        if isinstance(frame, bytes) and needle in frame:
            return True
    return False


# --- Socket.IO: auth ----------------------------------------------------------------


def test_socketio_accepts_access_token_through_gateway(api_client, sockets):
    user = api_client.register_user("collab-qa-auth")
    recorder = sockets(user.access_token)
    assert recorder.client.connected


@pytest.mark.xfail(
    strict=True, reason="[REAL] collab-service accepts refresh tokens as access tokens"
)
def test_socketio_rejects_refresh_token(api_client, base_url):
    user = api_client.register_user("collab-qa-refresh")
    client = socketio.Client(reconnection=False, request_timeout=3)
    try:
        with pytest.raises(socketio.exceptions.ConnectionError):
            client.connect(
                _socketio_url(base_url),
                auth={"token": user.refresh_token},
                transports=["websocket"],
            )
    finally:
        if client.connected:
            client.disconnect()


# --- Socket.IO: co-editing, history sync, presence ------------------------------------


def test_two_users_coedit_yjs_update_and_late_joiner_gets_full_state(
    api_client, sockets
):
    owner = api_client.register_user("collab-qa-owner")
    document = api_client.create_document(owner, f"Coedit {api_client.run_id}", "body")
    doc_id = document["id"]

    a = sockets(owner.access_token)
    b = sockets(owner.access_token)
    a.join(doc_id)
    b.join(doc_id)

    a.client.emit("document-update", {"documentId": doc_id, "update": YJS_UPDATE_HELLO})
    relayed = b.wait_for("document-update", lambda d: d["documentId"] == doc_id)
    assert relayed["update"] == YJS_UPDATE_HELLO
    assert not a.got("document-update"), "sender must not receive its own update"

    b.client.emit(
        "document-update", {"documentId": doc_id, "update": YJS_UPDATE_SECOND}
    )
    a.wait_for("document-update", lambda d: d["update"] == YJS_UPDATE_SECOND)

    late = sockets(owner.access_token)
    sync = late.join(doc_id)
    state = base64.b64decode(sync["state"])
    assert HELLO_TEXT in state and SECOND_TEXT in state


def test_invalid_crdt_update_is_rejected_and_not_broadcast(api_client, sockets):
    owner = api_client.register_user("collab-qa-badcrdt")
    doc_id = api_client.create_document(owner, f"Bad CRDT {api_client.run_id}", "x")[
        "id"
    ]
    a = sockets(owner.access_token)
    b = sockets(owner.access_token)
    a.join(doc_id)
    b.join(doc_id)

    a.client.emit(
        "document-update",
        {
            "documentId": doc_id,
            "update": base64.b64encode(b"\xff\xff\xff\xff").decode(),
        },
    )
    a.wait_for("document-update-error", lambda d: d["documentId"] == doc_id)
    time.sleep(0.5)
    assert not b.got("document-update")


def test_presence_tracks_join_and_leave(api_client, sockets):
    owner = api_client.register_user("collab-qa-presence")
    doc_id = api_client.create_document(owner, f"Presence {api_client.run_id}", "x")[
        "id"
    ]
    a = sockets(owner.access_token)
    b = sockets(owner.access_token)
    a.join(doc_id)
    b.join(doc_id)

    a.wait_for("user-joined", lambda d: d["userId"] == owner.id)
    a.wait_for("presence-update", lambda d: d["count"] == 2)
    presence = _presence(api_client, owner, doc_id)
    assert presence["count"] == 2
    assert {u["userId"] for u in presence["users"]} == {owner.id}
    assert all(u["displayName"] == owner.display_name for u in presence["users"])

    active = api_client.client.get(
        "/api/v1/collab/documents", headers=owner.auth_headers
    ).json()
    assert any(
        d["documentId"] == doc_id and d["userCount"] == 2 for d in active["documents"]
    )

    b.close()
    a.wait_for("user-left", lambda d: d["userId"] == owner.id)
    api_client.poll_until(
        lambda: _presence(api_client, owner, doc_id)["count"],
        lambda count: count == 1,
        timeout_seconds=5,
        description="presence count to drop to 1",
    )


def test_cursor_and_typing_indicators_fan_out(api_client, sockets):
    owner = api_client.register_user("collab-qa-cursor")
    doc_id = api_client.create_document(owner, f"Cursor {api_client.run_id}", "x")["id"]
    a = sockets(owner.access_token)
    b = sockets(owner.access_token)
    a.join(doc_id)
    b.join(doc_id)

    a.client.emit(
        "cursor-update",
        {"documentId": doc_id, "cursor": {"index": 3, "length": 0}, "selection": None},
    )
    cursor = b.wait_for("cursor-update")
    assert cursor["cursor"] == {"index": 3, "length": 0}
    assert cursor["displayName"] == owner.display_name
    assert cursor["color"].startswith("#")

    a.client.emit("typing-indicator", {"documentId": doc_id, "isTyping": True})
    typing = b.wait_for("typing-indicator")
    assert typing["isTyping"] is True and typing["userId"] == owner.id


# --- Socket.IO: comments --------------------------------------------------------------


def test_comment_add_update_delete_broadcast(api_client, sockets):
    owner = api_client.register_user("collab-qa-comments")
    doc_id = api_client.create_document(owner, f"Comments {api_client.run_id}", "x")[
        "id"
    ]
    a = sockets(owner.access_token)
    b = sockets(owner.access_token)
    a.join(doc_id)
    b.join(doc_id)

    comment_id = str(uuid.uuid4())
    a.client.emit(
        "comment-add",
        {
            "documentId": doc_id,
            "comment": {
                "id": comment_id,
                "threadId": comment_id,
                "content": "LGTM",
                "rangeStart": 0,
                "rangeEnd": 4,
            },
            # A spoofed author must be overwritten by the server.
        },
    )
    added_b = b.wait_for("comment-added", lambda d: d["id"] == comment_id)
    added_a = a.wait_for("comment-added", lambda d: d["id"] == comment_id)
    assert added_a == added_b
    assert added_b["author"] == {"userId": owner.id, "displayName": owner.display_name}
    assert added_b["documentId"] == doc_id and added_b["createdAt"]

    a.client.emit(
        "comment-update",
        {"documentId": doc_id, "commentId": comment_id, "content": "LGTM!"},
    )
    updated = b.wait_for("comment-updated", lambda d: d["commentId"] == comment_id)
    assert updated["content"] == "LGTM!" and updated["updatedBy"]["userId"] == owner.id

    a.client.emit("comment-delete", {"documentId": doc_id, "commentId": comment_id})
    deleted = b.wait_for("comment-deleted", lambda d: d["commentId"] == comment_id)
    assert deleted["deletedBy"] == owner.id


def test_document_service_comment_rest_crud(api_client):
    owner = api_client.register_user("collab-qa-rest-comment")
    doc_id = api_client.create_document(
        owner, f"REST comments {api_client.run_id}", "x"
    )["id"]
    created = api_client.client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=owner.auth_headers,
        json={"author_id": owner.id, "content": "first comment"},
    )
    assert created.status_code == 201, created.text
    comment = created.json()
    listed = api_client.client.get(
        f"/api/v1/documents/{doc_id}/comments", headers=owner.auth_headers
    )
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [comment["id"]]
    deleted = api_client.client.delete(
        f"/api/v1/documents/{doc_id}/comments/{comment['id']}",
        headers=owner.auth_headers,
    )
    assert deleted.status_code == 204
    assert (
        api_client.client.get(
            f"/api/v1/documents/{doc_id}/comments", headers=owner.auth_headers
        ).json()
        == []
    )


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] document-service comment routes trust body author_id and have no document authz",
)
def test_document_service_comment_rest_rejects_outsider_and_spoofed_author(api_client):
    owner = api_client.register_user("collab-qa-rest-owner")
    outsider = api_client.register_user("collab-qa-rest-outsider")
    doc_id = api_client.create_document(
        owner, f"Private comments {api_client.run_id}", "x"
    )["id"]
    spoofed = api_client.client.post(
        f"/api/v1/documents/{doc_id}/comments",
        headers=outsider.auth_headers,
        json={"author_id": owner.id, "content": "posted as the owner by someone else"},
    )
    assert spoofed.status_code in {403, 404}, spoofed.text


# --- Socket.IO: history / snapshots -----------------------------------------------------


def test_snapshot_and_history_sync(api_client, sockets):
    owner = api_client.register_user("collab-qa-history")
    doc_id = api_client.create_document(owner, f"History {api_client.run_id}", "x")[
        "id"
    ]
    a = sockets(owner.access_token)
    b = sockets(owner.access_token)
    a.join(doc_id)
    b.join(doc_id)
    a.client.emit("document-update", {"documentId": doc_id, "update": YJS_UPDATE_HELLO})
    b.wait_for("document-update")

    label = f"qa-{api_client.run_id}"
    a.client.emit("request-snapshot", {"documentId": doc_id, "label": label})
    snap_a = a.wait_for("snapshot-created", lambda d: d.get("label") == label)
    snap_b = b.wait_for("snapshot-created", lambda d: d.get("label") == label)
    assert snap_a["id"] == snap_b["id"] and snap_a["createdBy"] == owner.id

    b.client.emit("request-history", {"documentId": doc_id, "limit": 5})
    history = b.wait_for("document-history", lambda d: d["documentId"] == doc_id)
    assert snap_a["id"] in [s["id"] for s in history["snapshots"]]


def test_snapshot_for_unloaded_document_errors(api_client, sockets):
    owner = api_client.register_user("collab-qa-snaperr")
    a = sockets(owner.access_token)
    a.client.emit("request-snapshot", {"documentId": str(uuid.uuid4())})
    error = a.wait_for("snapshot-error")
    assert error["error"] == "Document not found"


# --- Socket.IO: reconnect ----------------------------------------------------------------


def test_reconnect_after_everyone_left_restores_persisted_state(api_client, sockets):
    owner = api_client.register_user("collab-qa-reconnect")
    doc_id = api_client.create_document(owner, f"Reconnect {api_client.run_id}", "x")[
        "id"
    ]
    a = sockets(owner.access_token)
    a.join(doc_id)
    a.client.emit("document-update", {"documentId": doc_id, "update": YJS_UPDATE_HELLO})
    time.sleep(0.5)
    a.close()
    # Wait until the room is evicted from memory (persist-and-cleanup on last leave).
    api_client.poll_until(
        lambda: _presence(api_client, owner, doc_id)["count"],
        lambda count: count == 0,
        timeout_seconds=5,
        description="presence to empty",
    )
    time.sleep(0.5)

    reconnected = sockets(owner.access_token)
    sync = reconnected.join(doc_id)
    assert HELLO_TEXT in base64.b64decode(sync["state"])


def test_switching_documents_leaves_previous_room(api_client, sockets):
    owner = api_client.register_user("collab-qa-switch")
    doc_one = api_client.create_document(owner, f"Switch 1 {api_client.run_id}", "x")[
        "id"
    ]
    doc_two = api_client.create_document(owner, f"Switch 2 {api_client.run_id}", "x")[
        "id"
    ]
    watcher = sockets(owner.access_token)
    mover = sockets(owner.access_token)
    watcher.join(doc_one)
    mover.join(doc_one)
    mover.join(doc_two)
    watcher.wait_for("user-left")
    assert _presence(api_client, owner, doc_one)["count"] == 1
    assert _presence(api_client, owner, doc_two)["count"] == 1


# --- Socket.IO: authorization gaps ([REAL]) -----------------------------------------------


@pytest.mark.xfail(strict=True, reason=REAL_NO_DOC_AUTHZ)
def test_outsider_cannot_join_and_read_someone_elses_document(api_client, sockets):
    owner = api_client.register_user("collab-qa-authz-owner")
    outsider = api_client.register_user("collab-qa-authz-outsider")
    doc_id = api_client.create_document(owner, f"Private {api_client.run_id}", "x")[
        "id"
    ]
    a = sockets(owner.access_token)
    a.join(doc_id)
    a.client.emit("document-update", {"documentId": doc_id, "update": YJS_UPDATE_HELLO})
    time.sleep(0.5)

    intruder = sockets(outsider.access_token)
    ack = intruder.client.call("join-document", {"documentId": doc_id}, timeout=5)
    assert ack.get("success") is False, (
        "outsider was allowed into the owner's document room"
    )


@pytest.mark.xfail(
    strict=True,
    reason=REAL_NO_DOC_AUTHZ + " (comment-add does not require room membership)",
)
def test_unjoined_socket_cannot_inject_comments(api_client, sockets):
    owner = api_client.register_user("collab-qa-inject-owner")
    outsider = api_client.register_user("collab-qa-inject-outsider")
    doc_id = api_client.create_document(owner, f"Inject {api_client.run_id}", "x")["id"]
    a = sockets(owner.access_token)
    a.join(doc_id)

    intruder = sockets(outsider.access_token)  # never joins the room
    intruder.client.emit(
        "comment-add",
        {
            "documentId": doc_id,
            "comment": {
                "id": "evil",
                "threadId": "evil",
                "content": "spam",
                "rangeStart": 0,
                "rangeEnd": 0,
            },
        },
    )
    time.sleep(1.0)
    assert not [c for c in a.got("comment-added") if c["id"] == "evil"]


@pytest.mark.xfail(
    strict=True,
    reason=REAL_NO_DOC_AUTHZ + " (presence leaks user emails for any document)",
)
def test_presence_of_foreign_document_is_not_disclosed(api_client, sockets):
    owner = api_client.register_user("collab-qa-leak-owner")
    outsider = api_client.register_user("collab-qa-leak-outsider")
    doc_id = api_client.create_document(owner, f"Leak {api_client.run_id}", "x")["id"]
    sockets(owner.access_token).join(doc_id)
    response = api_client.client.get(
        f"/api/v1/collab/documents/{doc_id}/presence", headers=outsider.auth_headers
    )
    assert response.status_code in {403, 404} or owner.email not in response.text


# --- y-websocket (the transport the TipTap editor actually uses) ------------------------


@pytest.mark.parametrize("token", [None, "not-a-jwt"])
def test_ywebsocket_rejects_missing_or_invalid_token(token):
    with pytest.raises(websocket.WebSocketBadStatusException) as excinfo:
        _yws_connect(f"document-{uuid.uuid4()}", token)
    assert excinfo.value.status_code == 401


def test_ywebsocket_two_clients_sync_and_late_joiner_receives_state(api_client):
    owner = api_client.register_user("collab-qa-yws")
    room = f"document-{api_client.create_document(owner, f'YWS {api_client.run_id}', 'x')['id']}"
    a = _yws_connect(room, owner.access_token)
    b = _yws_connect(room, owner.access_token)
    try:
        time.sleep(0.3)
        a.send_binary(_sync_update_message(base64.b64decode(YJS_UPDATE_HELLO)))
        assert _yws_collect(b, HELLO_TEXT), "second client never received the update"

        late = _yws_connect(room, owner.access_token)
        try:
            late.send_binary(SYNC_STEP1_EMPTY)
            assert _yws_collect(late, HELLO_TEXT), (
                "late joiner did not receive document state"
            )
        finally:
            late.close()
    finally:
        a.close()
        b.close()


def test_ywebsocket_client_reconnect_resyncs(api_client):
    owner = api_client.register_user("collab-qa-yws-reconnect")
    room = f"document-{api_client.create_document(owner, f'YWS RC {api_client.run_id}', 'x')['id']}"
    keeper = _yws_connect(room, owner.access_token)
    editor = _yws_connect(room, owner.access_token)
    try:
        editor.close()  # simulate a dropped connection
        keeper.send_binary(_sync_update_message(base64.b64decode(YJS_UPDATE_SECOND)))
        time.sleep(0.3)
        editor = _yws_connect(room, owner.access_token)
        editor.send_binary(SYNC_STEP1_EMPTY)
        assert _yws_collect(editor, SECOND_TEXT), (
            "reconnected client missed edits made while offline"
        )
    finally:
        keeper.close()
        editor.close()


@pytest.mark.xfail(
    strict=True,
    reason=REAL_NO_DOC_AUTHZ + " (y-websocket room accepts any document id)",
)
def test_ywebsocket_outsider_cannot_open_foreign_document_room(api_client):
    owner = api_client.register_user("collab-qa-yws-owner")
    outsider = api_client.register_user("collab-qa-yws-outsider")
    room = f"document-{api_client.create_document(owner, f'YWS private {api_client.run_id}', 'x')['id']}"
    with pytest.raises(websocket.WebSocketBadStatusException):
        _yws_connect(room, outsider.access_token).close()


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] y-websocket upgrade accepts refresh tokens as access tokens",
)
def test_ywebsocket_rejects_refresh_token(api_client):
    user = api_client.register_user("collab-qa-yws-refresh")
    with pytest.raises(websocket.WebSocketBadStatusException):
        _yws_connect(f"document-{uuid.uuid4()}", user.refresh_token).close()


@pytest.mark.xfail(
    strict=True,
    reason="[REAL] collab-service logs the full ?token= URL on y-websocket connect",
)
def test_ywebsocket_does_not_log_access_tokens(api_client):
    container = os.getenv("OTTERWORKS_COLLAB_CONTAINER", "otterworks-collab-service")
    if not shutil.which("docker"):
        pytest.skip("docker CLI not available to inspect collab-service logs")
    user = api_client.register_user("collab-qa-yws-logs")
    _yws_connect(f"document-{uuid.uuid4()}", user.access_token).close()
    time.sleep(0.5)
    logs = subprocess.run(
        ["docker", "logs", "--since", "30s", container],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if logs.returncode != 0:
        pytest.skip(f"cannot read {container} logs: {logs.stderr.strip()}")
    assert user.access_token not in logs.stdout + logs.stderr

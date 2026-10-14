"""QA: Socket.IO collaboration protocol through the API gateway (presence, cursors, comments, CRDT, reconnect)."""

import base64
import os
import time

import pycrdt
import pytest
import socketio

pytestmark = [pytest.mark.api_flow, pytest.mark.websocket]


def _collab_url(base_url: str) -> str:
    return os.getenv("OTTERWORKS_COLLAB_WS_URL", base_url.replace("http://", "ws://").replace("https://", "wss://"))


class Peer:
    def __init__(self, base_url: str, token: str):
        self.events: dict[str, list] = {}
        self.client = socketio.Client(reconnection=False, request_timeout=5)
        self.client.on("*", self._record)
        self.client.connect(_collab_url(base_url), auth={"token": token}, transports=["websocket"])

    def _record(self, event, data=None):
        self.events.setdefault(event, []).append(data)

    def join(self, document_id: str) -> dict:
        return self.client.call("join-document", {"documentId": document_id}, timeout=5)

    def emit(self, event: str, payload: dict) -> None:
        self.client.emit(event, payload)

    def wait(self, event: str, predicate=lambda _: True, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for item in self.events.get(event, []):
                if predicate(item):
                    return item
            time.sleep(0.05)
        raise AssertionError(f"timed out waiting for {event}; got {list(self.events)}")

    def close(self) -> None:
        if self.client.connected:
            self.client.disconnect()


def _yjs_insert(doc: pycrdt.Doc, index: int, value: str) -> str:
    before = doc.get_state()
    doc.get("content", type=pycrdt.Text).insert(index, value)
    return base64.b64encode(doc.get_update(before)).decode()


def _decode_state(state_b64: str) -> str:
    doc = pycrdt.Doc()
    doc.apply_update(base64.b64decode(state_b64))
    return str(doc.get("content", type=pycrdt.Text))


@pytest.fixture
def session(api_client, base_url):
    owner = api_client.register_user("qa-sio-owner")
    peer = api_client.register_user("qa-sio-peer")
    document = api_client.create_document(owner, title=f"QA SocketIO {api_client.run_id}", content="seed")
    peers: list[Peer] = []

    def connect(user) -> Peer:
        p = Peer(base_url, user.access_token)
        peers.append(p)
        return p

    yield owner, peer, document, connect
    for p in peers:
        p.close()


def test_presence_endpoint_reflects_join_and_disconnect(api_client, session):
    owner, peer, document, connect = session
    a, b = connect(owner), connect(peer)
    assert a.join(document["id"])["success"] is True
    assert b.join(document["id"])["success"] is True

    def presence():
        r = api_client.client.get(f"/api/v1/collab/documents/{document['id']}/presence", headers=owner.auth_headers)
        assert r.status_code == 200, r.text
        return r.json()

    body = api_client.poll_until(presence, lambda p: p["count"] == 2, timeout_seconds=5, description="presence=2")
    names = sorted(u["displayName"] for u in body["users"])
    assert names == sorted([owner.display_name, peer.display_name])
    assert len({u["color"] for u in body["users"]}) == 2

    b.close()
    a.wait("user-left", lambda d: d["userId"] == peer.id)
    api_client.poll_until(presence, lambda p: p["count"] == 1, timeout_seconds=5, description="presence=1")


def test_presence_endpoint_requires_authentication(api_client, session):
    _, _, document, _ = session
    r = api_client.client.get(f"/api/v1/collab/documents/{document['id']}/presence")
    assert r.status_code == 401, r.text


def test_cursor_and_typing_are_relayed_with_identity(session):
    owner, peer, document, connect = session
    a, b = connect(owner), connect(peer)
    a.join(document["id"])
    b.join(document["id"])
    a.emit("cursor-update", {"documentId": document["id"], "cursor": {"index": 3, "length": 0}, "selection": None})
    cursor = b.wait("cursor-update")
    assert cursor["userId"] == owner.id
    assert cursor["displayName"] == owner.display_name
    assert cursor["cursor"] == {"index": 3, "length": 0}

    a.emit("typing-indicator", {"documentId": document["id"], "isTyping": True})
    typing = b.wait("typing-indicator")
    assert typing["userId"] == owner.id and typing["isTyping"] is True


def test_comments_broadcast_with_server_side_author(session):
    owner, peer, document, connect = session
    a, b = connect(owner), connect(peer)
    a.join(document["id"])
    b.join(document["id"])
    a.emit(
        "comment-add",
        {
            "documentId": document["id"],
            "comment": {
                "id": "qa-c1",
                "threadId": "qa-t1",
                "content": "Please review",
                "rangeStart": 0,
                "rangeEnd": 4,
                "author": {"userId": "spoofed", "displayName": "Mallory"},
            },
        },
    )
    added = b.wait("comment-added")
    assert added["content"] == "Please review"
    assert added["author"]["userId"] == owner.id
    assert a.wait("comment-added")["id"] == "qa-c1"

    b.emit("comment-update", {"documentId": document["id"], "commentId": "qa-c1", "content": "Reviewed"})
    updated = a.wait("comment-updated")
    assert updated["content"] == "Reviewed" and updated["updatedBy"]["userId"] == peer.id

    b.emit("comment-delete", {"documentId": document["id"], "commentId": "qa-c1"})
    assert a.wait("comment-deleted") == {"commentId": "qa-c1", "deletedBy": peer.id}


def test_concurrent_yjs_updates_merge_and_late_joiner_syncs(api_client, session):
    owner, peer, document, connect = session
    a, b = connect(owner), connect(peer)
    a.join(document["id"])
    b.join(document["id"])
    doc_a, doc_b = pycrdt.Doc(), pycrdt.Doc()
    a.emit("document-update", {"documentId": document["id"], "update": _yjs_insert(doc_a, 0, "AAA")})
    b.emit("document-update", {"documentId": document["id"], "update": _yjs_insert(doc_b, 0, "BBB")})
    from_a = b.wait("document-update")
    from_b = a.wait("document-update")
    doc_b.apply_update(base64.b64decode(from_a["update"]))
    doc_a.apply_update(base64.b64decode(from_b["update"]))
    text_a = str(doc_a.get("content", type=pycrdt.Text))
    assert text_a == str(doc_b.get("content", type=pycrdt.Text))
    assert "AAA" in text_a and "BBB" in text_a

    late_user = api_client.register_user("qa-sio-late")
    late = connect(late_user)
    late.join(document["id"])
    sync = late.wait("sync-document")
    assert _decode_state(sync["state"]) == text_a


def test_reconnect_after_drop_resyncs_missed_edits(session):
    owner, peer, document, connect = session
    a, b = connect(owner), connect(peer)
    a.join(document["id"])
    b.join(document["id"])
    b.close()
    a.wait("user-left", lambda d: d["userId"] == peer.id)

    a.emit("document-update", {"documentId": document["id"], "update": _yjs_insert(pycrdt.Doc(), 0, "missed")})
    time.sleep(0.3)
    b2 = connect(peer)
    b2.join(document["id"])
    assert _decode_state(b2.wait("sync-document")["state"]) == "missed"
    assert a.wait("user-joined", lambda d: d["userId"] == peer.id)


def test_snapshot_and_history_roundtrip(session):
    owner, _, document, connect = session
    a = connect(owner)
    a.join(document["id"])
    a.emit("document-update", {"documentId": document["id"], "update": _yjs_insert(pycrdt.Doc(), 0, "v1")})
    time.sleep(0.2)
    a.emit("request-snapshot", {"documentId": document["id"], "label": "qa-milestone"})
    snap = a.wait("snapshot-created")
    assert snap["label"] == "qa-milestone" and snap["createdBy"] == owner.id
    a.emit("request-history", {"documentId": document["id"], "limit": 5})
    history = a.wait("document-history")
    assert history["snapshots"][0]["id"] == snap["id"]
    assert _decode_state(history["snapshots"][0]["state"]) == "v1"


def test_unshared_user_cannot_join_private_document(api_client, session):
    owner, outsider, document, connect = session
    a = connect(owner)
    a.join(document["id"])
    a.emit("document-update", {"documentId": document["id"], "update": _yjs_insert(pycrdt.Doc(), 0, "secret")})
    time.sleep(0.2)
    intruder = connect(outsider)
    ack = intruder.join(document["id"])
    assert ack.get("success") is not True, "unshared user was allowed to join a private document's collaboration room"

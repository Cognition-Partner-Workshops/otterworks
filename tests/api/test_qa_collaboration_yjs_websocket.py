"""QA: raw Yjs (y-websocket) collaboration on collab-service :8084, as used by the web editor."""

import pytest
import websocket

from qa_yjs_client import (
    YjsClient,
    collab_yjs_url,
    decode_awareness_message,
    pump_until,
)

pytestmark = [pytest.mark.api_flow, pytest.mark.websocket]


def _room(document_id: str) -> str:
    return f"document-{document_id}"


@pytest.fixture
def two_users_and_doc(api_client):
    owner = api_client.register_user("qa-yjs-owner")
    peer = api_client.register_user("qa-yjs-peer")
    document = api_client.create_document(owner, title=f"QA Yjs {api_client.run_id}", content="seed")
    return owner, peer, document


def _expect_rejected(url: str) -> int:
    with pytest.raises(websocket.WebSocketBadStatusException) as exc:
        websocket.create_connection(url, timeout=5)
    return exc.value.status_code


def test_yjs_upgrade_rejects_missing_token():
    assert _expect_rejected(f"{collab_yjs_url()}/document-qa-no-token") == 401


def test_yjs_upgrade_rejects_tampered_token(api_client):
    user = api_client.register_user("qa-yjs-tamper")
    tampered = user.access_token[:-4] + ("AAAA" if not user.access_token.endswith("AAAA") else "BBBB")
    assert _expect_rejected(f"{collab_yjs_url()}/document-qa-tamper?token={tampered}") == 401


def test_yjs_valid_token_receives_sync_step1(two_users_and_doc):
    owner, _, document = two_users_and_doc
    client = YjsClient(_room(document["id"]), owner.access_token).connect()
    try:
        pump_until([client], lambda: client.received_sync_step1, timeout_seconds=5, description="sync step1")
    finally:
        client.close()


def test_yjs_two_users_concurrent_edits_converge(two_users_and_doc):
    owner, peer, document = two_users_and_doc
    room = _room(document["id"])
    a = YjsClient(room, owner.access_token).connect()
    b = YjsClient(room, peer.access_token).connect()
    try:
        pump_until([a, b], lambda: a.received_sync_step1 and b.received_sync_step1, description="initial sync")
        # Both insert at index 0 before seeing each other's edit -> genuine concurrent conflict.
        a.text.insert(0, "Alice-was-here ")
        b.text.insert(0, "Bob-was-here ")
        pump_until(
            [a, b],
            lambda: a.content() == b.content() and "Alice-was-here" in a.content() and "Bob-was-here" in a.content(),
            description="CRDT convergence of concurrent inserts",
        )
        a.text.insert(len(a.text), " tail")
        b.text.insert(0, "head ")
        pump_until(
            [a, b],
            lambda: a.content() == b.content() and a.content().startswith("head ") and a.content().endswith(" tail"),
            description="second round convergence",
        )
    finally:
        a.close()
        b.close()


def test_yjs_late_joiner_receives_full_state(two_users_and_doc):
    owner, peer, document = two_users_and_doc
    room = _room(document["id"])
    a = YjsClient(room, owner.access_token).connect()
    try:
        pump_until([a], lambda: a.received_sync_step1, description="owner sync")
        a.text.insert(0, "written before peer joined")
        a.pump(0.5)
        late = YjsClient(room, peer.access_token).connect()
        try:
            pump_until([a, late], lambda: late.content() == "written before peer joined", description="late join sync")
        finally:
            late.close()
    finally:
        a.close()


def test_yjs_reconnect_after_drop_merges_offline_edits(two_users_and_doc):
    owner, peer, document = two_users_and_doc
    room = _room(document["id"])
    a = YjsClient(room, owner.access_token).connect()
    b = YjsClient(room, peer.access_token).connect()
    try:
        a.text.insert(0, "base")
        pump_until([a, b], lambda: b.content() == "base", description="initial replication")

        b.drop()
        a.text.insert(len(a.text), " +online-edit")
        b.text.insert(0, "offline-edit+ ")
        a.pump(0.3)

        b.connect()
        pump_until(
            [a, b],
            lambda: a.content() == b.content() and "online-edit" in a.content() and "offline-edit" in a.content(),
            description="convergence after reconnect",
        )
    finally:
        a.close()
        b.close()


def test_yjs_awareness_cursor_state_is_relayed(two_users_and_doc):
    owner, peer, document = two_users_and_doc
    room = _room(document["id"])
    a = YjsClient(room, owner.access_token).connect()
    b = YjsClient(room, peer.access_token).connect()
    try:
        pump_until([a, b], lambda: a.received_sync_step1 and b.received_sync_step1, description="initial sync")
        b.awareness_messages.clear()
        state = {"user": {"name": owner.display_name, "color": "#ef4444"}, "cursor": {"anchor": 1, "head": 3}}
        a.send_awareness(state)

        def got_cursor() -> bool:
            for message in b.awareness_messages:
                for client_id, _, s in decode_awareness_message(message):
                    if client_id == a.doc.client_id and s and s.get("cursor") == state["cursor"]:
                        return True
            return False

        pump_until([a, b], got_cursor, timeout_seconds=5, description="awareness relay")
    finally:
        a.close()
        b.close()


def test_yjs_rooms_are_isolated(api_client):
    owner = api_client.register_user("qa-yjs-iso")
    doc1 = api_client.create_document(owner, title=f"QA iso 1 {api_client.run_id}", content="x")
    doc2 = api_client.create_document(owner, title=f"QA iso 2 {api_client.run_id}", content="y")
    a = YjsClient(_room(doc1["id"]), owner.access_token).connect()
    b = YjsClient(_room(doc2["id"]), owner.access_token).connect()
    try:
        a.text.insert(0, "only-in-doc1")
        a.pump(0.5)
        b.pump(1.0)
        assert b.content() == ""
    finally:
        a.close()
        b.close()


def test_yjs_unshared_user_cannot_read_private_document(two_users_and_doc):
    """A user with no share on the document must not be able to join its Yjs room."""
    owner, outsider, document = two_users_and_doc
    room = _room(document["id"])
    a = YjsClient(room, owner.access_token).connect()
    try:
        a.text.insert(0, "confidential")
        a.pump(0.5)
        try:
            intruder = YjsClient(room, outsider.access_token).connect()
        except websocket.WebSocketBadStatusException as exc:
            assert exc.status_code in (401, 403)
            return
        try:
            intruder.pump(1.5)
            assert intruder.content() != "confidential", (
                "unshared user joined the document's Yjs room and read its content (no per-document authorization)"
            )
        finally:
            intruder.close()
    finally:
        a.close()

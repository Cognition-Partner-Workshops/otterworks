"""Minimal y-websocket protocol client used by the QA collaboration API tests."""

import json
import os
import time
from typing import Any

import pycrdt
import websocket

MSG_SYNC = 0
MSG_AWARENESS = 1


def collab_yjs_url() -> str:
    return os.getenv("OTTERWORKS_COLLAB_YJS_URL", "ws://localhost:8084").rstrip("/")


def _write_var_uint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    out.append(value)
    return bytes(out)


def _read_var_uint(buf: bytes, pos: int) -> tuple[int, int]:
    result, shift = 0, 0
    while True:
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, pos


def _write_var_string(value: str) -> bytes:
    data = value.encode()
    return _write_var_uint(len(data)) + data


def encode_awareness_message(client_id: int, clock: int, state: dict[str, Any] | None) -> bytes:
    payload = _write_var_uint(1) + _write_var_uint(client_id) + _write_var_uint(clock)
    payload += _write_var_string(json.dumps(state) if state is not None else "null")
    return _write_var_uint(MSG_AWARENESS) + _write_var_uint(len(payload)) + payload


def decode_awareness_message(message: bytes) -> list[tuple[int, int, Any]]:
    pos = 1
    _, pos = _read_var_uint(message, pos)
    count, pos = _read_var_uint(message, pos)
    entries = []
    for _ in range(count):
        client_id, pos = _read_var_uint(message, pos)
        clock, pos = _read_var_uint(message, pos)
        length, pos = _read_var_uint(message, pos)
        state = json.loads(message[pos : pos + length].decode())
        pos += length
        entries.append((client_id, clock, state))
    return entries


class YjsClient:
    """Speaks the y-websocket sync/awareness protocol against collab-service."""

    def __init__(self, room: str, token: str, doc: pycrdt.Doc | None = None, base_url: str | None = None):
        self.room = room
        self.token = token
        self.base_url = base_url or collab_yjs_url()
        self.doc = doc or pycrdt.Doc()
        self.text = self.doc.get("content", type=pycrdt.Text)
        self.awareness_messages: list[bytes] = []
        self.received_sync_step1 = False
        self._applying_remote = False
        self.ws: websocket.WebSocket | None = None
        self.doc.observe(self._on_local_update)

    def _on_local_update(self, event: Any) -> None:
        if self._applying_remote or self.ws is None or not self.ws.connected:
            return
        self.ws.send_binary(pycrdt.create_update_message(event.update))

    def connect(self) -> "YjsClient":
        self.ws = websocket.create_connection(f"{self.base_url}/{self.room}?token={self.token}", timeout=5)
        self.ws.send_binary(pycrdt.create_sync_message(self.doc))
        return self

    def drop(self) -> None:
        if self.ws is not None:
            try:
                self.ws.sock.shutdown(2)
            except OSError:
                pass
            self.ws.close()
            self.ws = None

    def pump(self, seconds: float = 0.5) -> None:
        assert self.ws is not None, "client is not connected"
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.ws.settimeout(max(0.05, deadline - time.monotonic()))
            try:
                message = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                return
            if not isinstance(message, bytes) or not message:
                continue
            if message[0] == MSG_SYNC:
                if len(message) > 1 and message[1] == 0:
                    self.received_sync_step1 = True
                self._applying_remote = True
                try:
                    reply = pycrdt.handle_sync_message(message[1:], self.doc)
                finally:
                    self._applying_remote = False
                if reply is not None:
                    self.ws.send_binary(reply)
            elif message[0] == MSG_AWARENESS:
                self.awareness_messages.append(message)

    def send_awareness(self, state: dict[str, Any] | None, clock: int = 1) -> None:
        assert self.ws is not None
        self.ws.send_binary(encode_awareness_message(self.doc.client_id, clock, state))

    def content(self) -> str:
        return str(self.text)

    def close(self) -> None:
        self.drop()


def pump_until(clients: list[YjsClient], predicate, timeout_seconds: float = 10.0, description: str = "condition"):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        for client in clients:
            client.pump(0.1)
        if predicate():
            return
    raise AssertionError(
        f"Timed out waiting for {description}; contents={[c.content() for c in clients]!r}"
    )

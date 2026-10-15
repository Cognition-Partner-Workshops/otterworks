"""Helpers for black-box collaboration tests (Socket.IO + y-websocket)."""

import os
import threading
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import pycrdt
import socketio
import websocket


def socketio_url(base_url: str) -> str:
    return os.getenv(
        "OTTERWORKS_COLLAB_WS_URL",
        base_url.replace("http://", "ws://").replace("https://", "wss://"),
    )


def yjs_ws_url(base_url: str) -> str:
    """y-websocket is served by collab-service directly (the web app uses VITE_COLLAB_WS_URL)."""
    explicit = os.getenv("OTTERWORKS_COLLAB_YJS_URL")
    if explicit:
        return explicit.rstrip("/")
    host = urlparse(base_url).hostname or "localhost"
    return f"ws://{host}:8084"


def collab_http_url(base_url: str) -> str:
    explicit = os.getenv("OTTERWORKS_COLLAB_HTTP_URL")
    if explicit:
        return explicit.rstrip("/")
    host = urlparse(base_url).hostname or "localhost"
    return f"http://{host}:8084"


def wait_for(predicate: Callable[[], Any], timeout: float = 10.0, description: str = "condition") -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {description}")


class RecordingSocket:
    """Socket.IO client that records every event it receives."""

    def __init__(self, url: str, token: str | None):
        self.url = url
        self.token = token
        self.events: list[tuple[str, Any]] = []
        self.client = socketio.Client(reconnection=False, request_timeout=5)
        self.client.on("*", self._record)

    def _record(self, event: str, data: Any = None) -> None:
        self.events.append((event, data))

    def connect(self) -> "RecordingSocket":
        self.client.connect(self.url, auth={"token": self.token}, transports=["websocket"], wait_timeout=5)
        return self

    def join(self, document_id: str) -> dict:
        return self.client.call("join-document", {"documentId": document_id}, timeout=5)

    def emit(self, event: str, data: dict) -> None:
        self.client.emit(event, data)

    def received(self, event: str) -> list[Any]:
        return [data for name, data in self.events if name == event]

    def wait_for_event(self, event: str, predicate: Callable[[Any], bool] = lambda _: True, timeout: float = 5.0) -> Any:
        return wait_for(
            lambda: next((d for d in self.received(event) if predicate(d)), None),
            timeout=timeout,
            description=f"socket.io event {event!r}",
        )

    def close(self) -> None:
        if self.client.connected:
            self.client.disconnect()


class YjsClient:
    """Minimal y-websocket client: speaks the Yjs sync protocol over a raw WebSocket."""

    def __init__(self, base: str, room: str, token: str | None):
        query = f"?token={token}" if token is not None else ""
        self.url = f"{base}/{room}{query}"
        self.doc = pycrdt.Doc()
        self.text = self.doc.get("probe", type=pycrdt.Text)
        self.synced = threading.Event()
        self.ws: websocket.WebSocket | None = None
        self._stop = threading.Event()
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._applying_remote = False
        self._subscription = None

    def connect(self) -> "YjsClient":
        self.ws = websocket.create_connection(self.url, timeout=5)
        self.ws.settimeout(0.2)
        self._subscription = self.doc.observe(self._on_local_update)
        self._send(pycrdt.create_sync_message(self.doc))
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        wait_for(self.synced.is_set, timeout=10, description=f"y-websocket sync for {self.url}")
        return self

    def _send(self, payload: bytes) -> None:
        with self._lock:
            if self.ws is not None and self.ws.connected:
                self.ws.send_binary(payload)

    def _on_local_update(self, event: Any) -> None:
        if not self._applying_remote:
            self._send(pycrdt.create_update_message(event.update))

    def _read_loop(self) -> None:
        while not self._stop.is_set():
            try:
                message = self.ws.recv() if self.ws else None
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                return
            if not isinstance(message, bytes) or not message:
                continue
            if message[0] == pycrdt.YMessageType.SYNC:
                self._applying_remote = True
                try:
                    reply = pycrdt.handle_sync_message(message[1:], self.doc)
                finally:
                    self._applying_remote = False
                if message[1] in (pycrdt.YSyncMessageType.SYNC_STEP2, pycrdt.YSyncMessageType.SYNC_UPDATE):
                    self.synced.set()
                if reply is not None:
                    self._send(reply)

    def insert(self, value: str) -> None:
        self.text += value

    def value(self) -> str:
        return str(self.text)

    def close(self) -> None:
        self._stop.set()
        if self._subscription is not None:
            self.doc.unobserve(self._subscription)
            self._subscription = None
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        if self._reader is not None:
            self._reader.join(timeout=2)
            self._reader = None

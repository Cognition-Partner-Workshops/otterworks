from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
import unittest
from typing import Any
from urllib.parse import urlencode

from collection_slack.config import load_config
from collection_slack.server import App, build_server

from .fake_v3 import FakeV3

API_KEY = "cog_FAKE-test-key-0123456789abcdef"
ACCESS_TOKEN = "ui-access-token-for-tests-0123456789"
ORG_ID = "org-fixture-example"
PERSONA = "user-fixture-persona"
WEBHOOK_SECRET = "webhook-secret-for-tests-0123456789"


class Client:
    def __init__(self, port: int) -> None:
        self.port = port
        self.cookie: str | None = None

    def request(
        self, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None, raw: bytes | None = None
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}"}
        if self.cookie:
            h["Cookie"] = self.cookie
        payload = raw
        if body is not None:
            payload = json.dumps(body).encode()
            h.update({"Content-Type": "application/json", "X-Collection-Client": "1"})
        h.update(headers or {})
        conn.request(method, path, body=payload, headers=h)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, data

    def login(self, token: str = ACCESS_TOKEN) -> int:
        status, headers, _ = self.request(
            "POST",
            "/login",
            raw=urlencode({"token": token}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if "set-cookie" in headers:
            self.cookie = headers["set-cookie"].split(";")[0]
        return status

    def json(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        status, _, data = self.request(method, path, body)
        return status, json.loads(data) if data else None


class AppCase(unittest.TestCase):
    live = True
    extra_env: dict[str, str] = {}

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="collection-slack-test-")
        self.db_path = os.path.join(self.tmp, "app.sqlite3")
        self.fake = FakeV3(API_KEY, ORG_ID, webhook_secret=WEBHOOK_SECRET).start()
        self.addCleanup(self.fake.stop)
        self.start_app()

    def env(self) -> dict[str, str]:
        e = {
            "COLLECTION_ACCESS_TOKEN": ACCESS_TOKEN,
            "COLLECTION_DB_PATH": self.db_path,
            "COLLECTION_PORT": "0",
            "COLLECTION_POLL_INTERVAL": "3600",
            "COLLECTION_HTTP_TIMEOUT": "0.5",
        }
        if self.live:
            e.update(
                {
                    "COLLECTION_MODE": "live",
                    "DEVIN_API_KEY": API_KEY,
                    "COLLECTION_DEVIN_ORG_ID": ORG_ID,
                    "COLLECTION_CREATE_AS_USER_ID": PERSONA,
                    "COLLECTION_DEVIN_API_BASE": self.fake.base,
                    "COLLECTION_REPOS": "example-org/example-repo",
                }
            )
        e.update({k: v.replace("{fake}", self.fake.base) for k, v in self.extra_env.items()})
        return e

    def start_app(self) -> None:
        self.app = App(load_config(self.env()))
        self.app.bridge.start()
        self.server = build_server(self.app)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = Client(self.server.server_address[1])
        self.assertEqual(self.client.login(), 303)

    def stop_app(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.app.bridge.stop()
        self.app.store.close()

    def tearDown(self) -> None:
        self.stop_app()

    def channel_id(self, name: str = "general") -> int:
        _, data = self.client.json("GET", "/api/bootstrap")
        return next(int(c["id"]) for c in data["channels"] if c["name"] == name)

    def post_thread(self, text: str, author: str = "ava", channel: str = "general", cid: str | None = None) -> Any:
        import uuid

        status, data = self.client.json(
            "POST",
            f"/api/channels/{self.channel_id(channel)}/threads",
            {"author": author, "text": text, "client_msg_id": cid or str(uuid.uuid4())},
        )
        self.assertIn(status, (200, 201), data)
        return data

    def reply(self, thread_id: int, text: str, author: str = "ben", cid: str | None = None) -> Any:
        import uuid

        status, data = self.client.json(
            "POST",
            f"/api/threads/{thread_id}/messages",
            {"author": author, "text": text, "client_msg_id": cid or str(uuid.uuid4())},
        )
        self.assertIn(status, (200, 201), data)
        return data

    def thread(self, thread_id: int) -> Any:
        return self.client.json("GET", f"/api/threads/{thread_id}")[1]

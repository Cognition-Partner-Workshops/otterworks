"""Tests for the incident channel. Run: pytest incident/oncall/channel -q"""

from __future__ import annotations

import base64
import http.client
import json
import sys
import threading
from collections.abc import Iterator
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import channel  # noqa: E402

CHANNEL_TOKEN = "test-channel-token-6b1f"
DEVIN_API_KEY = "apk_test_secret_do_not_leak_93c4e2"
GROUP_KEY = '{}/{page="oncall"}:{namespace="otterworks-oncall-before", oncall_group="folder-storm"}'
ORG_ID = "org-0c1d2e3f"
SESSION_ID = "devin-5a6b7c8d9e"


# ------------------------------------------------------------------- fixtures


class FakeDevin:
    """Records every request the channel forwards; `status` sets the reply code."""

    def __init__(self) -> None:
        self.requests: list[dict] = []
        self.status = 200
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fake.requests.append(
                    {"path": self.path, "headers": dict(self.headers.items()), "raw": raw}
                )
                body = json.dumps({"ok": fake.status < 300}).encode()
                self.send_response(fake.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class Running:
    def __init__(self, config: channel.Config) -> None:
        self.server = channel.make_server(config, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def request(
        self,
        method: str,
        path: str,
        body: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = None if body is None else json.dumps(body).encode()
        hdrs = {"Content-Type": "application/json"} if data is not None else {}
        hdrs.update(headers or {})
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse()
        payload = resp.read()
        conn.close()
        return resp.status, dict(resp.getheaders()), payload

    def json(self, method: str, path: str, body: object | None = None, **kw: object) -> tuple:
        status, _, raw = self.request(method, path, body, **kw)  # type: ignore[arg-type]
        return status, json.loads(raw) if raw else {}

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def bearer(token: str = CHANNEL_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_devin() -> Iterator[FakeDevin]:
    fake = FakeDevin()
    yield fake
    fake.close()


@pytest.fixture
def config(tmp_path: Path, fake_devin: FakeDevin) -> channel.Config:
    return channel.Config.from_env(
        {
            "CHANNEL_TOKEN": CHANNEL_TOKEN,
            "DEVIN_API_KEY": DEVIN_API_KEY,
            "DEVIN_API_BASE": fake_devin.base,
            "PERSONA_SRE_USER_ID": "user-sre-111",
            "PERSONA_IM_USER_ID": "user-im-222",
            "STATE_FILE": str(tmp_path / "state.json"),
        }
    )


@pytest.fixture
def app(config: channel.Config) -> Iterator[Running]:
    running = Running(config)
    yield running
    running.close()


STORM = [
    ("postgres", "PostgresCPUThrottled", "warning"),
    ("postgres", "PostgresLongRunningQueries", "warning"),
    ("postgres", "PostgresActiveConnectionsHigh", "warning"),
    ("document-service", "DbPoolSaturated", "warning"),
    ("document-service", "DbStatementTimeouts", "warning"),
    ("document-service", "FolderDigestBacklogGrowing", "warning"),
    ("document-service", "FolderListLatencyHigh", "critical"),
    ("document-service", "DocumentServiceErrorRateHigh", "critical"),
    ("api-gateway", "GatewayLatencyP95High", "warning"),
    ("api-gateway", "GatewayErrorRatioHigh", "critical"),
    ("web-edge", "EdgeLatencyP95High", "warning"),
    ("web-edge", "EdgeErrorRatioHigh", "critical"),
]


def alert(service: str, name: str, severity: str, status: str = "firing", **labels: str) -> dict:
    return {
        "status": status,
        "labels": {
            "alertname": name,
            "service": service,
            "severity": severity,
            "namespace": "otterworks-oncall-before",
            "page": "oncall",
            "oncall_group": "folder-storm",
            **labels,
        },
        "annotations": {"summary": f"{name} on {service}"},
        "startsAt": "2026-10-01T13:02:11.482913377Z",
        "endsAt": "2026-10-01T13:40:00Z" if status == "resolved" else "0001-01-01T00:00:00Z",
        "generatorURL": "http://prometheus/graph",
        "fingerprint": f"fp-{name}",
    }


def payload(alerts: list[dict], status: str | None = None, group_key: str = GROUP_KEY) -> dict:
    firing = any(a["status"] == "firing" for a in alerts)
    return {
        "version": "4",
        "groupKey": group_key,
        "truncatedAlerts": 0,
        "status": status or ("firing" if firing else "resolved"),
        "receiver": "devin-oncall",
        "groupLabels": {"namespace": "otterworks-oncall-before", "oncall_group": "folder-storm"},
        "commonLabels": {"page": "oncall", "namespace": "otterworks-oncall-before"},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager.monitoring:9093",
        "alerts": alerts,
    }


def storm(n: int, resolved: tuple[str, ...] = ()) -> list[dict]:
    return [alert(s, a, sev, "resolved" if a in resolved else "firing") for s, a, sev in STORM[:n]]


def bind_session(app: Running) -> None:
    status, _ = app.json(
        "POST",
        "/api/threads/latest/messages",
        {
            "author": "Devin",
            "text": "Picked this up.",
            "session_url": f"https://partner-workshops.devinenterprise.com/sessions/{SESSION_ID[6:]}",
            "session_id": SESSION_ID,
            "org_id": ORG_ID,
        },
        headers=bearer(),
    )
    assert status == 201


# ---------------------------------------------------------------------- tests


def test_healthz(app: Running) -> None:
    status, body = app.json("GET", "/healthz")
    assert status == 200 and body["ok"] is True


def test_first_payload_creates_one_thread_and_later_payloads_update_it(app: Running) -> None:
    status, first = app.json("POST", "/alertmanager", payload(storm(4)))
    assert status == 200 and first["created"] is True and first["alerts"] == 4

    status, second = app.json("POST", "/alertmanager", payload(storm(12)))
    assert status == 200 and second["created"] is False
    assert second["thread_id"] == first["thread_id"]

    _, state = app.json("GET", "/api/state")
    assert len(state["data"]) == 1
    thread = state["data"][0]
    assert thread["notifications"] == 2
    assert len(thread["alerts"]) == 12
    assert thread["status"] == "firing"
    assert state["html"].count('class="card ') == 1
    assert 'data-count="12"' in state["html"]
    for service in ("web-edge", "api-gateway", "document-service", "postgres"):
        assert f'data-service="{service}"' in state["html"]
    assert "DbPoolSaturated" in state["html"]
    assert "since 13:02:11" in state["html"]


def test_other_group_keys_get_their_own_thread(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(3)))
    app.json("POST", "/alertmanager", payload(storm(2), group_key='{}:{alertname="Other"}'))
    _, state = app.json("GET", "/api/state")
    assert len(state["data"]) == 2


def test_resolved_alerts_flip_and_card_turns_green(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(12)))
    app.json(
        "POST",
        "/alertmanager",
        payload(storm(12, resolved=("DbPoolSaturated", "PostgresActiveConnectionsHigh"))),
    )
    _, state = app.json("GET", "/api/state")
    alerts = {a["name"]: a["status"] for a in state["data"][0]["alerts"]}
    assert alerts["DbPoolSaturated"] == "resolved"
    assert alerts["EdgeErrorRatioHigh"] == "firing"
    assert state["data"][0]["status"] == "firing"
    assert '<li class="alert resolved" data-alert="DbPoolSaturated">' in state["html"]

    app.json("POST", "/alertmanager", payload(storm(12, resolved=tuple(a for _, a, _ in STORM))))
    _, state = app.json("GET", "/api/state")
    assert state["data"][0]["status"] == "resolved"
    assert 'class="card resolved"' in state["html"]
    assert "[RESOLVED]" in state["html"]
    assert 'class="chip ok"' in state["html"]


def test_bad_alertmanager_payload_is_rejected(app: Running) -> None:
    status, _ = app.json("POST", "/alertmanager", {"alerts": []})
    assert status == 400
    status, _ = app.json("POST", "/alertmanager", [1, 2])
    assert status == 400


def test_alertmanager_through_the_ingress_needs_the_token(app: Running) -> None:
    proxied = {"X-Forwarded-For": "203.0.113.9"}
    status, _ = app.json("POST", "/alertmanager", payload(storm(1)), headers=proxied)
    assert status == 401
    status, _ = app.json(
        "POST", "/alertmanager", payload(storm(1)), headers={**proxied, **bearer()}
    )
    assert status == 200


def test_bearer_auth_on_messages_and_reset(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(2)))
    message = {"author": "Devin", "text": "On it."}
    for headers in ({}, bearer("wrong"), {"Authorization": f"Basic {CHANNEL_TOKEN}"}):
        status, resp_headers, _ = app.request(
            "POST", "/api/threads/latest/messages", message, headers=headers
        )
        assert status == 401
        assert resp_headers.get("WWW-Authenticate", "").startswith("Bearer")
        status, _ = app.json("POST", "/api/reset", {}, headers=headers)
        assert status == 401

    _, state = app.json("GET", "/api/state")
    assert len(state["data"]) == 1 and state["data"][0]["messages"] == []

    status, body = app.json("POST", "/api/threads/latest/messages", message, headers=bearer())
    assert status == 201 and body["message_id"]
    status, body = app.json("POST", "/api/reset", {}, headers=bearer())
    assert status == 200 and body["cleared"] == 1
    _, state = app.json("GET", "/api/state")
    assert state["data"] == []


def test_reset_accepts_an_empty_body(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(2)))
    status, _, _ = app.request("POST", "/api/reset", None)
    assert status == 401
    _, state = app.json("GET", "/api/state")
    assert len(state["data"]) == 1

    status, body = app.json("POST", "/api/reset", headers=bearer())
    assert status == 200 and body["cleared"] == 1
    _, state = app.json("GET", "/api/state")
    assert state["data"] == []

    status, _, _ = app.request("POST", "/api/reset", [], headers=bearer())
    assert status == 400


def test_token_endpoints_fail_closed_without_a_configured_token(
    config: channel.Config,
) -> None:
    running = Running(replace(config, channel_token=""))
    try:
        status, _ = running.json("POST", "/api/reset", {}, headers=bearer(""))
        assert status == 503
    finally:
        running.close()


def test_messages_address_thread_by_group_key_id_or_latest(app: Running) -> None:
    _, first = app.json("POST", "/alertmanager", payload(storm(2)))
    quoted = channel.urllib.parse.quote(GROUP_KEY, safe="")
    for key in (quoted, first["thread_id"], "latest"):
        status, _ = app.json(
            "POST", f"/api/threads/{key}/messages", {"text": f"via {key[:8]}"}, headers=bearer()
        )
        assert status == 201
    status, _ = app.json("POST", "/api/threads/nope/messages", {"text": "x"}, headers=bearer())
    assert status == 404
    _, state = app.json("GET", "/api/state")
    assert len(state["data"][0]["messages"]) == 3


def test_devin_message_binds_session_and_renders_images(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(12)))
    status, _ = app.json(
        "POST",
        "/api/threads/latest/messages",
        {
            "author": "Devin",
            "text": "Grafana before the fix:",
            "session_id": SESSION_ID,
            "org_id": ORG_ID,
            "session_url": "https://partner-workshops.devinenterprise.com/sessions/5a6b7c8d9e",
            "attachments": [
                "https://files.example.test/grafana-before.png",
                "javascript:alert(1)",
            ],
        },
        headers=bearer(),
    )
    assert status == 201
    _, state = app.json("GET", "/api/state")
    thread = state["data"][0]
    assert thread["session_id"] == SESSION_ID
    assert '<img src="https://files.example.test/grafana-before.png"' in state["html"]
    assert "javascript:" not in state["html"]
    assert ">Devin session</a>" in state["html"]
    assert "/d/oncall-storm?var-namespace=otterworks-oncall-before" in state["html"]
    assert "alertmanager.otterworks.app/#/alerts?filter=" in state["html"]


def test_reply_forwards_exact_body_and_never_leaks_the_key(
    app: Running, fake_devin: FakeDevin, capsys: pytest.CaptureFixture[str]
) -> None:
    app.json("POST", "/alertmanager", payload(storm(12)))
    bind_session(app)
    text = "Customers on the before tenant can't open folders. What's the ETA?"
    status, headers, raw = app.request(
        "POST", "/api/threads/latest/reply", {"persona": "sre", "text": text}
    )
    assert status == 200
    body = json.loads(raw)
    assert body["delivery"]["state"] == "delivered"
    assert body["delivery"]["status"] == 200

    assert len(fake_devin.requests) == 1
    sent = fake_devin.requests[0]
    assert sent["path"] == f"/v3/organizations/{ORG_ID}/sessions/{SESSION_ID}/messages"
    assert json.loads(sent["raw"]) == {"message": text, "message_as_user_id": "user-sre-111"}
    assert list(json.loads(sent["raw"])) == ["message", "message_as_user_id"]
    assert sent["headers"]["Authorization"] == f"Bearer {DEVIN_API_KEY}"
    assert sent["headers"]["Content-Type"] == "application/json"

    status, _ = app.json(
        "POST", "/api/threads/latest/reply", {"persona": "incident-manager", "text": "Status?"}
    )
    assert status == 200
    assert json.loads(fake_devin.requests[1]["raw"]) == {
        "message": "Status?",
        "message_as_user_id": "user-im-222",
    }

    _, _, page = app.request("GET", "/")
    _, _, state_raw = app.request("GET", "/api/state")
    state = json.loads(state_raw)
    messages = state["data"][0]["messages"]
    assert [m["author"] for m in messages] == ["Devin", "SRE (on call)", "Incident manager"]
    assert messages[1]["delivery"]["state"] == "delivered"
    assert 'class="tick delivered"' in state["html"]

    captured = capsys.readouterr()
    snapshot = Path(app.server.app.config.state_file).read_text()  # type: ignore[attr-defined]
    for blob in (raw.decode(), state_raw.decode(), page.decode(), captured.err, captured.out):
        assert DEVIN_API_KEY not in blob
    assert DEVIN_API_KEY not in snapshot
    assert DEVIN_API_KEY not in repr(app.server.app.config)  # type: ignore[attr-defined]
    assert '"event": "devin_forward"' in captured.err


def test_reply_failure_shows_failed_tick(app: Running, fake_devin: FakeDevin) -> None:
    app.json("POST", "/alertmanager", payload(storm(3)))
    bind_session(app)
    fake_devin.status = 403
    status, body = app.json("POST", "/api/threads/latest/reply", {"persona": "sre", "text": "hi"})
    assert status == 200
    assert body["delivery"] == {"state": "failed", "status": 403, "at": body["delivery"]["at"]}
    _, state = app.json("GET", "/api/state")
    assert 'class="tick failed"' in state["html"]
    assert "Not delivered (HTTP 403)" in state["html"]


def test_reply_when_devin_api_is_down(app: Running, fake_devin: FakeDevin) -> None:
    app.json("POST", "/alertmanager", payload(storm(3)))
    bind_session(app)
    fake_devin.close()
    status, body = app.json("POST", "/api/threads/latest/reply", {"persona": "sre", "text": "hi"})
    assert status == 200 and body["delivery"]["state"] == "failed"
    assert DEVIN_API_KEY not in json.dumps(body)


def test_reply_before_session_is_bound_is_not_sent(app: Running, fake_devin: FakeDevin) -> None:
    app.json("POST", "/alertmanager", payload(storm(3)))
    status, body = app.json("POST", "/api/threads/latest/reply", {"persona": "sre", "text": "hi"})
    assert status == 200 and body["delivery"]["state"] == "not_sent"
    assert fake_devin.requests == []


def test_reply_without_persona_user_id_is_not_sent(
    config: channel.Config, fake_devin: FakeDevin
) -> None:
    personas = (channel.Persona("sre", "SRE (on call)", ""), config.personas[1])
    running = Running(replace(config, personas=personas))
    try:
        running.json("POST", "/alertmanager", payload(storm(1)))
        bind_session(running)
        _, body = running.json("POST", "/api/threads/latest/reply", {"persona": "sre", "text": "x"})
        assert body["delivery"] == {
            "state": "not_sent",
            "detail": "PERSONA_SRE_USER_ID is unset on the channel, reply kept here",
        }
        assert fake_devin.requests == []
    finally:
        running.close()


def test_reply_validates_persona_and_text(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(1)))
    for body in ({"persona": "ceo", "text": "x"}, {"persona": "sre", "text": "  "}, {"text": "x"}):
        status, _ = app.json("POST", "/api/threads/latest/reply", body)
        assert status == 400
    status, _ = app.json("POST", "/api/threads/missing/reply", {"persona": "sre", "text": "x"})
    assert status == 404
    status, _, _ = app.request(
        "POST", "/api/threads/latest/reply", headers={"Content-Type": "text/plain"}
    )
    assert status == 415


def test_optional_basic_auth_guards_page_and_reply(config: channel.Config) -> None:
    running = Running(replace(config, basic_auth_password="hunter2-test"))
    try:
        assert running.request("GET", "/")[0] == 401
        assert running.request("GET", "/api/state")[0] == 401
        status, _ = running.json("POST", "/api/threads/latest/reply", {"persona": "sre"})
        assert status == 401
        good = {"Authorization": "Basic " + base64.b64encode(b"oncall:hunter2-test").decode()}
        assert running.request("GET", "/", headers=good)[0] == 200
        assert running.request("GET", "/healthz")[0] == 200
    finally:
        running.close()


def test_alert_and_user_text_is_html_escaped(app: Running) -> None:
    evil = '<script>alert("x")</script>'
    hostile = alert(
        '<img src=x onerror="alert(1)">',
        evil,
        'critical" onmouseover="alert(2)',
    )
    hostile["annotations"]["summary"] = "<b>bold</b> & co"
    app.json("POST", "/alertmanager", payload([hostile]))
    app.json(
        "POST",
        "/api/threads/latest/messages",
        {
            "author": "<i>Devin</i>",
            "text": (
                "**Root cause** <svg onload=alert(3)> [x](javascript:alert(4)) "
                '`<b>code</b>` https://ok.example.test/a_b_c?x=1&y="2"\n- <u>item</u>'
            ),
        },
        headers=bearer(),
    )
    app.json(
        "POST",
        "/api/threads/latest/reply",
        {"persona": "sre", "text": '"><script>alert(5)</script>'},
    )
    _, _, page_raw = app.request("GET", "/")
    _, state = app.json("GET", "/api/state")
    for html_text in (page_raw.decode(), state["html"]):
        feed = html_text.split('<div id="feed">', 1)[-1].split("</footer>", 1)[0]
        assert "<script>" not in feed
        assert "<svg" not in feed and "<img src=x" not in feed
        assert "<b>bold</b>" not in feed and "<i>Devin</i>" not in feed
        assert "javascript:" not in feed.replace("[x](javascript", "")
        assert 'href="javascript' not in feed
        assert 'onmouseover="' not in feed
    html_text = state["html"]
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html_text
    assert "<strong>Root cause</strong>" in html_text
    assert "<code>&lt;b&gt;code&lt;/b&gt;</code>" in html_text
    assert '<a href="https://ok.example.test/a_b_c?x=1&amp;y=" target="_blank"' in html_text
    assert "<li>&lt;u&gt;item&lt;/u&gt;</li>" in html_text
    assert "&quot;&gt;&lt;script&gt;alert(5)&lt;/script&gt;" in html_text


def test_snapshot_restore_keeps_the_thread(config: channel.Config, fake_devin: FakeDevin) -> None:
    first = Running(config)
    try:
        first.json("POST", "/alertmanager", payload(storm(12)))
        bind_session(first)
        first.json("POST", "/api/threads/latest/reply", {"persona": "sre", "text": "Ack"})
        _, before = first.json("GET", "/api/state")
    finally:
        first.close()

    assert Path(config.state_file).exists()
    second = Running(config)
    try:
        _, after = second.json("GET", "/api/state")
        assert after["data"] == before["data"]
        assert after["version"] > before["version"]
        status, body = second.json("POST", "/alertmanager", payload(storm(12)))
        assert body["created"] is False
        status, body = second.json(
            "POST",
            "/api/threads/latest/messages",
            {"text": "Back after restart."},
            headers=bearer(),
        )
        assert status == 201
        ids = [m["id"] for m in second.json("GET", "/api/state")[1]["data"][0]["messages"]]
        assert len(ids) == len(set(ids)) == 3
    finally:
        second.close()


def test_corrupt_snapshot_starts_empty(config: channel.Config) -> None:
    Path(config.state_file).write_text("{not json")
    running = Running(config)
    try:
        _, state = running.json("GET", "/api/state")
        assert state["data"] == []
    finally:
        running.close()


def test_state_poll_returns_short_body_when_nothing_changed(app: Running) -> None:
    app.json("POST", "/alertmanager", payload(storm(1)))
    _, state = app.json("GET", "/api/state")
    _, again = app.json("GET", f"/api/state?since={state['version']}")
    assert again == {"version": state["version"]}


def test_page_shell(app: Running) -> None:
    status, headers, raw = app.request("GET", "/")
    page = raw.decode()
    assert status == 200
    assert "<title>#inc-otterworks" in page and "<h1>#inc-otterworks</h1>" in page
    assert '<option value="sre">SRE (on call)</option>' in page
    assert '<option value="incident-manager">Incident manager</option>' in page
    assert "setTimeout(poll, 2000)" in page
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_persona_defaults_and_overrides() -> None:
    defaults = channel.Config.from_env({})
    assert [p.name for p in defaults.personas] == ["SRE (on call)", "Incident manager"]
    custom = channel.Config.from_env({"PERSONA_SRE_NAME": "Priya (SRE)", "PERSONA_IM_NAME": "Sam"})
    assert [p.name for p in custom.personas] == ["Priya (SRE)", "Sam"]
    assert defaults.devin_api_base == "https://partner-workshops.devinenterprise.com/api"

"""Integration tests against the FAKE v3 server in tests/fake_v3.py (no real Devin calls)."""

from __future__ import annotations

import io
import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import redirect_stderr
from typing import Any

from collection_slack.bridge import STUB_NOTE

from .helpers import ACCESS_TOKEN, API_KEY, PERSONA, WEBHOOK_SECRET, AppCase, Client


def wait_for(pred: Any, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met")


class AttributionAndForwarding(AppCase):
    def test_session_created_with_persona_and_fusion_then_verified(self) -> None:
        t = self.post_thread("@devin please check the nightly load")
        self.assertEqual(t["route"], "direct")
        self.app.bridge.drain()
        creates = self.fake.calls("POST", "/sessions")
        self.assertEqual(len(creates), 1)
        body = creates[0].body
        self.assertEqual(body["create_as_user_id"], PERSONA)
        self.assertEqual(body["devin_mode"], "fusion")
        self.assertEqual(body["repos"], ["example-org/example-repo"])
        self.assertIn("Ava Ramirez: @devin please check the nightly load", body["prompt"])
        sid = next(iter(self.fake.sessions))
        self.assertEqual(len(self.fake.calls("GET", f"/sessions/{sid}")), 1)
        self.assertEqual(self.thread(t["thread_id"])["session"]["state"], "active")

    def test_later_posts_forwarded_with_author_name(self) -> None:
        t = self.post_thread("@devin hello")
        self.app.bridge.drain()
        r = self.reply(t["thread_id"], "row counts look off", author="chloe")
        self.assertEqual(r["route"], "forward")
        self.app.bridge.drain()
        sends = self.fake.calls("POST", "/messages")
        self.assertEqual([s.body for s in sends], [{"message": "Chloe Nguyen: row counts look off"}])
        self.assertEqual(len(self.fake.calls("POST", "/sessions")), 1)

    def test_unmentioned_thread_creates_nothing(self) -> None:
        t = self.post_thread("just chatting")
        self.reply(t["thread_id"], "still no bot")
        self.app.bridge.drain()
        self.assertEqual(self.fake.requests, [])

    def test_poll_dedupes_devin_messages_across_pages_and_restart(self) -> None:
        t = self.post_thread("@devin ping")
        self.app.bridge.drain()
        sid = next(iter(self.fake.sessions))
        for i in range(5):
            self.fake.add_event(sid, "devin", f"answer {i}")
        self.assertEqual(self.app.bridge.poll_once(), 5)
        self.assertEqual(self.app.bridge.poll_once(), 0)
        self.app.store.update_session(t["thread_id"], last_cursor=None)  # replay from the start
        self.assertEqual(self.app.bridge.poll_once(), 0)
        self.stop_app()
        self.start_app()
        self.assertEqual(self.app.bridge.poll_once(), 0)
        msgs = self.thread(t["thread_id"])["messages"]
        self.assertEqual([m["body"] for m in msgs if m["kind"] == "devin"], [f"answer {i}" for i in range(5)])
        self.assertTrue(all(m["author"] == "devin" for m in msgs if m["kind"] == "devin"))

    def test_browser_cannot_send_org_user_or_raw_payload(self) -> None:
        cid = self.channel_id()
        for extra in ({"create_as_user_id": "someone-else"}, {"org_id": "other"}, {"devin_mode": "fast"}):
            status, data = self.client.json(
                "POST",
                f"/api/channels/{cid}/threads",
                {"author": "ava", "text": "@devin hi", "client_msg_id": str(uuid.uuid4()), **extra},
            )
            self.assertEqual(status, 400, data)
        status, _ = self.client.json(
            "POST", f"/api/channels/{cid}/threads", {"author": "devin", "text": "x", "client_msg_id": str(uuid.uuid4())}
        )
        self.assertEqual(status, 400)
        self.assertEqual(self.fake.requests, [])


class VerificationFailsClosed(AppCase):
    def _assert_rejected(self) -> None:
        t = self.post_thread("@devin go")
        self.app.bridge.drain()
        view = self.thread(t["thread_id"])
        self.assertEqual(view["session"]["state"], "rejected")
        self.assertNotIn("url", view["session"])
        self.assertEqual(len(self.fake.calls("POST", "/archive")), 1)
        r = self.reply(t["thread_id"], "follow up")
        self.app.bridge.drain()
        self.assertNotEqual(r["route"], "forward")
        self.assertEqual(self.fake.calls("POST", "/messages"), [])
        self.assertEqual(self.app.bridge.poll_once(), 0)

    def test_user_mismatch(self) -> None:
        self.fake.override_user_id = "user-someone-else"
        self._assert_rejected()

    def test_mode_mismatch(self) -> None:
        self.fake.override_mode = "fast"
        self._assert_rejected()

    def test_verify_http_failure(self) -> None:
        self.fake.fail["get"] = 500
        self._assert_rejected()


class Failures(AppCase):
    def test_create_500_then_retry(self) -> None:
        self.fake.fail["create"] = 500
        t = self.post_thread("@devin first")
        self.app.bridge.drain()
        view = self.thread(t["thread_id"])
        self.assertEqual(view["session"]["state"], "failed")
        self.assertIn("HTTP 500", view["session"]["detail"])
        del self.fake.fail["create"]
        r = self.reply(t["thread_id"], "@devin again")
        self.assertEqual(r["route"], "direct")
        self.app.bridge.drain()
        self.assertEqual(self.thread(t["thread_id"])["session"]["state"], "active")

    def test_create_timeout_is_interrupted(self) -> None:
        self.fake.delay["create"] = 1.5
        t = self.post_thread("@devin slow")
        self.app.bridge.drain()
        self.assertEqual(self.thread(t["thread_id"])["session"]["state"], "interrupted")

    def test_forward_failure_marks_message(self) -> None:
        t = self.post_thread("@devin start")
        self.app.bridge.drain()
        self.fake.fail["send"] = 503
        r = self.reply(t["thread_id"], "this will fail")
        self.app.bridge.drain()
        msgs = self.thread(t["thread_id"])["messages"]
        self.assertEqual(next(m for m in msgs if m["id"] == r["message_id"])["forward_state"], "failed")
        self.assertTrue(any("HTTP 503" in m["body"] for m in msgs if m["kind"] == "system"))

    def test_poll_failure_is_counted_not_raised(self) -> None:
        self.post_thread("@devin start")
        self.app.bridge.drain()
        self.fake.fail["list"] = 502
        self.assertEqual(self.app.bridge.poll_once(), 0)
        self.assertGreaterEqual(self.app.bridge.metrics["http_failures_total"], 1)

    def test_restart_during_create_never_auto_recreates(self) -> None:
        t = self.post_thread("plain")
        self.app.store.claim_session(t["thread_id"], t["message_id"])  # simulate crash mid-create
        self.stop_app()
        self.start_app()
        self.app.bridge.drain()
        self.assertEqual(self.thread(t["thread_id"])["session"]["state"], "interrupted")
        self.assertEqual(self.fake.calls("POST", "/sessions"), [])


class Concurrency(AppCase):
    def test_parallel_mentions_create_exactly_one_session(self) -> None:
        self.fake.delay["create"] = 0.2
        t = self.post_thread("kickoff")
        errors: list[BaseException] = []

        def go(i: int) -> None:
            try:
                self.reply(t["thread_id"], f"@devin message {i}", author=["ava", "ben", "chloe", "dev", "elena"][i % 5])
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=go, args=(i,)) for i in range(12)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(errors, [])
        self.app.bridge.drain()
        self.assertEqual(len(self.fake.calls("POST", "/sessions")), 1)
        self.assertEqual(len(self.fake.calls("POST", "/messages")), 11)

    def test_duplicate_client_msg_id_is_idempotent(self) -> None:
        cid = str(uuid.uuid4())
        results: list[Any] = []
        lock = threading.Lock()

        def go() -> None:
            r = self.post_thread("@devin same", cid=cid)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=go) for _ in range(8)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(len({r["thread_id"] for r in results}), 1)
        self.assertEqual(sum(r["route"] == "direct" for r in results), 1)
        self.app.bridge.drain()
        self.assertEqual(len(self.fake.calls("POST", "/sessions")), 1)


class NoKeyLeaks(AppCase):
    def test_key_absent_from_responses_db_and_logs(self) -> None:
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.DEBUG)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        t = self.post_thread("@devin hi")
        self.app.bridge.drain()
        self.fake.fail["send"] = 500
        self.reply(t["thread_id"], "boom")
        self.app.bridge.drain()
        bodies = [
            self.client.request("GET", p)[2]
            for p in (
                "/",
                "/login",
                "/static/app.js",
                "/healthz",
                "/metrics",
                "/api/bootstrap",
                f"/api/threads/{t['thread_id']}",
                f"/api/channels/{self.channel_id()}/threads",
            )
        ]
        for b in bodies:
            self.assertNotIn(API_KEY.encode(), b)
            self.assertNotIn(ACCESS_TOKEN.encode(), b)
        self.app.store.close()
        for suffix in ("", "-wal", "-shm"):
            path = self.db_path + suffix
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    self.assertNotIn(API_KEY.encode(), fh.read())
        self.app.store = type(self.app.store)(self.db_path)
        self.assertNotIn(API_KEY, buf.getvalue())
        self.assertNotIn(API_KEY, repr(self.app.config))
        self.assertNotIn(API_KEY, repr(self.app.bridge.client))
        # The key is sent only as a bearer header to the configured API base.
        self.assertTrue(all(r.headers["Authorization"] == f"Bearer {API_KEY}" for r in self.fake.requests))
        self.assertTrue(all(API_KEY not in str(r.body) for r in self.fake.requests))


class Automation(AppCase):
    extra_env = {
        "COLLECTION_AUTOMATION_URL": "{fake}/webhook",
        "COLLECTION_AUTOMATION_ALLOWED_HOST": "127.0.0.1",
        "COLLECTION_AUTOMATION_SECRET": WEBHOOK_SECRET,
        "COLLECTION_AUTOMATION_RULES": "mention:collection-ops;alert:alerts:\\bSEV[12]\\b",
    }

    def test_mention_rule_posts_webhook_and_no_direct_session(self) -> None:
        t = self.post_thread("@devin investigate the stalled job", channel="collection-ops")
        self.assertEqual(t["route"], "automation")
        self.app.bridge.drain()
        self.assertEqual(len(self.fake.webhook_posts), 1)
        post = self.fake.webhook_posts[0]
        self.assertEqual(post.headers["X-Webhook-Secret"], WEBHOOK_SECRET)
        self.assertNotIn("Authorization", post.headers)
        self.assertEqual(post.body["event"], "mention")
        self.assertEqual(post.body["author"], "Ava Ramirez")
        self.assertEqual(self.fake.calls("POST", "/sessions"), [])

    def test_alert_rule(self) -> None:
        self.post_thread("SEV2: synthetic ingest lag above threshold", channel="alerts")
        self.post_thread("SEV4 informational", channel="alerts")
        self.app.bridge.drain()
        self.assertEqual([p.body["event"] for p in self.fake.webhook_posts], ["alert"])
        self.assertEqual(self.fake.requests, [])

    def test_other_channel_mention_still_direct(self) -> None:
        self.post_thread("@devin hi", channel="general")
        self.app.bridge.drain()
        self.assertEqual(self.fake.webhook_posts, [])
        self.assertEqual(len(self.fake.calls("POST", "/sessions")), 1)


class StubMode(AppCase):
    live = False

    def test_stub_is_labelled_and_creates_nothing(self) -> None:
        self.assertIsNone(self.app.bridge.client)
        t = self.post_thread("@devin hi")
        self.assertEqual(t["route"], "stub")
        view = self.thread(t["thread_id"])
        self.assertIsNone(view["session"])
        self.assertIn(STUB_NOTE, [m["body"] for m in view["messages"]])
        self.assertEqual(self.client.json("GET", "/healthz")[1]["mode"], "stub")
        self.assertEqual(self.fake.requests, [])


class HttpBoundary(AppCase):
    live = False

    def test_auth_required_and_wrong_token(self) -> None:
        from .helpers import Client

        anon = Client(self.client.port)
        self.assertEqual(anon.request("GET", "/api/bootstrap")[0], 401)
        self.assertEqual(anon.request("GET", "/")[0], 303)
        anon.login("wrong-token-wrong-token")
        self.assertIsNone(anon.cookie)
        anon.cookie = "collection_slack=forged.signature"
        self.assertEqual(anon.request("GET", "/api/bootstrap")[0], 401)
        self.assertEqual(anon.request("GET", "/healthz")[0], 200)

    def test_message_and_body_limits(self) -> None:
        cid = self.channel_id()
        status, _ = self.client.json(
            "POST", f"/api/channels/{cid}/threads", {"author": "ava", "text": "x" * 4001, "client_msg_id": "abcdefgh"}
        )
        self.assertEqual(status, 413)
        status, _, _ = self.client.request(
            "POST",
            f"/api/channels/{cid}/threads",
            raw=b"{" + b" " * 20000 + b"}",
            headers={"Content-Type": "application/json", "X-Collection-Client": "1"},
        )
        self.assertEqual(status, 413)

    def test_csrf_headers_required(self) -> None:
        cid = self.channel_id()
        status, _, _ = self.client.request(
            "POST",
            f"/api/channels/{cid}/threads",
            raw=b'{"author":"ava","text":"x","client_msg_id":"abcdefgh"}',
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 403)
        status, _, _ = self.client.request(
            "POST",
            f"/api/channels/{cid}/threads",
            {"author": "ava", "text": "x", "client_msg_id": "abcdefgh"},
            headers={"Origin": "https://evil.example"},
        )
        self.assertEqual(status, 403)

    def test_browser_form_login_origin_and_error_feedback(self) -> None:
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        same = {**form, "Origin": f"http://127.0.0.1:{self.client.port}"}
        status, headers, _ = self.client.request("GET", "/login")
        self.assertEqual(headers["referrer-policy"], "same-origin")
        fresh = Client(self.client.port)
        status, headers, _ = fresh.request("POST", "/login", raw=b"token=wrong-token", headers=same)
        self.assertEqual((status, headers["location"]), (303, "/login?error=1"))
        _, _, page = fresh.request("GET", "/login?error=1")
        self.assertIn(b"not accepted", page)
        _, _, page = fresh.request("GET", "/login")
        self.assertNotIn(b"not accepted", page)
        status, headers, _ = fresh.request("POST", "/login", raw=f"token={ACCESS_TOKEN}".encode(), headers=same)
        self.assertEqual((status, headers["location"]), (303, "/"))
        self.assertIn("set-cookie", headers)
        for origin in ("null", "https://evil.example"):
            status, headers, _ = fresh.request(
                "POST", "/login", raw=f"token={ACCESS_TOKEN}".encode(), headers={**form, "Origin": origin}
            )
            self.assertEqual(status, 403)
            self.assertNotIn("set-cookie", headers)

    def test_text_is_stored_verbatim_and_served_as_json_with_csp(self) -> None:
        t = self.post_thread("<img src=x onerror=alert(1)>")
        status, headers, raw = self.client.request("GET", f"/api/threads/{t['thread_id']}")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertIn("script-src 'self'", headers["content-security-policy"])
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        js = self.client.request("GET", "/static/app.js")[2].decode()
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("insertAdjacentHTML", js)

    def test_persistence_across_restart(self) -> None:
        t = self.post_thread("survives restart")
        self.reply(t["thread_id"], "reply too")
        self.stop_app()
        self.start_app()
        self.assertEqual([m["body"] for m in self.thread(t["thread_id"])["messages"]], ["survives restart", "reply too"])
        with sqlite3.connect(self.db_path) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"messages", "threads", "thread_sessions"} <= tables)

    def test_cookie_flags(self) -> None:
        from urllib.parse import urlencode

        _, headers, _ = self.client.request(
            "POST",
            "/login",
            raw=urlencode({"token": ACCESS_TOKEN}).encode(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertIn("HttpOnly", headers["set-cookie"])
        self.assertIn("SameSite=Strict", headers["set-cookie"])


_ = redirect_stderr

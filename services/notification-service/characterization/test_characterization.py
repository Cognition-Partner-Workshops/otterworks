"""Characterization tests for notification-service.

Black-box: they drive the RUNNING service over its real interfaces (HTTP, the
WebSocket push channel, and the SQS queue it consumes) and pin what it does
today, odd behaviour included. Standard library only so they run unchanged on
any runtime.

Environment:
  BASE_URL        service under test        (default http://localhost:8086)
  AWS_ENDPOINT    LocalStack edge           (default http://localhost:4566)
  SQS_QUEUE_URL   queue the service polls   (default <AWS_ENDPOINT>/000000000000/otterworks-notifications)
  EVENT_TIMEOUT   seconds to wait for an SQS event to be processed (default 60)
"""

import base64
import json
import os
import re
import socket
import struct
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8086").rstrip("/")
AWS_ENDPOINT = os.environ.get("AWS_ENDPOINT", "http://localhost:4566").rstrip("/")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", AWS_ENDPOINT + "/000000000000/otterworks-notifications")
EVENT_TIMEOUT = float(os.environ.get("EVENT_TIMEOUT", "60"))
SES_SENDER = os.environ.get("SES_SENDER", "notifications@otterworks.io")

USER_REQUIRED = {"error": "user_id is required (via X-User-ID header or query parameter)"}
NOT_FOUND = {"error": "Notification not found"}
INTERNAL = {"error": "Internal server error"}
DEFAULT_CHANNELS = {
    "file_shared": ["EMAIL", "IN_APP", "PUSH"],
    "comment_added": ["IN_APP", "PUSH"],
    "document_edited": ["IN_APP"],
    "user_mentioned": ["EMAIL", "IN_APP", "PUSH"],
}
EMAIL_FOOTER = "<!-- This is an automated message | OtterWorks Notification Service -->"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
INSTANT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
JSON_CT = "application/json"


def uid(prefix):
    return f"char-{prefix}-{uuid.uuid4().hex[:12]}"


class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.body)

    def header(self, name):
        return self.headers.get(name)


def http(method, path, body=None, headers=None, base=BASE_URL):
    data = None
    hdrs = dict(headers or {})
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        hdrs.setdefault("Content-Type", JSON_CT)
    req = urllib.request.Request(base + path, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Resp(r.status, r.headers, r.read().decode())
    except urllib.error.HTTPError as e:
        return Resp(e.code, e.headers, e.read().decode())


def sqs_send(message_body):
    aws_query("sqs", {
        "Action": "SendMessage",
        "QueueUrl": SQS_QUEUE_URL,
        "MessageBody": message_body if isinstance(message_body, str) else json.dumps(message_body),
    })


def aws_query(service, params):
    """AWS query-protocol call against LocalStack (signatures are not verified)."""
    req = urllib.request.Request(AWS_ENDPOINT + "/", data=urllib.parse.urlencode(params).encode(),
                                 method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"AWS4-HMAC-SHA256 Credential=test/20240101/us-east-1/{service}/aws4_request, "
                         "SignedHeaders=host, Signature=0",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        assert r.status == 200, r.status


def setUpModule():
    # Fixture: LocalStack SES rejects mail from an unverified sender, and
    # scripts/localstack-init.sh does not verify one. Verify the service's default
    # sender (idempotent) so the email channel is observable.
    aws_query("ses", {"Action": "VerifyEmailIdentity", "EmailAddress": SES_SENDER})


def ses_messages_to(address):
    with urllib.request.urlopen(AWS_ENDPOINT + "/_aws/ses", timeout=30) as r:
        msgs = json.loads(r.read().decode()).get("messages", [])
    return [m for m in msgs if address in (m.get("Destination", {}).get("ToAddresses") or [])]


def wait_for(fn, timeout=EVENT_TIMEOUT, interval=0.5):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(interval)
    return last


def list_for(user, query=""):
    return http("GET", "/api/v1/notifications" + query, headers={"X-User-ID": user})


def wait_for_total(user, total):
    def check():
        r = list_for(user, f"?page_size=100")
        return r.json() if r.status == 200 and r.json()["total"] >= total else None
    got = wait_for(check)
    if not got:
        raise AssertionError(f"timed out waiting for {total} notification(s) for {user}")
    return got


def metric_value(text, name):
    total = 0.0
    found = False
    for line in text.splitlines():
        if line.startswith(name + " ") or line.startswith(name + "{"):
            total += float(line.rsplit(" ", 1)[1])
            found = True
    return total if found else None


class WebSocket:
    """Minimal RFC 6455 client: text frames only, enough for the push channel."""

    def __init__(self, path, timeout=EVENT_TIMEOUT):
        u = urllib.parse.urlparse(BASE_URL)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET {path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, _, self.buf = buf.partition(b"\r\n\r\n")
        self.status_line = head.split(b"\r\n", 1)[0].decode()

    def _recv(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("socket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send_text(self, text):
        payload = text.encode()
        mask = os.urandom(4)
        header = bytes([0x81])
        n = len(payload)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv_text(self):
        while True:
            b0, b1 = self._recv(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv(8))[0]
            mask = self._recv(4) if b1 & 0x80 else None
            data = self._recv(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x1:
                return data.decode()
            if opcode == 0x8:
                raise ConnectionError("server closed websocket")

    def close(self):
        try:
            self.sock.sendall(bytes([0x88, 0x80]) + os.urandom(4))
        finally:
            self.sock.close()


class T01Health(unittest.TestCase):
    def test_health_ok(self):
        r = http("GET", "/health")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), JSON_CT)
        self.assertEqual(r.header("Vary"), "Origin")
        self.assertEqual(r.json(), {"status": "healthy", "service": "notification-service"})

    def test_unknown_route_is_404_empty(self):
        r = http("GET", "/does-not-exist")
        self.assertEqual(r.status, 404)
        self.assertEqual(r.body, "")

    def test_wrong_method_is_405_empty(self):
        r = http("POST", "/api/v1/notifications")
        self.assertEqual(r.status, 405)
        self.assertEqual(r.body, "")


class T02Metrics(unittest.TestCase):
    CORE = [
        "jvm_memory_used_bytes", "jvm_threads_live_threads", "jvm_classes_loaded_classes",
        "jvm_gc_pause_seconds_count", "process_cpu_usage", "process_uptime_seconds",
        "system_cpu_count", "ktor_http_server_requests_seconds_count",
        "ktor_http_server_requests_active", "notifications_processed_total",
        "notifications_email_sent_total", "notifications_push_sent_total",
        "notifications_processing_errors_total",
    ]

    def test_prometheus_scrape(self):
        http("GET", "/health")
        r = http("GET", "/metrics")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), "text/plain; charset=UTF-8")
        for name in self.CORE:
            self.assertIsNotNone(metric_value(r.body, name), name)
        self.assertRegex(r.body, r'ktor_http_server_requests_seconds_count\{[^}]*route="/health"')


class T03Cors(unittest.TestCase):
    def test_preflight_allowed_origin(self):
        r = http("OPTIONS", "/api/v1/notifications", headers={
            "Origin": "http://localhost:3000", "Access-Control-Request-Method": "PUT"})
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Access-Control-Allow-Origin"), "http://localhost:3000")
        self.assertEqual(r.header("Access-Control-Allow-Methods"), "DELETE, PATCH, PUT")
        self.assertEqual(r.header("Access-Control-Allow-Headers"), "Authorization, Content-Type")
        self.assertEqual(r.header("Access-Control-Max-Age"), "86400")

    def test_preflight_disallowed_origin_403(self):
        r = http("OPTIONS", "/api/v1/notifications", headers={
            "Origin": "http://evil.example", "Access-Control-Request-Method": "PUT"})
        self.assertEqual(r.status, 403)
        self.assertIsNone(r.header("Access-Control-Allow-Origin"))

    def test_simple_request_second_allowed_origin(self):
        r = http("GET", "/health", headers={"Origin": "http://localhost:4200"})
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Access-Control-Allow-Origin"), "http://localhost:4200")


class T04Validation(unittest.TestCase):
    def assertUserRequired(self, r):
        self.assertEqual(r.status, 400)
        self.assertEqual(r.header("Content-Type"), JSON_CT)
        self.assertEqual(r.json(), USER_REQUIRED)

    def test_list_requires_user(self):
        self.assertUserRequired(http("GET", "/api/v1/notifications"))

    def test_list_blank_header_requires_user(self):
        self.assertUserRequired(http("GET", "/api/v1/notifications", headers={"X-User-ID": ""}))

    def test_unread_count_requires_user(self):
        self.assertUserRequired(http("GET", "/api/v1/notifications/unread-count"))

    def test_read_all_requires_user(self):
        self.assertUserRequired(http("PUT", "/api/v1/notifications/read-all"))

    def test_preferences_requires_user(self):
        self.assertUserRequired(http("GET", "/api/v1/preferences"))

    def test_get_unknown_id_404(self):
        r = http("GET", "/api/v1/notifications/" + str(uuid.uuid4()))
        self.assertEqual(r.status, 404)
        self.assertEqual(r.json(), NOT_FOUND)

    def test_mark_read_unknown_id_404(self):
        r = http("PUT", f"/api/v1/notifications/{uuid.uuid4()}/read")
        self.assertEqual(r.status, 404)
        self.assertEqual(r.json(), NOT_FOUND)

    def test_delete_unknown_id_is_204(self):
        # Pinned as-is: DynamoDB DeleteItem does not fail for a missing key.
        r = http("DELETE", f"/api/v1/notifications/{uuid.uuid4()}")
        self.assertEqual(r.status, 204)
        self.assertEqual(r.body, "")

    def test_preferences_malformed_json_is_500(self):
        r = http("PUT", "/api/v1/preferences", body=b"{bad")
        self.assertEqual(r.status, 500)
        self.assertEqual(r.json(), INTERNAL)

    def test_preferences_unknown_channel_is_500(self):
        r = http("PUT", "/api/v1/preferences",
                 body={"userId": uid("p"), "eventType": "file_shared", "channels": ["SMS"]})
        self.assertEqual(r.status, 500)
        self.assertEqual(r.json(), INTERNAL)

    def test_preferences_without_content_type_is_415(self):
        req = urllib.request.Request(BASE_URL + "/api/v1/preferences", method="PUT",
                                     data=b'{"userId":"x","eventType":"file_shared","channels":[]}')
        req.remove_header("Content-type")
        try:
            urllib.request.urlopen(req, timeout=30)
            status = 200
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read().decode()
        self.assertEqual(status, 415)


class T05EmptyUser(unittest.TestCase):
    def test_list_empty_via_header(self):
        r = list_for(uid("empty"))
        self.assertEqual(r.status, 200)
        self.assertEqual(r.header("Content-Type"), JSON_CT)
        self.assertEqual(r.json(), {"data": [], "total": 0, "page": 1, "pageSize": 20, "hasMore": False})

    def test_list_query_param_and_bad_page_defaults(self):
        r = http("GET", f"/api/v1/notifications?user_id={uid('q')}&page=abc&page_size=2")
        self.assertEqual(r.json(), {"data": [], "total": 0, "page": 1, "pageSize": 2, "hasMore": False})

    def test_header_wins_over_query(self):
        u = uid("h")
        r = http("GET", f"/api/v1/notifications/unread-count?user_id=other", headers={"X-User-ID": u})
        self.assertEqual(r.json(), {"userId": u, "unreadCount": 0})

    def test_unread_count_zero(self):
        u = uid("u")
        r = http("GET", f"/api/v1/notifications/unread-count?user_id={u}")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json(), {"userId": u, "unreadCount": 0})

    def test_read_all_zero(self):
        r = http("PUT", "/api/v1/notifications/read-all", headers={"X-User-ID": uid("ra")})
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json(), {"markedCount": 0})

    def test_default_preferences(self):
        u = uid("dp")
        r = http("GET", "/api/v1/preferences", headers={"X-User-ID": u})
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, json.dumps({"userId": u, "channels": DEFAULT_CHANNELS}, separators=(",", ":")))


class T06Preferences(unittest.TestCase):
    def test_update_merges_into_defaults(self):
        u = uid("pref")
        r = http("PUT", "/api/v1/preferences",
                 body={"userId": u, "eventType": "comment_added", "channels": ["EMAIL"]})
        self.assertEqual(r.status, 204)
        self.assertEqual(r.body, "")
        r = http("PUT", "/api/v1/preferences",
                 body={"userId": u, "eventType": "custom_event", "channels": []})
        self.assertEqual(r.status, 204)
        got = http("GET", f"/api/v1/preferences?user_id={u}").json()
        expected = dict(DEFAULT_CHANNELS, comment_added=["EMAIL"], custom_event=[])
        self.assertEqual(got, {"userId": u, "channels": expected})


class T07EventPipeline(unittest.TestCase):
    """SQS event -> DynamoDB -> REST read model, plus SES email side effect."""

    def test_file_shared_lifecycle(self):
        user, owner, actor, file_id = uid("fs"), uid("own"), uid("act"), uid("file")
        sqs_send({"eventType": "file_shared", "fileId": file_id, "ownerId": owner,
                  "sharedWithUserId": user, "actorId": actor, "timestamp": "2024-01-01T00:00:00Z"})
        page = wait_for_total(user, 1)
        self.assertEqual(page["total"], 1)
        n = page["data"][0]
        self.assertRegex(n["id"], UUID_RE)
        self.assertRegex(n["createdAt"], INSTANT_RE)
        self.assertEqual({k: v for k, v in n.items() if k not in ("id", "createdAt")}, {
            "userId": user, "type": "file_shared", "title": "File Shared With You",
            "message": f"A file has been shared with you by user {actor}.",
            "resourceId": file_id, "resourceType": "file", "actorId": actor,
            "read": False, "deliveredVia": ["in_app", "email"],
        })

        emails = wait_for(lambda: ses_messages_to(f"{user}@otterworks.io"), timeout=10)
        self.assertEqual(len(emails), 1)
        e = emails[0]
        self.assertEqual(e["Source"], SES_SENDER)
        self.assertEqual(e["Subject"], "OtterWorks: A file has been shared with you")
        html = e["Body"]["html_part"]
        self.assertIn(f"<p>A file (ID: {file_id}) has been shared with you by user {actor}.</p>", html)
        self.assertTrue(html.endswith("\n" + EMAIL_FOOTER), html[-120:])

        r = http("GET", f"/api/v1/notifications/{n['id']}")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json(), n)
        self.assertEqual(http("GET", f"/api/v1/notifications/unread-count?user_id={user}").json()["unreadCount"], 1)

        r = http("PUT", f"/api/v1/notifications/{n['id']}/read")
        self.assertEqual(r.status, 204)
        self.assertEqual(r.body, "")
        self.assertTrue(http("GET", f"/api/v1/notifications/{n['id']}").json()["read"])
        self.assertEqual(http("GET", f"/api/v1/notifications/unread-count?user_id={user}").json()["unreadCount"], 0)
        self.assertEqual(http("PUT", f"/api/v1/notifications/{n['id']}/read").status, 204)

        r = http("DELETE", f"/api/v1/notifications/{n['id']}")
        self.assertEqual(r.status, 204)
        self.assertEqual(http("GET", f"/api/v1/notifications/{n['id']}").status, 404)
        self.assertEqual(list_for(user).json()["total"], 0)

    def test_pagination_ordering_and_read_all(self):
        user, actor = uid("pg"), uid("act")
        docs = [uid("doc") for _ in range(3)]
        for d in docs:
            sqs_send({"eventType": "document_edited", "documentId": d, "userId": user,
                      "actorId": actor, "timestamp": "2024-01-01T00:00:00Z"})
        wait_for_total(user, 3)
        p1 = list_for(user, "?page=1&page_size=2").json()
        p2 = list_for(user, "?page=2&page_size=2").json()
        self.assertEqual((len(p1["data"]), p1["total"], p1["page"], p1["pageSize"], p1["hasMore"]), (2, 3, 1, 2, True))
        self.assertEqual((len(p2["data"]), p2["total"], p2["page"], p2["pageSize"], p2["hasMore"]), (1, 3, 2, 2, False))
        items = p1["data"] + p2["data"]
        created = [i["createdAt"] for i in items]
        self.assertEqual(created, sorted(created, reverse=True))
        self.assertEqual(sorted(i["resourceId"] for i in items), sorted(docs))
        for i in items:
            self.assertEqual(i["title"], "Document Edited")
            self.assertEqual(i["message"], f"Document {i['resourceId']} was edited by user {actor}.")
            self.assertEqual(i["resourceType"], "document")
            self.assertEqual(i["deliveredVia"], ["in_app"])
        self.assertEqual(list_for(user, "?page=3&page_size=2").json()["data"], [])

        self.assertEqual(http("PUT", "/api/v1/notifications/read-all", headers={"X-User-ID": user}).json(), {"markedCount": 3})
        self.assertEqual(http("PUT", "/api/v1/notifications/read-all", headers={"X-User-ID": user}).json(), {"markedCount": 0})
        self.assertEqual(http("GET", f"/api/v1/notifications/unread-count?user_id={user}").json()["unreadCount"], 0)

    def test_preferences_drive_delivery_channels(self):
        user, actor, doc, comment = uid("pc"), uid("act"), uid("doc"), uid("cmt")
        self.assertEqual(http("PUT", "/api/v1/preferences", body={
            "userId": user, "eventType": "comment_added", "channels": ["EMAIL"]}).status, 204)
        sqs_send({"eventType": "comment_added", "documentId": doc, "commentId": comment,
                  "userId": user, "actorId": actor, "timestamp": "2024-01-01T00:00:00Z"})
        n = wait_for_total(user, 1)["data"][0]
        self.assertEqual(n["deliveredVia"], ["email"])
        self.assertEqual(n["resourceId"], comment)
        self.assertEqual(n["resourceType"], "comment")
        self.assertEqual(n["message"], f"A new comment was added by user {actor} on document {doc}.")
        emails = wait_for(lambda: ses_messages_to(f"{user}@otterworks.io"), timeout=10)
        self.assertEqual([m["Subject"] for m in emails], ["OtterWorks: New comment on your document"])

    def test_sns_envelope_and_epoch_timestamp_and_owner_fallback(self):
        user, owner, doc = uid("sns"), uid("own"), uid("doc")
        inner = json.dumps({"eventType": "comment_added", "documentId": doc, "ownerId": owner,
                            "userId": user, "timestamp": 1700000000})
        sqs_send({"Type": "Notification", "MessageId": str(uuid.uuid4()),
                  "TopicArn": "arn:aws:sns:us-east-1:000000000000:otterworks-events", "Message": inner})
        n = wait_for_total(user, 1)["data"][0]
        self.assertEqual(n["actorId"], owner)
        self.assertEqual(n["resourceId"], doc)
        self.assertEqual(n["message"], f"A new comment was added by user {owner} on document {doc}.")
        self.assertEqual(n["deliveredVia"], ["in_app"])

    def test_unknown_event_type_generic_render(self):
        user = uid("unk")
        sqs_send({"eventType": "something_else", "userId": user, "timestamp": "2024-01-01T00:00:00Z"})
        n = wait_for_total(user, 1)["data"][0]
        self.assertEqual({k: n[k] for k in ("type", "title", "message", "resourceId", "resourceType", "actorId", "deliveredVia")}, {
            "type": "something_else", "title": "Notification", "message": "You have a new notification.",
            "resourceId": "", "resourceType": "unknown", "actorId": "", "deliveredVia": ["in_app"],
        })

    def test_event_values_are_inserted_literally(self):
        user, doc = uid("lit"), uid("doc")
        actor = "{{sys:user.name}}${java:version}"
        sqs_send({"eventType": "document_edited", "documentId": doc, "userId": user,
                  "actorId": actor, "timestamp": "2024-01-01T00:00:00Z"})
        n = wait_for_total(user, 1)["data"][0]
        self.assertEqual(n["message"], f"Document {doc} was edited by user {actor}.")

    def test_unparseable_message_counts_processing_error(self):
        before = metric_value(http("GET", "/metrics").body, "notifications_processing_errors_total")
        sqs_send("not json at all")
        after = wait_for(lambda: (lambda v: v if v > before else None)(
            metric_value(http("GET", "/metrics").body, "notifications_processing_errors_total")))
        self.assertIsNotNone(after)
        self.assertGreaterEqual(after - before, 1.0)


class T08WebSocket(unittest.TestCase):
    def test_ping_pong(self):
        ws = WebSocket(f"/ws/notifications/{uid('ws')}")
        try:
            self.assertEqual(ws.status_line, "HTTP/1.1 101 Switching Protocols")
            ws.send_text("ping")
            self.assertEqual(ws.recv_text(), "pong")
        finally:
            ws.close()

    def test_push_delivery(self):
        user, actor, doc = uid("push"), uid("act"), uid("doc")
        ws = WebSocket(f"/ws/notifications/{user}")
        try:
            self.assertEqual(ws.status_line, "HTTP/1.1 101 Switching Protocols")
            sqs_send({"eventType": "user_mentioned", "documentId": doc, "mentionedUserId": user,
                      "actorId": actor, "timestamp": "2024-01-01T00:00:00Z"})
            pushed = json.loads(ws.recv_text())
        finally:
            ws.close()
        # Pinned as-is: the push encoder omits default-valued fields, so "read": false is absent.
        self.assertEqual(list(pushed.keys()), ["id", "userId", "type", "title", "message", "resourceId",
                                               "resourceType", "actorId", "deliveredVia", "createdAt"])
        self.assertEqual(pushed["type"], "user_mentioned")
        self.assertEqual(pushed["title"], "You Were Mentioned")
        self.assertEqual(pushed["message"], f"You were mentioned by user {actor} in document {doc}.")
        # The pushed copy is the pre-push record; "push" is added to the stored record afterwards.
        self.assertEqual(pushed["deliveredVia"], ["in_app", "email"])

        def stored_with_push():
            r = http("GET", f"/api/v1/notifications/{pushed['id']}")
            return r.json() if r.status == 200 and "push" in r.json()["deliveredVia"] else None
        stored = wait_for(stored_with_push, timeout=15)
        self.assertIsNotNone(stored)
        self.assertEqual(stored["deliveredVia"], ["in_app", "email", "push"])
        self.assertFalse(stored["read"])
        self.assertEqual({k: v for k, v in stored.items() if k not in ("deliveredVia", "read")},
                         {k: v for k, v in pushed.items() if k != "deliveredVia"})


if __name__ == "__main__":
    import sys
    print(f"BASE_URL={BASE_URL} AWS_ENDPOINT={AWS_ENDPOINT} SQS_QUEUE_URL={SQS_QUEUE_URL}")
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    print(f"Tests run: {result.testsRun}, Failures: {len(result.failures)}, "
          f"Errors: {len(result.errors)}, Skipped: {len(result.skipped)}")
    sys.exit(0 if result.wasSuccessful() else 1)

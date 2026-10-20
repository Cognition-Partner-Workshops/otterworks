"""Characterization tests for notify-svc, run over HTTP against a running app.

The golden files were recorded from the VM stand-in (Node 12 under PM2, redis-server
on the same box) on the seed accounts in data/seed.sql. The same tests run unchanged
against the replatformed container. Every test starts from an empty Redis.

    NOTIFY_URL        base URL of the app              (http://localhost:8084 = VM stand-in)
    NOTIFY_REDIS_URL  the Redis the app writes to      (redis://host:port[/db], password in the URL if any)
    NOTIFY_LOGS_CMD   command printing the app's stdout/stderr (e.g. "docker logs <container>")
    NOTIFY_REDIS_DOWN=1  also run test_zz_redis_down.py, which shuts the Redis down (run it last)

RECORD=1 rewrites the golden files; only do that against the VM stand-in.
"""
import http.client
import json
import os
import random
import re
import shlex
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import redis

BASE = os.environ.get("NOTIFY_URL", "http://localhost:8084").rstrip("/")
REDIS_URL = os.environ.get("NOTIFY_REDIS_URL")
LOGS_CMD = os.environ.get("NOTIFY_LOGS_CMD")
RECORD = os.environ.get("RECORD") == "1"
HERE = Path(__file__).parent
GOLDEN = HERE / "golden"
SEED = HERE.parents[1] / "data" / "seed.sql"
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
JSON_CT = "application/json; charset=utf-8"
HTML_CT = "text/html; charset=utf-8"

_url = urlsplit(BASE)


def request(method, path, body=None, content_type="application/json", timeout=15):
    conn = http.client.HTTPConnection(_url.hostname, _url.port or 80, timeout=timeout)
    headers = {}
    if body is not None:
        headers["Content-Type"] = content_type
        if isinstance(body, str):
            body = body.encode("utf-8")
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    text = resp.read().decode("utf-8")
    conn.close()
    return resp, text


def notify(payload, **kw):
    return request("POST", "/notify", json.dumps(payload), **kw)


def outbox(account):
    resp, text = request("GET", "/outbox/" + account)
    assert resp.status == 200
    assert resp.getheader("Content-Type") == JSON_CT
    return json.loads(text)


def golden_json(name, value):
    f = GOLDEN / name
    if RECORD:
        f.write_text(json.dumps(value, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert value == json.loads(f.read_text(encoding="utf-8"))


def golden_text(name, body):
    f = GOLDEN / name
    if RECORD:
        f.write_text(body, encoding="utf-8")
    assert f.exists(), f"missing golden file {f}; record it against the VM stand-in with RECORD=1"
    assert body == f.read_text(encoding="utf-8")


def seed_accounts():
    return re.findall(r"INSERT INTO accounts VALUES \('(\w+)',", SEED.read_text())


ACCOUNTS = seed_accounts()

KIND_FIELDS = {
    "statement_ready": {},
    "card_payment": {"amount": "12.40", "merchant": "Corner Cafe"},
    "low_balance": {"threshold": "100.00"},
}

# Requests whose status, content type and body are pinned in golden/cases.json.
CASES = {
    "statement_ready_empty_fields": '{"account":"HG611000001","kind":"statement_ready","fields":{}}',
    "statement_ready_no_fields": '{"account":"HG611000001","kind":"statement_ready"}',
    "card_payment": '{"account":"HG611000001","kind":"card_payment","fields":{"amount":"12.40","merchant":"Corner Cafe"}}',
    "card_payment_numeric_amount": '{"account":"HG611000001","kind":"card_payment","fields":{"amount":12.4,"merchant":"A {b}"}}',
    "card_payment_missing_amount": '{"account":"HG611000001","kind":"card_payment","fields":{}}',
    "card_payment_missing_merchant": '{"account":"HG611000001","kind":"card_payment","fields":{"amount":"1.00"}}',
    "card_payment_fields_string": '{"account":"HG611000001","kind":"card_payment","fields":"abc"}',
    "low_balance": '{"account":"HG611000001","kind":"low_balance","fields":{"threshold":"100.00"}}',
    "low_balance_zero_threshold": '{"account":"HG611000001","kind":"low_balance","fields":{"threshold":0}}',
    "low_balance_null_threshold": '{"account":"HG611000001","kind":"low_balance","fields":{"threshold":null}}',
    "unknown_kind": '{"account":"HG611000001","kind":"nope","fields":{}}',
    "prototype_kind_constructor": '{"account":"HG611000001","kind":"constructor"}',
    "prototype_kind_toString": '{"account":"HG611000001","kind":"toString"}',
    "account_override_ignored": '{"account":"HG631000003","kind":"statement_ready","fields":{"account":"X"}}',
    "extra_fields_ignored": '{"account":"HG631000003","kind":"statement_ready","fields":{"extra":"{account}"}}',
    "short_account_not_masked": '{"account":"AB1","kind":"statement_ready"}',
    "four_char_account_not_masked": '{"account":"AB12","kind":"statement_ready"}',
    "numeric_account": '{"account":12345678,"kind":"statement_ready"}',
    "missing_account": '{"kind":"statement_ready","fields":{}}',
    "empty_account": '{"account":"","kind":"statement_ready"}',
    "missing_kind": '{"account":"HG611000001"}',
    "empty_object": "{}",
    "json_array": "[1]",
    "json_null": "null",
    "json_string": '"x"',
    "malformed_json": "{bad",
}


@pytest.fixture(autouse=True)
def clean_redis(store):
    store.flushall()
    yield


@pytest.fixture(scope="session")
def store():
    assert REDIS_URL, "set NOTIFY_REDIS_URL to the Redis the app under test uses"
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def test_seed_has_the_expected_shape():
    assert len(ACCOUNTS) == 24
    assert ACCOUNTS[0] == "HG611000001" and ACCOUNTS[-1] == "HG841000024"


def test_post_cases_match_golden():
    got = {}
    for name, body in CASES.items():
        resp, text = request("POST", "/notify", body)
        got[name] = {"status": resp.status, "content_type": resp.getheader("Content-Type"), "body": text}
    golden_json("cases.json", got)


def test_form_encoded_body_is_ignored():
    resp, text = request("POST", "/notify", "account=HG611000001&kind=statement_ready",
                         content_type="application/x-www-form-urlencoded")
    assert (resp.status, text) == (400, '{"error":"account and kind are required"}')


def test_text_plain_body_is_ignored():
    resp, text = request("POST", "/notify", '{"account":"HG611000001","kind":"statement_ready"}',
                         content_type="text/plain")
    assert (resp.status, text) == (400, '{"error":"account and kind are required"}')


def test_body_over_100kb_is_rejected():
    big = json.dumps({"account": "HG611000001", "kind": "statement_ready", "fields": {"pad": "x" * 110000}})
    resp, text = request("POST", "/notify", big)
    assert resp.status == 413
    assert resp.getheader("Content-Type") == HTML_CT
    golden_text("413.html", text)


@pytest.mark.parametrize("account", ACCOUNTS)
def test_every_kind_for_every_seed_account(account, store):
    got = {}
    for kind, fields in KIND_FIELDS.items():
        resp, text = notify({"account": account, "kind": kind, "fields": fields})
        assert resp.getheader("Content-Type") == JSON_CT
        got[kind] = {"status": resp.status, "body": json.loads(text)}
    golden_json(f"account-{account}.json", got)
    items = outbox(account)
    assert [i["kind"] for i in items] == list(reversed(list(KIND_FIELDS)))
    for item, kind in zip(items, reversed(list(KIND_FIELDS))):
        assert list(item) == ["account", "kind", "text", "at"]
        assert item["account"] == account
        assert item["text"] == got[kind]["body"]["text"]
        assert ISO_UTC.match(item["at"])
    assert store.get("notify:rate:" + account) == "3"
    assert 3590 <= store.ttl("notify:rate:" + account) <= 3600
    assert store.ttl("notify:outbox:" + account) == -1
    assert sorted(store.keys("*")) == ["notify:outbox:" + account, "notify:rate:" + account]


def test_queued_message_is_stored_as_json_in_the_outbox_list(store):
    before = time.time()
    resp, _ = notify({"account": "HG611000001", "kind": "card_payment",
                      "fields": {"amount": "12.40", "merchant": "Corner Cafe"}})
    assert resp.status == 202
    raw = store.lrange("notify:outbox:HG611000001", 0, -1)
    assert len(raw) == 1
    assert re.fullmatch(r'\{"account":"HG611000001","kind":"card_payment","text":"Card payment of 12\.40 on '
                        r'\*\*\*\*0001 at Corner Cafe\.","at":"[0-9T:.Z-]+"\}', raw[0])
    at = json.loads(raw[0])["at"]
    stamp = time.mktime(time.strptime(at[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
    assert before - 5 <= stamp <= time.time() + 5


def test_numeric_account_is_kept_as_number(store):
    resp, _ = notify({"account": 12345678, "kind": "statement_ready"})
    assert resp.status == 202
    assert [i["account"] for i in outbox("12345678")] == [12345678]
    assert store.get("notify:rate:12345678") == "1"


def test_outbox_is_newest_first():
    for amount in ["1.00", "2.00", "3.00"]:
        notify({"account": "HG611000001", "kind": "card_payment", "fields": {"amount": amount, "merchant": "M"}})
    assert [i["text"] for i in outbox("HG611000001")] == [
        "Card payment of 3.00 on ****0001 at M.",
        "Card payment of 2.00 on ****0001 at M.",
        "Card payment of 1.00 on ****0001 at M.",
    ]


def test_outbox_returns_at_most_50_items(store):
    for n in range(55):
        store.lpush("notify:outbox:HG611000001", json.dumps({"account": "HG611000001", "kind": "k", "text": str(n), "at": "x"}))
    items = outbox("HG611000001")
    assert len(items) == 50
    assert items[0]["text"] == "54" and items[-1]["text"] == "5"
    assert store.llen("notify:outbox:HG611000001") == 55


def test_outbox_for_unknown_account_is_empty():
    resp, text = request("GET", "/outbox/HG999999999")
    assert (resp.status, resp.getheader("Content-Type"), text) == (200, JSON_CT, "[]")


def test_outbox_reads_do_not_remove_items():
    notify({"account": "HG611000001", "kind": "statement_ready"})
    assert len(outbox("HG611000001")) == 1
    assert len(outbox("HG611000001")) == 1


def test_rate_limit_20_per_account_per_hour(store):
    statuses = [notify({"account": "HG621000002", "kind": "low_balance", "fields": {"threshold": "5"}})[0].status
                for _ in range(22)]
    assert statuses == [202] * 20 + [429, 429]
    resp, text = notify({"account": "HG621000002", "kind": "statement_ready"})
    assert (resp.status, resp.getheader("Content-Type"), text) == (429, JSON_CT, '{"error":"rate limited"}')
    assert store.get("notify:rate:HG621000002") == "23"
    assert 3590 <= store.ttl("notify:rate:HG621000002") <= 3600
    assert len(outbox("HG621000002")) == 20
    assert store.llen("notify:outbox:HG621000002") == 20
    assert notify({"account": "HG631000003", "kind": "statement_ready"})[0].status == 202


def test_rate_limit_lifts_when_the_counter_expires(store):
    store.set("notify:rate:HG621000002", 20)
    assert notify({"account": "HG621000002", "kind": "statement_ready"})[0].status == 429
    store.delete("notify:rate:HG621000002")
    assert notify({"account": "HG621000002", "kind": "statement_ready"})[0].status == 202
    assert store.get("notify:rate:HG621000002") == "1"


def test_existing_counter_keeps_its_ttl(store):
    store.set("notify:rate:HG621000002", 3, ex=100)
    assert notify({"account": "HG621000002", "kind": "statement_ready"})[0].status == 202
    assert store.get("notify:rate:HG621000002") == "4"
    assert store.ttl("notify:rate:HG621000002") <= 100


def test_rejected_requests_do_not_use_rate_budget_or_store_anything(store):
    for body in ['{"account":"HG611000001","kind":"nope"}', '{"account":"HG611000001","kind":"card_payment"}',
                 '{"kind":"statement_ready"}', "{bad"]:
        assert request("POST", "/notify", body)[0].status == 400
    assert store.keys("*") == []


def test_queued_line_on_stdout():
    assert LOGS_CMD, "set NOTIFY_LOGS_CMD to a command that prints the app's stdout"
    suffix = "%04d" % random.randrange(10000)
    account = "LOG" + str(int(time.time())) + suffix
    assert notify({"account": account, "kind": "low_balance", "fields": {"threshold": "1"}})[0].status == 202
    want = f"queued low_balance for ****{account[-4:]}"
    for _ in range(20):
        out = subprocess.run(shlex.split(LOGS_CMD), capture_output=True, text=True, timeout=30)
        if want in (out.stdout + out.stderr).splitlines()[-200:] or any(
                line.endswith(want) for line in (out.stdout + out.stderr).splitlines()[-200:]):
            return
        time.sleep(0.5)
    pytest.fail(f"{want!r} not found in the app output")


@pytest.mark.parametrize("method,path,name", [
    ("GET", "/notify", "404-get-notify.html"),
    ("GET", "/", "404-root.html"),
    ("GET", "/outbox", "404-get-outbox.html"),
    ("DELETE", "/outbox/HG611000001", "404-delete-outbox.html"),
    ("PUT", "/notify", "404-put-notify.html"),
    ("POST", "/outbox/HG611000001", "404-post-outbox.html"),
])
def test_unknown_routes_are_404(method, path, name):
    resp, text = request(method, path)
    assert resp.status == 404
    assert resp.getheader("Content-Type") == HTML_CT
    golden_text(name, text)


def test_malformed_json_error_page():
    resp, text = request("POST", "/notify", "{bad")
    assert resp.status == 400
    assert resp.getheader("Content-Type") == HTML_CT
    assert resp.getheader("Content-Security-Policy") == "default-src 'none'"
    assert resp.getheader("X-Content-Type-Options") == "nosniff"
    golden_text("400-malformed.html", text)


def test_response_headers():
    resp, _ = notify({"account": "HG611000001", "kind": "statement_ready"})
    assert resp.status == 202
    assert resp.getheader("X-Powered-By") == "Express"
    assert resp.getheader("Content-Type") == JSON_CT
    assert re.fullmatch(r'W/"[0-9a-f]+-[A-Za-z0-9+/]+"', resp.getheader("ETag"))
    assert resp.getheader("Content-Length") == "70"


def test_health_route_accepted_difference():
    # The VM has no /health (Express 404); the platform build must add one that answers 200.
    resp, _ = request("GET", "/health")
    assert resp.status in (200, 404)

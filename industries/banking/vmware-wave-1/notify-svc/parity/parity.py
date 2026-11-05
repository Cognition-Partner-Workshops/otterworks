#!/usr/bin/env python3
"""Capture the fixed notify contract; compare raw responses except outbox timestamps."""
import argparse
import base64
import http.client
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit


ACCOUNTS = ["HG621000002", "HG631000003", "HG641000004", "HG651000005",
            "HG661000006", "HG671000007", "HG681000008", "1234", "HG000000000"]
AT = re.compile(rb'"at":"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"')


def cases():
    result = []

    def post(name, body, status=202, content_type="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        result.append((name, "POST", "/notify", raw, content_type, status))

    for index, (kind, fields) in enumerate([
        ("statement_ready", {}),
        ("card_payment", {"amount": 12.4, "merchant": "Café Zürich"}),
        ("low_balance", {"threshold": "100.00"}),
    ]):
        account = ACCOUNTS[index]
        post(kind + "-valid", dict(account=account, kind=kind, fields=fields))
        post(kind + "-missing-field", {"account": account} if index == 0 else
             dict(account=account, kind=kind, fields={}), 400)
    post("card-missing-merchant", dict(account=ACCOUNTS[1], kind="card_payment",
                                      fields={"amount": 12.4}), 400)
    post("missing-account", {"kind": "statement_ready"}, 400)
    post("missing-kind", {"account": ACCOUNTS[0]}, 400)
    post("unknown-kind", dict(account=ACCOUNTS[0], kind="nope"), 400)
    post("empty-object", {}, 400)
    post("malformed-json", b'{"account":', 400)
    post("non-json", b'account=HG621000002&kind=statement_ready', 400, "text/plain")
    for index in range(3, 6):
        post("additional-account-" + str(index), dict(
            account=ACCOUNTS[index], kind="card_payment",
            fields={"amount": "12.40", "merchant": "Shop " + str(index)}))
    post("same-account-newest", dict(account=ACCOUNTS[0], kind="low_balance",
                                     fields={"threshold": 42}))
    post("short-account", dict(account="1234", kind="statement_ready"))
    for index in range(1, 23):
        post("rate-%02d" % index, dict(account=ACCOUNTS[6], kind="card_payment",
             fields={"amount": index, "merchant": "Rate " + str(index)}),
             202 if index <= 20 else 429)
    for account in ACCOUNTS:
        result.append(("outbox-" + account, "GET", "/outbox/" + account,
                       None, "application/json", 200))
    for name, method, path in [("missing-outbox-account", "GET", "/outbox/"),
                               ("get-notify", "GET", "/notify"),
                               ("post-outbox", "POST", "/outbox/x")]:
        result.append((name, method, path, b"{}" if method == "POST" else None,
                       "application/json", 404))
    return result


def request(base, method, path, body=None, content_type="application/json"):
    url = urlsplit(base)
    cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = cls(url.hostname, url.port, timeout=10)
    try:
        conn.request(method, url.path.rstrip("/") + path, body=body, headers={
            "User-Agent": "notify-parity/1.0", "Accept": "*/*",
            "Content-Type": content_type, "Connection": "close"})
        response = conn.getresponse()
        return response.status, response.getheader("Content-Type"), response.read()
    finally:
        conn.close()


def capture(args):
    subprocess.run(args.reset_cmd, shell=True, check=True)
    deadline = time.monotonic() + 90
    while True:
        try:
            status, _, body = request(args.base, "GET", "/outbox/" + ACCOUNTS[0])
            if status == 200:
                break
        except (OSError, http.client.HTTPException):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError("service not ready after reset")
        time.sleep(0.5)
    for account in ACCOUNTS:
        status, _, body = request(args.base, "GET", "/outbox/" + account)
        if status != 200 or body != b"[]":
            raise RuntimeError("store is not clean: " + account)
    print("Clean store verified for %d accounts" % len(ACCOUNTS))
    records = []
    for name, method, path, payload, content_type, expected in cases():
        status, header, body = request(args.base, method, path, payload, content_type)
        records.append(dict(name=name, method=method, path=path, status=status,
                            content_type=header, body_base64=base64.b64encode(body).decode(),
                            normalization_count=normalize(method, path, body)[1]))
        if status != expected:
            raise RuntimeError("%s: expected %d, got %d: %r" % (name, expected, status, body))
        if name.startswith("outbox-"):
            rows = json.loads(body)
            posts = [r for r in records if r["status"] == 202]
            expected_texts = [json.loads(base64.b64decode(r["body_base64"]))["text"]
                              for r in reversed(posts)
                              if json.loads(next(c[3] for c in cases() if c[0] == r["name"]))["account"] == path.rsplit("/", 1)[1]]
            if [row["text"] for row in rows] != expected_texts:
                raise RuntimeError(name + ": outbox count/order/content mismatch")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "cases.json").write_text(json.dumps(records, indent=2) + "\n")
    print("Captured %d cases; timestamp normalizations: %d" % (
        len(records), sum(r["normalization_count"] for r in records)))


def normalize(method, path, body):
    if method == "GET" and path.startswith("/outbox/"):
        return AT.subn(b'"at":"<AT>"', body)
    return body, 0


def compare(left, right):
    a = json.loads((Path(left) / "cases.json").read_text())
    b = json.loads((Path(right) / "cases.json").read_text())
    failures = 0
    print("CASE                             STATUS TYPE BODY  AT(A/B) RESULT")
    for index in range(max(len(a), len(b))):
        if index >= min(len(a), len(b)):
            print("case %d missing: FAIL" % index)
            failures += 1
            continue
        x, y = a[index], b[index]
        bx, nx = normalize(x["method"], x["path"], base64.b64decode(x["body_base64"]))
        by, ny = normalize(y["method"], y["path"], base64.b64decode(y["body_base64"]))
        checks = [x["status"] == y["status"], x["content_type"] == y["content_type"], bx == by]
        ok = all(checks) and all(x[k] == y[k] for k in ("name", "method", "path"))
        failures += not ok
        print("%-32s %-6s %-4s %-5s %2d/%-2d %s" % (
            x["name"], *("=" if c else "DIFF" for c in checks), nx, ny,
            "PASS" if ok else "FAIL"))
    print("PASS: %d FAIL: %d" % (max(len(a), len(b)) - failures, failures))
    return int(failures != 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    if len(sys.argv) > 1 and sys.argv[1] == "compare":
        parser.add_argument("mode")
        parser.add_argument("left")
        parser.add_argument("right")
        args = parser.parse_args()
        return compare(args.left, args.right)
    parser.add_argument("--base", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--reset-cmd", required=True)
    capture(parser.parse_args())
    return 0


if __name__ == "__main__":
    sys.exit(main())

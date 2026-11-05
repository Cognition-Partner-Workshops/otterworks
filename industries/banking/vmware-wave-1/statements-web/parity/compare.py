#!/usr/bin/env python3
"""Compare raw HTTP responses from an untouched VM and the platform."""
import argparse
import hashlib
import http.cookiejar
import json
import pathlib
import re
import urllib.error
import urllib.request

APP = pathlib.Path(__file__).resolve().parents[1]
SEED = APP.parent / "data" / "seed.sql"


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def get(self, base, path):
        try:
            response = self.opener.open(base.rstrip("/") + path, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers.get("Content-Type"), response.read()


def cases(accounts):
    yield "accounts-fresh", "/statements/accounts", 200, None
    for account in accounts:
        yield "statement-" + account, "/statements/statement?account=" + account, 200, None
        yield "last-" + account, "/statements/accounts", 200, account
    yield "statement-unknown", "/statements/statement?account=UNKNOWN12345", 200, None
    yield "last-unknown", "/statements/accounts", 200, "UNKNOWN12345"
    for name, query in [
        ("missing", ""), ("empty", "?account="), ("bad", "?account=bad"),
        ("encoded", "?account=%3Cscript%3E"),
    ]:
        yield name, "/statements/statement" + query, 400, None
        yield "last-after-" + name, "/statements/accounts", 200, "UNKNOWN12345"
    yield "index", "/statements/", 200, None
    yield "index-html", "/statements/index.html", 200, None


def run(args):
    seed = SEED.read_bytes()
    accounts = re.findall(r"INSERT INTO accounts VALUES \('([^']+)'", seed.decode())
    assert len(accounts) == 24, "must exercise every seeded account"
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    vm, candidate = Client(), Client()

    def check(name, path, expected, last, before_client, after_client, target, suite):
        before = before_client.get(args.vm, path)
        after = after_client.get(target, path) if target else None
        for label, response in [("vm", before), ("container", after)]:
            if response is not None:
                folder = args.out / label
                folder.mkdir(exist_ok=True)
                (folder / (name + ".body")).write_bytes(response[2])
                (folder / (name + ".json")).write_text(json.dumps({
                    "status": response[0], "content_type": response[1],
                }, indent=2) + "\n")
        valid = before[0] == expected and (after is None or after == before)
        if last:
            marker = ('<p id="last">Last viewed: <a href="statement?account=' + last + '">').encode()
            valid = valid and marker in before[2]
        if name == "accounts-fresh":
            valid = valid and b'id="last"' not in before[2]
        if name == "statement-unknown":
            valid = valid and b"0 lines, net movement 0" in before[2]
        records.append({
            "case": name, "suite": suite, "path": path, "target": target,
            "vm_status": before[0], "vm_content_type": before[1], "vm_sha256": digest(before[2]),
            "container_status": after[0] if after else None,
            "container_content_type": after[1] if after else None,
            "container_sha256": digest(after[2]) if after else None,
            "passed": bool(valid),
        })
        print(("PASS " if valid else "FAIL ") + name)

    for name, path, expected, last in cases(accounts):
        check(name, path, expected, last, vm, candidate, args.candidate, "service")
    if args.replica:
        assert args.candidate and len(args.replica) == 2 and args.replica[0] != args.replica[1]
        vm, candidate = Client(), Client()
        for i, account in enumerate([accounts[0], accounts[-1]]):
            writer, reader = args.replica[i], args.replica[1 - i]
            check("pod-write-" + account, "/statements/statement?account=" + account, 200, None,
                  vm, candidate, writer, "cross-replica")
            check("pod-read-" + account, "/statements/accounts", 200, account,
                  vm, candidate, reader, "cross-replica")
        assert not any(c.name == "JSESSIONID" for c in candidate.jar), "platform must not create sessions"
        assert any(c.name == "JSESSIONID" for c in vm.jar), "baseline must use legacy sessions"
    result = {
        "seed_sha256": digest(seed), "normalisations": [],
        "cases": len(records), "passed": sum(r["passed"] for r in records), "responses": records,
    }
    (args.out / "transcript.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "responses"}, indent=2))
    return result["cases"] != result["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vm", default="http://127.0.0.1:8081")
    parser.add_argument("--candidate")
    parser.add_argument("--replica", action="append", help="distinct direct pod port-forward; supply twice")
    parser.add_argument("--out", type=pathlib.Path, default=APP / "parity" / "run")
    raise SystemExit(run(parser.parse_args()))

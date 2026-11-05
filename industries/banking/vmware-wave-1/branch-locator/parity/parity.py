#!/usr/bin/env python3
"""Side-by-side parity for branch-locator: the VM stand-in (web-02) and the platform container.

Every case is sent to both sides back to back. open_now depends on the clock, so a case is
repeated if the minute changed between the two requests (nothing is normalised away).
Compared per case: HTTP status, Content-Type and the raw body bytes.

  parity.py --vm http://localhost:8083 --platform http://127.0.0.1:18083 --out results/run1
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.request

# Every place the geocoder stub knows (vm/geo-stub/geo_stub.py), spelled as a user might.
PLACES = ["harbour", "market", "old town", "river", "hill", "lake"]
CASES = [("index", "/")]
CASES += [("nearest-" + p.replace(" ", "-"), "/api/nearest?q=" + urllib.request.quote(p)) for p in PLACES]
CASES += [
    ("nearest-upper-case", "/api/nearest?q=HARBOUR"),
    ("nearest-postcode-text", "/api/nearest?q=HG1%20Old%20Town"),
    ("nearest-padded", "/api/nearest?q=%20%20lake%20%20"),
    ("nearest-two-places", "/api/nearest?q=river%20market"),
    ("nearest-unknown-place", "/api/nearest?q=nowhere"),
    ("nearest-unicode", "/api/nearest?q=%C3%9Cn%C3%AFcode%20%E2%82%AC"),
    ("nearest-empty-q", "/api/nearest?q="),
    ("nearest-blank-q", "/api/nearest?q=%20%20"),
    ("nearest-missing-q", "/api/nearest"),
    ("nearest-other-param-only", "/api/nearest?query=harbour"),
    ("unknown-path", "/nope"),
    ("nearest-trailing-slash", "/api/nearest/"),
]


def fetch(base, path):
    try:
        with urllib.request.urlopen(base.rstrip("/") + path, timeout=15) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()


def minute():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vm", required=True)
    ap.add_argument("--platform", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    for side in ("vm", "platform"):
        (out / side).mkdir(parents=True, exist_ok=True)
    rows, failed = [], 0
    for name, path in CASES:
        for _ in range(3):
            m0 = minute()
            vm = fetch(a.vm, path)
            pf = fetch(a.platform, path)
            if minute() == m0:
                break
        for side, res in (("vm", vm), ("platform", pf)):
            (out / side / (name + ".body")).write_bytes(res[2])
        same = vm[0] == pf[0] and vm[1] == pf[1] and vm[2] == pf[2]
        failed += not same
        opens = None
        if vm[1] == "application/json" and vm[0] == 200:
            opens = [b["open_now"] for b in json.loads(vm[2])["branches"]]
        rows.append({"case": name, "path": path, "minute": m0, "equal": same,
                     "vm": {"status": vm[0], "content_type": vm[1], "sha256": hashlib.sha256(vm[2]).hexdigest()},
                     "platform": {"status": pf[0], "content_type": pf[1], "sha256": hashlib.sha256(pf[2]).hexdigest()},
                     "open_now": opens})
        print("%-4s %-26s %s %-32s %s" % ("ok" if same else "DIFF", name, vm[0], vm[1], opens if opens else ""))
    summary = {"vm": a.vm, "platform": a.platform, "cases": len(rows), "passed": len(rows) - failed, "results": rows}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("%d/%d cases equal" % (len(rows) - failed, len(rows)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

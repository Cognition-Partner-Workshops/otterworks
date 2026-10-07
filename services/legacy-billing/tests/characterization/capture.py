#!/usr/bin/env python3
"""Run the characterization scenario against a running legacy-billing app.

    python capture.py --base-url http://localhost:8096 --out golden/oracle.json

Each response is stored as {status, body}; JSON bodies are kept parsed with
only `generated_at` removed (wall clock). Nothing else is normalized: what
differs between engines is decided by parity.py, row by row.

The Oracle Free listener intermittently refuses the facade's per-request
connections under a fast replay (DPY-6005), which the app reports as 503
"estate unavailable". Such a call is retried; the 503 is only recorded if it
persists, so a deterministic 503 (for example a duplicate-key ORA-00001)
still lands in the transcript. A connect refusal never reaches a commit, so a
retry cannot double-apply a write.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import scenario  # noqa: E402

VOLATILE = {"generated_at"}
UNAVAILABLE = "legacy estate unavailable"
ATTEMPTS = 5


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def call(session: requests.Session, base: str, step: dict) -> dict:
    for attempt in range(1, ATTEMPTS + 1):
        result = _call_once(session, base, step)
        unavailable = result["status"] == 503 and isinstance(result["body"], dict) \
            and result["body"].get("error") == UNAVAILABLE
        if not unavailable or attempt == ATTEMPTS:
            if attempt > 1:
                result["attempts"] = attempt
            return result
        time.sleep(attempt)
    raise AssertionError("unreachable")


def _call_once(session: requests.Session, base: str, step: dict) -> dict:
    response = session.request(
        step.get("method", "GET"), base + step["path"],
        headers=step.get("headers"), json=step.get("json"), data=step.get("form"),
        allow_redirects=False, timeout=60,
    )
    try:
        body = _strip(response.json())
    except ValueError:
        body = response.text
    result = {"status": response.status_code, "body": body}
    if 300 <= response.status_code < 400:
        result["location"] = response.headers.get("Location")
    return result


def run(base: str) -> dict:
    out: dict = {}
    with requests.Session() as session:
        for step in scenario.steps():
            result = call(session, base, step)
            out[step["id"]] = result
            if step.get("follow_invoice_lines") and result["status"] == 200:
                for row in result["body"]:
                    sub = {"path": f"/api/v1/billing/invoices/{row['invoice_id']}/lines",
                           "headers": step["headers"]}
                    out[f"{step['id']}:lines:{row['invoice_id']}"] = call(session, base, sub)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    results = run(args.base_url.rstrip("/"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    statuses: dict[int, int] = {}
    for r in results.values():
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    retried = sum(1 for r in results.values() if r.get("attempts"))
    print(f"[capture] {len(results)} calls -> {args.out} statuses={dict(sorted(statuses.items()))}"
          f" retried={retried}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

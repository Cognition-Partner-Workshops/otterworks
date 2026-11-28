#!/usr/bin/env python3
"""Replay the pinned corpus against two live legacy-portal endpoints at once and diff them.

Unlike replay.py (one live target against the Java capture), this drives a live Java endpoint and a
live Lambda endpoint side by side. Each case is sent to both endpoints concurrently, in corpus order
per context, and the case passes only when:

  pair     the two live responses agree on status, media type and normalized body (replay.py rules)
  state    after a write case (POST/PUT/PATCH/DELETE), both stores hold the same normalized rows
  java-rec the live Java response matches java-reference.json (cross-check of the baseline)
  lambda-rec the live Lambda response matches java-reference.json

Before each context both stores are reset with --reset-cmd and their post-reset state must agree.
The fixture hash covers the corpus files, every --fixture-file and the per-context post-reset state,
so two runs with the same hash started from the same data.

  python3 live_parity.py --java-base http://127.0.0.1:18095 --lambda-base http://127.0.0.1:18096 \\
      --reset-cmd 'scripts/lp-local.sh reset {context}' --state-cmd 'scripts/lp-local.sh state {store} {context}'

--state-cmd prints a JSON object {"<schema.table>": [row objects]} for a store (java|lambda) and a
context. The corpus is left as is: requests.json, java-reference.json and SHA256SUMS are only read.
Exit status: 0 all selected cases passed, 1 any failed or selected-but-unrun, 3 corpus checksum mismatch.
"""
import argparse
import hashlib
import html
import http.client
import json
import re
import shlex
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from replay import canonical, compare, parse_contexts, render_body, verify_checksums

HERE = Path(__file__).resolve().parent
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
STORES = ("java", "lambda")
IDENTITY_HEADERS = ("server", "x-lp-local-function", "apigw-requestid")
STATE_TIMESTAMPS = {("announcements.announcement", "created_at"), ("feedback.feedback", "created_at")}
PG_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def send(base, case, timeout):
    """Same request as replay.send, also keeping identity headers and wall-clock times."""
    url = urllib.parse.urlsplit(base)
    conn_cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(url.hostname, url.port, timeout=timeout)
    headers = {"Accept": case.get("accept", "application/json")}
    payload = None
    if case.get("body") is not None:
        payload = case["body"].encode(case.get("bodyEncoding", "utf-8"))
        headers["Content-Type"] = case.get("contentType", "application/json")
    sent, started = now(), time.monotonic()
    try:
        conn.request(case["method"], url.path.rstrip("/") + case["path"], body=payload, headers=headers)
        resp = conn.getresponse()
        status, raw = resp.status, resp.read()
        content_type = resp.getheader("Content-Type") or ""
        ident = {h: resp.getheader(h) for h in IDENTITY_HEADERS if resp.getheader(h)}
    finally:
        conn.close()
    return {"status": status, "mediaType": content_type.split(";")[0].strip().lower(),
            "body": raw.decode("utf-8", errors="replace"), "sentUtc": sent,
            "elapsedMs": round((time.monotonic() - started) * 1000), "identity": ident}


def run_cmd(template, **fields):
    cmd = template.format(**fields)
    done = subprocess.run(shlex.split(cmd), capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"{cmd!r} exited {done.returncode}: {done.stderr.strip()[-400:]}")
    return done.stdout


def normalized_state(raw):
    """Rows sorted by content, wall-clock columns replaced by a placeholder (they differ per store)."""
    state = {}
    for table, rows in sorted(json.loads(raw or "{}").items()):
        rows = [
            {key: "<datetime>" if (table, key) in STATE_TIMESTAMPS and isinstance(value, str)
             and PG_TIMESTAMP.fullmatch(value) else value for key, value in sorted(row.items())}
            for row in rows or []
        ]
        state[table] = sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    return state


def snapshots(template, ctx):
    with ThreadPoolExecutor(2) as pool:
        futures = {s: pool.submit(run_cmd, template, store=s, context=ctx) for s in STORES}
        return {s: normalized_state(f.result()) for s, f in futures.items()}


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_context(ctx, cases, java_rec, args):
    run_cmd(args.reset_cmd, context=ctx)
    fixture = snapshots(args.state_cmd, ctx)
    if fixture["java"] != fixture["lambda"]:
        raise RuntimeError(f"[{ctx}] stores differ after reset: {json.dumps(fixture)[:400]}")
    results = []
    error = None
    for case in cases:
        try:
            with ThreadPoolExecutor(2) as pool:
                fj = pool.submit(send, args.java_base, case, args.timeout)
                fl = pool.submit(send, args.lambda_base, case, args.timeout)
                live = {"java": fj.result(), "lambda": fl.result()}
        except (OSError, http.client.HTTPException) as exc:
            error = f"{case['id']}: {exc}"
            break
        problems = {}
        jc, lc, pair = compare(live["java"], live["lambda"], args.strict_media_type)
        if pair:
            problems["pair"] = pair
        rec = java_rec.get(case["id"])
        if rec is None:
            problems["recording"] = ["missing Java capture"]
        else:
            for store in STORES:
                _, _, p = compare(rec, live[store], args.strict_media_type)
                if p:
                    problems[f"{store}-rec"] = p
        state = None
        is_write = case["method"].upper() in WRITES
        if is_write:
            try:
                state = snapshots(args.state_cmd, ctx)
            except (OSError, RuntimeError, ValueError) as exc:
                error = f"{case['id']}: {exc}"
                problems["state"] = ["persistent state could not be checked"]
            else:
                if state["java"] != state["lambda"]:
                    problems["state"] = ["persistent state differs"]
        results.append({
            "id": case["id"], "method": case["method"], "path": case["path"], "write": is_write,
            "passed": not problems, "problems": problems,
            "java": {**jc, **{k: live["java"][k] for k in ("sentUtc", "elapsedMs", "identity")}},
            "lambda": {**lc, **{k: live["lambda"][k] for k in ("sentUtc", "elapsedMs", "identity")}},
            "recording": canonical(rec) if rec else None,
            "state": state,
        })
        if error or (problems and args.stage == "first"):
            break
    result = {"context": ctx, "casesInCorpus": len(cases), "fixtureState": fixture["java"], "cases": results}
    if error:
        result["error"] = error
    return result


def identity(base, path, timeout):
    try:
        r = send(base, {"method": "GET", "path": path}, timeout)
        return {"status": r["status"], "body": r["body"][:400], **r["identity"]}
    except (OSError, http.client.HTTPException) as e:
        return {"error": str(e)}


def timeline_html(report):
    rows = []
    for ctx in report["contexts"]:
        for c in ctx["cases"]:
            cls = "ok" if c["passed"] else "bad"
            probs = "; ".join(f"{k}: {', '.join(v)}" for k, v in c["problems"].items()) or "identical"
            state = ""
            if c["write"]:
                state = "state unavailable" if c["state"] is None else (
                    "state &ne;" if "state" in c["problems"] else "state =")
            rows.append(
                f"<tr class={cls}><td>{html.escape(c['java']['sentUtc'][11:])}</td><td>{c['id']}</td>"
                f"<td>{c['method']} {html.escape(c['path'][:60])}</td>"
                f"<td>{c['java']['status']} {c['java']['mediaType'] or ''}</td>"
                f"<td>{c['lambda']['status']} {c['lambda']['mediaType'] or ''}"
                f" <small>{html.escape(c['lambda']['identity'].get('x-lp-local-function', ''))}</small></td>"
                f"<td>{state}</td>"
                f"<td>{html.escape(probs)}</td></tr>")
        for c in ctx["unrun"]:
            rows.append(f"<tr class=unrun><td></td><td>{c}</td><td colspan=5>unrun</td></tr>")
    t = report["totals"]
    ids = "".join(
        f"<div class=id><b>{s}</b> {html.escape(report['endpoints'][s]['base'])}"
        f"<pre>{html.escape(json.dumps(report['endpoints'][s]['identity'], indent=1))}</pre></div>" for s in STORES)
    return f"""<!doctype html><meta charset=utf-8><title>legacy-portal live parity {report['runToken']}</title>
<style>body{{font:13px system-ui;margin:16px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;
padding:2px 6px;text-align:left}}tr.ok td:last-child{{color:#176a2c}}tr.bad{{background:#fde2e2}}tr.unrun{{background:#eee}}
.ids{{display:flex;gap:16px}}.id{{flex:1;border:1px solid #999;padding:6px}}pre{{margin:4px 0;font-size:11px;white-space:pre-wrap}}
.sum{{font-size:16px;margin:10px 0}}</style>
<h2>legacy-portal live parity &middot; run {html.escape(report['runToken'])} &middot; {report['startedUtc']}</h2>
<div class=ids>{ids}</div>
<div class=sum>passed <b>{t['passed']}</b> &middot; failed <b>{t['failed']}</b> &middot; unrun <b>{t['unrun']}</b>
 of {t['corpus']} &middot; write cases with equal state {t['stateEqual']}/{t['writesRun']}
 &middot; fixture sha256 <code>{report['fixtureSha256']}</code></div>
<table><tr><th>sent (UTC)</th><th>case</th><th>request</th><th>java</th><th>lambda</th><th>state</th><th>result</th></tr>
{''.join(rows)}</table>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--java-base", required=True)
    ap.add_argument("--lambda-base", required=True)
    ap.add_argument("--reset-cmd", required=True, help="command resetting both stores; {context} is substituted")
    ap.add_argument("--state-cmd", required=True, help="command printing one store's rows; {store} {context}")
    ap.add_argument("--context", action="append", help="common|announcements|preferences|feedback|all")
    ap.add_argument("--stage", choices=["first", "full"], default="full")
    ap.add_argument("--requests", default=str(HERE / "requests.json"))
    ap.add_argument("--java-capture", default=str(HERE / "java-reference.json"))
    ap.add_argument("--fixture-file", action="append", default=[], help="store DDL/seed file folded into the hash")
    ap.add_argument("--run-token", default="")
    ap.add_argument("--java-identity-path", default="/health")
    ap.add_argument("--lambda-identity-path", default="/__lp_local/identity")
    ap.add_argument("--out", default=str(HERE / "out-live"))
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--strict-media-type", action="store_true")
    args = ap.parse_args()

    failures = verify_checksums(Path(args.requests).resolve().parent)
    if failures:
        print("corpus checksum mismatch, refusing to replay:", *failures, sep="\n  ", file=sys.stderr)
        return 3
    print("corpus checksums: OK (SHA256SUMS)")

    started = now()
    corpus = json.loads(Path(args.requests).read_text())["cases"]
    java_rec = {c["id"]: c["response"] for c in json.loads(Path(args.java_capture).read_text())["cases"]}
    report = {
        "runToken": args.run_token, "startedUtc": started, "stage": args.stage,
        "endpoints": {
            "java": {"base": args.java_base, "identity": identity(args.java_base, args.java_identity_path, args.timeout)},
            "lambda": {"base": args.lambda_base,
                       "identity": identity(args.lambda_base, args.lambda_identity_path, args.timeout)},
        },
        "contexts": [],
    }
    for ctx in parse_contexts(args.context):
        cases = [c for c in corpus if c["context"] == ctx]
        try:
            result = run_context(ctx, cases, java_rec, args)
        except (RuntimeError, OSError, ValueError) as e:
            result = {"context": ctx, "casesInCorpus": len(cases), "fixtureState": None, "cases": [],
                      "error": str(e)}
        if "error" in result:
            print(f"[{ctx}] aborted: {result['error']}", file=sys.stderr)
        done = {c["id"] for c in result["cases"]}
        result["unrun"] = [c["id"] for c in cases if c["id"] not in done]
        report["contexts"].append(result)
        passed = sum(c["passed"] for c in result["cases"])
        print(f"[{ctx}] passed {passed}, failed {len(result['cases']) - passed}, unrun {len(result['unrun'])} "
              f"of {len(cases)}")
        for c in result["cases"]:
            if not c["passed"]:
                print(f"  {c['id']} {c['method']} {c['path'][:80]}: {c['problems']}")
                print(f"    java   {c['java']['status']} {c['java']['mediaType']} {render_body(c['java'])[:200]}")
                print(f"    lambda {c['lambda']['status']} {c['lambda']['mediaType']} {render_body(c['lambda'])[:200]}")

    selected = {r["context"] for r in report["contexts"]}
    run_cases = [c for r in report["contexts"] for c in r["cases"]]
    writes = [c for c in run_cases if c["write"]]
    passed = sum(c["passed"] for c in run_cases)
    report["totals"] = {
        "corpus": len(corpus), "selected": sum(r["casesInCorpus"] for r in report["contexts"]),
        "passed": passed, "failed": len(run_cases) - passed,
        "unrun": len(corpus) - len(run_cases),
        "notSelected": sum(1 for c in corpus if c["context"] not in selected),
        "writesRun": len(writes), "stateEqual": sum("state" not in c["problems"] for c in writes),
        "byCheck": {k: sum(k in c["problems"] for c in run_cases)
                    for k in ("pair", "state", "java-rec", "lambda-rec", "recording")},
    }
    manifest = {
        "files": {Path(p).name: sha256_file(p) for p in [args.requests, args.java_capture, *args.fixture_file]},
        "resetState": {r["context"]: r["fixtureState"] for r in report["contexts"]},
    }
    report["fixtureManifest"] = manifest
    report["fixtureSha256"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "live-parity.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    (out / "timeline.html").write_text(timeline_html(report))
    t = report["totals"]
    print(f"\ntotal: passed {t['passed']}, failed {t['failed']}, unrun {t['unrun']} of {t['corpus']} "
          f"({t['notSelected']} of the unrun not selected) "
          f"(writes with equal state {t['stateEqual']}/{t['writesRun']}; failures by check {t['byCheck']})")
    print(f"fixture sha256: {report['fixtureSha256']}")
    print(f"evidence: {out / 'live-parity.json'}, timeline: {out / 'timeline.html'}")
    return 0 if t["failed"] == 0 and t["unrun"] == t["notSelected"] else 1


if __name__ == "__main__":
    sys.exit(main())

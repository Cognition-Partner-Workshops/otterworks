#!/usr/bin/env python3
"""Replay requests.json against the Java and .NET legacy-portal builds and diff the responses.

Compared per request: HTTP status, response media type (Content-Type without parameters) and
the JSON body. Bodies are compared as serialized JSON with key order and number formatting
preserved (so `3.0` vs `3` or a reordered object is a difference). Values that are wall-clock
timestamps are replaced by a placeholder naming their *format*, so only the format is compared.

Either side can be a live base URL or a capture file written by a previous run (--capture).

  python3 run_parity.py --java http://localhost:18095 --dotnet http://localhost:18098
  python3 run_parity.py --java-capture java-reference.json --dotnet http://localhost:8098 \
      --context feedback
  python3 run_parity.py --java http://localhost:18095 --capture java-reference.json
"""
import argparse
import http.client
import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ISO_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.(\d{3}|\d{6}|\d{9}))?Z$")
SPRING_ERROR_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$")
ANY_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, str):
        if ISO_INSTANT.match(value):
            return "<instant:ISO_INSTANT>"
        if SPRING_ERROR_TS.match(value):
            return "<timestamp:yyyy-MM-ddTHH:mm:ss.SSS+00:00>"
        if ANY_DATETIME.match(value):
            return "<datetime:unrecognized-format:" + value + ">"
    return value


def send(base, case):
    url = urllib.parse.urlsplit(base)
    if url.scheme not in ("http", "https") or not url.hostname:
        raise SystemExit(f"base URL must be http(s)://host[:port], got {base!r}")
    conn_cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = conn_cls(url.hostname, url.port, timeout=30)
    headers = {"Accept": case.get("accept", "application/json")}
    data = case.get("body")
    payload = None
    if data is not None:
        payload = data.encode(case.get("bodyEncoding", "utf-8"))
        headers["Content-Type"] = case.get("contentType", "application/json")
    try:
        conn.request(case["method"], url.path.rstrip("/") + case["path"], body=payload, headers=headers)
        resp = conn.getresponse()
        status, raw = resp.status, resp.read()
        content_type = resp.getheader("Content-Type") or ""
    finally:
        conn.close()
    media = content_type.split(";")[0].strip().lower()
    text = raw.decode("utf-8", errors="replace")
    return {"status": status, "mediaType": media, "body": text}


def canonical(resp):
    text = resp["body"]
    if not text.strip():
        return {"status": resp["status"], "mediaType": resp["mediaType"] or None, "json": None, "raw": ""}
    try:
        parsed = json.loads(text)
    except ValueError:
        return {"status": resp["status"], "mediaType": resp["mediaType"], "json": None, "raw": text}
    return {
        "status": resp["status"],
        "mediaType": resp["mediaType"],
        "json": json.dumps(normalize(parsed), ensure_ascii=False),
        "raw": None,
    }


def collect(base, capture_file, cases):
    if capture_file:
        captured = json.loads(Path(capture_file).read_text())
        by_id = {c["id"]: c["response"] for c in captured["cases"]}
        return {c["id"]: by_id.get(c["id"]) for c in cases}
    return {c["id"]: send(base, c) for c in cases}


def media_equivalent(a, b):
    def fam(m):
        return "json" if m and (m == "application/json" or m.endswith("+json")) else m
    return fam(a) == fam(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--java")
    ap.add_argument("--java-capture")
    ap.add_argument("--dotnet")
    ap.add_argument("--dotnet-capture")
    ap.add_argument("--context", action="append", help="announcements|preferences|feedback|common (repeatable)")
    ap.add_argument("--requests", default=str(HERE / "requests.json"))
    ap.add_argument("--capture", help="only hit --java (or --dotnet) and write responses to this file")
    ap.add_argument("--report", default=str(HERE / "REPORT.md"))
    ap.add_argument("--results", default=str(HERE / "results.json"))
    ap.add_argument("--strict-media-type", action="store_true",
                    help="treat application/json vs application/*+json as a difference")
    args = ap.parse_args()

    cases = json.loads(Path(args.requests).read_text())["cases"]
    if args.context:
        cases = [c for c in cases if c["context"] in args.context]

    if args.capture:
        base = args.java or args.dotnet
        out = [{**c, "response": send(base, c)} for c in cases]
        Path(args.capture).write_text(json.dumps({"base": base, "cases": out}, indent=2) + "\n")
        print(f"captured {len(out)} responses from {base} -> {args.capture}")
        return 0

    java = collect(args.java, args.java_capture, cases)
    dotnet = collect(args.dotnet, args.dotnet_capture, cases)

    results, diffs = [], 0
    for c in cases:
        jr, dr = java[c["id"]], dotnet[c["id"]]
        if jr is None or dr is None:
            results.append({"id": c["id"], "match": False, "problems": ["missing capture"]})
            diffs += 1
            continue
        jc, dc = canonical(jr), canonical(dr)
        problems = []
        if jc["status"] != dc["status"]:
            problems.append(f"status {jc['status']} != {dc['status']}")
        same_media = jc["mediaType"] == dc["mediaType"] if args.strict_media_type else media_equivalent(jc["mediaType"], dc["mediaType"])
        if not same_media:
            problems.append(f"media type {jc['mediaType']} != {dc['mediaType']}")
        if jc["json"] != dc["json"] or jc["raw"] != dc["raw"]:
            problems.append("body differs")
        match = not problems
        diffs += 0 if match else 1
        results.append({
            "id": c["id"], "context": c["context"], "method": c["method"], "path": c["path"][:80],
            "match": match, "problems": problems,
            "java": jc, "dotnet": dc,
        })

    Path(args.results).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    lines = ["# legacy-portal Java vs .NET response parity", "",
             f"Java: `{args.java or args.java_capture}`  ",
             f".NET: `{args.dotnet or args.dotnet_capture}`", "",
             f"**{len(results) - diffs}/{len(results)} requests identical** "
             "(status, media type, JSON body incl. key order and number formatting; "
             "timestamps compared by format only).", "",
             "| Case | Request | Java status | .NET status | Result |", "|---|---|---|---|---|"]
    for r in results:
        js = r.get("java", {}).get("status", "?")
        ds = r.get("dotnet", {}).get("status", "?")
        verdict = "identical" if r["match"] else "DIFF: " + "; ".join(r["problems"])
        lines.append(f"| {r['id']} | `{r.get('method', '')} {r.get('path', '')}` | {js} | {ds} | {verdict} |")
    for r in results:
        if not r["match"] and "java" in r:
            lines += ["", f"### {r['id']}", "", "Java:", "```", r["java"]["json"] or r["java"]["raw"] or "", "```",
                      ".NET:", "```", r["dotnet"]["json"] or r["dotnet"]["raw"] or "", "```"]
    Path(args.report).write_text("\n".join(lines) + "\n")
    print(f"{len(results) - diffs}/{len(results)} identical; report: {args.report}")
    for r in results:
        if not r["match"]:
            print(f"  DIFF {r['id']}: {'; '.join(r['problems'])}")
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())

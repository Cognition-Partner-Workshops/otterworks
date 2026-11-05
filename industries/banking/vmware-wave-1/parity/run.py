#!/usr/bin/env python3
"""Compare independent endpoints and batch spools against the same seed."""

import argparse
import difflib
import hashlib
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPS = json.loads((HERE / "requests.json").read_text())
MAX_BODY = 4 * 1024 * 1024


def digest(body):
    return hashlib.sha256(body).hexdigest()


def accounts():
    return re.findall(
        r"INSERT INTO accounts VALUES \('([^']+)'",
        (HERE.parent / "data/seed.sql").read_text(),
    )


def requests_for(app):
    for spec in APPS[app]:
        values = accounts() if spec.get("per_account") else spec.get("queries", [""])
        for value in values:
            fields = {"account": value, "query": urllib.parse.quote(value)}
            yield f"{spec['name']}:{value}", spec, fields


def strip_keys(value, omitted):
    if isinstance(value, dict):
        return {k: strip_keys(v, omitted) for k, v in value.items() if k not in omitted}
    if isinstance(value, list):
        return [strip_keys(v, omitted) for v in value]
    return value


def comparable(body, spec):
    text = body.decode("utf-8", errors="replace")
    if spec.get("generated_document_names"):
        text = re.sub(
            r"(passport|id-card|proof-of-address|payslip)-\d{10,}(\.[a-z]+)",
            r"\1-<generated-time>\2",
            text,
        )
    try:
        value = strip_keys(json.loads(text), set(spec.get("omit_json_keys", [])))
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    except (ValueError, TypeError):
        return text.encode()


def request_body(spec, fields):
    if spec.get("multipart"):
        boundary = "parity-fixture-boundary"
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            'filename="fixture.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
            f"%PDF-1.4\nSynthetic parity fixture\n%%EOF\r\n--{boundary}--\r\n"
        ).encode()
        return body, f"multipart/form-data; boundary={boundary}"
    if "json" in spec:
        return json.dumps(
            {k: str(v).format(**fields) for k, v in spec["json"].items()}
        ).encode(), "application/json"
    return None, "application/octet-stream"


def fetch(base, spec, fields, context):
    body, content_type = request_body(spec, fields)
    req = urllib.request.Request(
        base.rstrip("/") + spec["path"].format(**fields),
        data=body,
        method=spec.get("method", "GET"),
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=context) as response:
            result = response.read(MAX_BODY + 1)
            status = response.status
    except urllib.error.HTTPError as exc:
        status, result = exc.code, exc.read(MAX_BODY + 1)
    if len(result) > MAX_BODY:
        raise ValueError("response exceeds 4 MiB")
    return status, result


def compare_http(app, vm, kind, context):
    rows = []
    for key, spec, fields in requests_for(app):
        row = {"case": key, "expected_status": spec["status"]}
        bodies = {}
        for side, base in (("vm", vm), ("kind", kind)):
            try:
                status, body = fetch(base, spec, fields, context)
                bodies[side] = comparable(body, spec)
                row[side] = {
                    "status": status,
                    "raw_sha256": digest(body),
                    "body_sha256": digest(bodies[side]),
                }
            except (OSError, ValueError, urllib.error.URLError):
                row[side] = {
                    "error": "request failed; check endpoint and TLS configuration"
                }
        row["status_pass"] = all(
            row[s].get("status") == spec["status"] for s in ("vm", "kind")
        )
        row["body_checked"] = not spec.get("status_only", False)
        row["body_pass"] = (
            (len(bodies) == 2 and bodies["vm"] == bodies["kind"])
            if row["body_checked"]
            else None
        )
        row["normalization"] = {
            k: spec[k]
            for k in ("omit_json_keys", "generated_document_names")
            if k in spec
        }
        if row["body_checked"] and len(bodies) == 2 and not row["body_pass"]:
            row["sample_diff"] = list(
                difflib.unified_diff(
                    bodies["vm"].decode(errors="replace").splitlines(),
                    bodies["kind"].decode(errors="replace").splitlines(),
                    fromfile="vm",
                    tofile="kind",
                    lineterm="",
                )
            )[:12]
        rows.append(row)
    return rows


def compare_batch(vm_dir, kind_dir):
    rows = []
    for day in APPS["rates-batch"]["business_days"]:
        row = {"case": day}
        bodies = {}
        filename = APPS["rates-batch"]["filename"].format(day=day)
        for side, directory in (("vm", vm_dir), ("kind", kind_dir)):
            path = directory / filename
            if not path.is_file() or not 0 < path.stat().st_size <= MAX_BODY:
                row[side] = {"error": "missing, empty or oversized batch output"}
            else:
                bodies[side] = path.read_bytes()
                row[side] = {
                    "file_sha256": digest(bodies[side]),
                    "bytes": len(bodies[side]),
                }
        row["file_pass"] = len(bodies) == 2 and bodies["vm"] == bodies["kind"]
        if len(bodies) == 2 and not row["file_pass"]:
            row["sample_diff"] = list(
                difflib.unified_diff(
                    bodies["vm"].decode(errors="replace").splitlines(),
                    bodies["kind"].decode(errors="replace").splitlines(),
                    lineterm="",
                )
            )[:12]
        rows.append(row)
    return rows


def report(app, rows):
    if app == "rates-batch":
        depths = {
            "HTTP status": "N/A",
            "body hash per endpoint/account": "N/A",
            "batch file hash per business day": f"{sum(r['file_pass'] for r in rows)}/{len(rows)}",
        }
        passed = all(r["file_pass"] for r in rows)
    else:
        checked = [r for r in rows if r["body_checked"]]
        depths = {
            "HTTP status": f"{sum(r['status_pass'] for r in rows)}/{len(rows)}",
            "body hash per endpoint/account": f"{sum(r['body_pass'] for r in checked)}/{len(checked)}",
            "batch file hash per business day": "N/A",
        }
        passed = all(
            r["status_pass"] and (not r["body_checked"] or r["body_pass"]) for r in rows
        )
    return {"app": app, "pass": passed and bool(rows), "depth": depths, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", choices=APPS, required=True)
    parser.add_argument("--vm-base")
    parser.add_argument("--kind-base")
    parser.add_argument("--vm-dir", type=Path)
    parser.add_argument("--kind-dir", type=Path)
    parser.add_argument("--ca-file")
    parser.add_argument("--insecure-loopback", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.app == "rates-batch":
        if (
            not args.vm_dir
            or not args.kind_dir
            or args.vm_dir.resolve() == args.kind_dir.resolve()
        ):
            parser.error("set two independent --vm-dir and --kind-dir spools")
        rows = compare_batch(args.vm_dir, args.kind_dir)
    else:
        if (
            not args.vm_base
            or not args.kind_base
            or args.vm_base.rstrip("/") == args.kind_base.rstrip("/")
        ):
            parser.error("set independent --vm-base and --kind-base endpoints")
        for base in (args.vm_base, args.kind_base):
            url = urllib.parse.urlsplit(base)
            if (
                url.scheme not in ("http", "https")
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                parser.error(
                    "endpoint must be an HTTP(S) base URL without credentials, query or fragment"
                )
            if args.insecure_loopback and url.hostname not in (
                "localhost",
                "127.0.0.1",
                "::1",
            ):
                parser.error("insecure TLS is permitted only for loopback stand-ins")
        context = ssl.create_default_context(cafile=args.ca_file)
        if args.insecure_loopback:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        rows = compare_http(args.app, args.vm_base, args.kind_base, context)
    result = report(args.app, rows)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"{args.app}: {'PASS' if result['pass'] else 'FAIL'}")
    print("| Depth | Matched / checked |\n| --- | --- |")
    for depth, count in result["depth"].items():
        print(f"| {depth} | {count} |")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

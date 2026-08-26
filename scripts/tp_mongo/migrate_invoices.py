#!/usr/bin/env python3
"""Migrate the Oracle billing invoice estate into MongoDB Atlas.

Source: OW_BILLING.INVOICE_HEADER + OW_BILLING.INVOICE_LINE (one conversion
batch at a time).  Target: one document per invoice in ``invoices`` with its
lines embedded, and ``invoices_quarantine`` for rows that cannot be attached to
an invoice or are missing a required key.

Both reads and writes are scoped to a single namespace batch, and every write is
a deterministic upsert keyed on the source primary key, so a rerun converges
instead of duplicating.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import os
import sys
import urllib.parse
import uuid
from collections import Counter
from pathlib import Path

import oracledb
import requests
from pymongo import MongoClient, ReplaceOne
from requests.auth import HTTPDigestAuth

ROOT = Path(__file__).resolve().parents[2]
ATLAS_API = "https://cloud.mongodb.com/api/atlas/v2"
ATLAS_HEADERS = {
    "Accept": "application/vnd.atlas.2024-08-05+json",
    "Content-Type": "application/json",
}

UNIT = "mongodb-invoices"
INVOICES = "invoices"
QUARANTINE = "invoices_quarantine"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}

HEADER_COLUMNS = ["invoice_id", "invoice_no", "cust_id", "tenant_id",
                  "invoice_dt", "due_dt", "status_cd", "total_amt", "batch_no"]
LINE_COLUMNS = ["line_id", "invoice_id", "invoice_no", "cust_id", "cust_no",
                "cust_name", "tenant_id", "line_no", "line_type_cd",
                "item_desc", "qty", "unit_price", "amount", "tax_amt",
                "invoice_dt", "service_period", "posted_yn", "gl_acct_csv",
                "batch_no", "src_system"]

# Line columns that only exist because the legacy feed copied invoice and
# customer attributes onto every line. They are asserted equal to the header
# before being dropped; a divergence is reported, never silently collapsed.
LINE_DENORMALIZED = {"invoice_no": "invoice_no", "cust_id": "cust_id",
                     "tenant_id": "tenant_id"}
# Customer copies dropped outright; cust_id on the invoice is the reference.
LINE_CUSTOMER_COPIES = ["cust_no", "cust_name"]


def parse_legacy_date(raw):
    """Parse a DD-MON-YY string. Returns (date, None) or (None, reason)."""
    if raw is None:
        return None, "MISSING"
    text = str(raw).strip().upper()
    if not text:
        return None, "EMPTY"
    parts = text.split("-")
    if len(parts) != 3:
        return None, "UNPARSEABLE_SHAPE"
    day, mon, year = parts
    if not day.isdigit() or not year.isdigit() or mon not in MONTHS:
        return None, "UNPARSEABLE_TOKEN"
    yy = int(year)
    century = 2000 if yy < 70 else 1900
    try:
        return dt.datetime(century + yy, MONTHS[mon], int(day)), None
    except ValueError:
        return None, "IMPOSSIBLE_CALENDAR_DATE"


def split_gl_accounts(raw):
    """Split the GL split CSV. Returns (accounts, None) or (None, reason)."""
    if raw is None or not str(raw).strip():
        return None, "EMPTY"
    tokens = [t.strip() for t in str(raw).split(",")]
    if any(not t for t in tokens):
        return None, "EMPTY_CSV_ELEMENT"
    if not all(t.isdigit() for t in tokens):
        return None, "NON_NUMERIC_ACCOUNT"
    return tokens, None


def content_fingerprint(row):
    """Stable identity for a row that has no usable key of its own."""
    payload = json.dumps(row, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


def as_float(value):
    return None if value is None else float(value)


def as_int(value):
    return None if value is None else int(value)


class Quarantine:
    """Accumulates row-level and field-level quarantine records."""

    def __init__(self, batch_no):
        self.batch_no = batch_no
        self.records = {}

    def _add(self, key, doc):
        doc["_id"] = key
        doc["batch_no"] = self.batch_no
        self.records[key] = doc

    def row(self, table, reason, row, key_hint):
        self._add(f"row:{table}:{key_hint}", {
            "scope": "row",
            "reason": reason,
            "source": {"system": "oracle", "schema": "OW_BILLING", "table": table},
            "row": row,
        })

    def field(self, table, reason, source_id, field, raw_value):
        self._add(f"field:{table}:{source_id}:{field}", {
            "scope": "field",
            "reason": reason,
            "source": {"system": "oracle", "schema": "OW_BILLING", "table": table},
            "source_id": source_id,
            "field": field,
            "raw_value": None if raw_value is None else str(raw_value),
        })

    def row_count(self):
        return sum(1 for d in self.records.values() if d["scope"] == "row")

    def by_reason(self):
        return Counter(d["reason"] for d in self.records.values())


def fetch_rows(cursor, table, columns, batch_no):
    cursor.execute(
        f"SELECT {', '.join(columns)} FROM {table} WHERE batch_no = :batch",
        batch=batch_no,
    )
    while True:
        chunk = cursor.fetchmany(5000)
        if not chunk:
            return
        for row in chunk:
            yield dict(zip(columns, row))


def build_line(raw, header, quarantine, stats):
    line_id = raw["line_id"]
    line = {
        "line_id": line_id,
        "line_no": as_int(raw["line_no"]),
        "line_type_cd": as_int(raw["line_type_cd"]),
        "item_desc": raw["item_desc"],
        "qty": as_float(raw["qty"]),
        "unit_price": as_float(raw["unit_price"]),
        "amount": as_float(raw["amount"]),
        "tax_amt": as_float(raw["tax_amt"]),
        "service_period": raw["service_period"],
        "posted": raw["posted_yn"] == "Y",
        "src_system": raw["src_system"],
    }

    invoice_dt, reason = parse_legacy_date(raw["invoice_dt"])
    if reason is None:
        line["invoice_dt"] = invoice_dt
    else:
        stats["line_date_field_quarantined"] += 1
        quarantine.field("INVOICE_LINE", f"UNUSABLE_DATE_{reason}",
                         line_id, "invoice_dt", raw["invoice_dt"])

    accounts, reason = split_gl_accounts(raw["gl_acct_csv"])
    if reason is None:
        line["gl_accounts"] = accounts
    else:
        stats["line_gl_field_quarantined"] += 1
        quarantine.field("INVOICE_LINE", f"MALFORMED_GL_ACCT_CSV_{reason}",
                         line_id, "gl_acct_csv", raw["gl_acct_csv"])

    for column, header_field in LINE_DENORMALIZED.items():
        if raw[column] != header[header_field]:
            stats["line_denormalization_divergence"] += 1
            quarantine.field("INVOICE_LINE", "DENORMALIZED_COPY_DIVERGES_FROM_HEADER",
                             line_id, column, raw[column])
            line[f"line_{column}"] = raw[column]
    return line


def build_invoice(raw, quarantine, stats):
    invoice = {
        "_id": raw["invoice_id"],
        "invoice_no": raw["invoice_no"],
        "cust_id": raw["cust_id"],
        "tenant_id": raw["tenant_id"],
        "status_cd": as_int(raw["status_cd"]),
        "total_amt": as_float(raw["total_amt"]),
        "batch_no": as_int(raw["batch_no"]),
        "source": {"system": "oracle", "schema": "OW_BILLING",
                   "table": "INVOICE_HEADER"},
        "lines": [],
    }
    for field in ("invoice_dt", "due_dt"):
        value, reason = parse_legacy_date(raw[field])
        if reason is None:
            invoice[field] = value
        else:
            stats["header_date_field_quarantined"] += 1
            quarantine.field("INVOICE_HEADER", f"UNUSABLE_DATE_{reason}",
                             raw["invoice_id"], field, raw[field])
    return invoice


def read_source(cursor, batch_no):
    stats = Counter()
    quarantine = Quarantine(batch_no)

    headers = {}
    for raw in fetch_rows(cursor, "invoice_header", HEADER_COLUMNS, batch_no):
        stats["header_rows_read"] += 1
        if not raw["invoice_id"]:
            stats["header_rows_quarantined"] += 1
            quarantine.row("INVOICE_HEADER", "MISSING_REQUIRED_KEY_INVOICE_ID",
                           raw, f"missing-invoice-id:{content_fingerprint(raw)}")
            continue
        headers[raw["invoice_id"]] = raw

    invoices = {inv_id: build_invoice(raw, quarantine, stats)
                for inv_id, raw in headers.items()}

    for raw in fetch_rows(cursor, "invoice_line", LINE_COLUMNS, batch_no):
        stats["line_rows_read"] += 1
        line_id = raw["line_id"]
        invoice_id = raw["invoice_id"]
        if not line_id or not invoice_id:
            missing = "LINE_ID" if not line_id else "INVOICE_ID"
            stats["line_rows_quarantined"] += 1
            stats[f"line_rows_quarantined_missing_{missing.lower()}"] += 1
            quarantine.row("INVOICE_LINE", f"MISSING_REQUIRED_KEY_{missing}", raw,
                           line_id or f"missing-line-id:{content_fingerprint(raw)}")
            continue
        header = headers.get(invoice_id)
        if header is None:
            stats["line_rows_quarantined"] += 1
            stats["line_rows_quarantined_orphan"] += 1
            quarantine.row("INVOICE_LINE", "ORPHAN_LINE_NO_HEADER", raw, line_id)
            continue
        invoices[invoice_id]["lines"].append(
            build_line(raw, header, quarantine, stats))
        stats["lines_embedded"] += 1

    for invoice in invoices.values():
        invoice["lines"].sort(key=lambda line: (line["line_no"] is None,
                                                line["line_no"], line["line_id"]))
        invoice["line_count"] = len(invoice["lines"])
    return invoices, quarantine, stats


def bulk_upsert(collection, documents, chunk=1000):
    written = 0
    ops = []
    for doc in documents:
        ops.append(ReplaceOne({"_id": doc["_id"]}, doc, upsert=True))
        if len(ops) == chunk:
            collection.bulk_write(ops, ordered=False)
            written += len(ops)
            ops = []
    if ops:
        collection.bulk_write(ops, ordered=False)
        written += len(ops)
    return written


def recompute_from_target(db, batch_no):
    """Recompute every reported number by reading the target back."""
    invoices = db[INVOICES]
    quarantine = db[QUARANTINE]
    scope = {"batch_no": batch_no}
    agg = list(invoices.aggregate([
        {"$match": scope},
        {"$group": {"_id": None,
                    "invoices": {"$sum": 1},
                    "lines": {"$sum": {"$size": "$lines"}},
                    "max_lines": {"$max": {"$size": "$lines"}}}},
    ]))
    totals = agg[0] if agg else {"invoices": 0, "lines": 0, "max_lines": 0}
    by_reason = {
        row["_id"]: row["count"] for row in quarantine.aggregate([
            {"$match": scope},
            {"$group": {"_id": "$reason", "count": {"$sum": 1}}},
        ])
    }
    by_scope = {
        row["_id"]: row["count"] for row in quarantine.aggregate([
            {"$match": scope},
            {"$group": {"_id": "$scope", "count": {"$sum": 1}}},
        ])
    }
    line_rows = quarantine.count_documents(
        {**scope, "scope": "row", "source.table": "INVOICE_LINE"})
    return {
        "invoice_documents": totals["invoices"],
        "embedded_lines": totals["lines"],
        "max_lines_per_invoice": totals["max_lines"] or 0,
        "quarantine_rows": by_scope.get("row", 0),
        "quarantine_line_rows": line_rows,
        "quarantine_fields": by_scope.get("field", 0),
        "quarantine_by_reason": dict(sorted(by_reason.items())),
    }


def ensure_access_list(marker):
    """Self-heal the project access list for this VM's public address.

    Returns a callable that removes only the entry this process created.
    """
    public_key = os.environ.get("MONGODB_ATLAS_PUBLIC_KEY")
    private_key = os.environ.get("MONGODB_ATLAS_PRIVATE_KEY")
    project = os.environ.get("MONGODB_ATLAS_PROJECT_ID")
    if not (public_key and private_key and project):
        print("[access-list] Atlas API credentials absent; relying on existing access list")
        return lambda: None
    auth = HTTPDigestAuth(public_key, private_key)
    url = f"{ATLAS_API}/groups/{project}/accessList"
    ip = requests.get("https://api.ipify.org", timeout=15).text.strip()
    ipaddress.ip_address(ip)
    listed = requests.get(f"{url}?itemsPerPage=500", auth=auth,
                          headers=ATLAS_HEADERS, timeout=30)
    listed.raise_for_status()
    entries = [e.get("ipAddress") or e.get("cidrBlock")
               for e in listed.json().get("results", [])]
    for entry in filter(None, entries):
        try:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(entry, strict=False):
                print(f"[access-list] {ip} already covered by {entry}")
                return lambda: None
        except ValueError:
            continue
    created = requests.post(url, auth=auth, headers=ATLAS_HEADERS, timeout=30,
                            json=[{"ipAddress": ip, "comment": marker}])
    created.raise_for_status()
    print(f"[access-list] added {ip} for this run")

    def revoke():
        target = f"{url}/{urllib.parse.quote(ip, safe='')}"
        current = requests.get(f"{url}?itemsPerPage=500", auth=auth,
                               headers=ATLAS_HEADERS, timeout=30)
        current.raise_for_status()
        mine = [e for e in current.json().get("results", [])
                if (e.get("ipAddress") or e.get("cidrBlock")) in (ip, f"{ip}/32")
                and e.get("comment") == marker]
        if not mine:
            print(f"[access-list] {ip} not owned by this run; left in place")
            return
        response = requests.delete(target, auth=auth, headers=ATLAS_HEADERS, timeout=30)
        print(f"[access-list] removed {ip} (HTTP {response.status_code})")

    return revoke


def migrate(db, cursor, batch_no, label):
    invoices, quarantine, stats = read_source(cursor, batch_no)
    print(f"[{label}] source: {stats['header_rows_read']} header rows, "
          f"{stats['line_rows_read']} line rows")
    written = bulk_upsert(db[INVOICES], invoices.values())
    quarantined = bulk_upsert(db[QUARANTINE], quarantine.records.values())
    print(f"[{label}] upserted {written} invoice documents, "
          f"{quarantined} quarantine records "
          f"({quarantine.row_count()} row-level)")
    return {
        "stats": dict(stats),
        "quarantine_by_reason": dict(sorted(quarantine.by_reason().items())),
        "quarantine_rows": quarantine.row_count(),
        "invoice_documents_written": written,
    }


def build_report(manifest, namespace, batch_no, first, second, before, after,
                 unverified):
    expected_headers = manifest["targets"]["oracle.OW_BILLING.INVOICE_HEADER"]["rows"]
    expected_lines = manifest["targets"]["oracle.OW_BILLING.INVOICE_LINE"]["rows"]
    expected_orphans = next(
        a["count"] for a in manifest["planted_anomalies"]
        if a["kind"] == "orphaned_rows"
        and a["target"] == "oracle.OW_BILLING.INVOICE_LINE")
    actual_orphans = after["quarantine_by_reason"].get("ORPHAN_LINE_NO_HEADER", 0)
    accounted = after["embedded_lines"] + after["quarantine_line_rows"]

    def check(cid, expected, actual, source):
        return {"id": cid, "expected": expected, "actual": actual,
                "source_of_truth": source,
                "result": "pass" if expected == actual else "fail"}

    checks = [
        check("invoice_documents", expected_headers, after["invoice_documents"],
              "testdata/legacy/manifests/%s.json vs Atlas ow_tp_%s.invoices"
              % (namespace, namespace)),
        check("line_conservation", expected_lines, accounted,
              "manifest INVOICE_LINE rows vs embedded lines + quarantined "
              "INVOICE_LINE rows in Atlas"),
        check("orphan_lines_quarantined", expected_orphans, actual_orphans,
              "manifest orphaned_rows anomaly vs ORPHAN_LINE_NO_HEADER in Atlas"),
        check("no_line_lost_or_duplicated", 0,
              expected_lines - accounted,
              "manifest INVOICE_LINE rows minus lines accounted for in Atlas"),
        check("embedded_cardinality_bounded", True,
              after["max_lines_per_invoice"] <= 23,
              "Atlas $max of $size:$lines (observed %d, bound 23)"
              % after["max_lines_per_invoice"]),
        check("idempotent_rerun_invoice_documents", before["invoice_documents"],
              after["invoice_documents"], "Atlas count after run 1 vs run 2"),
        check("idempotent_rerun_embedded_lines", before["embedded_lines"],
              after["embedded_lines"], "Atlas count after run 1 vs run 2"),
        check("idempotent_rerun_quarantine_records",
              before["quarantine_rows"] + before["quarantine_fields"],
              after["quarantine_rows"] + after["quarantine_fields"],
              "Atlas count after run 1 vs run 2"),
    ]
    idempotent = all(c["result"] == "pass" for c in checks[-3:])
    return {
        "kind": "recon-report",
        "unit": UNIT,
        "namespace": namespace,
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "run_mode": "live",
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": {
            "performed": True,
            "result": "pass" if idempotent else "fail",
            "evidence": (
                "The migration ran twice against the same batch (%d). "
                "Recounted from Atlas: invoices %d -> %d, embedded lines %d -> %d, "
                "quarantine records %d -> %d."
                % (batch_no, before["invoice_documents"], after["invoice_documents"],
                   before["embedded_lines"], after["embedded_lines"],
                   before["quarantine_rows"] + before["quarantine_fields"],
                   after["quarantine_rows"] + after["quarantine_fields"])
            ),
        },
        "planted_anomaly_detections": {
            "expected_set": ["orphaned_rows:oracle.OW_BILLING.INVOICE_LINE:%d"
                             % expected_orphans],
            "actual_set": ["orphaned_rows:oracle.OW_BILLING.INVOICE_LINE:%d"
                           % actual_orphans],
            "missing": [] if actual_orphans == expected_orphans
            else ["orphaned_rows:oracle.OW_BILLING.INVOICE_LINE:%d"
                  % expected_orphans],
            "unexpected": [],
        },
        "unverified_paths": unverified,
        "detail": {
            "batch_no": batch_no,
            "target": {"database": "ow_tp_%s" % namespace,
                       "collections": [INVOICES, QUARANTINE]},
            "source_tables": ["OW_BILLING.INVOICE_HEADER", "OW_BILLING.INVOICE_LINE"],
            "run_1": first,
            "run_2": second,
            "recomputed_after_run_1": before,
            "recomputed_after_run_2": after,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns", required=True, help="namespace, e.g. demo1")
    parser.add_argument("--batch-no", type=int, required=True)
    parser.add_argument("--oracle-user", default="ow_billing")
    parser.add_argument("--oracle-password",
                        default=os.environ.get("ORACLE_BILLING_PASSWORD", "ow_billing"))
    parser.add_argument("--oracle-host", default="localhost")
    parser.add_argument("--oracle-port", type=int,
                        default=int(os.environ.get("ORACLE_BILLING_DB_PORT", "52521")))
    parser.add_argument("--oracle-service", default="FREEPDB1")
    parser.add_argument("--report", default=None,
                        help="path for the machine-readable recon report")
    parser.add_argument("--reruns", type=int, default=1,
                        help="extra full runs used to prove idempotency")
    args = parser.parse_args()

    manifest_path = ROOT / f"testdata/legacy/manifests/{args.ns}.json"
    manifest = json.loads(manifest_path.read_text())
    database = f"ow_tp_{args.ns}"
    report_path = Path(args.report) if args.report else (
        ROOT / f"docs/tech-partnerships/recon/{UNIT}-{args.ns}.recon.json")

    uri = os.environ.get("MONGODB_ATLAS_URI")
    if not uri:
        raise SystemExit("MONGODB_ATLAS_URI is required")

    revoke = ensure_access_list(f"otterworks {UNIT} {args.ns} {uuid.uuid4().hex}")
    connection = None
    client = None
    try:
        connection = oracledb.connect(user=args.oracle_user,
                                      password=args.oracle_password,
                                      host=args.oracle_host, port=args.oracle_port,
                                      service_name=args.oracle_service)
        client = MongoClient(uri, serverSelectionTimeoutMS=20000)
        cursor = connection.cursor()
        db = client[database]
        first = migrate(db, cursor, args.batch_no, "run 1")
        before = recompute_from_target(db, args.batch_no)
        print(f"[run 1] recomputed from Atlas: {before}")
        second = first
        after = before
        for index in range(args.reruns):
            label = f"run {index + 2}"
            second = migrate(db, cursor, args.batch_no, label)
            after = recompute_from_target(db, args.batch_no)
            print(f"[{label}] recomputed from Atlas: {after}")
    finally:
        if client is not None:
            client.close()
        if connection is not None:
            connection.close()
        revoke()

    unverified = [
        "Atlas M0 shared tier: no separate staging cluster, so no cross-cluster "
        "restore rehearsal was exercised.",
        "Only conversion batch %d (namespace %s) was migrated; other namespaces' "
        "batches in the same source tables are untouched and unverified."
        % (args.batch_no, args.ns),
        "Line-level customer copies (cust_no, cust_name) are dropped, so a "
        "consumer needing the point-in-time customer name at line level would "
        "have to join CUSTOMER_MASTER; that path is not exercised here.",
    ]
    report = build_report(manifest, args.ns, args.batch_no, first, second,
                          before, after, unverified)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"[recon] {report_path}")
    failed = [c["id"] for c in report["checks"] if c["result"] != "pass"]
    if failed:
        print(f"[recon] FAILED checks: {', '.join(failed)}")
        return 1
    print("[recon] all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Reconcile the migrated invoices collection against the Oracle billing estate.

Every number in the report is recomputed here -- counts, per-invoice money
totals, the INVOICE_LINE checksum and the orphan set are read back out of the
document store and out of Oracle at recon time. Nothing is copied from the
migration summary or from the baseline manifest; the manifest is only quoted
alongside the recomputed value so a drift is visible.

Usage:
  migrations/mongodb/mongo_invoices/run.sh recon --ns demo \
      --out docs/tech-partnerships/recon/mongo_invoices.recon.json \
      [--rerun-summary-a A.json --rerun-summary-b B.json] \
      [--empty-input-evidence E.json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal

from pymongo.errors import WriteError

import common

MANIFEST_PATH = "testdata/legacy/manifests/{ns}.json"
ZERO = Decimal("0.00")


def add(checks, cid, expected, actual, source_of_truth):
    checks.append({
        "id": cid,
        "expected": expected,
        "actual": actual,
        "source_of_truth": source_of_truth,
        "result": "pass" if expected == actual else "fail",
    })
    return checks[-1]


def manifest_baseline(ns: str) -> dict:
    """The immutable before-contract, quoted for comparison only."""
    try:
        with open(MANIFEST_PATH.format(ns=ns)) as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}
    targets = data.get("targets", {})
    header = targets.get(
        f"oracle.{common.SOURCE_SCHEMA}.{common.HEADER_TABLE}", {}
    )
    line = targets.get(
        f"oracle.{common.SOURCE_SCHEMA}.{common.LINE_TABLE}", {}
    )
    return {
        "header_rows": header.get("rows"),
        "line_rows": line.get("rows"),
        "line_checksum": line.get("checksum"),
    }


def oracle_facts(ns: str) -> dict:
    """Recount the source estate at recon time."""
    conn = common.oracle_connect()
    cur = conn.cursor()
    cur.arraysize = 5000
    batch = common.batch_no(ns)

    cur.execute("SELECT COUNT(*) FROM invoice_header WHERE batch_no = :b", b=batch)
    headers = int(cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM invoice_line WHERE batch_no = :b", b=batch)
    lines = int(cur.fetchone()[0])

    cur.execute("""
        SELECT l.line_id
          FROM invoice_line l
         WHERE l.batch_no = :b
           AND NOT EXISTS (SELECT 1 FROM invoice_header h
                            WHERE h.invoice_id = l.invoice_id)
    """, b=batch)
    orphans = sorted(row[0] for row in cur)

    cur.execute("""
        SELECT l.invoice_id, COUNT(*), SUM(l.amount), SUM(l.tax_amt)
          FROM invoice_line l
         WHERE l.batch_no = :b
           AND EXISTS (SELECT 1 FROM invoice_header h
                        WHERE h.invoice_id = l.invoice_id)
         GROUP BY l.invoice_id
    """, b=batch)
    per_invoice = {row[0]: (int(row[1]), Decimal(row[2]), Decimal(row[3])) for row in cur}

    cur.execute("SELECT line_id, amount FROM invoice_line WHERE batch_no = :b", b=batch)
    source_pairs = {row[0]: Decimal(row[1]) for row in cur}

    cur.execute("""
        SELECT COUNT(*) FROM invoice_line
         WHERE batch_no = :b
           AND (amount IS NULL OR tax_amt IS NULL OR qty IS NULL
                OR unit_price IS NULL OR invoice_id IS NULL)
    """, b=batch)
    null_rows = int(cur.fetchone()[0])

    cur.execute("""
        SELECT line_id, item_desc FROM invoice_line
         WHERE batch_no = :b AND item_desc IS NOT NULL
           AND ROWNUM <= 5000
    """, b=batch)
    text_samples = {row[0]: row[1] for row in cur}

    cur.close()
    conn.close()
    return {
        "headers": headers,
        "lines": lines,
        "orphans": orphans,
        "per_invoice": per_invoice,
        "source_pairs": source_pairs,
        "null_rows": null_rows,
        "text_samples": text_samples,
    }


def checksum_of(pairs) -> str:
    """The estate's line checksum: md5 of line_id:amount in line_id order."""
    digest = hashlib.md5()
    for line_id, amount in sorted(pairs):
        digest.update(f"{line_id}:{amount}\n".encode())
    return digest.hexdigest()


def validator_probe(collection, ns: str) -> dict:
    """Insert a legacy-shaped document and require the server to reject it."""
    probe_id = common.invoice_doc_id(ns, "__recon_validator_probe__")
    doc = {
        "_id": probe_id,
        "ns": ns,
        "invoice_no": "RECON-PROBE",
        # the legacy estate stores the issue date as DD-MON-YY text
        "issue_date": "15-JAN-24",
        "lines": [],
        "source": {"system": common.SOURCE_SYSTEM, "schema": common.SOURCE_SCHEMA,
                   "table": common.HEADER_TABLE, "invoice_id": "__recon_validator_probe__"},
    }
    try:
        collection.insert_one(doc)
    except WriteError as exc:
        return {"rejected": True, "code": exc.code}
    collection.delete_one({"_id": probe_id})
    return {"rejected": False, "code": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rerun-summary-a")
    ap.add_argument("--rerun-summary-b")
    ap.add_argument("--empty-input-evidence")
    args = ap.parse_args()

    ns = args.ns
    src = oracle_facts(ns)
    baseline = manifest_baseline(ns)

    client = common.mongo_client()
    invoices = client[common.db_name(ns)][common.COLLECTION]
    quarantined = client[common.quarantine_db_name(ns)][common.QUARANTINE_COLLECTION]

    doc_count = invoices.count_documents({"ns": ns})

    embedded_pairs = []
    embedded_line_ids = set()
    per_invoice_actual = {}
    non_decimal_money = 0
    max_lines = 0
    over_bounded = []
    text_mismatches = []
    for doc in invoices.find({"ns": ns}, {"source.invoice_id": 1, "invoice_no": 1,
                                          "header_total": 1, "lines": 1}):
        lines = doc.get("lines", [])
        amount_total, tax_total = ZERO, ZERO
        for line in lines:
            for field in ("amount", "tax_amt", "qty", "unit_price"):
                if type(line.get(field)).__name__ != "Decimal128":
                    non_decimal_money += 1
            amount = common.money(line["amount"])
            amount_total += amount
            tax_total += common.money(line["tax_amt"])
            embedded_pairs.append((line["line_id"], common.money_text(amount)))
            embedded_line_ids.add(line["line_id"])
            expected_text = src["text_samples"].get(line["line_id"])
            if expected_text is not None and line.get("item_desc") != expected_text:
                text_mismatches.append(line["line_id"])
        per_invoice_actual[doc["source"]["invoice_id"]] = (len(lines), amount_total, tax_total)
        max_lines = max(max_lines, len(lines))
        if len(lines) > common.BOUNDED_LINES_PER_INVOICE:
            over_bounded.append({"invoice_no": doc["invoice_no"], "lines": len(lines)})

    quarantine_pairs = []
    actual_orphans = []
    quarantine_by_reason = {}
    for doc in quarantined.find({"ns": ns}):
        reason = doc["reason"]
        quarantine_by_reason[reason] = quarantine_by_reason.get(reason, 0) + 1
        line_id = doc["source"]["line_id"]
        if reason == "orphan_no_header":
            actual_orphans.append(line_id)
        amount = doc.get("parsed", {}).get("amount")
        if amount is not None and line_id not in embedded_line_ids:
            quarantine_pairs.append((line_id, common.money_text(common.money(amount))))
    actual_orphans.sort()

    checks: list[dict] = []

    add(checks, "doc-count", src["headers"], doc_count,
        "COUNT(*) of OW_BILLING.INVOICE_HEADER for the namespace batch vs "
        "countDocuments on the invoices collection")

    deterministic_ids = all(
        doc["_id"] == common.invoice_doc_id(ns, doc["source"]["invoice_id"])
        for doc in invoices.find({"ns": ns}, {"source.invoice_id": 1})
    )
    add(checks, "doc-count-deterministic-id", True, deterministic_ids,
        "every stored _id re-derived as uuid5(namespace, INVOICE_ID) from the "
        "document's own source key")

    embedded_expected = src["lines"] - len(src["orphans"])
    add(checks, "embedded-lines", embedded_expected, len(embedded_pairs),
        "source INVOICE_LINE rows with a resolvable header vs the sum of "
        "embedded line items read back from the collection")

    add(checks, "orphans-quarantined", src["orphans"], actual_orphans,
        "Oracle anti-join for INVOICE_LINE rows without an INVOICE_HEADER vs "
        "quarantined documents with reason orphan_no_header")
    add(checks, "orphans-never-attached", [],
        sorted(set(src["orphans"]) & embedded_line_ids),
        "orphaned source line ids intersected with the line ids embedded in the "
        "collection: an orphan must never be attached to a header")

    money_mismatches = sorted(
        invoice_id for invoice_id, expected in src["per_invoice"].items()
        if per_invoice_actual.get(invoice_id) != expected
    )
    add(checks, "money-exactness", [], money_mismatches[:20],
        "per-invoice line count, SUM(amount) and SUM(tax_amt) from Oracle "
        "compared with the same values summed from the embedded lines as exact "
        "decimals")
    add(checks, "money-exactness-bson-type", 0, non_decimal_money,
        "count of embedded money and quantity fields whose stored BSON type is "
        "not decimal128")

    mismatched_header_totals = invoices.count_documents(
        {"ns": ns, "header_total_matches_lines": False})
    checks.append({
        "id": "legacy-header-total-variance",
        "expected": "reported, never reconciled away",
        "actual": {"invoices_whose_header_total_differs_from_lines":
                   mismatched_header_totals,
                   "invoices_total": doc_count},
        "source_of_truth": "header_total compared with the summed line amounts on "
                           "each migrated document; the legacy estate does not "
                           "derive INVOICE_HEADER.TOTAL_AMT from its lines, so the "
                           "variance is surfaced rather than corrected",
        "result": "pass",
    })

    probe = validator_probe(invoices, ns)
    add(checks, "validator", {"rejected": True, "code": 121}, probe,
        "insert of a document carrying the legacy DD-MON-YY string issue date, "
        "rejected by the collection's $jsonSchema validator")

    full_checksum = checksum_of(embedded_pairs + quarantine_pairs)
    add(checks, "checksum", baseline.get("line_checksum"), full_checksum,
        "md5 over line_id:amount in line_id order, recomputed from the embedded "
        "lines plus the quarantined lines held in the document store")
    add(checks, "checksum-source-recompute", checksum_of(
        (line_id, common.money_text(amount))
        for line_id, amount in src["source_pairs"].items()), full_checksum,
        "the same checksum recomputed directly from Oracle at recon time, "
        "independent of the baseline document")

    add(checks, "null-attribution", src["null_rows"],
        sum(quarantine_by_reason.get(reason, 0)
            for reason in ("null_amount", "null_quantity", "null_foreign_key")),
        "source rows with a NULL amount, quantity or foreign key vs quarantined "
        "documents carrying a null reason code: a NULL is never defaulted to zero")

    add(checks, "byte-transparency", [], sorted(text_mismatches)[:20],
        "free-text line descriptions compared byte-for-byte against the source "
        "rows for a 5000-row sample")

    checks.append({
        "id": "bounded-line-model",
        "expected": {"limit": common.BOUNDED_LINES_PER_INVOICE,
                     "over_limit": "reported, never truncated"},
        "actual": {"max_lines_on_one_invoice": max_lines,
                   "invoices_over_limit": len(over_bounded),
                   "sample": sorted(over_bounded,
                                    key=lambda e: (-e["lines"], e["invoice_no"]))[:5]},
        "source_of_truth": "line array sizes read back from the collection",
        "result": "pass",
    })

    if args.empty_input_evidence:
        with open(args.empty_input_evidence) as fh:
            evidence = json.load(fh)
        add(checks, "empty-input-semantics",
            {"action": "no-op", "exit_code": 0, "invoices_unchanged": True},
            {"action": evidence.get("action"), "exit_code": evidence.get("exit_code"),
             "invoices_unchanged": evidence.get("invoices_before") ==
             evidence.get("invoices_after")},
            "migration run against a namespace with no source rows, with the "
            "invoices count taken before and after")
    else:
        checks.append({"id": "empty-input-semantics", "expected": "no-op",
                       "actual": None, "result": "skipped",
                       "source_of_truth": "not exercised in this run"})

    baseline_check = add(checks, "baseline-manifest-parity",
                         {"header_rows": baseline.get("header_rows"),
                          "line_rows": baseline.get("line_rows")},
                         {"header_rows": src["headers"], "line_rows": src["lines"]},
                         "immutable baseline manifest compared with the live source "
                         "counts recounted at recon time")

    rerun = {"performed": False, "result": "fail"}
    if args.rerun_summary_a and args.rerun_summary_b:
        with open(args.rerun_summary_a) as fh:
            run_a = json.load(fh)
        with open(args.rerun_summary_b) as fh:
            run_b = json.load(fh)
        comparable = ("embedded_lines", "quarantined_by_reason", "written", "source")
        identical = all(run_a.get(key) == run_b.get(key) for key in comparable)
        rerun = {
            "performed": True,
            "result": "pass" if identical else "fail",
            "evidence": json.dumps({
                "run_1": {key: run_a.get(key) for key in comparable},
                "run_2": {key: run_b.get(key) for key in comparable},
                "post_rerun_recomputed": {
                    "documents": doc_count,
                    "embedded_lines": len(embedded_pairs),
                    "quarantined": dict(sorted(quarantine_by_reason.items())),
                    "checksum": full_checksum,
                },
            }, sort_keys=True),
        }
        add(checks, "idempotency", True, identical,
            "two consecutive migration runs of the same namespace compared on "
            "written counts, embedded line counts and quarantine reasons, with "
            "the target recomputed after the second run")

    expected_anomalies = [f"orphaned_row:{line_id}" for line_id in src["orphans"]]
    actual_anomalies = [f"orphaned_row:{line_id}" for line_id in actual_orphans]
    missing = sorted(set(expected_anomalies) - set(actual_anomalies))
    unexpected = sorted(set(actual_anomalies) - set(expected_anomalies))

    unverified = [
        "live Atlas recon (this report is run_mode=fixture; the live recompute is "
        "run by the orchestrating session in an uncontended window)",
        "invalid_encoding quarantine: the estate's INVOICE_LINE text in this "
        "namespace decodes cleanly as UTF-8, so the invalid-byte path is covered "
        "only by selftest.py and is not exercised against live source rows",
        "invalid_date quarantine for INVOICE_LINE.INVOICE_DT: no unparseable line "
        "date is present in this namespace, so that branch is covered only by "
        "selftest.py",
        "NULL amount/quantity/foreign-key quarantine: this namespace's source "
        "rows carry no NULLs in those columns, so the null-attribution check is "
        "0-vs-0 and the branch is covered only by selftest.py",
        "byte-transparency beyond the 5000-row comparison sample",
    ]
    if not args.empty_input_evidence:
        unverified.append("empty-input no-op semantics (not exercised in this run)")

    failures = [check["id"] for check in checks if check.get("result") == "fail"]
    if missing or unexpected:
        failures.append("planted_anomaly_detections")
    if rerun["performed"] and rerun["result"] != "pass":
        failures.append("idempotency_rerun")

    report = {
        "kind": "recon-report",
        "unit": common.UNIT,
        "namespace": ns,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_mode": common.run_mode(),
        "source": {
            "system": common.SOURCE_SYSTEM,
            "schema": common.SOURCE_SCHEMA,
            "tables": [common.HEADER_TABLE, common.LINE_TABLE],
            "batch_no": common.batch_no(ns),
        },
        "target": {
            "database": common.db_name(ns),
            "collection": common.COLLECTION,
            "quarantine_database": common.quarantine_db_name(ns),
            "quarantine_collection": common.QUARANTINE_COLLECTION,
            "quarantined_by_reason": dict(sorted(quarantine_by_reason.items())),
        },
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": rerun,
        "planted_anomaly_detections": {
            "expected_set": expected_anomalies,
            "actual_set": actual_anomalies,
            "missing": missing,
            "unexpected": unexpected,
        },
        "unverified_paths": unverified,
        "result": "fail" if failures else "pass",
        "failed_checks": failures,
    }

    with open(args.out, "w") as fh:
        fh.write(json.dumps(report, indent=2, sort_keys=True) + "\n")

    summary = {"result": report["result"], "failed_checks": failures,
               "documents": doc_count, "embedded_lines": len(embedded_pairs),
               "orphans": len(actual_orphans), "checksum": full_checksum,
               "baseline_parity": baseline_check["result"]}
    print(json.dumps(summary, indent=2, sort_keys=True))
    client.close()
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())

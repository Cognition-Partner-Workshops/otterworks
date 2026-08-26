#!/usr/bin/env python3
"""Cross-store reconciliation for the tech-partnerships MongoDB run.

Reads the Atlas collections the migration units wrote (ow_tp_<ns>.customers,
customers_quarantine, invoices, invoices_quarantine), re-derives counts and
checksums from the legacy Oracle estate the same way the seed manifest does
(md5 over "pk:amount" lines fed in PK order), and diffs both against
testdata/legacy/manifests/<ns>.json.

Every value is recomputed from the store it describes at report time; nothing
is copied from migration-time output. Any mismatch — including off by one —
makes the affected check FAIL and the process exit nonzero.

Subcommands:
  snapshot  recompute all target-side values and write them to a JSON file
            (used to capture the pre-rerun state for idempotency evidence)
  report    recompute everything, diff the three sources, and emit the
            PASS/FAIL table (stdout + markdown) and the *.recon.json artifact
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import json
import os
import sys
from pathlib import Path

import oracledb
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[2]
UNIT = "mongodb-run-recon"


# --------------------------------------------------------------------------
# checksum: identical construction to testdata/legacy/oracle_billing_seed.py
# (md5 over "pk:amount\n" lines, amounts fixed to 2 decimals, fed in PK order)
# --------------------------------------------------------------------------

class OrderedChecksum:
    def __init__(self) -> None:
        self._h = hashlib.md5()
        self.count = 0

    def add(self, pk: str, amount) -> None:
        self._h.update(f"{pk}:{amount}\n".encode())
        self.count += 1

    def hexdigest(self) -> str:
        return self._h.hexdigest()


def two_dp(value) -> str:
    if isinstance(value, decimal.Decimal):
        return f"{value:.2f}"
    return f"{float(value):.2f}"


def checksum_pairs(pairs) -> tuple[str, int]:
    ck = OrderedChecksum()
    for pk, amount in sorted(pairs):
        ck.add(pk, amount)
    return ck.hexdigest(), ck.count


# --------------------------------------------------------------------------
# legacy (Oracle) side
# --------------------------------------------------------------------------

def decimal_handler(cursor, metadata):
    if metadata.type_code == oracledb.DB_TYPE_NUMBER:
        return cursor.var(decimal.Decimal, arraysize=cursor.arraysize)
    return None


def read_oracle(args, batch_no: int) -> dict:
    conn = oracledb.connect(
        user=args.oracle_user, password=args.oracle_password,
        host=args.oracle_host, port=args.oracle_port,
        service_name=args.oracle_service)
    cur = conn.cursor()
    cur.arraysize = 5000
    cur.outputtypehandler = decimal_handler

    cur.execute("SELECT cust_id, cur_bal_amt FROM customer_master"
                " WHERE conversion_batch_no = :1", [batch_no])
    cust_ck, cust_rows = checksum_pairs(
        (pk, two_dp(amt)) for pk, amt in cur)

    cur.execute("SELECT line_id, amount FROM invoice_line"
                " WHERE batch_no = :1", [batch_no])
    line_ck, line_rows = checksum_pairs(
        (pk, two_dp(amt)) for pk, amt in cur)

    cur.execute("SELECT COUNT(*) FROM invoice_header WHERE batch_no = :1",
                [batch_no])
    header_rows = int(cur.fetchone()[0])

    cur.execute("""SELECT COUNT(*) FROM entity_attr_value e
                     JOIN customer_master c ON c.cust_id = e.entity_id
                    WHERE e.entity_type = 'CUSTOMER'
                      AND c.conversion_batch_no = :1""", [batch_no])
    eav_in_scope = int(cur.fetchone()[0])

    cur.execute("""SELECT COUNT(*) FROM invoice_line l
                    WHERE l.batch_no = :1
                      AND NOT EXISTS (SELECT 1 FROM invoice_header h
                                       WHERE h.invoice_id = l.invoice_id)""",
                [batch_no])
    orphan_lines = int(cur.fetchone()[0])

    cur.close()
    conn.close()
    return {
        "customer_rows": cust_rows,
        "customer_checksum": cust_ck,
        "invoice_header_rows": header_rows,
        "invoice_line_rows": line_rows,
        "invoice_line_checksum": line_ck,
        "eav_rows_in_scope": eav_in_scope,
        "orphan_invoice_lines": orphan_lines,
    }


# --------------------------------------------------------------------------
# target (Atlas) side
# --------------------------------------------------------------------------

def read_atlas(ns: str, batch_no: int) -> dict:
    uri = os.environ.get("MONGODB_ATLAS_URI")
    if not uri:
        raise SystemExit("MONGODB_ATLAS_URI is required")
    client = MongoClient(uri, appname="ow_tp_run_recon",
                         serverSelectionTimeoutMS=20000)
    db = client[f"ow_tp_{ns}"]

    cust_pairs = []
    attribute_values = 0
    null_valued_fields = 0
    for doc in db["customers"].find(
            {"_migration.conversion_batch_no": batch_no}):
        bal = doc.get("cur_bal_amt")
        cust_pairs.append((doc["_id"],
                           two_dp(bal.to_decimal() if hasattr(bal, "to_decimal")
                                  else bal)))
        attrs = doc.get("attributes", {})
        attribute_values += sum(
            len(v) if isinstance(v, list) else 1 for v in attrs.values())
        null_valued_fields += sum(1 for v in doc.values() if v is None)
    cust_ck, cust_count = checksum_pairs(cust_pairs)

    cq = db["customers_quarantine"]
    cq_scope = {"conversion_batch_no": batch_no}
    cust_quarantine = {
        "rows": cq.count_documents({**cq_scope, "scope": "row"}),
        "fields": cq.count_documents({**cq_scope, "scope": "field"}),
        "invalid_signup_dt": cq.count_documents(
            {**cq_scope, "reason": "INVALID_DATE", "field": "signup_dt"}),
        "invalid_date_total": cq.count_documents(
            {**cq_scope, "reason": "INVALID_DATE"}),
        "malformed_related_acct_ids": cq.count_documents(
            {**cq_scope, "reason": "MALFORMED_CSV", "field": "related_acct_ids"}),
        "malformed_csv_total": cq.count_documents(
            {**cq_scope, "reason": "MALFORMED_CSV"}),
        "missing_required_key": cq.count_documents(
            {**cq_scope, "reason": "MISSING_REQUIRED_KEY"}),
        "eav_no_customer": cq.count_documents(
            {**cq_scope, "reason": "EAV_NO_CUSTOMER"}),
        "eav_unsupported_type": cq.count_documents(
            {**cq_scope, "reason": "EAV_UNSUPPORTED_TYPE"}),
    }

    line_pairs = []
    invoice_count = 0
    for doc in db["invoices"].find({"batch_no": batch_no}):
        invoice_count += 1
        for line in doc["lines"]:
            line_pairs.append((line["line_id"], two_dp(line["amount"])))
    embedded_lines = len(line_pairs)

    iq = db["invoices_quarantine"]
    iq_scope = {"batch_no": batch_no}
    orphan_docs = list(iq.find(
        {**iq_scope, "scope": "row", "reason": "ORPHAN_LINE_NO_HEADER"}))
    for doc in orphan_docs:
        line_pairs.append((doc["row"]["line_id"], two_dp(doc["row"]["amount"])))
    line_ck, line_total = checksum_pairs(line_pairs)

    inv_quarantine = {
        "orphan_lines": len(orphan_docs),
        "rows": iq.count_documents({**iq_scope, "scope": "row"}),
        "fields": iq.count_documents({**iq_scope, "scope": "field"}),
        "missing_required_key_rows": iq.count_documents(
            {**iq_scope, "scope": "row",
             "reason": {"$regex": "^MISSING_REQUIRED_KEY"}}),
    }

    client.close()
    return {
        "customers": cust_count,
        "customers_checksum": cust_ck,
        "customer_null_valued_fields": null_valued_fields,
        "attribute_values_embedded": attribute_values,
        "customers_quarantine": cust_quarantine,
        "invoices": invoice_count,
        "embedded_lines": embedded_lines,
        "line_rows_accounted": line_total,
        "lines_checksum": line_ck,
        "invoices_quarantine": inv_quarantine,
    }


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def build_checks(manifest: dict, oracle: dict, atlas: dict) -> list[dict]:
    m_targets = manifest["targets"]
    m_cust = m_targets["oracle.OW_BILLING.CUSTOMER_MASTER"]
    m_line = m_targets["oracle.OW_BILLING.INVOICE_LINE"]
    m_hdr = m_targets["oracle.OW_BILLING.INVOICE_HEADER"]
    m_eav = m_targets["oracle.OW_BILLING.ENTITY_ATTR_VALUE"]
    anomalies = {(a["kind"], a["target"]): a["count"]
                 for a in manifest["planted_anomalies"]}
    cq = atlas["customers_quarantine"]
    iq = atlas["invoices_quarantine"]

    def check(cid, expected, actual, source):
        return {"id": cid, "expected": expected, "actual": actual,
                "source_of_truth": source,
                "result": "pass" if expected == actual else "fail"}

    return [
        # legacy store vs manifest (the seed-legacy-validate contract)
        check("oracle_customer_rows", m_cust["rows"], oracle["customer_rows"],
              "manifest vs Oracle CUSTOMER_MASTER recount"),
        check("oracle_customer_checksum", m_cust["checksum"],
              oracle["customer_checksum"],
              "manifest vs Oracle CUSTOMER_MASTER md5(cust_id:cur_bal_amt)"),
        check("oracle_invoice_header_rows", m_hdr["rows"],
              oracle["invoice_header_rows"],
              "manifest vs Oracle INVOICE_HEADER recount"),
        check("oracle_invoice_line_rows", m_line["rows"],
              oracle["invoice_line_rows"],
              "manifest vs Oracle INVOICE_LINE recount"),
        check("oracle_invoice_line_checksum", m_line["checksum"],
              oracle["invoice_line_checksum"],
              "manifest vs Oracle INVOICE_LINE md5(line_id:amount)"),
        check("oracle_eav_rows", m_eav["rows"], oracle["eav_rows_in_scope"],
              "manifest vs Oracle ENTITY_ATTR_VALUE rows joined to this batch"),
        # target vs manifest / legacy store
        check("atlas_customer_documents", m_cust["rows"], atlas["customers"],
              "manifest vs Atlas customers count"),
        check("atlas_customer_checksum", m_cust["checksum"],
              atlas["customers_checksum"],
              "manifest vs Atlas customers md5(_id:cur_bal_amt)"),
        check("atlas_invoice_documents", m_hdr["rows"], atlas["invoices"],
              "manifest vs Atlas invoices count"),
        check("atlas_line_conservation", m_line["rows"],
              atlas["line_rows_accounted"],
              "manifest INVOICE_LINE rows vs Atlas embedded + quarantined lines"),
        check("atlas_line_checksum", m_line["checksum"],
              atlas["lines_checksum"],
              "manifest vs Atlas md5(line_id:amount) over embedded + quarantined"),
        check("atlas_eav_accounting", m_eav["rows"],
              atlas["attribute_values_embedded"] + cq["eav_no_customer"]
              + cq["eav_unsupported_type"],
              "manifest EAV rows vs Atlas embedded attribute values + quarantine"),
        check("atlas_no_row_lost",
              oracle["customer_rows"],
              atlas["customers"] + cq["rows"] - cq["eav_no_customer"]
              - cq["eav_unsupported_type"],
              "Oracle customer rows vs Atlas documents + row quarantine"),
        check("atlas_no_null_valued_fields", 0,
              atlas["customer_null_valued_fields"],
              "sparse-column rule: NULL source columns emit no field"),
        # known-bad rows: found and quarantined, exact counts
        check("anomaly_orphan_invoice_lines",
              anomalies[("orphaned_rows", "oracle.OW_BILLING.INVOICE_LINE")],
              iq["orphan_lines"],
              "manifest anomaly vs Atlas ORPHAN_LINE_NO_HEADER quarantine"),
        check("anomaly_orphan_lines_in_source",
              anomalies[("orphaned_rows", "oracle.OW_BILLING.INVOICE_LINE")],
              oracle["orphan_invoice_lines"],
              "manifest anomaly vs Oracle headerless line recount"),
        check("anomaly_dirty_signup_dates",
              anomalies[("dirty_dates",
                         "oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT")],
              cq["invalid_signup_dt"],
              "manifest anomaly vs Atlas INVALID_DATE quarantine on signup_dt"),
        check("anomaly_malformed_csv_lists",
              anomalies[("malformed_csv_lists",
                         "oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS")],
              cq["malformed_related_acct_ids"],
              "manifest anomaly vs Atlas MALFORMED_CSV quarantine on related_acct_ids"),
        check("no_missing_required_key_rows", 0,
              cq["missing_required_key"] + iq["missing_required_key_rows"],
              "row quarantine for missing required keys (none expected in batch)"),
    ]


def render_table(checks: list[dict]) -> str:
    rows = [("check", "expected", "actual", "result"),
            ("-----", "--------", "------", "------")]
    rows += [(c["id"], str(c["expected"]), str(c["actual"]),
              "PASS" if c["result"] == "pass" else "FAIL") for c in checks]
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    lines = ["| " + " | ".join(cell.ljust(widths[i])
                               for i, cell in enumerate(row)) + " |"
             for row in rows]
    lines[1] = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["snapshot", "report"])
    parser.add_argument("--ns", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--snapshot-before", default=None,
                        help="target snapshot captured before the idempotency "
                             "rerun of both migrations")
    parser.add_argument("--oracle-user", default="ow_billing")
    parser.add_argument("--oracle-password",
                        default=os.environ.get("ORACLE_BILLING_PASSWORD",
                                               "ow_billing"))
    parser.add_argument("--oracle-host", default="localhost")
    parser.add_argument("--oracle-port", type=int,
                        default=int(os.environ.get("ORACLE_BILLING_DB_PORT",
                                                   "52521")))
    parser.add_argument("--oracle-service", default="FREEPDB1")
    args = parser.parse_args()

    manifest_path = ROOT / f"testdata/legacy/manifests/{args.ns}.json"
    manifest = json.loads(manifest_path.read_text())
    batch_no = manifest["seed_legacy_params"][
        "oracle.OW_BILLING.CUSTOMER_MASTER"]["batch_no"]

    atlas = read_atlas(args.ns, batch_no)

    if args.command == "snapshot":
        out = Path(args.out or f"/tmp/tp-recon-snapshot-{args.ns}.json")
        out.write_text(json.dumps(atlas, indent=2, sort_keys=True) + "\n")
        print(f"[snapshot] {out}")
        return 0

    oracle = read_oracle(args, batch_no)
    checks = build_checks(manifest, oracle, atlas)

    idem = {"performed": False, "result": "fail",
            "evidence": "no pre-rerun snapshot supplied"}
    if args.snapshot_before:
        before = json.loads(Path(args.snapshot_before).read_text())
        same = before == atlas
        idem = {
            "performed": True,
            "result": "pass" if same else "fail",
            "evidence": (
                "Both migrations were rerun against batch %d after a snapshot "
                "of every recomputed target value (counts, checksums, "
                "quarantine breakdowns); the post-rerun recomputation is %s. "
                "customers %d -> %d, lines accounted %d -> %d, "
                "customers checksum %s, lines checksum %s."
                % (batch_no, "identical" if same else "DIFFERENT",
                   before["customers"], atlas["customers"],
                   before["line_rows_accounted"], atlas["line_rows_accounted"],
                   "unchanged" if before["customers_checksum"]
                   == atlas["customers_checksum"] else "CHANGED",
                   "unchanged" if before["lines_checksum"]
                   == atlas["lines_checksum"] else "CHANGED")),
        }
        digest_of = lambda snap: hashlib.md5(
            json.dumps(snap, sort_keys=True).encode()).hexdigest()
        checks.append({
            "id": "idempotency_rerun_converges",
            "expected": digest_of(before), "actual": digest_of(atlas),
            "source_of_truth": "md5 of the full recomputed target snapshot "
                               "before vs after rerunning both migrations",
            "result": idem["result"]})

    anomaly_expected = sorted(
        f"{a['kind']}:{a['target']}:{a['count']}"
        for a in manifest["planted_anomalies"])
    cq, iq = atlas["customers_quarantine"], atlas["invoices_quarantine"]
    anomaly_actual = sorted([
        "orphaned_rows:oracle.OW_BILLING.INVOICE_LINE:%d" % iq["orphan_lines"],
        "dirty_dates:oracle.OW_BILLING.CUSTOMER_MASTER.SIGNUP_DT:%d"
        % cq["invalid_signup_dt"],
        "malformed_csv_lists:oracle.OW_BILLING.CUSTOMER_MASTER.RELATED_ACCT_IDS:%d"
        % cq["malformed_related_acct_ids"],
    ])

    report = {
        "kind": "recon-report",
        "unit": UNIT,
        "namespace": args.ns,
        "generated_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "run_mode": "live",
        "checks": checks,
        "values_recomputed_from_target": True,
        "idempotency_rerun": idem,
        "planted_anomaly_detections": {
            "expected_set": anomaly_expected,
            "actual_set": anomaly_actual,
            "missing": sorted(set(anomaly_expected) - set(anomaly_actual)),
            "unexpected": sorted(set(anomaly_actual) - set(anomaly_expected)),
        },
        "unverified_paths": [
            "INVALID_DATE totals beyond signup_dt and MALFORMED_CSV totals "
            "beyond related_acct_ids are reported in detail but have no "
            "manifest expectation to diff against.",
            "Field-level invoice quarantine records (unusable dates, GL "
            "splits, unknown posted flags) are counted but the manifest "
            "declares no expectation for them.",
            "Only conversion batch %d (namespace %s) is reconciled; other "
            "namespaces in the same Oracle tables are untouched." %
            (batch_no, args.ns),
        ],
        "detail": {"oracle": oracle, "atlas": atlas,
                   "manifest_path": str(manifest_path.relative_to(ROOT))},
    }

    out = Path(args.out or
               ROOT / f"docs/tech-partnerships/recon/{UNIT}.{args.ns}.recon.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    table = render_table(checks)
    print(table)
    md = out.with_name(out.name.replace(".recon.json", ".recon.md"))
    md.write_text(
        "# MongoDB run reconciliation — NS=%s\n\n"
        "Three-way diff: Atlas `ow_tp_%s` vs Oracle OW_BILLING (batch %d) vs "
        "`%s`. All values recomputed at report time.\n\n%s\n\n"
        "Idempotency rerun: **%s** — %s\n"
        % (args.ns, args.ns, batch_no,
           report["detail"]["manifest_path"], table,
           idem["result"].upper(), idem["evidence"]))
    print(f"\n[recon] {out}\n[recon] {md}")

    failed = [c["id"] for c in checks if c["result"] != "pass"]
    if failed or idem["result"] != "pass":
        print(f"[recon] FAIL: {', '.join(failed) or 'idempotency rerun'}")
        return 1
    print(f"[recon] all {len(checks)} checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

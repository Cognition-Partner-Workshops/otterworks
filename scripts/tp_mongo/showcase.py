#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pymongo==4.10.1"]
# ///
"""Showcase the migrated OtterWorks MongoDB estate: enforced document contracts,
one-pipeline reporting, and the recon/failure loop.

Everything is namespace-scoped (`--ns`): databases are `ow_tp_mongodb_<ns>` and
`ow_tp_mongodb_<ns>_quarantine`. DDL (collMod) runs only on the named
namespace's own collections.

  validators     apply the $jsonSchema validators (collMod) to customers+invoices
  validate-demo  the stage moment: conforming writes land, contract violations
                 (a DD-MON-YY string date, a 156th ad-hoc field, a CSV blob)
                 are rejected by the database itself
  recon          recompute every baseline check from the target against the
                 seeder manifest; exit non-zero on any failure
  run-job        run recon and, on failure, POST {namespace, failing_checks,
                 run_url, base_branch} to the Devin automation webhook
  drift          stage a REAL failure in a rehearsal namespace (refuses the
                 persistent demo namespace): stale | corrupt | missing
  teardown       drop the namespace's databases (refuses demo) and verify absence

Credentials come from MONGODB_ATLAS_URI (or MONGODB_URI / --mongodb-uri); the
tool never prints the URI. The webhook secret comes only from the
OW_TP_MONGO_RECON_WEBHOOK_SECRET environment variable and is never printed.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from bson.decimal128 import Decimal128
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, WriteError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validators import VALIDATORS

REPO = Path(__file__).resolve().parents[2]
DB_PREFIX = "ow_tp_mongodb_"
PROBE_PREFIX = "showcase-probe"
SHOWCASE_DIR = REPO / "docs/tech-partnerships/showcase"
PERSISTENT_NS = "demo"
WEBHOOK_SECRET_ENV = "OW_TP_MONGO_RECON_WEBHOOK_SECRET"


def require_ns(ns: str) -> str:
    if not ns or not ns.replace("_", "").isalnum() or ns != ns.lower():
        raise SystemExit(f"--ns must be a lowercase identifier, got {ns!r}")
    return ns


def connect(args) -> MongoClient:
    uri = args.mongodb_uri or os.getenv("MONGODB_ATLAS_URI") or os.getenv("MONGODB_URI")
    if not uri:
        raise SystemExit("set MONGODB_ATLAS_URI (or MONGODB_URI, or pass --mongodb-uri)")
    return MongoClient(uri)


def database(client: MongoClient, ns: str):
    return client[f"{DB_PREFIX}{ns}"]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- validators --------------------------------------------------------------
def apply_validators(client: MongoClient, ns: str) -> None:
    """collMod the namespace's own collections only, after proving the entire
    existing population already satisfies the schema (a validator that the
    migrated data cannot pass would be a lie, not a contract)."""
    db = database(client, ns)
    existing = set(db.list_collection_names())
    missing = [name for name in VALIDATORS if name not in existing]
    if missing:
        raise SystemExit(
            f"{db.name} has no {', '.join(missing)} collection(s); "
            "migrate the namespace first, nothing collModded"
        )
    for name, schema in VALIDATORS.items():
        nonconforming = db[name].count_documents(
            {"$nor": [{"$jsonSchema": schema}]}, limit=1
        )
        if nonconforming:
            sample = db[name].find_one({"$nor": [{"$jsonSchema": schema}]}, {"_id": 1})
            sample_id = sample["_id"] if sample else "?"
            raise SystemExit(
                f"{name}: existing documents do not satisfy the proposed validator "
                f"(e.g. _id={sample_id!r}); refusing to collMod"
            )
    for name, schema in VALIDATORS.items():
        db.command(
            "collMod",
            name,
            validator={"$jsonSchema": schema},
            validationLevel="strict",
            validationAction="error",
        )
        print(f"validator applied: {db.name}.{name} (strict/error)")


def cmd_validators(client: MongoClient, args) -> int:
    apply_validators(client, args.ns)
    return 0


# --- validate-demo -----------------------------------------------------------
def conforming_customer(ns: str) -> dict:
    return {
        "_id": f"{ns}:{PROBE_PREFIX}:customer",
        "ns": ns,
        "tenant_id": "00000000-0000-0000-0000-00000000f00d",
        "cust_no": f"{ns.upper()}-99999901",
        "name": f"{ns}::showcase-probe",
        "legal_name": f"{ns}::showcase-probe LLC",
        "email": "billing@showcase-probe.example",
        "address": {"line1": "1 Contract Way", "city": "Fairview", "state": "TN", "zip": "37062"},
        "phones": [{"number": "615-555-0100", "type_cd": 1}],
        "status": {"status_cd": 1, "sub_status_cd": 1, "cust_type_cd": 1, "segment_cd": 1, "region_cd": 1},
        "flags": {"tax_exempt": False, "credit_hold": False, "vip": False},
        "balances": {"current": 0.0, "past_due": 0.0, "ytd_billed": 0.0, "credit_limit": 1000.0},
        "lineage": {"legacy_sys_key": "SHOWCASE", "created_by": "showcase", "row_version_no": 1},
        "signup_dt": datetime(2026, 2, 1, tzinfo=timezone.utc),
        "last_activity_dt": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "related_acct_ids": ["ACCT-0001", "ACCT-0002"],
        "promo_codes": ["WELCOME10"],
    }


def conforming_invoice(ns: str) -> dict:
    def line(no: int, amount: str) -> dict:
        return {
            "line_id": f"{ns}:{PROBE_PREFIX}:line:{no}",
            "line_no": Decimal128(str(no)),
            "line_type_cd": Decimal128("1"),
            "item_desc": "Showcase subscription",
            "qty": Decimal128("1"),
            "unit_price": Decimal128(amount),
            "amount": Decimal128(amount),
            "tax_amt": Decimal128("0.00"),
            "invoice_dt": "01-FEB-26",
            "service_period": "022026-022026",
            "src_system": "MAINFRAME",
            "posted_yn": "Y",
            "gl_accts": ["40001"],
            "cust_no": f"{ns.upper()}-99999901",
            "cust_name": f"{ns}::showcase-probe",
        }

    return {
        "_id": f"{ns}:{PROBE_PREFIX}:invoice",
        "ns": ns,
        "tenant_id": "00000000-0000-0000-0000-00000000f00d",
        "cust_id": f"{ns}:{PROBE_PREFIX}:customer",
        "invoice_no": f"{ns.upper()}-SHOWCASE-01",
        "invoice_dt": "01-FEB-26",
        "due_dt": "03-MAR-26",
        "status_cd": Decimal128("20"),
        "total_amt": Decimal128("49.00"),
        "batch_no": Decimal128("1"),
        "lines": [line(1, "49.00")],
    }


def probe_insert(collection, doc: dict, expect: str) -> dict:
    """Insert (and always clean up) one probe document; report what the
    database decided. expect is 'accept' or 'reject'."""
    outcome: dict = {"collection": collection.name, "_id": doc["_id"], "expected": expect}
    try:
        collection.insert_one(doc)
        outcome["result"] = "accepted"
    except DuplicateKeyError as exc:
        outcome["result"] = "error"
        outcome["code"] = exc.code
        outcome["error"] = "probe _id already present (leftover residue); not a validator rejection"
    except WriteError as exc:
        outcome["result"] = "rejected"
        outcome["code"] = exc.code
        details = (exc.details or {}).get("errInfo", {}).get("details", {})
        outcome["rule_violations"] = [
            rule.get("operatorName", "?")
            for rule in details.get("schemaRulesNotSatisfied", [])
        ]
        outcome["error"] = str((exc.details or {}).get("errmsg", exc))
    finally:
        if outcome.get("result") == "accepted":
            collection.delete_many({"_id": doc["_id"]})
    outcome["ok"] = (
        outcome["result"] == "accepted" if expect == "accept" else outcome["result"] == "rejected"
    )
    return outcome


def cmd_validate_demo(client: MongoClient, args) -> int:
    ns = args.ns
    db = database(client, ns)
    apply_validators(client, ns)

    probes: list[tuple[str, str, dict, str]] = []

    good_customer = conforming_customer(ns)
    probes.append(("conforming customer document", "customers", good_customer, "accept"))

    legacy_date = copy.deepcopy(good_customer)
    legacy_date["signup_dt"] = "03-FEB-09"
    probes.append((
        "legacy DD-MON-YY string where a BSON date is required",
        "customers", legacy_date, "reject",
    ))

    adhoc_field = copy.deepcopy(good_customer)
    adhoc_field["y2k_verified_flag_2"] = "Y"
    probes.append((
        "a 156th ad-hoc field (the legacy table would have taken it)",
        "customers", adhoc_field, "reject",
    ))

    csv_blob = copy.deepcopy(good_customer)
    csv_blob["related_acct_ids"] = "A1001,A1002,A1003"
    probes.append((
        "CSV blob where the contract demands an array",
        "customers", csv_blob, "reject",
    ))

    good_invoice = conforming_invoice(ns)
    probes.append(("conforming invoice with embedded lines", "invoices", good_invoice, "accept"))

    iso_date = copy.deepcopy(good_invoice)
    iso_date["invoice_dt"] = "2026-02-01"
    probes.append((
        "invoice date breaking the pinned legacy format",
        "invoices", iso_date, "reject",
    ))

    csv_line = copy.deepcopy(good_invoice)
    csv_line["lines"][0]["gl_acct_csv"] = "40001,40002"
    probes.append((
        "embedded line resurrecting the GL_ACCT_CSV column",
        "invoices", csv_line, "reject",
    ))

    results = []
    for title, coll, doc, expect in probes:
        outcome = probe_insert(db[coll], doc, expect)
        outcome["probe"] = title
        results.append(outcome)
        verdict = "OK " if outcome["ok"] else "FAIL"
        print(f"[{verdict}] {coll}: {title} -> {outcome['result']}"
              + (f" ({', '.join(outcome.get('rule_violations', []))})"
                 if outcome["result"] == "rejected" else ""))

    residue = sum(
        db[coll].count_documents({"_id": {"$regex": f":{PROBE_PREFIX}:"}})
        for coll in VALIDATORS
    )
    report = {
        "kind": "validator-demo",
        "namespace": ns,
        "generated_at": now(),
        "collections": {
            name: {
                "validation_level": "strict",
                "validation_action": "error",
                "required": VALIDATORS[name]["required"],
                "additional_properties": VALIDATORS[name]["additionalProperties"],
            }
            for name in VALIDATORS
        },
        "probes": results,
        "probe_residue_documents": residue,
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"report: {out}")
    failed = [r["probe"] for r in results if not r["ok"]]
    if failed:
        print(f"validate-demo FAILED probes: {failed}")
    if residue:
        print(f"validate-demo left {residue} probe documents behind (unexpected)")
    return 0 if not failed and not residue else 1


# --- recon -------------------------------------------------------------------
class FoldedChecksum:
    """Order-independent md5 sum (mirrors testdata/legacy/legacy_common.py)."""

    _MOD = 1 << 128

    def __init__(self) -> None:
        self._total = 0
        self.count = 0

    def add(self, line: str) -> None:
        digest = hashlib.md5(line.encode()).digest()
        self._total = (self._total + int.from_bytes(digest, "big")) % self._MOD
        self.count += 1

    def hexdigest(self) -> str:
        return f"{self._total:032x}"


def load_manifest(ns: str, path: str = "") -> dict:
    manifest_path = Path(path) if path else REPO / "testdata/legacy/manifests" / f"{ns}.json"
    if not manifest_path.exists():
        raise SystemExit(
            f"manifest not found: {manifest_path} "
            f"(run `make oracle-billing-seed NS={ns}` and `make seed-legacy NS={ns}`)"
        )
    return json.loads(manifest_path.read_text())


def recon_checks(client: MongoClient, ns: str, manifest: dict) -> list[dict]:
    """Recompute every baseline check from the target (never from migration-time
    memory), exactly as the per-unit recon reports do, against the seeder
    manifest as the source of truth."""
    db = database(client, ns)
    quarantine = client[f"{DB_PREFIX}{ns}_quarantine"]
    targets = manifest["targets"]
    checks: list[dict] = []

    def check(cid: str, expected, actual) -> None:
        checks.append({
            "id": cid,
            "expected": expected,
            "actual": actual,
            "result": "pass" if expected == actual else "fail",
        })

    # customers: ordered PK+balance checksum, folded EAV entries
    m_cust = targets["oracle.OW_BILLING.CUSTOMER_MASTER"]
    cust_ck = hashlib.md5()
    n_customers = n_eav = 0
    for doc in db["customers"].find({"ns": ns}, sort=[("_id", 1)]):
        n_customers += 1
        bal = doc.get("balances", {}).get("current")
        cust_ck.update(f"{doc['_id']}:{bal:.2f}\n".encode() if bal is not None
                       else f"{doc['_id']}:\n".encode())
        for entries in doc.get("attributes", {}).values():
            n_eav += len(entries)
    check("customers-count", m_cust["rows"], n_customers)
    check("customers-checksum", m_cust["checksum"], cust_ck.hexdigest())
    check("customers-eav-entries",
          targets["oracle.OW_BILLING.ENTITY_ATTR_VALUE"]["rows"], n_eav)

    # invoices: header count plus embedded+quarantined line checksum
    m_lines = targets["oracle.OW_BILLING.INVOICE_LINE"]
    pairs: list[tuple[str, str]] = []
    n_invoices = n_embedded = 0
    for doc in db["invoices"].find({"ns": ns}, {"lines.line_id": 1, "lines.amount": 1}):
        n_invoices += 1
        for line in doc.get("lines", []):
            n_embedded += 1
            pairs.append((line["line_id"], f"{line['amount'].to_decimal():.2f}"))
    n_quarantined = 0
    for doc in quarantine["invoice_lines_quarantine"].find({"ns": ns}, {"amount": 1}):
        n_quarantined += 1
        amount = doc.get("amount")
        pairs.append((doc["_id"],
                      f"{amount.to_decimal():.2f}" if amount is not None else "None"))
    lines_ck = hashlib.md5()
    for pk, amt in sorted(pairs):
        lines_ck.update(f"{pk}:{amt}\n".encode())
    check("invoices-count", targets["oracle.OW_BILLING.INVOICE_HEADER"]["rows"], n_invoices)
    check("invoice-lines-total", m_lines["rows"], n_embedded + n_quarantined)
    check("invoice-lines-checksum", m_lines["checksum"], lines_ck.hexdigest())

    # documents: count and embedded versions
    n_documents = n_versions = 0
    for doc in db["documents"].find({"ns": ns}, {"versions.version_number": 1}):
        n_documents += 1
        n_versions += len(doc.get("versions", []))
    check("documents-count", targets[f"postgres.otterworks_{ns}.documents"]["rows"], n_documents)
    check("document-versions-embedded",
          targets[f"postgres.otterworks_{ns}.document_versions"]["rows"], n_versions)

    # files: order-independent id|size|key checksum (files are tenant-scoped)
    m_files = targets["dynamodb.file-metadata"]
    files_ck = FoldedChecksum()
    for doc in db["files"].find({"tenant": ns}, {"_id": 1, "size_bytes": 1, "s3_key": 1}):
        files_ck.add(f"{doc['_id']}|{doc.get('size_bytes')}|{doc.get('s3_key')}")
    check("files-count", m_files["items"], files_ck.count)
    check("files-checksum", m_files["checksum"], files_ck.hexdigest())

    # contracts: the Unit A validators are still enforced
    enforced = sorted(
        info["name"]
        for info in db.list_collections()
        if info["name"] in VALIDATORS
        and "$jsonSchema" in info.get("options", {}).get("validator", {})
        and info["options"].get("validationAction") == "error"
    )
    check("validators-enforced", sorted(VALIDATORS), enforced)
    return checks


def run_recon(client: MongoClient, args) -> tuple[list[dict], list[str]]:
    ns = args.ns
    checks = recon_checks(client, ns, load_manifest(ns, args.manifest))
    failing = [c["id"] for c in checks if c["result"] == "fail"]
    width = max(len(c["id"]) for c in checks)
    for c in checks:
        print(f"[{'PASS' if c['result'] == 'pass' else 'FAIL'}] {c['id']:<{width}} "
              f"expected={c['expected']} actual={c['actual']}")
    print(f"recon {ns}: {'GREEN' if not failing else 'FAILED'}"
          + (f" failing_checks={failing}" if failing else f" ({len(checks)} checks)"))
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "kind": "showcase-recon",
            "namespace": ns,
            "generated_at": now(),
            "values_recomputed_from_target": True,
            "checks": checks,
            "failing_checks": failing,
            "result": "pass" if not failing else "fail",
        }, indent=2, sort_keys=True) + "\n")
        print(f"recon report: {out}")
    return checks, failing


def cmd_recon(client: MongoClient, args) -> int:
    _, failing = run_recon(client, args)
    return 0 if not failing else 1


def current_branch() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def cmd_run_job(client: MongoClient, args) -> int:
    """The hand-triggered wrapper: recon, and on failure notify the Devin
    automation webhook. Green runs never fire the webhook."""
    _, failing = run_recon(client, args)
    if not failing:
        print("run-job: recon green, webhook not fired")
        return 0

    if not args.webhook_url:
        raise SystemExit("recon FAILED but no --webhook-url "
                         "(or OW_TP_MONGO_RECON_WEBHOOK_URL) configured")
    secret = os.environ.get(WEBHOOK_SECRET_ENV, "")
    if not secret:
        raise SystemExit(f"recon FAILED but {WEBHOOK_SECRET_ENV} is not set; "
                         "webhook not fired")
    payload = {
        "namespace": args.ns,
        "failing_checks": failing,
        "run_url": args.run_url,
        "base_branch": args.base_branch or current_branch(),
    }
    print(f"run-job: recon FAILED, notifying Devin automation: {json.dumps(payload)}")
    request = urllib.request.Request(
        args.webhook_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Webhook-Secret": secret},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"run-job: webhook fired ({response.status})")
    return 1


# --- drift (rehearsal namespaces only) ----------------------------------------
def require_rehearsal(client: MongoClient, ns: str) -> None:
    if ns == PERSISTENT_NS:
        raise SystemExit(f"refusing: {PERSISTENT_NS!r} is the persistent showcase "
                         "namespace; stage drift in a rehearsal namespace")
    if f"{DB_PREFIX}{ns}" not in client.list_database_names():
        raise SystemExit(f"{DB_PREFIX}{ns} does not exist; migrate the rehearsal "
                         "namespace first")


def cmd_drift(client: MongoClient, args) -> int:
    """Stage a REAL failure: genuinely drifted data that a recomputed recon
    check must catch. Never a hard-coded error, never the demo namespace."""
    require_rehearsal(client, args.ns)
    ns = args.ns
    db = database(client, ns)
    if args.kind == "stale":
        victims = [d["_id"] for d in db["invoices"]
                   .find({"ns": ns}, {"_id": 1}).sort("_id", -1).limit(args.n)]
        result = db["invoices"].delete_many({"_id": {"$in": victims}})
        print(f"drift(stale): deleted {result.deleted_count} invoices from "
              f"{db.name}.invoices (as if a load never ran)")
    elif args.kind == "corrupt":
        victims = [d["_id"] for d in db["customers"]
                   .find({"ns": ns}, {"_id": 1}).sort("_id", 1).limit(args.n)]
        result = db["customers"].update_many(
            {"_id": {"$in": victims}}, {"$inc": {"balances.current": 0.01}})
        print(f"drift(corrupt): shifted balances.current by 0.01 on "
              f"{result.modified_count} customers (schema-valid, checksum-breaking)")
    else:  # missing
        db["documents"].drop()
        print(f"drift(missing): dropped {db.name}.documents entirely")
    print("stage the proof with: run-job (recon must fail on recomputed checks)")
    return 0


# --- teardown ------------------------------------------------------------------
def cmd_teardown(client: MongoClient, args) -> int:
    ns = args.ns
    if ns == PERSISTENT_NS:
        raise SystemExit(f"refusing: {PERSISTENT_NS!r} is the persistent showcase "
                         "namespace and is never torn down")
    names = [f"{DB_PREFIX}{ns}", f"{DB_PREFIX}{ns}_quarantine"]
    for name in names:
        client.drop_database(name)
        print(f"dropped {name}")
    residue = [n for n in client.list_database_names() if n in names]
    if residue:
        print(f"teardown FAILED, still present: {residue}")
        return 1
    print(f"teardown verified: {', '.join(names)} absent")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ns", default="demo")
    parser.add_argument("--mongodb-uri", default="")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validators")
    demo = sub.add_parser("validate-demo")
    demo.add_argument("--out", default="")

    recon = sub.add_parser("recon")
    run_job = sub.add_parser("run-job")
    for p in (recon, run_job):
        p.add_argument("--manifest", default="")
        p.add_argument("--out", default="")
    run_job.add_argument("--webhook-url",
                         default=os.environ.get("OW_TP_MONGO_RECON_WEBHOOK_URL", ""))
    run_job.add_argument("--run-url", required=True,
                         help="URL identifying this run (workflow run, artifact, or log)")
    run_job.add_argument("--base-branch", default="",
                         help="base branch for the remediation PR (default: current branch)")

    drift = sub.add_parser("drift")
    drift.add_argument("--kind", required=True, choices=["stale", "corrupt", "missing"])
    drift.add_argument("--n", type=int, default=250,
                       help="documents to delete/corrupt for stale/corrupt drift")

    sub.add_parser("teardown")

    args = parser.parse_args()
    args.ns = require_ns(args.ns)
    commands = {
        "validators": cmd_validators,
        "validate-demo": cmd_validate_demo,
        "recon": cmd_recon,
        "run-job": cmd_run_job,
        "drift": cmd_drift,
        "teardown": cmd_teardown,
    }
    return commands[args.command](connect(args), args)


if __name__ == "__main__":
    raise SystemExit(main())

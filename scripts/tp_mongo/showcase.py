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
  report         the legacy month-end finance rollup as ONE aggregation
                 pipeline over the invoices collection (embedded lines: group
                 and unwind, no joins), asserted equal to the legacy golden
                 report to the cent; --emit-golden regenerates the golden file
                 from the seeded Oracle fixture

Credentials come from MONGODB_ATLAS_URI (or MONGODB_URI / --mongodb-uri); the
tool never prints the URI.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from decimal import Decimal
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

# the CODES rows and inline DECODE the legacy report resolves its magic
# numbers through (scripts/tp_mongo/legacy_finance_report.sql)
INV_STATUS = {10: "draft", 20: "issued", 30: "paid", 40: "overdue"}
LINE_TYPE = {1: "CHARGE", 2: "CREDIT", 3: "ADJUSTMENT", 9: "MISC"}


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


# --- report ------------------------------------------------------------------
def cents(value) -> str:
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    return str(Decimal(value).quantize(Decimal("0.01")))


def ns_batch_no(ns: str) -> int:
    """The namespace's deterministic batch number in the shared Oracle fixture
    (same derivation as migrations/mongodb/invoices/migrate.py)."""
    return int(hashlib.sha256(ns.encode()).hexdigest()[:8], 16) % 90_000_000 + 1_000_000


def legacy_finance_report(container: str, ns: str) -> dict:
    """Run the committed legacy SQL (scripts/tp_mongo/legacy_finance_report.sql)
    against the seeded Oracle fixture, scoped to the namespace's batch_no, and
    parse its CSV sections."""
    sql = (
        f"DEFINE batch_no = {ns_batch_no(ns)}\n".encode()
        + (REPO / "scripts/tp_mongo/legacy_finance_report.sql").read_bytes()
    )
    proc = subprocess.run(
        [
            "docker", "exec", "-i", container, "bash", "-c",
            "sqlplus -s ow_billing/ow_billing@localhost:1521/FREEPDB1",
        ],
        input=sql,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"legacy report failed (sqlplus exit {proc.returncode}): "
            f"{(proc.stdout.decode().strip() or proc.stderr.decode().strip())[-500:]}"
        )
    by_status: dict[str, dict] = {}
    by_status_line_type: dict[str, dict] = {}
    section = ""
    for raw in proc.stdout.decode().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in ("SECTION1", "SECTION2"):
            section = line
            continue
        if line.startswith("STATUS_DESC"):
            continue
        parts = line.split(",")
        if section == "SECTION1":
            if len(parts) != 3:
                raise SystemExit(f"unexpected legacy report output: {line!r}")
            status, count, total = parts
            by_status[status] = {
                "invoice_count": int(count),
                "header_total_amt": cents(total),
            }
        elif section == "SECTION2":
            if len(parts) != 6:
                raise SystemExit(f"unexpected legacy report output: {line!r}")
            status, line_type, count, amount, tax, touched = parts
            by_status_line_type[f"{status}|{line_type}"] = {
                "line_count": int(count),
                "line_amount": cents(amount),
                "line_tax": cents(tax),
                "invoices_touched": int(touched),
            }
    if not by_status or not by_status_line_type:
        raise SystemExit(
            "legacy report returned no rows; is the Oracle fixture seeded? "
            f"(stderr: {proc.stderr.decode().strip()[:500]})"
        )
    return {"by_status": by_status, "by_status_line_type": by_status_line_type}


def decode(field: str, mapping: dict[int, str]) -> dict:
    """The CODES join / inline DECODE of the legacy report as a $switch."""
    return {
        "$switch": {
            "branches": [
                {"case": {"$eq": [field, code]}, "then": name}
                for code, name in mapping.items()
            ],
            "default": {"$concat": ["UNKNOWN(", {"$toString": field}, ")"]},
        }
    }


def finance_pipeline(ns: str) -> list[dict]:
    """The whole legacy month-end finance rollup as ONE aggregation pipeline:
    embedded lines mean group-and-unwind, no joins, and the 37 orphaned legacy
    lines are absent by construction (they live in quarantine, not here)."""
    return [
        {"$match": {"ns": ns}},
        {"$addFields": {"status_desc": decode("$status_cd", INV_STATUS)}},
        {"$facet": {
            "by_status": [
                {"$group": {
                    "_id": "$status_desc",
                    "invoice_count": {"$sum": 1},
                    "header_total_amt": {"$sum": "$total_amt"},
                }},
                {"$sort": {"_id": 1}},
            ],
            "by_status_line_type": [
                {"$unwind": "$lines"},
                {"$group": {
                    "_id": {
                        "status": "$status_desc",
                        "line_type": decode("$lines.line_type_cd", LINE_TYPE),
                    },
                    "line_count": {"$sum": 1},
                    "line_amount": {"$sum": "$lines.amount"},
                    "line_tax": {"$sum": "$lines.tax_amt"},
                    "invoice_ids": {"$addToSet": "$_id"},
                }},
                {"$addFields": {"invoices_touched": {"$size": "$invoice_ids"}}},
                {"$project": {"invoice_ids": 0}},
                {"$sort": {"_id.status": 1, "_id.line_type": 1}},
            ],
        }},
    ]


def mongo_finance_report(client: MongoClient, ns: str) -> dict:
    [facets] = list(database(client, ns)["invoices"].aggregate(finance_pipeline(ns)))
    by_status = {
        row["_id"]: {
            "invoice_count": row["invoice_count"],
            "header_total_amt": cents(row["header_total_amt"]),
        }
        for row in facets["by_status"]
    }
    by_status_line_type = {
        f"{row['_id']['status']}|{row['_id']['line_type']}": {
            "line_count": row["line_count"],
            "line_amount": cents(row["line_amount"]),
            "line_tax": cents(row["line_tax"]),
            "invoices_touched": row["invoices_touched"],
        }
        for row in facets["by_status_line_type"]
    }
    return {"by_status": by_status, "by_status_line_type": by_status_line_type}


def diff_reports(golden: dict, live: dict) -> list[str]:
    mismatches = []
    for section in ("by_status", "by_status_line_type"):
        g, l = golden[section], live[section]
        for key in sorted(set(g) | set(l)):
            if key not in l:
                mismatches.append(f"{section}[{key}]: missing from aggregation")
            elif key not in g:
                mismatches.append(f"{section}[{key}]: absent from legacy golden")
            elif g[key] != l[key]:
                mismatches.append(f"{section}[{key}]: legacy={g[key]} mongo={l[key]}")
    return mismatches


def cmd_report(client: MongoClient, args) -> int:
    ns = args.ns
    golden_path = Path(args.golden or SHOWCASE_DIR / f"finance_report.{ns}.golden.json")

    if args.emit_golden:
        golden = {
            "kind": "finance-report-golden",
            "namespace": ns,
            "generated_at": now(),
            "source": {
                "sql": "scripts/tp_mongo/legacy_finance_report.sql",
                "store": "oracle invoice_header/invoice_line/codes",
                "container": args.oracle_container,
            },
            "report": legacy_finance_report(args.oracle_container, ns),
        }
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(json.dumps(golden, indent=2, sort_keys=True) + "\n")
        print(f"golden: {golden_path}")
        return 0

    if not golden_path.exists():
        raise SystemExit(f"golden baseline not found: {golden_path} (run report --emit-golden)")
    golden = json.loads(golden_path.read_text())["report"]
    live = mongo_finance_report(client, ns)
    mismatches = diff_reports(golden, live)

    print(f"{'STATUS':<10} {'LINE_TYPE':<12} {'LINES':>7} {'AMOUNT':>16} {'TAX':>14}")
    for key, row in sorted(live["by_status_line_type"].items()):
        status, line_type = key.split("|")
        print(f"{status:<10} {line_type:<12} {row['line_count']:>7} "
              f"{row['line_amount']:>16} {row['line_tax']:>14}")
    verdict = "MATCH to the cent" if not mismatches else f"{len(mismatches)} MISMATCHES"
    print(f"aggregation vs legacy golden: {verdict}")
    for m in mismatches:
        print(f"  {m}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "kind": "finance-report-comparison",
            "namespace": ns,
            "generated_at": now(),
            "golden_baseline": str(golden_path.relative_to(REPO)) if golden_path.is_relative_to(REPO) else str(golden_path),
            "pipeline": "scripts/tp_mongo/showcase.py finance_pipeline (one aggregation, $facet group+unwind)",
            "legacy": golden,
            "mongodb": live,
            "mismatches": mismatches,
            "match": not mismatches,
        }, indent=2, sort_keys=True) + "\n")
        print(f"report: {out}")
    return 0 if not mismatches else 1


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
    report = sub.add_parser("report")
    report.add_argument("--out", default="")
    report.add_argument("--golden", default="")
    report.add_argument("--emit-golden", action="store_true")
    report.add_argument(
        "--oracle-container",
        default="otterworks-oracle-billing-oracle-billing-1",
    )

    args = parser.parse_args()
    args.ns = require_ns(args.ns)
    commands = {
        "validators": cmd_validators,
        "validate-demo": cmd_validate_demo,
        "report": cmd_report,
    }
    needs_mongo = not (args.command == "report" and args.emit_golden)
    return commands[args.command](connect(args) if needs_mongo else None, args)


if __name__ == "__main__":
    raise SystemExit(main())

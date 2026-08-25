"""RPT-114 month-end finance report, rebuilt over the migrated invoices.

The legacy report (``services/legacy-billing/app/reports.py``) is three Oracle
queries against ``INVOICE_HEADER``, ``INVOICE_LINE`` and the generic ``CODES``
lookup, joined with ``(+)`` outer-join syntax. The migrated estate embeds the
lines in the invoice document and folds the balances into the customer
document, so the same report is one aggregation per collection with no joins at
all: ``$unwind`` replaces the header/line join and a ``$switch`` built from the
``CODES`` rows replaces the lookup join.

Legacy semantics are contractual (see
``docs/tech-partnerships/billing-report-contract.md``): unmapped status codes
render as ``UNKNOWN(<cd>)``, line types are decoded inline, orphaned lines fall
out of the report because they are not embedded in any invoice, and amounts are
strings with exactly two decimals.

This module is the single implementation of the report: the service serves it
from here and the migration's reconciliation tool
(``scripts/tp_mongo/showcase.py``) imports the same functions, so recon proves
parity for exactly the code the app runs. It therefore depends on nothing but
``pymongo``/``bson``.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal
from typing import Any

from bson.decimal128 import Decimal128

# CODES('INV_STATUS') as seeded by services/legacy-billing/db/oracle/schema/01_tables.sql.
INV_STATUS: dict[int, str] = {10: "draft", 20: "issued", 30: "paid", 40: "overdue"}

# The DECODE(l.line_type_cd, ...) branches spelled out in LINE_SQL.
LINE_TYPES: dict[int, str] = {1: "CHARGE", 2: "CREDIT", 3: "ADJUSTMENT", 9: "MISC"}

INVOICES = "invoices"
CUSTOMERS = "customers"
# Written by `scripts/tp_mongo/showcase.py --ns <ns> baseline`: the golden legacy
# report and the counts the namespace was signed off green with.
BASELINE_COLLECTION = "tp_showcase_baseline"
BASELINE_ID = "showcase-baseline"
ESTATE_DB_PREFIX = "ow_tp_mongodb"
NS_RE = re.compile(r"[a-z][a-z0-9_]{0,30}")


def estate_database_name(ns: str, prefix: str = ESTATE_DB_PREFIX) -> str:
    """The migrated namespace's database, mirroring the migration units."""
    if not NS_RE.fullmatch(ns):
        raise ValueError(f"invalid namespace: {ns!r}")
    return f"{prefix}_{ns}"


def batch_no(ns: str) -> int:
    """Deterministic conversion batch number for a namespace.

    Mirrors testdata/legacy/legacy_common.ns_seed and the legacy app's
    reports.ns_batch_no: sha256(ns)[:8] folded into the NUMBER(8) batch range.
    """
    seed = int(hashlib.sha256(ns.encode()).hexdigest()[:8], 16)
    return seed % 90_000_000 + 1_000_000


def _unknown(field: str) -> dict:
    # Oracle renders an unmapped code as UNKNOWN(<cd>); TO_CHAR(NULL) is empty.
    return {"$concat": ["UNKNOWN(", {"$ifNull": [{"$toString": field}, ""]}, ")"]}


def _decode(field: str, codes: dict[int, str]) -> dict:
    return {
        "$switch": {
            "branches": [
                {"case": {"$eq": [field, code]}, "then": desc}
                for code, desc in sorted(codes.items())
            ],
            "default": _unknown(field),
        }
    }


def month_end_pipeline(ns: str) -> list[dict]:
    """One pipeline for the whole RPT-114 rollup.

    ``$facet`` runs the header rollup and the line rollup over the same matched
    documents, so the report is a single pass over one collection where the
    legacy report needed two queries and a three-table join.
    """
    return [
        {"$match": {"ns": ns, "source.batch_no": batch_no(ns)}},
        {
            "$facet": {
                "by_status": [
                    {
                        "$group": {
                            "_id": _decode("$status_code", INV_STATUS),
                            "invoice_count": {"$sum": 1},
                            "header_total_amt": {"$sum": "$header_total"},
                            # SUM() of an all-NULL group is NULL, not zero
                            "header_totals_present": {
                                "$sum": {
                                    "$cond": [{"$gt": ["$header_total", None]}, 1, 0]
                                }
                            },
                        }
                    },
                    {"$sort": {"_id": 1}},
                ],
                "by_status_line_type": [
                    {"$unwind": "$lines"},
                    {
                        "$group": {
                            "_id": {
                                "status": _decode("$status_code", INV_STATUS),
                                "line_type": _decode(
                                    "$lines.line_type_code", LINE_TYPES
                                ),
                            },
                            "line_count": {"$sum": 1},
                            "line_amount": {"$sum": "$lines.amount"},
                            "line_tax": {"$sum": "$lines.tax_amt"},
                            "invoices": {"$addToSet": "$_id"},
                        }
                    },
                    {
                        "$project": {
                            "line_count": 1,
                            "line_amount": 1,
                            "line_tax": 1,
                            "invoices_touched": {"$size": "$invoices"},
                        }
                    },
                    {"$sort": {"_id.status": 1, "_id.line_type": 1}},
                ],
            }
        },
    ]


def balances_pipeline(ns: str) -> list[dict]:
    """The BALANCES_SQL rollup over the folded customer balances."""
    return [
        {"$match": {"namespace": ns, "source.batch_no": batch_no(ns)}},
        {
            "$group": {
                "_id": None,
                "customer_count": {"$sum": 1},
                "current_balance_total": {"$sum": "$balances.current_amount"},
                "past_due_total": {"$sum": "$balances.past_due_amount"},
            }
        },
    ]


def money(value: Any) -> str | None:
    """The estate's canonical two-decimal money rendering (FM...0.00)."""
    if value is None:
        return None
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    return f"{Decimal(value):.2f}"


def shape_month_end(facet: dict) -> dict[str, list[dict]]:
    """Turn the pipeline's output into the contract's JSON rows."""
    by_status = [
        {
            "status": row["_id"],
            "invoice_count": row["invoice_count"],
            "header_total_amt": (
                money(row["header_total_amt"]) if row["header_totals_present"] else None
            ),
        }
        for row in facet["by_status"]
    ]
    by_status_line_type = [
        {
            "status": row["_id"]["status"],
            "line_type": row["_id"]["line_type"],
            "line_count": row["line_count"],
            "line_amount": money(row["line_amount"]),
            "line_tax": money(row["line_tax"]),
            "invoices_touched": row["invoices_touched"],
        }
        for row in facet["by_status_line_type"]
    ]
    return {"by_status": by_status, "by_status_line_type": by_status_line_type}


def shape_balances(rows: list[dict]) -> dict:
    if not rows:
        return {
            "customer_count": 0,
            "current_balance_total": None,
            "past_due_total": None,
        }
    row = rows[0]
    return {
        "customer_count": row["customer_count"],
        "current_balance_total": money(row["current_balance_total"]),
        "past_due_total": money(row["past_due_total"]),
    }


def month_end(database, ns: str) -> dict[str, list[dict]]:
    facet = next(
        iter(
            database[INVOICES].aggregate(month_end_pipeline(ns), allowDiskUse=True)
        )
    )
    return shape_month_end(facet)


def balances(database, ns: str) -> dict:
    return shape_balances(
        list(database[CUSTOMERS].aggregate(balances_pipeline(ns), allowDiskUse=True))
    )


SOURCE = {
    "engine": "mongodb",
    "system": "migrated document store (MongoDB)",
    "detail": "one aggregation pipeline over invoices with embedded lines "
              "(RPT-114 equivalent)",
}


def month_end_report(database, ns: str) -> dict:
    """The `/api/reports/month-end` body, served from the document store."""
    return {
        "report": "month-end-finance",
        "namespace": ns,
        "batch_no": batch_no(ns),
        "source": dict(SOURCE),
        **month_end(database, ns),
    }


def report_diff(golden: dict, actual: dict) -> list[dict]:
    """Row-level differences between two RPT-114 report bodies."""
    diffs = []
    for section, key in (
        ("by_status", ("status",)),
        ("by_status_line_type", ("status", "line_type")),
    ):
        left = {tuple(row[k] for k in key): row for row in golden.get(section) or []}
        right = {tuple(row[k] for k in key): row for row in actual.get(section) or []}
        for row_key in sorted(set(left) | set(right)):
            if left.get(row_key) != right.get(row_key):
                diffs.append({
                    "section": section,
                    "key": list(row_key),
                    "legacy": left.get(row_key),
                    "mongodb": right.get(row_key),
                })
    return diffs


def read_baseline(database) -> dict | None:
    """The golden before-state stored in the namespace by the showcase tool."""
    return database[BASELINE_COLLECTION].find_one({"_id": BASELINE_ID})


def embedded_line_integrity(database, ns: str) -> dict:
    """Invoices whose embedded lines disagree with their own rollups.

    The legacy estate could not express this: the totals lived on the header row
    and the lines lived in another table, so nothing checked them against each
    other. Here it is one aggregation over the document itself.
    """
    pipeline = [
        {"$match": {"ns": ns}},
        {
            "$project": {
                "count_mismatch": {
                    "$ne": [{"$size": {"$ifNull": ["$lines", []]}}, "$lines_count"]
                },
                "total_mismatch": {
                    "$ne": [
                        {"$sum": "$lines.amount"},
                        {"$ifNull": ["$lines_total", {"$literal": 0}]},
                    ]
                },
                "tax_mismatch": {
                    "$ne": [
                        {"$sum": "$lines.tax_amt"},
                        {"$ifNull": ["$lines_tax_total", {"$literal": 0}]},
                    ]
                },
            }
        },
        {
            "$group": {
                "_id": None,
                "count_mismatch": {"$sum": {"$cond": ["$count_mismatch", 1, 0]}},
                "total_mismatch": {"$sum": {"$cond": ["$total_mismatch", 1, 0]}},
                "tax_mismatch": {"$sum": {"$cond": ["$tax_mismatch", 1, 0]}},
            }
        },
    ]
    rows = list(database[INVOICES].aggregate(pipeline, allowDiskUse=True))
    if not rows:
        return {"count_mismatch": 0, "total_mismatch": 0, "tax_mismatch": 0}
    row = rows[0]
    return {key: row[key] for key in
            ("count_mismatch", "total_mismatch", "tax_mismatch")}


def non_decimal_money(database, ns: str) -> int:
    """Embedded money and quantity fields not stored as decimal128."""
    pipeline = [
        {"$match": {"ns": ns}},
        {"$unwind": "$lines"},
        {
            "$project": {
                "bad": {
                    "$size": {
                        "$filter": {
                            "input": [
                                {"$type": "$lines.amount"},
                                {"$type": "$lines.tax_amt"},
                                {"$type": "$lines.qty"},
                                {"$type": "$lines.unit_price"},
                            ],
                            "cond": {"$ne": ["$$this", "decimal"]},
                        }
                    }
                }
            }
        },
        {"$group": {"_id": None, "bad": {"$sum": "$bad"}}},
    ]
    rows = list(database[INVOICES].aggregate(pipeline, allowDiskUse=True))
    return rows[0]["bad"] if rows else 0


def validators_applied(database) -> dict[str, bool]:
    """`$jsonSchema` presence read back from the collections' own options."""
    present = {CUSTOMERS: False, INVOICES: False}
    for info in database.list_collections(filter={"name": {"$in": list(present)}}):
        validator = (info.get("options") or {}).get("validator") or {}
        present[info["name"]] = "$jsonSchema" in validator
    return present


def _check(name: str, expected, actual) -> dict:
    check: dict[str, Any] = {
        "name": name,
        "status": "pass" if expected == actual else "fail",
    }
    if check["status"] == "fail":
        check["expected"] = expected
        check["actual"] = actual
    return check


def reconciliation_report(database, ns: str) -> dict:
    """The `/api/reports/reconciliation` body for the migrated backend.

    Contract-shaped checks (`docs/tech-partnerships/billing-report-contract.md`):
    document-level invariants the legacy estate could not express, plus parity
    against the golden legacy report when this namespace carries a showcase
    baseline document.
    """
    current = month_end_report(database, ns)
    balance_totals = balances(database, ns)
    integrity = embedded_line_integrity(database, ns)
    checks = [
        _check("embedded-lines-count", 0, integrity["count_mismatch"]),
        _check("embedded-lines-total", 0, integrity["total_mismatch"]),
        _check("embedded-lines-tax", 0, integrity["tax_mismatch"]),
        _check("money-bson-type", 0, non_decimal_money(database, ns)),
        _check("validators-applied", {CUSTOMERS: True, INVOICES: True},
               validators_applied(database)),
    ]
    baseline = read_baseline(database)
    if baseline:
        golden = baseline["legacy_report"]
        checks.append(_check("report-golden-parity", [],
                             report_diff(golden, current)[:10]))
        checks.append(_check("balances-golden-parity", golden["balances"],
                             balance_totals))
        checks.append(_check("invoice-count", baseline["counts"][INVOICES],
                             database[INVOICES].count_documents({"ns": ns})))
        checks.append(_check("customer-count", baseline["counts"][CUSTOMERS],
                             database[CUSTOMERS].count_documents({"namespace": ns})))
    else:
        checks.append({
            "name": "report-golden-parity",
            "status": "skipped",
            "detail": "no showcase baseline document in this namespace; run "
                      "`scripts/tp_mongo/showcase.py --ns <ns> baseline`",
        })
    failing = [check["name"] for check in checks if check["status"] == "fail"]
    return {
        "namespace": ns,
        "batch_no": batch_no(ns),
        "source": dict(SOURCE),
        "balances": balance_totals,
        "status": "fail" if failing else "pass",
        "checks": checks,
    }

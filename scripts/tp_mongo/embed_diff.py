"""Embedded-child verification for the wave: every child field, every child row.

The harness grades embeds by cardinality only — `EmbedMapping` carries `child_table` and
`child_where`, so Tier 1 counts array elements against child rows and Tier 3's keyed diff
compares the root document's mapped fields. Nothing in the approved mapping contract states a
child field, so no tier compares one. Tier 4 sees lines only through the month-end report's
grouped totals and never reads `attributes[]` at all.

That is a gap in the *evidence*, not a harness defect (raised as H4 in the census), and it is
not closed by widening a tolerance or editing a verdict. This runner closes it the only way
available without a mapping version bump: it re-reads both sides independently and compares
every embedded child field, positionally, keyed by the child's own identity.

What it proves: no embedded child row is missing, extra, misattributed to another parent,
reordered, or altered field by field between the estate and Atlas.

What it does not prove: that the *choice* of child field mapping is right. It reproduces the
loader's declared child shape, because that shape is the only statement of it that exists —
STOP B approved the embeds by cardinality. A wrong target path or BSON type for a child field
is a STOP B question, not something this can catch.

Read-only on both sides.

    python3 scripts/tp_mongo/embed_diff.py --ns demo \
        --source-dsn-secret OW_BILLING_SOURCE_DSN --target-uri-secret MONGODB_ATLAS_URI \
        --target-db ow_tp_demo --out .migration/recon/wave/embeds/
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from bson.decimal128 import Decimal128

from common import (
    CONVENTIONS,
    assert_designated_cluster,
    canonical,
    mongo_database,
    ns_batch_no,
    oracle_connect,
)
from customers_load import EAV_TABLE
from customers_load import ROOT_TABLE as CUSTOMER_TABLE
from invoices_load import LINE_FIELDS, LINE_RULES, LINE_TABLE
from invoices_load import ROOT_TABLE as INVOICE_TABLE

MAX_REPORTED = 20


def comparable(value):
    """One value in a form two sides can be compared by equality.

    Decimal128 compares by its own decimal value rather than its string form, so a rescaled
    but equal amount is equal; a datetime is compared in UTC.
    """
    if isinstance(value, Decimal128):
        return ("decimal", value.to_decimal())
    if isinstance(value, dt.datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
        return ("datetime", moment.astimezone(dt.timezone.utc))
    return (type(value).__name__, value)


def diff_children(expected: dict[str, list[dict]], actual: dict[str, list[dict]],
                  array_path: str, identity: str) -> list[dict]:
    """Compare each parent's child array element by element, in order.

    Both sides are keyed by parent, so a child attached to the wrong parent shows up twice —
    missing from one array, extra in the other — rather than cancelling out.
    """
    findings: list[dict] = []
    for parent in sorted(set(expected) | set(actual)):
        want, got = expected.get(parent, []), actual.get(parent, [])
        if len(want) != len(got):
            findings.append({"parent": parent, "kind": "child_count",
                             "array_path": array_path,
                             "expected": len(want), "actual": len(got)})
            continue
        for position, (want_child, got_child) in enumerate(zip(want, got)):
            if want_child.get(identity) != got_child.get(identity):
                findings.append({"parent": parent, "kind": "child_order_or_identity",
                                 "array_path": array_path, "position": position,
                                 "expected": str(want_child.get(identity)),
                                 "actual": str(got_child.get(identity))})
                continue
            for field in sorted(set(want_child) | set(got_child)):
                want_value, got_value = want_child.get(field), got_child.get(field)
                if comparable(want_value) != comparable(got_value):
                    findings.append({
                        "parent": parent, "kind": "child_field_diff",
                        "array_path": f"{array_path}.{field}",
                        "child": str(want_child.get(identity)),
                        "expected": str(want_value), "actual": str(got_value)})
    return findings


def flatten(document: dict, prefix: str = "") -> dict:
    """A child document as `dotted.path -> value`, so a nested `legacy.*` value is compared
    rather than compared as an opaque dict."""
    flat: dict = {}
    for key, value in document.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


def source_lines(cursor, batch_no: int) -> dict[str, list[dict]]:
    """Every in-scope invoice line, converted to the shape the loader states, keyed by header.

    Orphans are excluded by the same `EXISTS` the loader uses: they are quarantined whole, so
    they belong to no array.
    """
    columns = [column for column, _, _ in LINE_FIELDS]
    cursor.execute(
        f"SELECT l.INVOICE_ID, {', '.join('l.' + c for c in columns)} "
        f"  FROM {LINE_TABLE} l "
        f" WHERE l.BATCH_NO = :b "
        f"   AND EXISTS (SELECT 1 FROM {INVOICE_TABLE} h "
        f"                WHERE h.INVOICE_ID = l.INVOICE_ID AND h.BATCH_NO = :b) "
        f" ORDER BY l.INVOICE_ID, l.LINE_ID", b=batch_no)

    by_invoice: dict[str, list[dict]] = {}
    for row in cursor:
        record = dict(zip(["INVOICE_ID"] + columns, row))
        child = {target: canonical(record[column], bson_type, LINE_RULES.get(column, []))
                 for column, target, bson_type in LINE_FIELDS}
        by_invoice.setdefault(record["INVOICE_ID"], []).append(flatten(child))
    return by_invoice


def target_lines(db, ns: str) -> dict[str, list[dict]]:
    """The stored lines, restricted to the loader's declared child fields.

    `invoice_at` is dropped on purpose: it is derived from `legacy.invoice_dt`, which is
    compared, and its absence is the D4 quarantine policy rather than a missing value.
    """
    declared = {target for _, target, _ in LINE_FIELDS}
    by_invoice: dict[str, list[dict]] = {}
    for doc in db["invoices"].find({"ns": ns}, {"lines": 1}):
        by_invoice[doc["_id"]] = [
            {path: value for path, value in flatten(line).items() if path in declared}
            for line in doc.get("lines", [])]
    return by_invoice


def source_attributes(cursor, batch_no: int) -> dict[str, list[dict]]:
    """The EAV rows the loader embeds, in the order it embeds them (`ENTITY_ID, EAV_ID`)."""
    cursor.execute(
        f"SELECT e.ENTITY_ID, e.ATTR_NAME, e.ATTR_VALUE, e.ATTR_TYPE, e.CREATED_DT "
        f"  FROM {EAV_TABLE} e "
        f" WHERE e.ENTITY_TYPE = 'CUSTOMER' "
        f"   AND EXISTS (SELECT 1 FROM {CUSTOMER_TABLE} c "
        f"                WHERE c.CUST_ID = e.ENTITY_ID AND c.CONVERSION_BATCH_NO = :b) "
        f" ORDER BY e.ENTITY_ID, e.EAV_ID", b=batch_no)
    by_entity: dict[str, list[dict]] = {}
    for entity_id, name, value, attr_type, created_dt in cursor:
        by_entity.setdefault(entity_id, []).append(
            {"name": name, "value": value, "type": attr_type, "legacy.created_dt": created_dt})
    return by_entity


def target_attributes(db, ns: str) -> dict[str, list[dict]]:
    by_entity: dict[str, list[dict]] = {}
    for doc in db["customers"].find({"ns": ns}, {"cust_id": 1, "attributes": 1}):
        by_entity[doc["cust_id"]] = [flatten(a) for a in doc.get("attributes", [])]
    return by_entity


def unit_report(expected: dict[str, list[dict]], actual: dict[str, list[dict]],
                array_path: str, identity: str, fields: int) -> dict:
    """One unit's embedded-child report, including what was compared.

    The compared counts are part of the evidence, not decoration: a verifier that silently
    read nothing would otherwise report the same clean verdict as one that read everything.
    """
    findings = diff_children(expected, actual, array_path, identity)
    children = sum(len(v) for v in expected.values())
    if not children:
        raise SystemExit(f"{array_path}: no source children read; refusing to report a "
                         f"verdict over an empty comparison")
    return {
        "array_path": array_path,
        "verdict": "PASS" if not findings else "FAIL",
        "parents_compared": len(set(expected) | set(actual)),
        "children_compared": children,
        "fields_per_child": fields,
        "value_comparisons": children * fields,
        "finding_count": len(findings),
        "findings": findings[:MAX_REPORTED],
    }


def run(connection, db, ns: str) -> dict:
    batch_no = ns_batch_no(ns)
    with connection.cursor() as cursor:
        lines = unit_report(source_lines(cursor, batch_no), target_lines(db, ns),
                            "invoices.lines", "line_id", len(LINE_FIELDS))
        attributes = unit_report(source_attributes(cursor, batch_no),
                                 target_attributes(db, ns), "customers.attributes", "name", 4)
    return {
        "check": "embedded_child_fields",
        "ns": ns,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "note": ("supplementary evidence for census finding H3; the recon harness verdict "
                 "remains the only merge authority"),
        "units": {"invoices": lines, "customers": attributes},
        "verdict": "PASS" if lines["verdict"] == attributes["verdict"] == "PASS" else "FAIL",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="embed_diff")
    p.add_argument("--ns", default="demo")
    p.add_argument("--source-dsn-secret", required=True)
    p.add_argument("--target-uri-secret", required=True)
    p.add_argument("--target-db", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    assert_designated_cluster(CONVENTIONS, args.target_uri_secret)
    db = mongo_database(args.target_uri_secret, args.target_db)
    with oracle_connect(args.source_dsn_secret) as connection:
        result = run(connection, db, args.ns)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "embed_diff.json").write_text(json.dumps(result, indent=2, default=str) + "\n")
    for unit, report in result["units"].items():
        print(f"embedded fields {report['verdict']}: unit={unit} "
              f"children={report['children_compared']} "
              f"values={report['value_comparisons']} "
              f"findings={report['finding_count']}")
    print(f"-> {args.out}/embed_diff.json")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

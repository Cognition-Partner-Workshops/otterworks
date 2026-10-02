#!/usr/bin/env python3
"""Read-only cardinality probe for the OW_BILLING -> Atlas mapping spec (plan step s3.1-mapping-spec).

Measures, as the OW_TP_ORACLE_RO_DSN principal under SET TRANSACTION READ ONLY, the child-per-parent
fan-out of every parent/child pair the mapping spec embeds or deliberately keeps referenced, plus the
row-length figures the 16 MB document-size guard is computed from. Writes
migration/billing/mapping/cardinality.json; mapping_spec.json#size_guard cites it.

usage: python migration/billing/mapping/cardinality.py [--out migration/billing/mapping/cardinality.json]
       OW_TP_ORACLE_RO_DSN is JSON {user,password,dsn} or a plain connect string (never printed).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import oracledb

REPO = Path(__file__).resolve().parents[3]
SCHEMA = "OW_BILLING"

# (parent table, child table, child FK column, parent key column)
FANOUT = [
    ("TENANTS", "SUBSCRIPTIONS", "TENANT_ID", "ID"),
    ("TENANTS", "USAGE_EVENTS", "TENANT_ID", "ID"),
    ("TENANTS", "RATING_PERIODS", "TENANT_ID", "ID"),
    ("TENANTS", "INVOICES", "TENANT_ID", "ID"),
    ("TENANTS", "CREDIT_NOTES", "TENANT_ID", "ID"),
    ("TENANTS", "DUNNING_ATTEMPTS", "TENANT_ID", "ID"),
    ("TENANTS", "NOTIFICATIONS", "TENANT_ID", "ID"),
    ("TENANTS", "CUSTOMER_MASTER", "TENANT_ID", "ID"),
    ("RATING_PERIODS", "RATING_RESULTS", "PERIOD_ID", "ID"),
    ("INVOICES", "INVOICE_LINES", "INVOICE_ID", "ID"),
    ("INVOICES", "DUNNING_ATTEMPTS", "INVOICE_ID", "ID"),
    ("SUBSCRIPTIONS", "SUBSCRIPTIONS_HIST", "ID", "ID"),
    ("CUSTOMER_MASTER", "ENTITY_ATTR_VALUE", "ENTITY_ID", "CUST_ID"),
    ("CUSTOMER_MASTER", "CUSTOMER_MASTER_HIST", "CUST_ID", "CUST_ID"),
    ("INVOICE_HEADER", "INVOICE_LINE", "INVOICE_ID", "INVOICE_ID"),
]

# Row-length proxy: SUM(VSIZE(col)) over every column, per table (bytes as stored by Oracle).
ROWLEN_TABLES = ["SUBSCRIPTIONS", "USAGE_EVENTS", "RATING_RESULTS", "INVOICE_LINES", "DUNNING_ATTEMPTS",
                 "ENTITY_ATTR_VALUE", "INVOICE_LINE", "CUSTOMER_MASTER", "INVOICE_HEADER", "INVOICES",
                 "RATING_PERIODS", "BILLING_AUDIT_LOG"]

VOCAB = {
    "ENTITY_ATTR_VALUE.ENTITY_TYPE": "SELECT entity_type AS v, COUNT(*) AS n FROM {s}.entity_attr_value GROUP BY entity_type ORDER BY 1",
    "ENTITY_ATTR_VALUE.ATTR_TYPE": "SELECT attr_type AS v, COUNT(*) AS n FROM {s}.entity_attr_value GROUP BY attr_type ORDER BY 1",
    "ENTITY_ATTR_VALUE.ATTR_NAME": "SELECT attr_name AS v, COUNT(*) AS n FROM {s}.entity_attr_value GROUP BY attr_name ORDER BY 1",
    "INVOICE_LINE.LINE_TYPE_CD": "SELECT TO_CHAR(line_type_cd) AS v, COUNT(*) AS n FROM {s}.invoice_line GROUP BY line_type_cd ORDER BY 1",
    "INVOICE_HEADER.STATUS_CD": "SELECT TO_CHAR(status_cd) AS v, COUNT(*) AS n FROM {s}.invoice_header GROUP BY status_cd ORDER BY 1",
    "INVOICES.STATUS_CD": "SELECT TO_CHAR(status_cd) AS v, COUNT(*) AS n FROM {s}.invoices GROUP BY status_cd ORDER BY 1",
    "INVOICE_LINES.LINE_TYPE": "SELECT line_type AS v, COUNT(*) AS n FROM {s}.invoice_lines GROUP BY line_type ORDER BY 1",
    "BILLING_AUDIT_LOG.ID_TYPE": "SELECT CASE WHEN log_id IS NULL THEN 'NULL' ELSE 'NUMBER' END AS v, COUNT(*) AS n FROM {s}.billing_audit_log GROUP BY CASE WHEN log_id IS NULL THEN 'NULL' ELSE 'NUMBER' END",
}

ORPHANS = {
    "INVOICE_LINE_without_INVOICE_HEADER": "SELECT COUNT(*) FROM {s}.invoice_line l WHERE NOT EXISTS (SELECT 1 FROM {s}.invoice_header h WHERE h.invoice_id = l.invoice_id)",
    "ENTITY_ATTR_VALUE_without_CUSTOMER_MASTER": "SELECT COUNT(*) FROM {s}.entity_attr_value e WHERE e.entity_type = 'CUSTOMER' AND NOT EXISTS (SELECT 1 FROM {s}.customer_master c WHERE c.cust_id = e.entity_id)",
    "ENTITY_ATTR_VALUE_non_CUSTOMER": "SELECT COUNT(*) FROM {s}.entity_attr_value e WHERE e.entity_type <> 'CUSTOMER'",
    "INVOICE_LINE_duplicate_invoice_line_no": "SELECT COUNT(*) FROM (SELECT invoice_id, line_no FROM {s}.invoice_line GROUP BY invoice_id, line_no HAVING COUNT(*) > 1)",
}


def connect() -> oracledb.Connection:
    raw = os.environ["OW_TP_ORACLE_RO_DSN"]
    try:
        cfg = json.loads(raw)
        kw = {"user": cfg["user"], "password": cfg["password"], "dsn": cfg["dsn"]}
    except (ValueError, KeyError, TypeError):
        kw = {"dsn": raw}
    return oracledb.connect(**kw)


def rows(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def one(cur, sql: str) -> dict:
    return rows(cur, sql)[0]


def num(v):
    return None if v is None else (int(v) if float(v).is_integer() else float(v))


def columns(cur, table: str) -> list[str]:
    return [r["column_name"] for r in rows(
        cur, f"SELECT column_name FROM all_tab_columns WHERE owner = '{SCHEMA}' AND table_name = '{table}' ORDER BY column_id")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "migration/billing/mapping/cardinality.json"))
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()
    cur.execute("SET TRANSACTION READ ONLY")
    principal = one(cur, "SELECT USER AS principal, SYS_CONTEXT('USERENV','CON_NAME') AS container FROM dual")
    s = SCHEMA

    fanout = {}
    for parent, child, fk, pk in FANOUT:
        agg = one(cur, f"""
            SELECT COUNT(*) AS parents_with_children, MIN(n) AS min_n, MAX(n) AS max_n, AVG(n) AS avg_n,
                   PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY n) AS p99_n
              FROM (SELECT {fk}, COUNT(*) AS n FROM {s}.{child} GROUP BY {fk})""")
        total_children = one(cur, f"SELECT COUNT(*) AS n FROM {s}.{child}")["n"]
        parents = one(cur, f"SELECT COUNT(*) AS n FROM {s}.{parent}")["n"]
        matched = one(cur, f"SELECT COUNT(*) AS n FROM {s}.{child} c WHERE EXISTS (SELECT 1 FROM {s}.{parent} p WHERE p.{pk} = c.{fk})")["n"]
        fanout[f"{parent}->{child}"] = {
            "parent": parent, "child": child, "child_fk": fk, "parent_key": pk,
            "parent_rows": int(parents), "child_rows": int(total_children),
            "child_rows_with_parent": int(matched), "child_rows_without_parent": int(total_children - matched),
            "parents_with_children": int(agg["parents_with_children"] or 0),
            "children_per_parent": {"min": num(agg["min_n"]), "max": num(agg["max_n"]),
                                    "avg": None if agg["avg_n"] is None else round(float(agg["avg_n"]), 3),
                                    "p99": num(agg["p99_n"])},
        }

    rowlen = {}
    for table in ROWLEN_TABLES:
        cols = columns(cur, table)
        expr = " + ".join(f"NVL(VSIZE({c}), 0)" for c in cols)
        r = one(cur, f"SELECT COUNT(*) AS n, MAX({expr}) AS max_bytes, AVG({expr}) AS avg_bytes FROM {s}.{table}")
        rowlen[table] = {"rows": int(r["n"]), "columns": len(cols),
                         "max_row_bytes": num(r["max_bytes"]),
                         "avg_row_bytes": None if r["avg_bytes"] is None else round(float(r["avg_bytes"]), 1),
                         "method": "SUM(NVL(VSIZE(col),0)) over every column; Oracle stored bytes, a proxy for BSON size"}

    vocab = {k: {str(r["v"]): int(r["n"]) for r in rows(cur, sql.format(s=s))} for k, sql in VOCAB.items()}
    orphans = {k: int(one(cur, sql.format(s=s))["count(*)"]) for k, sql in ORPHANS.items()}
    eav_len = one(cur, f"SELECT MAX(LENGTH(attr_value)) AS max_len, MAX(LENGTH(attr_name)) AS max_name FROM {s}.entity_attr_value")
    csv_len = one(cur, f"SELECT MAX(LENGTH(related_acct_ids)) AS related, MAX(LENGTH(promo_codes_csv)) AS promo FROM {s}.customer_master")

    out = {
        "kind": "mapping-cardinality",
        "version": 1,
        "plan_step": "s3.1-mapping-spec",
        "captured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"system": "oracle", "schema": SCHEMA, "mode": "live", "dsn_secret": "OW_TP_ORACLE_RO_DSN",
                   "principal": principal["principal"], "container": principal["container"],
                   "transaction": "SET TRANSACTION READ ONLY"},
        "fanout": fanout,
        "row_length": rowlen,
        "vocabulary": vocab,
        "orphans": orphans,
        "string_lengths": {"ENTITY_ATTR_VALUE.ATTR_VALUE.max": num(eav_len["max_len"]),
                           "ENTITY_ATTR_VALUE.ATTR_NAME.max": num(eav_len["max_name"]),
                           "CUSTOMER_MASTER.RELATED_ACCT_IDS.max": num(csv_len["related"]),
                           "CUSTOMER_MASTER.PROMO_CODES_CSV.max": num(csv_len["promo"])},
        "note": "Read-only measurement of the live estate; the mapping spec's size guard uses these as observed bounds, not as limits.",
    }
    conn.rollback()
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=False) + "\n")
    print(f"wrote {args.out}: {len(fanout)} fan-out pairs, {len(rowlen)} row-length tables, mode=live")
    return 0


if __name__ == "__main__":
    sys.exit(main())

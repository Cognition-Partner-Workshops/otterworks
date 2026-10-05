#!/usr/bin/env python3
"""Census of the Oracle OW_BILLING schema (plan step s2.1-census).

Read-only dictionary queries through python-oracledb (thin) as the
OW_TP_ORACLE_RO_DSN principal, joined with census/buckets.json so every
object lands in exactly one bucket (migrate / migrate-as-logic / retire /
out-of-scope) with a cite. Writes migration/billing/census.json.

Before any dictionary query the principal's privileges are read from
USER_SYS_PRIVS / USER_TAB_PRIVS / USER_ROLE_PRIVS / SESSION_PRIVS and the
run aborts unless every privilege is on the read-only allowlist. The
session is also put in SET TRANSACTION READ ONLY.

ALL_* views only expose objects the principal holds object privileges on;
SELECT ANY TABLE surfaces tables and indexes but not the packages, triggers,
sequences or scheduler jobs, so each class is also read from its DBA_* view
(readable through SELECT ANY DICTIONARY, still read-only) and the census
records which view supplied the rows.

usage: python migration/billing/census/census.py [--ns demo] [--out migration/billing/census.json]
       OW_TP_ORACLE_RO_DSN is JSON {user,password,dsn} or a plain connect string.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import oracledb

HERE = Path(__file__).resolve().parent
SCHEMA = "OW_BILLING"
READ_ONLY_SYS_PRIVS = {"CREATE SESSION", "SELECT ANY TABLE", "READ ANY TABLE", "SELECT ANY DICTIONARY", "SET CONTAINER"}
READ_ONLY_TAB_PRIVS = {"SELECT", "READ", "INHERIT PRIVILEGES"}
BUCKETS = ("migrate", "migrate-as-logic", "retire", "out-of-scope")


def connect() -> oracledb.Connection:
    raw = os.environ["OW_TP_ORACLE_RO_DSN"]
    try:
        cfg = json.loads(raw)
        kw = {"user": cfg["user"], "password": cfg["password"], "dsn": cfg["dsn"]}
    except (ValueError, KeyError, TypeError):
        kw = {"dsn": raw}
    return oracledb.connect(**kw)


def rows(cur, sql: str, **binds) -> list[dict]:
    cur.execute(sql, binds)
    cols = [d[0].lower() for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def scalar(cur, sql: str, **binds):
    cur.execute(sql, binds)
    return cur.fetchone()[0]


def check_principal(cur) -> dict:
    who = rows(cur, "SELECT USER AS principal, SYS_CONTEXT('USERENV','CON_NAME') AS container FROM dual")[0]
    sys_privs = [r["privilege"] for r in rows(cur, "SELECT privilege FROM user_sys_privs ORDER BY 1")]
    tab_privs = rows(cur, "SELECT owner, table_name, privilege FROM user_tab_privs ORDER BY 1, 2, 3")
    roles = [r["granted_role"] for r in rows(cur, "SELECT granted_role FROM user_role_privs ORDER BY 1")]
    session_privs = [r["privilege"] for r in rows(cur, "SELECT privilege FROM session_privs ORDER BY 1")]
    role_sys = rows(cur, "SELECT role, privilege FROM role_sys_privs ORDER BY 1, 2") if roles else []
    role_tab = rows(cur, "SELECT role, owner, table_name, privilege FROM role_tab_privs ORDER BY 1, 2, 3, 4") if roles else []
    own_objects = scalar(cur, "SELECT COUNT(*) FROM user_objects")

    offending = sorted(
        {p for p in sys_privs + session_privs + [r["privilege"] for r in role_sys] if p not in READ_ONLY_SYS_PRIVS}
        | {f'{r["privilege"]} ON {r["owner"]}.{r["table_name"]}' for r in tab_privs + role_tab if r["privilege"] not in READ_ONLY_TAB_PRIVS}
    )
    return {
        "principal": who["principal"],
        "container": who["container"],
        "read_only": not offending,
        "offending_privileges": offending,
        "user_sys_privs": sys_privs,
        "user_tab_privs": tab_privs,
        "user_role_privs": roles,
        "role_sys_privs": role_sys,
        "role_tab_privs": role_tab,
        "session_privs": session_privs,
        "owns_objects": own_objects,
        "allowlist": {"system": sorted(READ_ONLY_SYS_PRIVS), "object": sorted(READ_ONLY_TAB_PRIVS)},
        "check": "no INSERT/UPDATE/DELETE/DDL/EXECUTE/GRANT privilege in USER_SYS_PRIVS, USER_TAB_PRIVS, USER_ROLE_PRIVS (resolved through ROLE_*_PRIVS) or SESSION_PRIVS; INHERIT PRIVILEGES on the principal itself is Oracle's default self-grant",
    }


class Dictionary:
    """Runs a query against the ALL_ view and the DBA_ view and keeps the fuller answer."""

    def __init__(self, cur):
        self.cur = cur
        self.provenance: dict[str, dict] = {}

    def query(self, view: str, sql: str, **binds) -> list[dict]:
        out = {}
        for prefix in ("ALL_", "DBA_"):
            name = prefix + view
            try:
                out[name] = rows(self.cur, sql.format(view=name), **binds)
            except oracledb.DatabaseError as exc:
                out[name] = exc
        all_rows, dba_rows = out["ALL_" + view], out["DBA_" + view]
        usable = {k: v for k, v in out.items() if not isinstance(v, Exception)}
        used = max(usable, key=lambda k: len(usable[k]))
        self.provenance[view] = {
            "ALL_" + view: len(all_rows) if not isinstance(all_rows, Exception) else f"error: {str(all_rows).splitlines()[0]}",
            "DBA_" + view: len(dba_rows) if not isinstance(dba_rows, Exception) else f"error: {str(dba_rows).splitlines()[0]}",
            "used": used,
        }
        return usable[used]


SIGNATURE_RE = re.compile(r"^\s*(FUNCTION|PROCEDURE)\s+([a-z0-9_]+)\s*(\([^)]*\))?\s*(RETURN\s+[A-Za-z0-9_$]+)?", re.IGNORECASE | re.MULTILINE)


def census(ns: str) -> dict:
    with connect() as con:
        cur = con.cursor()
        cur.execute("SET TRANSACTION READ ONLY")
        principal = check_principal(cur)
        if not principal["read_only"]:
            raise SystemExit(f"OW_TP_ORACLE_RO_DSN principal is not read-only: {principal['offending_privileges']}")

        instance = rows(cur, "SELECT instance_name, version_full, SYS_CONTEXT('USERENV','DB_NAME') AS db_name FROM v$instance")[0]
        d = Dictionary(cur)
        owner = {"owner": SCHEMA}

        objects = d.query("OBJECTS", "SELECT object_name, object_type, status, TO_CHAR(created,'YYYY-MM-DD') AS created FROM {view} WHERE owner=:owner ORDER BY object_type, object_name", **owner)
        tables = d.query("TABLES", "SELECT table_name, num_rows AS stats_num_rows, temporary, partitioned FROM {view} WHERE owner=:owner ORDER BY table_name", **owner)
        columns = d.query("TAB_COLUMNS", "SELECT table_name, column_id, column_name, data_type, data_length, data_precision, data_scale, nullable, data_default FROM {view} WHERE owner=:owner ORDER BY table_name, column_id", **owner)
        constraints = d.query("CONSTRAINTS", "SELECT table_name, constraint_name, constraint_type, status, r_owner, r_constraint_name, index_name, search_condition_vc AS search_condition FROM {view} WHERE owner=:owner ORDER BY table_name, constraint_name", **owner)
        cons_cols = d.query("CONS_COLUMNS", "SELECT constraint_name, column_name, position FROM {view} WHERE owner=:owner ORDER BY constraint_name, position", **owner)
        indexes = d.query("INDEXES", "SELECT index_name, table_name, uniqueness, index_type, status FROM {view} WHERE owner=:owner ORDER BY table_name, index_name", **owner)
        ind_cols = d.query("IND_COLUMNS", "SELECT index_name, column_name, column_position FROM {view} WHERE index_owner=:owner ORDER BY index_name, column_position", **owner)
        source = d.query("SOURCE", "SELECT name, type, line, text FROM {view} WHERE owner=:owner ORDER BY name, type, line", **owner)
        triggers = d.query("TRIGGERS", "SELECT trigger_name, trigger_type, triggering_event, table_name, status, when_clause FROM {view} WHERE owner=:owner ORDER BY trigger_name", **owner)
        sequences = d.query("SEQUENCES", "SELECT sequence_name, min_value, increment_by, cache_size, last_number FROM {view} WHERE sequence_owner=:owner ORDER BY sequence_name", **owner)
        dependencies = d.query("DEPENDENCIES", "SELECT name, type, referenced_owner, referenced_name, referenced_type FROM {view} WHERE owner=:owner ORDER BY name, type, referenced_owner, referenced_name", **owner)
        jobs = d.query("SCHEDULER_JOBS", "SELECT job_name, job_type, job_action, repeat_interval, enabled, state, run_count, failure_count, comments FROM {view} WHERE owner=:owner ORDER BY job_name", **owner)

        counts = {t["table_name"]: scalar(cur, f'SELECT COUNT(*) FROM {SCHEMA}."{t["table_name"]}"') for t in tables}
        tenant_ns = rows(cur, f"SELECT REGEXP_SUBSTR(name, '^([^:]+)::', 1, 1, NULL, 1) AS namespace, COUNT(*) AS n FROM {SCHEMA}.tenants GROUP BY REGEXP_SUBSTR(name, '^([^:]+)::', 1, 1, NULL, 1) ORDER BY 1 NULLS FIRST")
        tenants_in_ns = scalar(cur, f"SELECT COUNT(*) FROM {SCHEMA}.tenants WHERE name LIKE :pfx", pfx=f"{ns}::%")

    cols_by_table = defaultdict(list)
    for c in columns:
        cols_by_table[c["table_name"]].append({k: v for k, v in c.items() if k != "table_name"})
    cc = defaultdict(list)
    for c in cons_cols:
        cc[c["constraint_name"]].append(c["column_name"])
    cons_by_table = defaultdict(list)
    for c in constraints:
        if c["constraint_type"] == "C" and (c["search_condition"] or "").endswith("IS NOT NULL"):
            continue
        cons_by_table[c["table_name"]].append({**{k: v for k, v in c.items() if k != "table_name"}, "columns": cc.get(c["constraint_name"], [])})
    ic = defaultdict(list)
    for c in ind_cols:
        ic[c["index_name"]].append(c["column_name"])
    idx_by_table = defaultdict(list)
    for i in indexes:
        idx_by_table[i["table_name"]].append({**{k: v for k, v in i.items() if k != "table_name"}, "columns": ic.get(i["index_name"], [])})

    src_units = {}
    for (name, typ), lines in _group(source, lambda s: (s["name"], s["type"])).items():
        text = "".join(l["text"] for l in lines)
        unit = {"lines": len(lines), "sha256": hashlib.sha256(text.encode()).hexdigest()}
        if typ == "PACKAGE":
            unit["signatures"] = [" ".join(p for p in m.groups() if p).strip() for m in SIGNATURE_RE.finditer(text)]
            unit["package_state_globals"] = sorted(set(re.findall(r"^\s*(g_[a-z0-9_]+)\s", text, re.IGNORECASE | re.MULTILINE)))
        if typ in ("PACKAGE BODY", "TRIGGER"):
            unit["oracle_constructs"] = sorted({k for k, pat in ORACLE_CONSTRUCTS.items() if re.search(pat, text, re.IGNORECASE)})
        src_units[f"{typ}:{name}"] = unit

    internal_edges = [e for e in dependencies if e["referenced_owner"] == SCHEMA]
    external_refs = sorted({f'{e["referenced_owner"]}.{e["referenced_name"]} ({e["referenced_type"]})' for e in dependencies if e["referenced_owner"] != SCHEMA})
    referenced_by = defaultdict(set)
    for e in internal_edges:
        referenced_by[f'{e["referenced_type"]}:{e["referenced_name"]}'].add(f'{e["type"]}:{e["name"]}')

    buckets = json.loads((HERE / "buckets.json").read_text())
    table_bucket = {k.split(":", 1)[1]: v["bucket"] for k, v in buckets["objects"].items() if k.startswith("TABLE:")}
    cite_root = buckets["cite_root"]
    bucketed, unbucketed, stale = [], [], set(buckets["objects"])
    for o in objects:
        key = f'{o["object_type"]}:{o["object_name"]}'
        entry = {"key": key, "object_type": o["object_type"], "name": o["object_name"], "status": o["status"]}
        if o["object_type"] == "INDEX":
            table = next(i["table_name"] for i in indexes if i["index_name"] == o["object_name"])
            entry.update(bucket=table_bucket[table], cite=buckets["index_rule"]["cite"], note=f'index on {table}: {buckets["index_rule"]["note"]}', table=table)
        elif key in buckets["objects"]:
            b = buckets["objects"][key]
            entry.update(bucket=b["bucket"], cite=cite_root + b["cite"], note=b.get("note"))
            stale.discard(key)
        else:
            unbucketed.append(key)
            continue
        if entry["bucket"] not in BUCKETS:
            raise SystemExit(f"{key}: unknown bucket {entry['bucket']!r}")
        if key in referenced_by:
            entry["referenced_by"] = sorted(referenced_by[key])
        bucketed.append(entry)
    if unbucketed or stale:
        raise SystemExit(f"census incomplete: unbucketed live objects {unbucketed}; bucket entries without a live object {sorted(stale)}")

    summary = defaultdict(lambda: defaultdict(int))
    for e in bucketed:
        summary[e["bucket"]][e["object_type"]] += 1

    return {
        "kind": "oracle-census",
        "version": 1,
        "plan_step": "s2.1-census",
        "captured_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "namespace": ns,
        "source": {
            "system": "oracle",
            "schema": SCHEMA,
            "mode": "live",
            "dsn_secret": "OW_TP_ORACLE_RO_DSN",
            "instance": instance["instance_name"],
            "db_name": instance["db_name"],
            "version": instance["version_full"],
            "driver": f"python-oracledb {oracledb.__version__} thin={oracledb.is_thin_mode()}",
            "transaction": "SET TRANSACTION READ ONLY",
        },
        "principal": principal,
        "dictionary_views": {
            "note": "ALL_* only lists objects the principal holds object privileges on (SELECT ANY TABLE covers tables/indexes, nothing else); DBA_* is readable through SELECT ANY DICTIONARY. Both are plain read-only dictionary reads.",
            "queries": d.provenance,
        },
        "buckets": buckets["buckets"],
        "coverage": {
            "objects_total": len(objects),
            "objects_bucketed": len(bucketed),
            "unbucketed": unbucketed,
            "by_bucket": {b: dict(sorted(summary[b].items())) for b in BUCKETS},
            "by_object_type": dict(sorted(_count(objects, "object_type").items())),
        },
        "objects": bucketed,
        "row_counts": {
            "method": "SELECT COUNT(*) per table at capture time (exact); ALL_TABLES.NUM_ROWS is optimizer statistics and is reported separately",
            "tables": dict(sorted(counts.items())),
            "tenants_by_namespace": [{"namespace": r["namespace"] or "(baseline, no prefix)", "rows": r["n"]} for r in tenant_ns],
            "tenants_in_namespace": {"namespace": ns, "filter": f"name LIKE '{ns}::%'", "rows": tenants_in_ns},
        },
        "tables": [
            {
                "name": t["table_name"],
                "bucket": table_bucket[t["table_name"]],
                "rows": counts[t["table_name"]],
                "stats_num_rows": t["stats_num_rows"],
                "column_count": len(cols_by_table[t["table_name"]]),
                "constraints": cons_by_table[t["table_name"]],
                "indexes": idx_by_table[t["table_name"]],
                "columns": cols_by_table[t["table_name"]],
            }
            for t in tables
        ],
        "source_units": dict(sorted(src_units.items())),
        "triggers": triggers,
        "sequences": sequences,
        "scheduler_jobs": jobs,
        "dependencies": {"internal": internal_edges, "external_references": external_refs},
    }


ORACLE_CONSTRUCTS = {
    "autonomous_transaction": r"PRAGMA\s+AUTONOMOUS_TRANSACTION",
    "execute_immediate": r"EXECUTE\s+IMMEDIATE",
    "sys_refcursor": r"SYS_REFCURSOR",
    "cursor_loop": r"\bOPEN\s+\w+|FOR\s+\w+\s+IN\s*\(",
    "when_others_null": r"WHEN\s+OTHERS\s+THEN\s+NULL",
    "oracle_outer_join": r"\(\+\)",
    "decode": r"\bDECODE\s*\(",
    "nvl": r"\bNVL\s*\(",
    "to_char_to_date": r"\bTO_(CHAR|DATE)\s*\(",
    "raise_application_error": r"RAISE_APPLICATION_ERROR",
    "sequence_nextval": r"\.NEXTVAL\b",
    "sysdate": r"\bSYSDATE\b",
    "utl_raw_or_dbms": r"\b(UTL_RAW|DBMS_\w+)\.",
}


def _group(items, key):
    out = defaultdict(list)
    for it in items:
        out[key(it)].append(it)
    return out


def _count(items, field):
    out = defaultdict(int)
    for it in items:
        out[it[field]] += 1
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ns", default="demo", help="namespace whose TENANTS slice to count (default: demo)")
    ap.add_argument("--out", default=str(HERE.parent / "census.json"))
    args = ap.parse_args()
    result = census(args.ns)
    Path(args.out).write_text(json.dumps(result, indent=2, default=str) + "\n")
    cov = result["coverage"]
    print(f"principal={result['principal']['principal']} read_only={result['principal']['read_only']} "
          f"sys_privs={result['principal']['user_sys_privs']}")
    print(f"objects={cov['objects_total']} bucketed={cov['objects_bucketed']} by_bucket="
          + json.dumps({b: sum(v.values()) for b, v in cov['by_bucket'].items()}))
    for t in result["tables"]:
        print(f"  {t['name']:<22} {t['bucket']:<17} rows={t['rows']:<7} cols={t['column_count']}")
    print(f"tenants {result['row_counts']['tenants_in_namespace']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

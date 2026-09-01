"""Read-only Oracle census for the OW_BILLING estate.

Runs the mongo-migration oracle profile's discovery_commands verbatim and writes a
machine-readable census to .migration/census/. SELECT-only: no DDL, no DML, autocommit off.

DSN comes from the OW_ORACLE_BILLING_DSN env var (user/pass@host:port/service).
"""

import json
import os
import pathlib
import sys

import oracledb

SCHEMA = "OW_BILLING"
OUT = pathlib.Path(__file__).resolve().parents[1] / "census"

QUERIES = {
    "tables": """
        SELECT owner, table_name, num_rows FROM all_tables
        WHERE owner = :schema ORDER BY table_name
    """,
    "columns": """
        SELECT table_name, column_id, column_name, data_type, data_length,
               data_precision, data_scale, nullable, char_used, data_default
        FROM all_tab_columns WHERE owner = :schema ORDER BY table_name, column_id
    """,
    "constraints": """
        SELECT c.table_name, c.constraint_name, c.constraint_type, cc.column_name,
               cc.position, c.r_constraint_name, c.search_condition_vc, c.status, c.validated
        FROM all_constraints c
        JOIN all_cons_columns cc
          ON c.constraint_name = cc.constraint_name AND c.owner = cc.owner
        WHERE c.owner = :schema AND c.constraint_type IN ('P','R','U','C')
        ORDER BY c.table_name, c.constraint_name, cc.position
    """,
    "indexes": """
        SELECT i.index_name, i.table_name, i.uniqueness, i.index_type, ic.column_name,
               ic.column_position
        FROM all_indexes i
        LEFT JOIN all_ind_columns ic
          ON ic.index_name = i.index_name AND ic.index_owner = i.owner
        WHERE i.owner = :schema
        ORDER BY i.table_name, i.index_name, ic.column_position
    """,
    "plsql_objects": """
        SELECT object_name, object_type, status FROM all_objects
        WHERE owner = :schema
          AND object_type IN ('PACKAGE','PACKAGE BODY','PROCEDURE','FUNCTION',
                              'TRIGGER','MATERIALIZED VIEW','VIEW','TYPE')
        ORDER BY object_type, object_name
    """,
    "dependencies": """
        SELECT name, type, referenced_name, referenced_type FROM all_dependencies
        WHERE owner = :schema AND referenced_owner = :schema
        ORDER BY name, referenced_name
    """,
    "sequences": """
        SELECT sequence_name, last_number, increment_by, min_value, max_value, cycle_flag
        FROM all_sequences WHERE sequence_owner = :schema ORDER BY sequence_name
    """,
    "rowid_usage": """
        SELECT DISTINCT name, type FROM all_source
        WHERE owner = :schema AND UPPER(text) LIKE '%ROWID%' ORDER BY name
    """,
    "scheduler_jobs": """
        SELECT job_name, job_type, job_action, enabled, repeat_interval
        FROM all_scheduler_jobs WHERE owner = :schema ORDER BY job_name
    """,
    "triggers": """
        SELECT trigger_name, table_name, trigger_type, triggering_event, status
        FROM all_triggers WHERE owner = :schema ORDER BY table_name, trigger_name
    """,
    "source_lines": """
        SELECT name, type, COUNT(*) AS lines FROM all_source
        WHERE owner = :schema GROUP BY name, type ORDER BY name, type
    """,
}


def rows(cur, sql, **binds):
    cur.execute(sql, **binds)
    cols = [d[0].lower() for d in cur.description]
    out = []
    for r in cur:
        rec = {}
        for c, v in zip(cols, r):
            if isinstance(v, oracledb.LOB):
                v = v.read()
            elif hasattr(v, "isoformat"):
                v = v.isoformat()
            rec[c] = v
        out.append(rec)
    return out


def main():
    dsn = os.environ.get("OW_ORACLE_BILLING_DSN")
    if not dsn:
        sys.exit("OW_ORACLE_BILLING_DSN is not set")
    user, _, rest = dsn.partition("/")
    password, _, conn_str = rest.partition("@")

    OUT.mkdir(parents=True, exist_ok=True)
    census = {}
    with (oracledb.connect(user=user, password=password, dsn=conn_str) as con,
          con.cursor() as cur):
        for name, sql in QUERIES.items():
            census[name] = rows(cur, sql, schema=SCHEMA)
        # exact counts (num_rows in all_tables is a stale optimizer estimate)
        counts = {}
        for t in census["tables"]:
            tn = t["table_name"]
            cur.execute(f'SELECT COUNT(*) FROM {SCHEMA}."{tn}"')
            counts[tn] = cur.fetchone()[0]
        census["exact_counts"] = counts

    for name, data in census.items():
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=2, default=str))
    print(json.dumps({k: len(v) for k, v in census.items()}, indent=2))


if __name__ == "__main__":
    main()

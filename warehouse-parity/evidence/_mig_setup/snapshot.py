"""Snapshot information_schema for the unprefixed harness schemas (read-only).

Run from warehouse-parity/ with WP_SF_SCHEMA_PREFIX=MIG_ set:
    python evidence/_mig_setup/snapshot.py OUT.json
Schema names appear only inside string literals, so the prefix remap leaves them alone and
the queries read DW, STG, AUDIT and PARITY themselves. Nothing is written to Snowflake.
"""
import json
import sys

from wp.engines import connect

SCHEMAS = "('DW', 'STG', 'AUDIT', 'PARITY')"
QUERIES = {
    "schemas": "SELECT schema_name, created, last_altered FROM information_schema.schemata "
               f"WHERE schema_name IN {SCHEMAS} ORDER BY 1",
    "tables": "SELECT table_schema, table_name, table_type, row_count, bytes, created, last_altered "
              f"FROM information_schema.tables WHERE table_schema IN {SCHEMAS} ORDER BY 1, 2",
    "functions": "SELECT function_schema, function_name, argument_signature, created, last_altered "
                 f"FROM information_schema.functions WHERE function_schema IN {SCHEMAS} ORDER BY 1, 2, 3",
    "procedures": "SELECT procedure_schema, procedure_name, argument_signature, created, last_altered "
                  f"FROM information_schema.procedures WHERE procedure_schema IN {SCHEMAS} ORDER BY 1, 2, 3",
}


def main(out):
    sf = connect("snowflake")
    snap = {}
    for name, q in QUERIES.items():
        cols, rows = sf.query(q)
        snap[name] = [dict(zip([c.lower() for c in cols], r)) for r in rows]
    with open(out, "w") as fh:
        json.dump(snap, fh, indent=1, default=str, sort_keys=True)
    print(out, {k: len(v) for k, v in snap.items()})


if __name__ == "__main__":
    main(sys.argv[1])

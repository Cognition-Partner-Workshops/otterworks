"""Land completed Teradata emulator tables as Delta without changing values.

TD_DSN is read from the environment; never pass source credentials as arguments.
python -m warehouse.databricks.baseline --subject billing
The caller runs the BTEQ daily chain before invoking the loader.
"""
import argparse
from datetime import date, datetime
from decimal import Decimal
import json
import os
import re
from uuid import uuid4

from .sql import Warehouse, identifier


def delta_type(data_type):
    simple = {"bigint": "BIGINT", "integer": "INT", "smallint": "SMALLINT",
              "boolean": "BOOLEAN", "date": "DATE", "text": "STRING",
              "timestamp without time zone": "TIMESTAMP", "timestamp with time zone": "TIMESTAMP",
              "double precision": "DOUBLE", "real": "FLOAT"}
    if data_type in simple:
        return simple[data_type]
    match = re.fullmatch(r"numeric\((\d+),(\d+)\)", data_type)
    if match:
        return f"DECIMAL({match[1]},{match[2]})"
    if re.fullmatch(r"(?:character varying|character)(?:\(\d+\))?", data_type):
        return "STRING"
    raise ValueError("unsupported baseline type: " + data_type)


def literal(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        value = value.isoformat()
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def load(source, target, subject, *, catalog="cpw", schema="dbx_d1111_before", batch=200):
    from psycopg import sql

    if catalog != "cpw" or schema != "dbx_d1111_before":
        raise ValueError("baseline loader writes only cpw.dbx_d1111_before")
    if subject not in {"billing", "users", "documents", "audit"}:
        raise ValueError("unknown Teradata subject area")
    source_schema = "sfx_" + subject
    comment = "run_token=dbx-d1111 expires=2026-11-24"
    target.execute(f"CREATE SCHEMA IF NOT EXISTS {identifier(catalog)}.{identifier(schema)} "
                   f"COMMENT '{comment}'", step="baseline-schema")
    tables = source.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s ORDER BY tablename",
                            (source_schema,)).fetchall()
    receipts = []
    for (table,) in tables:
        # Name every subject to prevent collisions between source databases.
        destination = f"{identifier(catalog)}.{identifier(schema)}.{identifier(subject + '__' + table)}"
        columns = source.execute("SELECT a.attname,format_type(a.atttypid,a.atttypmod) "
                                 "FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid "
                                 "JOIN pg_namespace n ON c.relnamespace=n.oid "
                                 "WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 "
                                 "AND NOT a.attisdropped ORDER BY a.attnum", (source_schema, table)).fetchall()
        ddl = ", ".join(f"{identifier(n)} {delta_type(t)}" for n, t in columns)
        staging = f"{identifier(catalog)}.{identifier(schema)}.{identifier('_loading_' + uuid4().hex)}"
        target.execute(f"CREATE TABLE {staging} ({ddl}) USING DELTA "
                       f"COMMENT '{comment}'", step="baseline-stage")
        try:
            cursor = source.execute(sql.SQL("SELECT * FROM {}.{}").format(
                sql.Identifier(source_schema), sql.Identifier(table)))
            count = 0
            while rows := cursor.fetchmany(batch):
                values = ",".join("(" + ",".join(literal(v) for v in row) + ")" for row in rows)
                target.execute(f"INSERT INTO {staging} VALUES {values}", step="baseline-load")
                count += len(rows)
            actual = target.execute(f"SELECT COUNT(*) FROM {staging}", step="baseline-count")
            if int(actual["rows"][0][0]) != count:
                raise RuntimeError("baseline row count mismatch: " + table)
            # Delta publishes one completed table atomically, including a changed schema.
            published = target.execute(f"CREATE OR REPLACE TABLE {destination} USING DELTA "
                                       f"COMMENT '{comment}' AS SELECT * FROM {staging}",
                                       step="baseline-publish")
        finally:
            target.execute(f"DROP TABLE IF EXISTS {staging}", step="baseline-stage-cleanup")
        receipts.append({"source": source_schema + "." + table, "target": destination,
                         "rows": count, "statement_id": published["statement_id"],
                         "count_statement_id": actual["statement_id"]})
    if not receipts:
        raise RuntimeError("no baseline tables found; run the Teradata daily chain first")
    return receipts


def main():
    import psycopg

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", choices=["billing", "users", "documents", "audit"], required=True)
    args = parser.parse_args()
    source_dsn = os.getenv("TD_DSN")
    if not source_dsn:
        parser.error("TD_DSN is required in the environment")
    with psycopg.connect(source_dsn) as source:
        print(json.dumps(load(source, Warehouse(act="prove"), args.subject), indent=2))


if __name__ == "__main__":
    main()

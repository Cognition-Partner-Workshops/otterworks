"""Land completed Teradata emulator tables as Delta without changing values.

TD_DSN is read from the environment; never pass source credentials as arguments.
python -m warehouse.databricks.baseline --subject billing
The caller runs the BTEQ daily chain before invoking the loader.
"""
import argparse
from collections import deque
from datetime import date, datetime
from decimal import Decimal
import json
import io
import os
import re
from uuid import uuid4

from .sql import Warehouse, identifier


class MacroConnection:
    """Capture result metadata while Runner retains ownership of EXEC semantics."""

    def __init__(self, connection):
        self.connection = connection
        self.descriptions = []

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, *args, **kwargs):
        cursor = self.connection.execute(*args, **kwargs)
        if cursor.description:
            self.descriptions.append(cursor.description)
        return cursor


def macro_result(source, subject, name):
    from warehouse.teradata.bteq.runner import Runner

    source.commit()
    source.autocommit = True
    connection = MacroConnection(source)
    runner = Runner(connection=connection, output=io.StringIO())
    params = "DATE '2026-11-01', DATE '2026-12-01'" if name == "m_storage_totals" else "'20261109'"
    runner.execute(f"EXEC SFX_{subject}.{name}({params})")
    if runner.errorcode:
        raise RuntimeError(f"baseline macro {subject}.{name}: {runner.output.getvalue()}")
    description = next((d for d in reversed(connection.descriptions)
                        if [c.name for c in d] == runner.headers), None)
    if not description:
        raise RuntimeError("baseline macro returned no result metadata: " + name)
    columns = []
    for index, column in enumerate(description):
        data_type = source.execute("SELECT format_type(%s, -1)", (column.type_code,)).fetchone()[0]
        if data_type == "numeric":
            scale = max((max(0, -row[index].as_tuple().exponent) for row in runner.rows
                         if row[index] is not None), default=18)
            data_type = f"numeric(38,{scale})"
        columns.append((column.name, data_type))
    return columns, deque(runner.rows)


def delta_type(data_type):
    simple = {"bigint": "BIGINT", "integer": "INT", "smallint": "SMALLINT",
              "boolean": "BOOLEAN", "date": "DATE", "text": "STRING",
              "timestamp without time zone": "TIMESTAMP", "timestamp with time zone": "TIMESTAMP",
              "double precision": "DOUBLE", "real": "FLOAT", "numeric": "DECIMAL(38,18)"}
    if data_type in simple:
        return simple[data_type]
    if re.fullmatch(r"timestamp\(\d+\) (?:with|without) time zone", data_type):
        return "TIMESTAMP"
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


def load(source, target, subject, *, catalog="cpw", schema="dbx_d1111_before", batch=2000):
    from psycopg import sql

    if catalog != "cpw" or schema != "dbx_d1111_before":
        raise ValueError("baseline loader writes only cpw.dbx_d1111_before")
    if subject not in {"billing", "users", "documents", "audit"}:
        raise ValueError("unknown Teradata subject area")
    if batch < 1:
        raise ValueError("batch must be positive")
    source_schema = "sfx_" + subject
    comment = "run_token=dbx-d1111 expires=2026-11-24"
    target.execute(f"CREATE SCHEMA IF NOT EXISTS {identifier(catalog)}.{identifier(schema)} "
                   f"COMMENT '{comment}'", step="baseline-schema")
    tables = source.execute("SELECT tablename FROM pg_tables WHERE schemaname=%s "
                            "UNION SELECT viewname FROM pg_views WHERE schemaname=%s ORDER BY 1",
                            (source_schema, source_schema)).fetchall()
    macros = source.execute("SELECT split_part(name,'.',2) FROM sfx_td.routines "
                            "WHERE kind='MACRO' AND split_part(name,'.',1)=%s ORDER BY name",
                            (source_schema,)).fetchall()
    receipts = []
    for table, is_macro in [(n, False) for (n,) in tables] + [(n, True) for (n,) in macros]:
        # Name every subject to prevent collisions between source databases.
        destination = f"{identifier(catalog)}.{identifier(schema)}.{identifier(subject + '__' + table)}"
        if is_macro:
            columns, macro_rows = macro_result(source, subject, table)
        else:
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
            if is_macro:
                def fetchmany(size):
                    return [macro_rows.popleft() for _ in range(min(size, len(macro_rows)))]
            else:
                cursor = source.execute(sql.SQL("SELECT * FROM {}.{}").format(
                    sql.Identifier(source_schema), sql.Identifier(table)))
                fetchmany = cursor.fetchmany
            count = 0
            while rows := fetchmany(batch):
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
    parser.add_argument("--subject", choices=["billing", "users", "documents", "audit"], required=True,
                        action="append")
    parser.add_argument("--batch", type=int, default=2000)
    args = parser.parse_args()
    source_dsn = os.getenv("TD_DSN")
    if not source_dsn:
        parser.error("TD_DSN is required in the environment")
    with psycopg.connect(source_dsn) as source:
        target = Warehouse(act="prove", consumer="billing")
        receipts = []
        for subject in dict.fromkeys(args.subject):
            receipts.extend(load(source, target, subject, batch=args.batch))
        print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()

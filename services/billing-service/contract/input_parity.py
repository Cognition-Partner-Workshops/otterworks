"""Compare complete physical input tables, normalizing only original CHAR padding."""

import hashlib
import os
from collections import Counter

import psycopg

from app.warehouse.databricks import execute

TABLES = ("customer_account", "invoice_hdr", "payment")


def row_counts(rows, columns, char_columns):
    return Counter(
        tuple(
            None
            if value is None
            else str(value).rstrip(" ")
            if columns[index] in char_columns
            else str(value)
            for index, value in enumerate(row)
        )
        for row in rows
    )


def row_hash(rows, columns, char_columns):
    total = 0
    for row in rows:
        values = [
            "<NULL>"
            if value is None
            else str(value).rstrip(" ")
            if columns[index] in char_columns
            else str(value)
            for index, value in enumerate(row)
        ]
        total += int(hashlib.md5("|".join(values).encode()).hexdigest()[:15], 16)
    return str(total)


def input_equality():
    settings = {
        key: os.getenv("TD_PG_" + variable, default)
        for key, variable, default in (
            ("host", "HOST", "localhost"),
            ("port", "PORT", "5432"),
            ("dbname", "DB", "teradata"),
            ("user", "USER", "postgres"),
            ("password", "PASSWORD", ""),
        )
    }
    evidence = {}
    with psycopg.connect(
        os.getenv("TD_PG_DSN", ""), **({} if os.getenv("TD_PG_DSN") else settings)
    ) as connection:
        for table in TABLES:
            char_columns = {
                row[0]
                for row in connection.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='sfx_billing' AND table_name=%s AND data_type='character'",
                    [table],
                )
            }
            # Identifiers come exclusively from the fixed table allowlist above.
            cursor = connection.execute("SELECT * FROM sfx_billing." + table)
            columns = [column.name for column in cursor.description]
            old_rows = cursor.fetchall()
            live = execute(
                "SELECT * FROM cpw.dbx_d1111_before.billing__" + table, step="input-parity"
            )
            assert [column.lower() for column in live["columns"]] == columns
            old = (len(old_rows), row_hash(old_rows, columns, char_columns))
            baseline = (len(live["rows"]), row_hash(live["rows"], columns, char_columns))
            evidence[table] = {
                "emulator_count": old[0],
                "baseline_count": baseline[0],
                "emulator_hash": old[1],
                "baseline_hash": baseline[1],
                "char_columns": sorted(char_columns),
                "statement_id": live["statement_id"],
            }
            assert old == baseline, f"input mismatch for {table}: {evidence[table]}"
            assert row_counts(old_rows, columns, char_columns) == row_counts(
                live["rows"], columns, char_columns
            ), f"input row mismatch for {table} despite matching hash"
    return evidence

#!/usr/bin/env python3
"""Create the source database, load extracts, and replay the package catalog."""

from __future__ import annotations

import argparse
import importlib
import os
import re
import sys
from pathlib import Path
from typing import Any

import pymssql
import yaml

SNOWFLAKE_ROOT = Path(__file__).resolve().parents[1]
if str(SNOWFLAKE_ROOT) not in sys.path:
    sys.path.insert(0, str(SNOWFLAKE_ROOT))

run_package = importlib.import_module("source.replay.ssis_replay").run_package

SOURCE = Path(__file__).resolve().parent
DATABASE = "OtterWorksUBW"
DDL_ORDER = ("stg.sql", "dim.sql", "fact.sql", "mart.sql", "ops.sql")
PACKAGE_ORDER = (
    "pkg_billing_core",
    "pkg_billing_usage",
    "pkg_billing_invoices",
    "pkg_auth_users",
    "pkg_auth_memberships",
    "pkg_documents",
    "pkg_document_versions",
    "pkg_files",
    "pkg_file_versions",
    "pkg_collaboration",
    "pkg_audit",
    "pkg_analytics",
)


def connect(database: str = DATABASE) -> Any:
    return pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("UBW_SQL_PORT", "14333")),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ.get("UBW_SQL_PASSWORD", "OtterUbw_2016dev"),
        database=database,
        autocommit=True,
    )


def split_batches(sql: str) -> list[str]:
    return [batch.strip() for batch in re.split(r"(?im)^\s*GO\s*$", sql) if batch.strip()]


def reset_database() -> None:
    connection = connect("master")
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            IF DB_ID(N'{DATABASE}') IS NOT NULL
            BEGIN
                ALTER DATABASE [{DATABASE}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
                DROP DATABASE [{DATABASE}];
            END;
            CREATE DATABASE [{DATABASE}];
            """
        )
        cursor.close()
    finally:
        connection.close()


def apply_sql_files(cursor: Any, paths: list[Path]) -> None:
    for path in paths:
        content = path.read_text(encoding="utf-8")
        for batch in split_batches(content):
            cursor.execute(batch)


def _load_jobs(cursor: Any) -> int:
    jobs_path = SOURCE / "agent" / "jobs.yaml"
    catalog = yaml.safe_load(jobs_path.read_text(encoding="utf-8"))
    count = 0
    for job in catalog["jobs"]:
        schedule = job["schedule"]
        steps = job["steps"]
        for index, step in enumerate(steps):
            cursor.execute(
                """
                INSERT INTO ops.agent_jobs (
                    job_name, step_id, step_name, subsystem, command,
                    on_success_action, on_fail_action, schedule_name,
                    schedule_freq, schedule_detail, active_start_time,
                    enabled, owner_login, loaded_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, GETDATE()
                )
                """,
                (
                    job["name"],
                    step["id"],
                    step["name"],
                    step["subsystem"],
                    step["command"],
                    step.get(
                        "on_success",
                        "next_step" if index < len(steps) - 1 else "quit_success",
                    ),
                    step.get("on_fail", "quit_failure"),
                    schedule["name"],
                    schedule["freq"],
                    schedule["detail"],
                    schedule["active_start_time"],
                    job["owner"],
                ),
            )
            count += 1
    return count


def load_database() -> None:
    reset_database()
    connection = connect()
    try:
        cursor = connection.cursor()
        ddl_paths = [SOURCE / "ddl" / filename for filename in DDL_ORDER]
        apply_sql_files(cursor, ddl_paths)
        procedure_paths = sorted((SOURCE / "procs").glob("usp_*.sql"))
        if len(procedure_paths) != 25:
            raise RuntimeError(
                f"Expected 25 source procedures, found {len(procedure_paths)} under source/procs"
            )
        apply_sql_files(cursor, procedure_paths)
        step_count = _load_jobs(cursor)
        print(f"Loaded {step_count} SQL Agent steps")
        for name in PACKAGE_ORDER:
            print(f"Replaying {name}")
            run_package(name, connection)
        cursor.close()
    finally:
        connection.close()


def _ddl_tables() -> list[tuple[str, str]]:
    tables: list[tuple[str, str]] = []
    for path in (SOURCE / "ddl").glob("*.sql"):
        sql = path.read_text(encoding="utf-8")
        tables.extend(
            (schema.lower(), name.lower())
            for schema, name in re.findall(
                r"CREATE TABLE\s+([a-zA-Z_]\w*)\.([a-zA-Z_]\w*)\s*\(",
                sql,
                re.IGNORECASE,
            )
        )
    order = {schema: index for index, schema in enumerate(("stg", "dim", "fact", "mart", "ops"))}
    return sorted(tables, key=lambda item: (order.get(item[0], 99), item[1]))


def print_counts() -> None:
    connection = connect()
    totals = {schema: 0 for schema in ("stg", "dim", "fact", "mart", "ops")}
    try:
        cursor = connection.cursor()
        for schema, table in _ddl_tables():
            cursor.execute(f"SELECT COUNT_BIG(*) FROM [{schema}].[{table}]")
            row_count = int(cursor.fetchone()[0])
            totals[schema] += row_count
            print(f"{schema}.{table}: {row_count}")
        for schema, total in totals.items():
            print(f"{schema} total: {total}")
        cursor.close()
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the SQL Server source fixture.")
    parser.add_argument("--counts", action="store_true")
    args = parser.parse_args(argv)
    if args.counts:
        print_counts()
    else:
        load_database()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

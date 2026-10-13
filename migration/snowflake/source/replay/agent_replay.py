#!/usr/bin/env python3
"""Replay SQL Agent steps against the source database."""

from __future__ import annotations

import argparse
import importlib
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pymssql
import yaml

SNOWFLAKE_ROOT = Path(__file__).resolve().parents[2]
if str(SNOWFLAKE_ROOT) not in sys.path:
    sys.path.insert(0, str(SNOWFLAKE_ROOT))

run_package = importlib.import_module("source.replay.ssis_replay").run_package

SOURCE = SNOWFLAKE_ROOT / "source"


def _connect() -> Any:
    return pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("UBW_SQL_PORT", "14333")),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ.get("UBW_SQL_PASSWORD", "OtterUbw_2016dev"),
        database=os.environ.get("UBW_SQL_DATABASE", "OtterWorksUBW"),
        autocommit=True,
    )


def _server_now(connection: Any) -> datetime:
    cursor = connection.cursor()
    cursor.execute("SELECT GETDATE()")
    row = cursor.fetchone()
    cursor.close()
    if row is None:
        raise RuntimeError("SQL Server did not return its local time")
    return row[0]


def _yaml_catalog() -> list[dict[str, Any]]:
    return yaml.safe_load((SOURCE / "agent" / "jobs.yaml").read_text(encoding="utf-8"))["jobs"]


def _job_steps(connection: Any, job_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT step_id, step_name, subsystem, command, on_success_action, on_fail_action
        FROM ops.agent_jobs
        WHERE job_name = %s
        ORDER BY step_id
        """,
        (job_name,),
    )
    rows = cursor.fetchall()
    cursor.close()
    catalog = _yaml_catalog()
    job = next((item for item in catalog if item["name"] == job_name), None)
    if job is None:
        raise ValueError(f"Unknown SQL Agent job {job_name!r}")
    if rows:
        steps = [
            {
                "id": int(row[0]),
                "name": row[1],
                "subsystem": row[2],
                "command": row[3],
                "on_success": row[4],
                "on_fail": row[5],
            }
            for row in rows
        ]
    else:
        steps = job["steps"]
    return steps, job


def _all_steps(connection: Any | None = None) -> list[tuple[str, int, str, str]]:
    if connection is not None:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT job_name, step_id, step_name, subsystem "
            "FROM ops.agent_jobs ORDER BY job_name, step_id"
        )
        rows = cursor.fetchall()
        cursor.close()
        if rows:
            return [(str(row[0]), int(row[1]), str(row[2]), str(row[3])) for row in rows]
    return [
        (job["name"], step["id"], step["name"], step["subsystem"])
        for job in _yaml_catalog()
        for step in job["steps"]
    ]


def _record_history(
    connection: Any,
    job_name: str,
    step: dict[str, Any],
    business_date: date,
    run_status: int,
    started: datetime,
    duration: int,
    message: str | None,
) -> None:
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO ops.agent_job_history (
            job_name, step_id, step_name, business_date, run_status,
            run_date, run_time, run_duration, message
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            job_name,
            step["id"],
            step["name"],
            business_date,
            run_status,
            int(started.strftime("%Y%m%d")),
            int(started.strftime("%H%M%S")),
            duration,
            message,
        ),
    )
    cursor.close()


def _duration_hhmmss(seconds: float) -> int:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return int(f"{hours:02d}{minutes:02d}{seconds:02d}")


def _run_step(
    connection: Any,
    job_name: str,
    step: dict[str, Any],
    business_date: date,
) -> None:
    started = _server_now(connection)
    monotonic_start = time.monotonic()
    try:
        subsystem = str(step["subsystem"]).upper()
        command = str(step["command"])
        if subsystem == "SSIS":
            match = re.search(r"(pkg_[a-z_]+\.dtsx)", command)
            if match is None:
                raise ValueError(f"Could not find an SSIS package in step {step['name']}")
            run_package(match.group(1), connection, business_date)
        elif subsystem == "TSQL":
            cursor = connection.cursor()
            batch = f"DECLARE @business_date date = '{business_date.isoformat()}';\n{command}"
            cursor.execute(batch)  # nosemgrep: python.lang.security.audit.formatted-sql-query.formatted-sql-query, python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query  # noqa: E501
            cursor.close()
        else:
            raise ValueError(f"Unsupported SQL Agent subsystem {subsystem}")
        _record_history(
            connection,
            job_name,
            step,
            business_date,
            1,
            started,
            _duration_hhmmss(time.monotonic() - monotonic_start),
            None,
        )
    except Exception as error:
        _record_history(
            connection,
            job_name,
            step,
            business_date,
            0,
            started,
            _duration_hhmmss(time.monotonic() - monotonic_start),
            str(error)[:4000],
        )
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay a SQL Agent job from the source catalog.")
    parser.add_argument("--job")
    parser.add_argument("--business-date", type=date.fromisoformat)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if not args.list and (not args.job or args.business_date is None):
        parser.error("--job and --business-date are required unless --list is used")
    connection = _connect()
    try:
        if args.list:
            for job_name, step_id, step_name, subsystem in _all_steps(connection):
                print(f"{job_name} [{step_id}] {subsystem}: {step_name}")
            return 0
        steps, _job = _job_steps(connection, args.job)
        for step in steps:
            print(f"Running {args.job} [{step['id']}] {step['name']}")
            _run_step(connection, args.job, step, args.business_date)
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

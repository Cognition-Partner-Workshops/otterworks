"""Inspect and operate the doc_usage_dashboard refresh drill."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'workloads/attribution'))
import sf_attribution as attr  # noqa: E402

WORKLOAD = 'doc_usage_dashboard'
SWITCH_NAME = 'REFRESH_DOC_USAGE_DASHBOARD'
TERMINAL_STATES = {'SUCCEEDED', 'FAILED', 'CANCELLED', 'SKIPPED'}


def object_names() -> dict[str, str]:
    return attr.names([WORKLOAD])


def connection_parameters(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    session_url = env.get('SESSION_URL')
    if not session_url:
        raise ValueError('SESSION_URL is required')
    endpoint = attr.Endpoint.from_csid('cs_doc_usage_dashboard_account_usage', WORKLOAD)
    params = attr.connection_params(
        endpoint,
        account=env['SNOWFLAKE_ACCOUNT'],
        private_key_file=env['SNOWFLAKE_PRIVATE_KEY_FILE'],
        phase='dev',
        commit=attr.current_commit(str(ROOT)),
        run_id=attr.make_run_id(WORKLOAD, 'dev'),
        session_url=session_url,
        role=env['SNOWFLAKE_ROLE'],
        schema='OPS',
    )
    params['user'] = env['SNOWFLAKE_USER']
    return params


def connect():
    import snowflake.connector

    os.environ.pop('SNOWFLAKE_HOST', None)
    return snowflake.connector.connect(**connection_parameters())


def freshness_sql() -> str:
    return (
        'SELECT TABLE_NAME, TASK_NAME, LAST_REFRESHED_AT, AGE_MINUTES, MAX_AGE_MINUTES, IS_STALE, CHECKED_AT '
        f'FROM {object_names()["ops_schema_" + WORKLOAD]}.WORKLOAD_FRESHNESS ORDER BY TABLE_NAME'
    )


def task_history_sql(limit: int = 24) -> str:
    if limit < 1:
        raise ValueError('limit must be a positive integer')
    names = object_names()
    return (
        'SELECT NAME, STATE, SCHEDULED_TIME, QUERY_START_TIME, COMPLETED_TIME, QUERY_ID, ERROR_CODE, '
        'ERROR_MESSAGE, RUN_ID '
        f"FROM TABLE({names[f'db_{WORKLOAD}']}.INFORMATION_SCHEMA.TASK_HISTORY("
        f"TASK_NAME=>'{attr.task_name(WORKLOAD).split('.')[-1]}',"
        "SCHEDULED_TIME_RANGE_START=>DATEADD('hour', -24, CURRENT_TIMESTAMP()),"
        "SCHEDULED_TIME_RANGE_END=>DATEADD('hour', 24, CURRENT_TIMESTAMP()),"
        f'RESULT_LIMIT=>{limit})) ORDER BY SCHEDULED_TIME DESC'
    )


def task_state_sql() -> str:
    names = object_names()
    return (
        f"SHOW TASKS LIKE '{attr.task_name(WORKLOAD).split('.')[-1]}' "
        f"IN SCHEMA {names[f'db_{WORKLOAD}']}.ANALYTICS"
    )


def fault_read_sql() -> str:
    return (
        'SELECT SWITCH_NAME, ARMED, NOTE, CHANGED_AT, CHANGED_BY '
        f'FROM {object_names()["ops_schema_" + WORKLOAD]}.FAULT_SWITCH WHERE SWITCH_NAME = %s'
    )


def fault_update_sql(armed: bool) -> str:
    value = 'TRUE' if armed else 'FALSE'
    return (
        f'UPDATE {object_names()["ops_schema_" + WORKLOAD]}.FAULT_SWITCH '
        f'SET ARMED = {value}, NOTE = COALESCE(%s, NOTE), CHANGED_AT = CURRENT_TIMESTAMP(), CHANGED_BY = %s '
        'WHERE SWITCH_NAME = %s'
    )


def run_task_history_sql() -> str:
    names = object_names()
    return (
        'SELECT NAME, STATE, SCHEDULED_TIME, QUERY_START_TIME, COMPLETED_TIME, QUERY_ID, ERROR_CODE, '
        'ERROR_MESSAGE, RUN_ID '
        f"FROM TABLE({names[f'db_{WORKLOAD}']}.INFORMATION_SCHEMA.TASK_HISTORY("
        f"TASK_NAME=>'{attr.task_name(WORKLOAD).split('.')[-1]}',"
        'SCHEDULED_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s),'
        'SCHEDULED_TIME_RANGE_END=>CURRENT_TIMESTAMP(), RESULT_LIMIT=>10)) ORDER BY SCHEDULED_TIME'
    )


def _stale_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.upper() in {'TRUE', '1', 'YES'}
    return bool(value)


def freshness_is_stale(row: Mapping[str, Any] | tuple[Any, ...]) -> bool:
    if isinstance(row, Mapping):
        refreshed_at = row.get('LAST_REFRESHED_AT')
        stale = row.get('IS_STALE')
    else:
        refreshed_at, stale = row[2], row[5]
    return refreshed_at is None or _stale_value(stale)


def freshness_exit_code(rows: list[Mapping[str, Any]] | list[tuple[Any, ...]]) -> int:
    return 3 if any(freshness_is_stale(row) for row in rows) else 0


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.isoformat() + 'Z'
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _column_names(cursor) -> list[str]:
    return [
        description.name if hasattr(description, 'name') else description[0]
        for description in cursor.description
    ]


def _json_rows(cursor, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    columns = _column_names(cursor)
    return [
        {column: _json_value(value) for column, value in zip(columns, row)}
        for row in rows
    ]


def freshness(cursor) -> tuple[list[dict[str, Any]], int]:
    rows = cursor.execute(freshness_sql()).fetchall()
    formatted = _json_rows(cursor, rows)
    return formatted, freshness_exit_code(formatted)


def task_history(cursor, limit: int) -> dict[str, Any]:
    history = cursor.execute(task_history_sql(limit)).fetchall()
    history_rows = _json_rows(cursor, history)
    tasks = cursor.execute(task_state_sql()).fetchall()
    return {'history': history_rows, 'tasks': _json_rows(cursor, tasks)}


def fault(cursor, action: str, note: str | None, session_url: str) -> dict[str, Any]:
    if action in {'arm', 'disarm'}:
        cursor.execute(
            fault_update_sql(action == 'arm'),
            (note, session_url, SWITCH_NAME),
        )
    rows = cursor.execute(fault_read_sql(), (SWITCH_NAME,)).fetchall()
    if not rows:
        raise RuntimeError(f'Fault switch row not found: {SWITCH_NAME}')
    return _json_rows(cursor, rows)[0]


def run_task(cursor, wait: bool) -> tuple[dict[str, Any], int]:
    task = attr.task_name(WORKLOAD)
    started = cursor.execute('SELECT CURRENT_TIMESTAMP()').fetchone()[0]
    cursor.execute(f'EXECUTE TASK {task}')
    if not wait:
        return {'task': task, 'started_at': _json_value(started), 'state': 'EXECUTED'}, 0

    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        rows = cursor.execute(run_task_history_sql(), (started,)).fetchall()
        columns = _column_names(cursor)
        run_rows = [
            dict(zip(columns, row))
            for row in rows
            if row[1] in TERMINAL_STATES
        ]
        if run_rows:
            result = {key: _json_value(value) for key, value in run_rows[0].items()}
            return result, 0 if result['STATE'] == 'SUCCEEDED' else 1
        time.sleep(5)
    return {'task': task, 'started_at': _json_value(started), 'error': 'Task did not finish within 15 minutes'}, 1


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, default=_json_value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('freshness')
    history = commands.add_parser('task-history')
    history.add_argument('--limit', type=int, default=24)
    fault_parser = commands.add_parser('fault')
    fault_parser.add_argument('action', choices=('status', 'arm', 'disarm'))
    fault_parser.add_argument('--note')
    run = commands.add_parser('run-task')
    run.add_argument('--wait', action='store_true')
    args = parser.parse_args(argv)

    try:
        con = connect()
        try:
            cursor = con.cursor()
            cursor.execute('USE SECONDARY ROLES NONE')
            if args.command == 'freshness':
                result, status = freshness(cursor)
            elif args.command == 'task-history':
                result, status = task_history(cursor, args.limit), 0
            elif args.command == 'fault':
                result = fault(cursor, args.action, args.note, os.environ['SESSION_URL'])
                status = 0
            else:
                result, status = run_task(cursor, args.wait)
            _print_json(result)
            return status
        finally:
            con.close()
    except (KeyError, ValueError) as error:
        _print_json({'error': str(error)})
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

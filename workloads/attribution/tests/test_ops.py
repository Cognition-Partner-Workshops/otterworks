from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'snowflake'))
import ops  # noqa: E402


def test_freshness_exit_code_marks_null_refresh_stale():
    rows = [
        {'TABLE_NAME': 'fresh', 'LAST_REFRESHED_AT': datetime.now(timezone.utc), 'IS_STALE': False},
        {'TABLE_NAME': 'never', 'LAST_REFRESHED_AT': None, 'IS_STALE': False},
    ]
    assert ops.freshness_exit_code(rows[:1]) == 0
    assert ops.freshness_exit_code(rows[1:]) == 3
    assert ops.freshness_exit_code(rows) == 3


def test_ops_sql_uses_attribution_names():
    names = ops.attr.names([ops.WORKLOAD])
    assert names['ops_schema_doc_usage_dashboard'] in ops.freshness_sql()
    assert names['db_doc_usage_dashboard'] in ops.task_history_sql()
    assert names['ops_schema_doc_usage_dashboard'] in ops.fault_read_sql()


def test_fault_update_sql_sets_armed_state_and_session_actor():
    arm = ops.fault_update_sql(True)
    disarm = ops.fault_update_sql(False)
    assert 'SET ARMED = TRUE' in arm
    assert 'SET ARMED = FALSE' in disarm
    assert 'CHANGED_BY = %s' in arm
    assert 'CHANGED_AT = CURRENT_TIMESTAMP()' in arm
    assert 'NOTE = COALESCE(%s, NOTE)' in disarm


def test_ops_requires_session_url_before_connecting():
    with pytest.raises(ValueError, match='SESSION_URL'):
        ops.connection_parameters({})


def test_ops_main_refuses_session_without_session_url(monkeypatch, capsys):
    monkeypatch.setattr(ops, 'connect', lambda: ops.connection_parameters({}))
    assert ops.main(['freshness']) == 2
    assert '"error": "SESSION_URL is required"' in capsys.readouterr().out


def test_json_rows_formats_timestamps_as_utc():
    class Cursor:
        description = [('CHECKED_AT',)]

    rows = ops._json_rows(Cursor(), [(datetime(2026, 11, 4, 12, tzinfo=timezone.utc),)])
    assert rows == [{'CHECKED_AT': '2026-11-04T12:00:00Z'}]

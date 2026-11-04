import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

SPEC = importlib.util.spec_from_file_location("measure", Path(__file__).parents[1] / "rightsize_measure.py")
measure = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measure)


def record():
    return {"run_id": "test", "warehouse": "WH_TEST", "started_at": "2026-11-04T22:00:00Z"}


def test_reported_zero_is_not_pending():
    con = Mock()
    con.cursor.return_value.fetchone.side_effect = [(2, 1.25), (1, 0)]
    assert measure.usage(con, record()) == (2, 1.25, 0, "ACCOUNT_USAGE")


def test_fallback_and_pending_credits():
    con = Mock()
    cur = con.cursor.return_value
    cur.fetchone.side_effect = [(0, None), (0, None)]
    cur.fetchall.return_value = [('{}', 999), ('bad', 100), ('{"run_id":"test"}', 1250)]
    assert measure.usage(con, record()) == (1, 1.25, "pending", "INFORMATION_SCHEMA")
    assert "END_TIME_RANGE_START=>TO_TIMESTAMP_LTZ(%s)" in cur.execute.call_args_list[1].args[0]


def test_empty_history_is_pending():
    con = Mock()
    con.cursor.return_value.fetchone.side_effect = [(0, None), (0, None)]
    con.cursor.return_value.fetchall.return_value = []
    assert measure.usage(con, record()) == ("pending", "pending", "pending", "INFORMATION_SCHEMA")


def test_history_errors_are_not_reported_as_zero():
    con = Mock()
    con.cursor.return_value.execute.side_effect = RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        measure.usage(con, record())


def test_declared_restores_after_build_failure(tmp_path):
    args = SimpleNamespace(workload="doc_search_api", label="declared", code_root=tmp_path,
                           results=tmp_path / "results.json")
    con = Mock()
    with patch.object(measure.attr, "current_commit", return_value="a" * 40), \
            patch.object(measure, "settings", side_effect=[{"size": "Large"}, {"size": "X-Small"}]), \
            patch.object(measure, "build", side_effect=RuntimeError("build failed")):
        with pytest.raises(RuntimeError, match="build failed"):
            measure.run(args, con)
    assert "'XSMALL'" in con.cursor.return_value.execute.call_args.args[0]
    assert json.loads(args.results.read_text())[0]["status"] == "failed"


def test_successful_run_records_settings(tmp_path):
    args = SimpleNamespace(workload="churn_model", label="before", code_root=tmp_path,
                           results=tmp_path / "results.json")
    with patch.object(measure.attr, "current_commit", return_value="a" * 40), \
            patch.object(measure, "settings", return_value={"size": "X-Small"}), \
            patch.object(measure, "build") as build:
        measure.run(args, Mock())
    saved = json.loads(args.results.read_text())[0]
    assert saved["status"] == "succeeded"
    assert saved["settings"]["size"] == "X-Small"
    assert build.call_args.args[2] == saved["run_id"]

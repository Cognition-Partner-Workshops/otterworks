from __future__ import annotations

import json
import logging
import types

import pendulum

from otterworks_etl.common import StructuredFormatter, get_logger, log_event, log_task_failure
from otterworks_etl.common.callbacks import failure_event


def _record(logger_name="otterworks_etl.test", msg="hello", **extra):
    return logging.LogRecord(logger_name, logging.WARNING, __file__, 1, msg, None, None)


def test_get_logger_returns_the_named_logger():
    assert get_logger("otterworks_etl.x") is logging.getLogger("otterworks_etl.x")


def test_formatter_renders_plain_records_as_json():
    out = json.loads(StructuredFormatter().format(_record()))
    assert out["level"] == "WARNING"
    assert out["logger"] == "otterworks_etl.test"
    assert out["message"] == "hello"
    assert out["timestamp"].endswith("+00:00")


def test_formatter_includes_extra_fields_and_exceptions():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord("n", logging.ERROR, __file__, 1, "m", None, sys.exc_info())
    record.rows = 7
    out = json.loads(StructuredFormatter().format(record))
    assert out["rows"] == 7
    assert "ValueError: boom" in out["exc_info"]


def test_log_event_message_is_json_and_formatter_flattens_it(caplog):
    logger = get_logger("otterworks_etl.test")
    with caplog.at_level(logging.INFO, logger="otterworks_etl.test"):
        log_event(logger, "rows_loaded", rows=3, table="analytics_daily_summary")
    (record,) = caplog.records
    assert json.loads(record.getMessage()) == {
        "event": "rows_loaded",
        "rows": 3,
        "table": "analytics_daily_summary",
    }
    out = json.loads(StructuredFormatter().format(record))
    assert out["event"] == "rows_loaded" and out["rows"] == 3 and "message" not in out


def test_payload_fields_never_replace_the_envelope(caplog):
    logger = get_logger("otterworks_etl.test")
    with caplog.at_level(logging.ERROR, logger="otterworks_etl.test"):
        log_event(logger, "job_state", logging.ERROR, timestamp="2020-01-01", state="failed")
    (record,) = caplog.records
    record.level = "INFO"
    record.logger = "spoofed"
    out = json.loads(StructuredFormatter().format(record))
    assert out["level"] == "ERROR"
    assert out["logger"] == "otterworks_etl.test"
    assert out["timestamp"] != "2020-01-01" and out["timestamp"].endswith("+00:00")
    assert out["field_timestamp"] == "2020-01-01"
    assert out["field_level"] == "INFO" and out["field_logger"] == "spoofed"
    assert out["event"] == "job_state" and out["state"] == "failed"
    assert json.loads(record.getMessage()) == {
        "event": "job_state",
        "timestamp": "2020-01-01",
        "state": "failed",
    }


def _context():
    ti = types.SimpleNamespace(
        dag_id="otterworks_analytics_etl",
        task_id="extract_from_sqs",
        map_index=-1,
        try_number=4,
        max_tries=3,
        log_url="http://localhost:8280/log?dag_id=otterworks_analytics_etl",
    )
    return {
        "task_instance": ti,
        "run_id": "scheduled__2026-10-06T02:00:00+00:00",
        "logical_date": pendulum.datetime(2026, 10, 6, 2, tz="UTC"),
        "exception": TimeoutError("SQS receive timed out"),
    }


def test_failure_event_fields():
    assert failure_event(_context()) == {
        "dag_id": "otterworks_analytics_etl",
        "task_id": "extract_from_sqs",
        "run_id": "scheduled__2026-10-06T02:00:00+00:00",
        "map_index": -1,
        "logical_date": "2026-10-06T02:00:00+00:00",
        "try_number": 4,
        "max_tries": 3,
        "exception_type": "TimeoutError",
        "exception": "SQS receive timed out",
        "log_url": "http://localhost:8280/log?dag_id=otterworks_analytics_etl",
    }


def test_failure_callback_logs_one_structured_error(caplog):
    with caplog.at_level(logging.ERROR, logger="otterworks_etl.common.callbacks"):
        log_task_failure(_context())
    (record,) = caplog.records
    assert record.levelno == logging.ERROR
    payload = json.loads(record.getMessage())
    assert payload["event"] == "task_failed"
    assert payload["task_id"] == "extract_from_sqs"


def test_failure_callback_never_raises_on_odd_context(caplog):
    class Exploding(dict):
        def get(self, key, default=None):
            raise RuntimeError("bad context")

    with caplog.at_level(logging.ERROR, logger="otterworks_etl.common.callbacks"):
        log_task_failure(Exploding())
        log_task_failure({})
    first, second = (json.loads(r.getMessage()) for r in caplog.records)
    assert first == {"event": "task_failed", "callback_error": "RuntimeError('bad context')"}
    assert second["event"] == "task_failed" and second["dag_id"] is None

"""Failure callback shared by every task (etl/ETL_UPGRADE_GUIDE.md, axis 9)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from otterworks_etl.common.log import get_logger, log_event

logger = get_logger(__name__)


def _attr(obj: Any, name: str) -> Any:
    return getattr(obj, name, None) if obj is not None else None


def failure_event(context: Mapping[str, Any]) -> dict[str, Any]:
    """Build the ``task_failed`` fields from an Airflow task context."""
    ti = context.get("task_instance") or context.get("ti")
    dag_run = context.get("dag_run")
    exc = context.get("exception")
    logical_date = context.get("logical_date")
    return {
        "dag_id": _attr(ti, "dag_id") or _attr(context.get("dag"), "dag_id"),
        "task_id": _attr(ti, "task_id") or _attr(context.get("task"), "task_id"),
        "run_id": context.get("run_id") or _attr(dag_run, "run_id"),
        "map_index": _attr(ti, "map_index"),
        "logical_date": logical_date.isoformat() if logical_date is not None else None,
        "try_number": _attr(ti, "try_number"),
        "max_tries": _attr(ti, "max_tries"),
        "exception_type": type(exc).__name__ if exc is not None else None,
        "exception": str(exc) if exc is not None else None,
        "log_url": _attr(ti, "log_url"),
    }


def log_task_failure(context: Mapping[str, Any]) -> None:
    """``on_failure_callback``: log one structured ``task_failed`` event; never raises."""
    try:
        fields = failure_event(context)
    except Exception as exc:  # a broken callback must not mask the task failure
        fields = {"callback_error": repr(exc)}
    log_event(logger, "task_failed", level=logging.ERROR, **fields)

"""Run date with legacy semantics (ticket decision d-run-date: keep ds = run date).

The cron scripts compute ``ds = datetime.now(utc).date()``, i.e. the day they run. Airflow's
``ds`` is the logical date, which for a scheduled run is the start of the interval (the day
before). The legacy value is the later of ``logical_date`` and ``data_interval_end``: for a
scheduled or backfill run that is the scheduled fire time, for a manual run the trigger time.
Both are fixed per DAG run, so retries and clears see the same date. ``dag_run.conf["run_date"]``
(YYYY-MM-DD) overrides it for replays such as parity runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

RUN_DATE_CONF_KEY = "run_date"


def _utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        raise ValueError(f"naive datetime {value!r}; Airflow context dates are timezone-aware")
    return value.astimezone(UTC).date()


def legacy_run_date(context: Mapping[str, Any]) -> str:
    """Return the legacy ``ds`` (``YYYY-MM-DD``, UTC) for an Airflow task context."""
    dag_run = context.get("dag_run")
    conf = getattr(dag_run, "conf", None) or {}
    override = conf.get(RUN_DATE_CONF_KEY)
    if override is not None:
        return date.fromisoformat(str(override)).isoformat()

    candidates = [
        value
        for value in (context.get("logical_date"), context.get("data_interval_end"))
        if value is not None
    ]
    if not candidates:
        raise KeyError("context has neither logical_date nor data_interval_end")
    return max(_utc_date(value) for value in candidates).isoformat()

"""Decision d-run-date: DAGs keep the legacy ds (the UTC day the job runs)."""

from __future__ import annotations

import types

import pendulum
import pytest
from airflow.timetables.base import DataInterval, TimeRestriction
from airflow.timetables.interval import CronDataIntervalTimetable

from otterworks_etl.common import LEGACY_SCHEDULES, legacy_run_date

UTC = pendulum.UTC


def _timetable(dag_id):
    return CronDataIntervalTimetable(LEGACY_SCHEDULES[dag_id], UTC)


def _utc(*args):
    return pendulum.datetime(*args, tz=UTC)


def _scheduled_context(dag_id, previous_end):
    timetable = _timetable(dag_id)
    previous = DataInterval(timetable._get_prev(previous_end), previous_end)
    info = timetable.next_dagrun_info(
        last_automated_data_interval=previous,
        restriction=TimeRestriction(earliest=None, latest=None, catchup=True),
    )
    return {
        "logical_date": info.logical_date,
        "data_interval_start": info.data_interval.start,
        "data_interval_end": info.data_interval.end,
        "ds": info.logical_date.strftime("%Y-%m-%d"),
    }


def _manual_context(dag_id, triggered_at):
    interval = _timetable(dag_id).infer_manual_data_interval(run_after=triggered_at)
    return {
        "logical_date": triggered_at,
        "data_interval_start": interval.start,
        "data_interval_end": interval.end,
        "dag_run": types.SimpleNamespace(conf={}),
    }


@pytest.mark.parametrize(
    ("dag_id", "previous_end", "airflow_ds", "legacy_ds"),
    [
        # analytics_daily.py at 02:00 on 2026-10-07 processes ds=2026-10-07
        ("otterworks_analytics_etl", _utc(2026, 10, 6, 2), "2026-10-06", "2026-10-07"),
        ("otterworks_storage_cleanup", _utc(2026, 10, 6, 2, 30), "2026-10-06", "2026-10-07"),
        ("otterworks_user_activity_report", _utc(2026, 10, 6, 5), "2026-10-06", "2026-10-07"),
        # weekly jobs on Sunday 2026-10-11 use that Sunday, not the previous one
        ("otterworks_audit_archive", _utc(2026, 10, 4, 3), "2026-10-04", "2026-10-11"),
        ("otterworks_search_reindex", _utc(2026, 10, 4, 4), "2026-10-04", "2026-10-11"),
    ],
)
def test_scheduled_run_uses_the_day_it_fires(dag_id, previous_end, airflow_ds, legacy_ds):
    context = _scheduled_context(dag_id, previous_end)
    assert context["ds"] == airflow_ds
    assert legacy_run_date(context) == legacy_ds


@pytest.mark.parametrize("hour", [0, 1, 2, 14, 23])
def test_manual_trigger_uses_the_trigger_day(hour):
    context = _manual_context("otterworks_analytics_etl", _utc(2026, 10, 7, hour, 15))
    assert legacy_run_date(context) == "2026-10-07"


def test_non_utc_dates_are_converted_to_utc():
    late_evening_la = pendulum.datetime(2026, 10, 6, 20, tz="America/Los_Angeles")
    assert legacy_run_date({"logical_date": late_evening_la}) == "2026-10-07"


def test_conf_override_for_replays():
    context = _manual_context("otterworks_analytics_etl", pendulum.datetime(2026, 10, 7, tz=UTC))
    context["dag_run"].conf = {"run_date": "2026-06-30"}
    assert legacy_run_date(context) == "2026-06-30"
    context["dag_run"].conf = {"run_date": "30/06/2026"}
    with pytest.raises(ValueError):
        legacy_run_date(context)


def test_missing_dates_fail_loudly():
    with pytest.raises(KeyError):
        legacy_run_date({})

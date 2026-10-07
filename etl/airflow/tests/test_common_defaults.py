from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator

from otterworks_etl.common import (
    DEFAULT_OWNER,
    LEGACY_SCHEDULES,
    default_args,
    log_task_failure,
    otterworks_dag_kwargs,
)
from tests.conftest import LEGACY_CRONTAB

START = pendulum.datetime(2026, 1, 1, tz="UTC")


def test_default_args_match_the_ticket():
    args = default_args()
    assert args["owner"] == DEFAULT_OWNER
    assert args["retries"] == 3
    assert args["retry_delay"] == timedelta(minutes=5)
    assert args["retry_exponential_backoff"] is True
    assert args["max_retry_delay"] == timedelta(minutes=30)
    assert args["on_failure_callback"] is log_task_failure
    assert args["email_on_failure"] is False


def test_default_args_overrides_do_not_leak():
    assert default_args(retries=5)["retries"] == 5
    assert default_args()["retries"] == 3


def test_dag_kwargs_merge_tags_and_task_overrides():
    kwargs = otterworks_dag_kwargs(tags=["analytics", "otterworks"], default_args={"retries": 1})
    assert kwargs["tags"] == ["otterworks", "analytics"]
    assert kwargs["max_active_runs"] == 1
    assert kwargs["catchup"] is False
    assert kwargs["default_args"]["retries"] == 1
    assert kwargs["default_args"]["max_retry_delay"] == timedelta(minutes=30)
    assert "schedule" not in kwargs


def test_operators_inherit_the_defaults():
    with DAG(
        "conventions_probe",
        schedule=LEGACY_SCHEDULES["otterworks_analytics_etl"],
        start_date=START,
        **otterworks_dag_kwargs(),
    ) as dag:
        task = PythonOperator(task_id="noop", python_callable=lambda: None)

    assert dag.max_active_runs == 1 and dag.catchup is False
    assert task.owner == DEFAULT_OWNER
    assert task.retries == 3
    assert task.retry_delay == timedelta(minutes=5)
    assert task.retry_exponential_backoff is True
    assert task.max_retry_delay == timedelta(minutes=30)
    assert task.on_failure_callback is log_task_failure


def test_legacy_schedules_mirror_the_crontab():
    lines = LEGACY_CRONTAB.read_text().splitlines()
    cron = {
        line.split()[6]: " ".join(line.split()[:5])
        for line in lines
        if line and not line.startswith("#")
    }
    assert cron == {
        "analytics_daily.py": LEGACY_SCHEDULES["otterworks_analytics_etl"],
        "audit_archive_weekly.py": LEGACY_SCHEDULES["otterworks_audit_archive"],
        "search_reindex_weekly.py": LEGACY_SCHEDULES["otterworks_search_reindex"],
        "storage_cleanup_daily.py": LEGACY_SCHEDULES["otterworks_storage_cleanup"],
        "user_activity_daily.py": LEGACY_SCHEDULES["otterworks_user_activity_report"],
    }

"""DAG-level and task-level defaults (etl/ETL_UPGRADE_GUIDE.md, axes 1 and 7)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from otterworks_etl.common.callbacks import log_task_failure

DEFAULT_OWNER = "otterworks-data"
DEFAULT_TAG = "otterworks"

# Legacy cron expressions from etl/crontab, keyed by target DAG id. Keeping the same wall-clock
# times preserves the legacy run date (see run_date.legacy_run_date).
LEGACY_SCHEDULES: dict[str, str] = {
    "otterworks_analytics_etl": "0 2 * * *",
    "otterworks_storage_cleanup": "30 2 * * *",
    "otterworks_user_activity_report": "0 5 * * *",
    "otterworks_audit_archive": "0 3 * * 0",
    "otterworks_search_reindex": "0 4 * * 0",
}


def default_args(**overrides: Any) -> dict[str, Any]:
    """Task defaults: 3 retries backing off exponentially from 5 to at most 30 minutes.

    Email/Slack/PagerDuty alerting needs real endpoints; until they exist the only failure
    callback is the structured log event. Add notifiers by passing a list, e.g.
    ``on_failure_callback=[log_task_failure, SlackNotifier(...)]``.
    """
    args: dict[str, Any] = {
        "owner": DEFAULT_OWNER,
        "depends_on_past": False,
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=30),
        "email_on_failure": False,
        "email_on_retry": False,
        "on_failure_callback": log_task_failure,
    }
    args.update(overrides)
    return args


def otterworks_dag_kwargs(
    *, tags: list[str] | tuple[str, ...] = (), **overrides: Any
) -> dict[str, Any]:
    """Keyword arguments for ``DAG(...)`` / ``@dag(...)``; ``schedule`` stays explicit per DAG.

    ``max_active_runs=1`` keeps runs from overlapping like the single cron host did, and
    ``catchup=False`` stops a new or unpaused DAG from replaying every interval since
    ``start_date``. Backfills stay available through ``airflow dags backfill``.
    """
    task_overrides = overrides.pop("default_args", {})
    kwargs: dict[str, Any] = {
        "default_args": default_args(**task_overrides),
        "max_active_runs": 1,
        "catchup": False,
        "tags": [DEFAULT_TAG, *(t for t in tags if t != DEFAULT_TAG)],
    }
    kwargs.update(overrides)
    return kwargs

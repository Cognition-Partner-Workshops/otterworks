"""Conventions every OtterWorks ETL DAG shares.

Defaults, logging, failure alerts, the legacy run date and S3 staging.
"""

from otterworks_etl.common.callbacks import log_task_failure
from otterworks_etl.common.dag_defaults import (
    DEFAULT_OWNER,
    DEFAULT_TAG,
    LEGACY_SCHEDULES,
    default_args,
    otterworks_dag_kwargs,
)
from otterworks_etl.common.log import StructuredFormatter, get_logger, log_event
from otterworks_etl.common.run_date import legacy_run_date
from otterworks_etl.common.staging import load_staged_json, stage_json, staging_key

__all__ = [
    "DEFAULT_OWNER",
    "DEFAULT_TAG",
    "LEGACY_SCHEDULES",
    "StructuredFormatter",
    "default_args",
    "get_logger",
    "legacy_run_date",
    "load_staged_json",
    "log_event",
    "log_task_failure",
    "otterworks_dag_kwargs",
    "stage_json",
    "staging_key",
]

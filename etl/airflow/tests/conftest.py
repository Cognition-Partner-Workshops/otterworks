from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "false")

AIRFLOW_ROOT = Path(__file__).resolve().parents[1]
DAGS_FOLDER = AIRFLOW_ROOT / "dags"
# etl/crontab before the cutover (etl/RUNBOOK.md §5); etl/crontab itself ends up empty.
LEGACY_CRONTAB = Path(
    os.environ.get(
        "OTTERWORKS_LEGACY_CRONTAB", AIRFLOW_ROOT.parent / "legacy-cron" / "crontab.pre-cutover"
    )
)


def _no_connection(*args, **kwargs):
    raise AssertionError(f"Connection/Variable read at DAG parse time: {args} {kwargs}")


@pytest.fixture(scope="session")
def dagbag():
    from airflow.hooks.base import BaseHook
    from airflow.models import DagBag, Variable

    with (
        mock.patch.object(BaseHook, "get_connection", side_effect=_no_connection),
        mock.patch.object(Variable, "get", side_effect=_no_connection),
    ):
        return DagBag(dag_folder=str(DAGS_FOLDER), include_examples=False, read_dags_from_db=False)

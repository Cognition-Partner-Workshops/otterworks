"""Every DAG in dags/ imports cleanly and follows otterworks_etl.common conventions."""

from __future__ import annotations

from datetime import timedelta

import pytest

from otterworks_etl.common import DEFAULT_TAG, log_task_failure
from tests.conftest import AIRFLOW_ROOT, DAGS_FOLDER
from tests.dag_static_checks import dag_calls_without_schedule, dag_files, top_level_hook_calls

DAG_FILES = dag_files(DAGS_FOLDER)


def _dags(dagbag):
    return sorted(dagbag.dags.values(), key=lambda d: d.dag_id)


def test_dag_folder_is_not_empty(dagbag):
    assert DAG_FILES, f"no DAG files under {DAGS_FOLDER}"
    assert dagbag.dags, "DagBag parsed no DAGs"


def test_dagbag_has_no_import_errors(dagbag):
    assert dagbag.import_errors == {}


def test_every_dag_file_defines_a_dag(dagbag):
    files_with_dags = {dag.fileloc for dag in dagbag.dags.values()}
    assert {str(p) for p in DAG_FILES} <= files_with_dags


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.name)
def test_no_hook_or_connection_calls_at_parse_time(path):
    assert top_level_hook_calls(path.read_text()) == []


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.name)
def test_schedule_is_explicit(path):
    assert dag_calls_without_schedule(path.read_text()) == []


def test_dags_have_owner_and_tags(dagbag):
    for dag in _dags(dagbag):
        assert dag.owner and dag.owner != "airflow", dag.dag_id
        assert DEFAULT_TAG in dag.tags, dag.dag_id
        assert dag.description or dag.doc_md, f"{dag.dag_id} has no description/doc_md"


def test_dags_do_not_overlap_or_catch_up(dagbag):
    for dag in _dags(dagbag):
        assert dag.max_active_runs == 1, dag.dag_id
        assert dag.catchup is False, dag.dag_id


def test_tasks_retry_with_backoff_and_alert(dagbag):
    for dag in _dags(dagbag):
        assert dag.tasks, f"{dag.dag_id} has no tasks"
        for task in dag.tasks:
            where = f"{dag.dag_id}.{task.task_id}"
            assert task.owner and task.owner != "airflow", where
            assert task.retries >= 1, where
            assert task.retry_delay >= timedelta(minutes=1), where
            assert task.retry_exponential_backoff, where
            assert task.max_retry_delay is not None, where
            callbacks = task.on_failure_callback
            callbacks = callbacks if isinstance(callbacks, list) else [callbacks]
            assert log_task_failure in callbacks, where


def test_image_wheel_ships_every_otterworks_etl_package():
    """The DAGs import the installed wheel, not this checkout; every subpackage must be in it."""
    from importlib.metadata import files

    shipped = {str(f) for f in files("otterworks-etl") or []}
    package_root = AIRFLOW_ROOT / "otterworks_etl"
    packages = sorted(
        str(init.relative_to(AIRFLOW_ROOT)) for init in package_root.rglob("__init__.py")
    )
    assert packages and [p for p in packages if p not in shipped] == []

"""The AST checks catch what they claim to catch."""

from __future__ import annotations

import textwrap

from tests.dag_static_checks import dag_calls_without_schedule, top_level_hook_calls

BAD = textwrap.dedent(
    """
    from airflow import DAG
    from airflow.decorators import dag, task
    from airflow.models import Variable
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    bucket = Variable.get("bucket")
    hook = S3Hook(aws_conn_id="aws_default")

    @dag(start_date=None)
    def bad():
        conn = BaseHook.get_connection("otterworks_postgres")

        @task
        def fine():
            return S3Hook().get_conn()

        fine()

    with DAG("also_bad") as d:
        pass

    @dag
    def bare():
        pass
    """
)

GOOD = textwrap.dedent(
    """
    from airflow.decorators import dag, task
    from airflow.providers.amazon.aws.hooks.s3 import S3Hook

    def _extract():
        return S3Hook(aws_conn_id="aws_default").list_keys("b")

    @dag(schedule=None)
    def good():
        @task
        def extract():
            return _extract()

        extract()

    good()
    """
)


def test_flags_parse_time_hooks_variables_and_connections():
    problems = top_level_hook_calls(BAD)
    assert [p.split(":")[0] for p in problems] == ["line 7", "line 8", "line 12"]


def test_flags_missing_schedule():
    assert [p.split(":")[0] for p in dag_calls_without_schedule(BAD)] == [
        "line 10",
        "line 20",
        "line 23",
    ]


def test_good_dag_passes():
    assert top_level_hook_calls(GOOD) == []
    assert dag_calls_without_schedule(GOOD) == []


DELEGATED = textwrap.dedent(
    """
    from airflow.decorators import dag, task
    from airflow.models import Variable
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    def _bucket():
        return Variable.get("bucket")

    def _rows():
        return _count() + _rows()

    def _count():
        return PostgresHook().get_records("select 1")

    def _only_in_task():
        return Variable.get("fine")

    BUCKET = _bucket()

    @dag(schedule=None)
    def delegated():
        _rows()

        @task
        def extract():
            return _only_in_task()

        extract()

    delegated()
    """
)


def test_follows_module_helpers_called_at_parse_time():
    problems = top_level_hook_calls(DELEGATED)
    assert [p.split(":")[0] for p in problems] == ["line 7", "line 13", "line 13"]

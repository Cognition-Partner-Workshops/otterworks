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

"""Manual-only check that the image's providers and the otterworks_etl package import.

Parsing this file exercises the Amazon, Postgres and HTTP provider hooks the ETL DAGs
use; triggering it reports the installed versions.
"""

from __future__ import annotations

from importlib.metadata import version

import pendulum
from airflow.decorators import dag, task
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.http.hooks.http import HttpHook
from airflow.providers.postgres.hooks.postgres import PostgresHook

import otterworks_etl
from otterworks_etl.common import otterworks_dag_kwargs

DISTRIBUTIONS = (
    "apache-airflow",
    "apache-airflow-providers-amazon",
    "apache-airflow-providers-postgres",
    "apache-airflow-providers-http",
    "otterworks-etl",
)


@dag(
    dag_id="otterworks_platform_check",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    doc_md=__doc__,
    **otterworks_dag_kwargs(tags=["platform"]),
)
def otterworks_platform_check():
    @task
    def report_versions() -> dict[str, str]:
        versions = {name: version(name) for name in DISTRIBUTIONS}
        versions["otterworks_etl.__version__"] = otterworks_etl.__version__
        versions["hooks"] = ",".join(h.__name__ for h in (S3Hook, PostgresHook, HttpHook))
        return versions

    report_versions()


otterworks_platform_check()

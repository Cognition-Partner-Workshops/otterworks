"""Toy DAGs for the DAG parity runner (etl/tests/golden/README.md, "DAG parity").

parity_passthrough__<script>
    Runs the unchanged legacy script with its legacy pins: DockerOperator starts the pinned
    Python 3.9 legacy image (legacy/Dockerfile) with the golden shim, the same mounts,
    environment and `/opt/etl/run.sh <script>.py` command as the golden harness
    (harness/runner.py), on the harness's Docker network. Its parity report must be identical.

parity_wrong__audit_archive_weekly
    The audit pass-through followed by one deliberate mistake through the Amazon provider hook
    (a stray object in the data lake). Its parity report must have a failed row.

Only the parity runner loads this folder (`airflow dags test --subdir`); it is not baked into
the Airflow image. The runner sets PARITY_* per scenario before parsing.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from harness import runner, settings  # noqa: E402

LEGACY_IMAGE = os.environ.get("PARITY_LEGACY_IMAGE", runner.image_tag())
CONFIG_PATH = Path(os.environ.get("PARITY_CONFIG_PATH", "/nonexistent/config.ini"))
FROZEN_TIME = os.environ.get("PARITY_FROZEN_TIME", "")
STRAY_KEY = "parity-toy/wrong-dag-was-here.json"


def legacy_task(script: str) -> DockerOperator:
    return DockerOperator(
        task_id="run_legacy_%s" % script,
        image=LEGACY_IMAGE,
        # One string, not a list: DockerOperator renders list items ending in .sh as Jinja
        # template files. The Docker SDK splits it like a shell would.
        command=" ".join(runner.legacy_command(script)),
        environment=runner.legacy_environment(FROZEN_TIME),
        mounts=[
            Mount(target=dst, source=str(src), type="bind", read_only=True)
            for src, dst in runner.legacy_mounts(CONFIG_PATH)
        ],
        network_mode=settings.DOCKER_NETWORK,
        docker_url="unix://var/run/docker.sock",
        mount_tmp_dir=False,
        auto_remove="force",
        execution_timeout=timedelta(seconds=settings.CONTAINER_TIMEOUT_SECONDS),
    )


def toy_dag(dag_id: str, doc: str) -> DAG:
    return DAG(
        dag_id=dag_id,
        schedule=None,
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        catchup=False,
        max_active_runs=1,
        default_args={"owner": "otterworks-data", "retries": 0},
        tags=["otterworks", "parity-toy"],
        doc_md=doc,
    )


for _script in settings.SCRIPTS:
    with toy_dag(
        "parity_passthrough__%s" % _script,
        "Pass-through: unchanged legacy `%s.py` in the pinned legacy image." % _script,
    ) as _dag:
        legacy_task(_script)
    globals()[_dag.dag_id] = _dag


def write_stray_object() -> None:
    S3Hook(aws_conn_id="aws_default").load_string(
        '{"deliberately": "wrong"}',
        key=STRAY_KEY,
        bucket_name=Variable.get("data_lake_bucket"),
        replace=True,
    )


with toy_dag(
    "parity_wrong__audit_archive_weekly",
    "Deliberately wrong: the audit pass-through plus a stray S3 object. Must fail parity.",
) as parity_wrong__audit_archive_weekly:
    legacy_task("audit_archive_weekly") >> PythonOperator(
        task_id="write_stray_object", python_callable=write_stray_object
    )

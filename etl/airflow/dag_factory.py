from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shlex
import sys

from airflow import DAG
from airflow.operators.bash import BashOperator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "spark/jobs/py"))
from common.schemas import TABLES

RETRY_POLICY = {
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=10),
}


def build_dags(registry, spark_root):
    dags = {}
    for path in sorted(Path(registry).glob("*.yaml")):
        entry = json.loads(path.read_text())
        status = entry["status"]
        if status in ("legacy", "retired"):
            continue
        if status not in ("template", "snowflake"):
            raise ValueError(f"Unknown status: {status}")
        job = entry["job"]
        command = (f"bash {shlex.quote(str(Path(spark_root) / 'template/submit.sh'))} {shlex.quote(job)}"
                   if status == "template" else entry["command"])
        if not command.strip():
            raise ValueError(f"Empty command: {job}")
        ingest = entry.get("ingest")
        if status == "snowflake":
            available = {f"{area}.{table}" for area, tables in TABLES.items() for table in tables}
            if ingest is not None and (not isinstance(ingest, list) or
                                       any(not isinstance(name, str) or name not in available for name in ingest)):
                raise ValueError(f"Invalid ingest tables: {job}")
            if entry["schedule"] is not None and not ingest:
                raise ValueError(f"Scheduled Snowflake job requires ingest: {job}")
        dag = DAG(
            dag_id=f"sfx_spark_{job}", schedule=entry["schedule"],
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc), catchup=False,
            max_active_runs=1, default_args=RETRY_POLICY,
        )
        repo_root = Path(os.environ.get("SFX_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
        env = {"SFX_RUN_DATE": "{{ ds }}", "SFX_SPARK_JOB": job}
        run = BashOperator(task_id="run", bash_command=command, dag=dag, append_env=True, cwd=str(repo_root),
                           env=env)
        if status == "snowflake" and ingest:
            ingest_task = BashOperator(
                task_id="ingest", dag=dag, append_env=True, cwd=str(repo_root), env=env,
                bash_command="warehouse/.venv/bin/python warehouse/snowflake/spark_landing.py --tables "
                             + shlex.quote(",".join(ingest)),
            )
            ingest_task >> run
        dags[dag.dag_id] = dag
    return dags

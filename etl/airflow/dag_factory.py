from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shlex

from airflow import DAG
from airflow.operators.bash import BashOperator

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
        dag = DAG(
            dag_id=f"sfx_spark_{job}", schedule=entry["schedule"],
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc), catchup=False,
            max_active_runs=1, default_args=RETRY_POLICY,
        )
        repo_root = Path(os.environ.get("SFX_REPO_ROOT", Path(__file__).resolve().parents[2])).resolve()
        BashOperator(task_id="run", bash_command=command, dag=dag, append_env=True, cwd=str(repo_root),
                     env={"SFX_RUN_DATE": "{{ ds }}", "SFX_SPARK_JOB": job})
        dags[dag.dag_id] = dag
    return dags

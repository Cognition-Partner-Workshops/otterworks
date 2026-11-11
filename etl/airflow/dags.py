import os
from pathlib import Path

from airflow import DAG
from dag_factory import build_dags

root = Path(__file__).resolve().parents[1] / "spark"
globals().update(build_dags(os.environ.get("SFX_REGISTRY_DIR", root / "jobs/registry"),
                            os.environ.get("SFX_SPARK_ROOT", "/opt/etl/spark")))

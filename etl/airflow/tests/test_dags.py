import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from airflow.models import DagBag

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dag_factory import build_dags, RETRY_POLICY


class DagTest(unittest.TestCase):
    def test_dagbag(self):
        bag = DagBag(dag_folder=str(ROOT), include_examples=False)
        self.assertEqual(bag.import_errors, {})
        registry = ROOT.parent / "spark/jobs/registry"
        expected = {f'sfx_spark_{entry["job"]}' for path in registry.glob("*.yaml")
                    if (entry := json.loads(path.read_text()))["status"] in ("template", "snowflake")}
        self.assertEqual(set(bag.dags), expected)

    def test_factory_routes_and_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            for job, status in (("old", "legacy"), ("retired", "retired"), ("compute", "template"), ("sql", "snowflake")):
                (Path(directory) / f"{job}.yaml").write_text(json.dumps({
                    "job": job, "status": status, "schedule": "0 1 * * *", "command": "echo sql",
                    "ingest": ["billing.PLAN_CATALOG"],
                }))
            dags = build_dags(directory, "/opt/etl/spark")
            self.assertEqual(set(dags), {"sfx_spark_compute", "sfx_spark_sql"})
            for dag in dags.values():
                task = dag.get_task("run")
                self.assertEqual(task.retries, 2)
                self.assertTrue(task.retry_exponential_backoff)
                self.assertEqual(task.retry_delay, RETRY_POLICY["retry_delay"])
                self.assertEqual(task.max_retry_delay, RETRY_POLICY["max_retry_delay"])
                self.assertEqual(dag.max_active_runs, 1)
            self.assertEqual(dags["sfx_spark_compute"].get_task("run").bash_command,
                             "bash /opt/etl/spark/template/submit.sh compute")
            self.assertEqual(dags["sfx_spark_sql"].get_task("run").bash_command, "echo sql")
            with patch.dict("os.environ", {"SFX_REGISTRY_DIR": directory}):
                bag = DagBag(dag_folder=str(ROOT / "dags.py"), include_examples=False)
            self.assertEqual(bag.import_errors, {})
            self.assertEqual(set(bag.dags), set(dags))

    def test_empty_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(build_dags(directory, "/spark"), {})

    def test_scheduled_snowflake_requires_ingest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sql.yaml"
            for ingest in (None, [], ["billing.UNKNOWN"], "billing.PLAN_CATALOG"):
                path.write_text(json.dumps({"job": "sql", "status": "snowflake",
                                            "schedule": "@daily", "command": "echo sql", "ingest": ingest}))
                with self.assertRaises(ValueError):
                    build_dags(directory, "/spark")

    def test_ingest_precedes_run(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "sql.yaml").write_text(json.dumps({
                "job": "sql", "status": "snowflake", "schedule": "@daily", "command": "echo sql",
                "ingest": ["billing.INVOICE_HDR", "billing.PLAN_CATALOG"],
            }))
            dag = build_dags(directory, "/spark")["sfx_spark_sql"]
            ingest, run = dag.get_task("ingest"), dag.get_task("run")
            self.assertEqual(run.upstream_task_ids, {"ingest"})
            self.assertEqual(ingest.bash_command, "warehouse/.venv/bin/python warehouse/snowflake/spark_landing.py "
                             "--tables billing.INVOICE_HDR,billing.PLAN_CATALOG")
            self.assertEqual((ingest.cwd, ingest.env, ingest.append_env), (run.cwd, run.env, run.append_env))

    def test_real_scheduled_snowflake_ingests(self):
        registry = ROOT.parent / "spark/jobs/registry"
        dags = build_dags(registry, "/spark")
        for path in registry.glob("*.yaml"):
            entry = json.loads(path.read_text())
            if entry["status"] == "snowflake" and entry["schedule"] is not None:
                self.assertIn("ingest", dags[f'sfx_spark_{entry["job"]}'].get_task("run").upstream_task_ids)

    def test_repo_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for job, status in (("compute", "template"), ("sql", "snowflake")):
                (Path(directory) / f"{job}.yaml").write_text(json.dumps({
                    "job": job, "status": status, "schedule": None, "command": "echo sql",
                }))
            with patch.dict(os.environ):
                os.environ.pop("SFX_REPO_ROOT", None)
                dags = build_dags(directory, "/spark")
                for dag in dags.values():
                    self.assertEqual(dag.get_task("run").cwd, str(ROOT.parents[1]))
                os.environ["SFX_REPO_ROOT"] = directory
                for dag in build_dags(directory, "/spark").values():
                    self.assertEqual(dag.get_task("run").cwd, directory)

    def test_retired_registry_has_no_dags(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "retired.yaml").write_text(json.dumps({"status": "retired"}))
            self.assertEqual(build_dags(directory, "/spark"), {})

    def test_invalid_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            for entry in ({"status": "invalid"}, {"job": "sql", "status": "snowflake", "command": ""}):
                path.write_text(json.dumps(entry))
                with self.assertRaises(ValueError):
                    build_dags(directory, "/spark")

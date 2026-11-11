import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunnerTest(unittest.TestCase):
    def run_jobs(self, jobs, statuses=None, **settings):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spark = root / "etl/spark"
            spark.mkdir(parents=True)
            shutil.copy(ROOT / "run.sh", spark / "run.sh")
            (spark / "jobs.txt").write_text("\n".join(jobs) + "\n")
            registry = spark / "jobs/registry"
            registry.mkdir(parents=True)
            for job in jobs:
                (registry / f"{job}.yaml").write_text(json.dumps({"job": job, "status": (statuses or {}).get(job, "legacy")}))
            binary = root / "bin"
            binary.mkdir()
            docker = binary / "docker"
            docker.write_text('#!/usr/bin/env bash\n[[ "${*: -1}" != */second.sh ]]\n')
            docker.chmod(0o755)
            env = dict(os.environ, PATH=str(binary) + ":" + os.environ["PATH"], JOB="", SPARK_JOBS="30", NS="sfx-d1110-check")
            env.update(settings)
            result = subprocess.run(["bash", str(spark / "run.sh")], env=env, capture_output=True, text=True)
            self.assertTrue((spark / ".data" / env["NS"] / "logs").is_dir())
            self.assertFalse((spark / ".data" / "logs").exists())
            return result

    def test_continues_after_failure(self):
        result = self.run_jobs(["first", "second", "third"])
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, "first +OK")
        self.assertRegex(result.stdout, "second +FAILED")
        self.assertRegex(result.stdout, "third +OK")

    def test_limit_and_single_selection(self):
        result = self.run_jobs(["first", "second"], SPARK_JOBS="1")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("second", result.stdout)
        result = self.run_jobs(["first", "second", "third"], JOB="third", SPARK_JOBS="1")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("first", result.stdout)
        self.assertRegex(result.stdout, "third +OK")

    def test_empty_selection(self):
        result = self.run_jobs(["first"], SPARK_JOBS="0")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("first", result.stdout)

    def test_invalid_selection(self):
        for settings in ({"JOB": "unknown"}, {"SPARK_JOBS": "-1"}):
            result = self.run_jobs(["first"], **settings)
            self.assertEqual(result.returncode, 2)

    def test_template_and_snowflake_routing(self):
        result = self.run_jobs(["first", "second", "third"], statuses={"second": "template", "third": "snowflake"})
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, "second +OK")
        self.assertNotIn("third", result.stdout)
        result = self.run_jobs(["third"], statuses={"third": "snowflake"}, JOB="third")
        self.assertEqual(result.returncode, 2)

    def test_job_inventory(self):
        entries = [json.loads(path.read_text()) for path in sorted((ROOT / "jobs/registry").glob("*.yaml"))]
        jobs = [entry["job"] for entry in entries]
        self.assertEqual(len(jobs), 30)
        self.assertEqual(len(set(jobs)), 30)
        self.assertIn("docs_folder_legacy_report", jobs)
        for job in jobs:
            if next(entry for entry in entries if entry["job"] == job)["status"] == "legacy":
                self.assertTrue((ROOT / "submit" / (job + ".sh")).is_file())

    def test_retired_jobs_are_not_run(self):
        result = self.run_jobs(["first", "retired"], statuses={"retired": "retired"})
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, "first +OK")
        self.assertNotIn("retired", result.stdout)
        result = self.run_jobs(["retired"], statuses={"retired": "retired"})
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("retired", result.stdout)
        result = self.run_jobs(["retired"], statuses={"retired": "retired"}, JOB="retired")
        self.assertEqual(result.returncode, 2)

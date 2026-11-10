import os
import json
from pathlib import Path
import re
import shlex
import shutil
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
LABEL = {"otterworks.run-token": "sfx-d1110"}


class InventoryTest(unittest.TestCase):
    def test_job_inventory(self):
        entries = [json.loads(path.read_text()) for path in sorted((ROOT / "jobs/registry").glob("*.yaml"))]
        jobs = [entry["job"] for entry in entries]
        registry = {entry["job"]: entry for entry in entries}
        self.assertEqual(len(jobs), 30)
        self.assertEqual(len(set(jobs)), 30)
        classifications = yaml.safe_load((ROOT / "classification.yaml").read_text())
        self.assertEqual(len(classifications), 30)
        classified = {entry["job"]: entry for entry in classifications}
        self.assertEqual(set(classified), set(jobs))
        self.assertEqual({path.stem for path in (ROOT / "submit").glob("*.sh")},
                         {job for job in jobs if registry[job]["status"] == "legacy"} |
                         {job for job in jobs if registry[job]["status"] == "template" and
                          (ROOT / "submit" / f"{job}.sh").exists()})
        applications = {}
        for path in (ROOT / "k8s").glob("jobs/*/application.yaml"):
            obj = yaml.safe_load(path.read_text())
            self.assertEqual(obj["metadata"]["labels"], LABEL, path.name)
            if obj["kind"] == "SparkApplication":
                applications[path.parent.name] = obj
        self.assertEqual(set(applications), {job for job in jobs if registry[job]["status"] in ("legacy", "template")})
        crontab = [line for path in (ROOT / "cron.d").glob("*") for line in path.read_text().splitlines()]
        for job in jobs:
            with self.subTest(job=job):
                entry = registry[job]
                self.assertIn(entry["status"], ("legacy", "template", "snowflake", "retired"))
                self.assertEqual(entry["language"], classified[job]["language"])
                if entry["status"] == "retired":
                    self.assertIn(entry["target"], (classified[job]["target"], "retired"))
                else:
                    self.assertEqual(entry["target"], classified[job]["target"])
                self.assertIn(entry["profile"], ("small", "large"))
                path = ROOT / "submit" / f"{job}.sh"
                if entry["status"] != "legacy":
                    self.assertFalse((ROOT / "cron.d" / job).exists())
                    if entry["status"] in ("snowflake", "retired"):
                        if entry["status"] == "snowflake":
                            self.assertTrue(entry["command"].strip())
                        self.assertFalse(path.exists())
                        self.assertTrue((ROOT / "k8s/jobs" / job / "kustomization.yaml").is_file())
                        self.assertFalse((ROOT / "k8s/jobs" / job / "application.yaml").exists())
                        self.assert_snowflake_kustomization(ROOT / "k8s/jobs" / job)
                    elif path.exists():
                        self.assertIn("template/submit.sh", path.read_text())
                        self.assertNotIn("--executor", path.read_text())
                    continue
                self.assertTrue(os.access(path, os.X_OK))
                script = path.read_text()
                tokens = shlex.split(script.replace("\\\n", " "), comments=True)
                def option(flag):
                    return tokens[tokens.index(flag) + 1]
                lines = [line for line in crontab if f"/{job}.sh " in line]
                self.assertEqual(len(lines), 1)
                self.assertEqual(lines[0].lstrip().startswith("#"), job == "docs_folder_legacy_report")
                self.assertEqual(entry["schedule"], " ".join(lines[0].lstrip("# ").split()[:5]))
                spec = applications[job]["spec"]
                self.assertEqual(applications[job]["apiVersion"], "sparkoperator.k8s.io/v1beta2")
                self.assertEqual(applications[job]["metadata"]["namespace"], "sfx-d1110-before")
                self.assertEqual(spec["executor"]["memory"], option("--executor-memory"))
                cores = int(option("--executor-cores"))
                self.assertEqual(spec["executor"]["cores"], cores)
                instances = int(option("--num-executors")) if "--num-executors" in tokens else int(option("--total-executor-cores")) // cores
                self.assertEqual(spec["executor"]["instances"], instances)
                for index, token in enumerate(tokens):
                    if token == "--conf":
                        key, value = tokens[index + 1].split("=", 1)
                        self.assertEqual(spec["sparkConf"][key], value)
                scala = "--class" in tokens
                self.assertEqual(classified[job]["language"], "scala" if scala else "python")
                self.assertEqual(spec["type"], "Scala" if scala else "Python")
                self.assertIn(classified[job]["target"], ("dbt", "snowpark_python", "spark_standard_template"))
                self.assertTrue(classified[job]["reason"])
                if scala:
                    self.assertEqual(spec["mainClass"], option("--class"))
                    self.assertEqual(spec["mainApplicationFile"], "local:///opt/sfx/spark/.cache/sfx-spark-jobs.jar")
                else:
                    self.assertEqual(spec["mainApplicationFile"], f"local:///opt/sfx/spark/jobs/py/{job}.py")
                    self.assertEqual(spec["deps"]["pyFiles"], ["local:///opt/sfx/spark/.cache/common.zip"])
                inline = dict(re.findall(r"^export (\w+)=(\S+) # gitleaks:allow$", script, re.MULTILINE))
                for role in ("driver", "executor"):
                    self.assertEqual(spec[role]["labels"], LABEL)
                    environment = {entry["name"]: entry for entry in spec[role]["env"]}
                    for key, value in inline.items():
                        self.assertEqual(environment[key]["value"], value)
                    if not inline:
                        self.assertIn("valueFrom", environment["TD_JDBC_PASSWORD"])
                text = (ROOT / "k8s/jobs" / job / "application.yaml").read_text()
                self.assertEqual(text.count("# gitleaks:allow"), 2 * len(inline))

    def test_kustomization(self):
        directory = ROOT / "k8s"
        kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text())
        expected = {path.name for path in directory.glob("*.yaml")} - {"kustomization.yaml"}
        expected.update("jobs/" + path.name for path in (directory / "jobs").iterdir())
        self.assertEqual(set(kustomization["resources"]), expected)
        self.assertEqual(len(kustomization["resources"]), len(expected))
        for path in (directory / "jobs").iterdir():
            obj = yaml.safe_load((path / "kustomization.yaml").read_text())
            self.assertEqual(obj["resources"], [p.name for p in path.glob("application.yaml")])

    def assert_snowflake_kustomization(self, directory):
        obj = yaml.safe_load((directory / "kustomization.yaml").read_text())
        self.assertEqual(obj["resources"], [])
        self.assertFalse((directory / "application.yaml").exists())

    def test_retired_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("jobs/registry", "submit", "cron.d", "k8s"):
                if (ROOT / name).exists():
                    shutil.copytree(ROOT / name, root / name)
                else:
                    (root / name).mkdir(parents=True)
            shutil.copy(ROOT / "classification.yaml", root / "classification.yaml")
            job = "docs_folder_legacy_report"
            registration = root / "jobs/registry" / f"{job}.yaml"
            entry = json.loads(registration.read_text())
            entry.update(status="retired", target="retired")
            registration.write_text(json.dumps(entry))
            (root / "submit" / f"{job}.sh").unlink(missing_ok=True)
            (root / "cron.d" / job).unlink(missing_ok=True)
            (root / "k8s/jobs" / job / "application.yaml").unlink(missing_ok=True)
            (root / "k8s/jobs" / job / "kustomization.yaml").write_text("resources: []\n")
            with patch(__name__ + ".ROOT", root):
                self.test_job_inventory()
                self.test_kustomization()

    def test_snowflake_kustomization_stub(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "kustomization.yaml"
            path.write_text("resources: []\n")
            self.assert_snowflake_kustomization(directory)
            path.write_text("resources: [application.yaml]\n")
            with self.assertRaises(AssertionError):
                self.assert_snowflake_kustomization(directory)
            path.write_text("resources: []\n")
            (directory / "application.yaml").write_text("kind: SparkApplication\n")
            with self.assertRaises(AssertionError):
                self.assert_snowflake_kustomization(directory)


if __name__ == "__main__":
    unittest.main()

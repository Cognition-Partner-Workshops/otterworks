import os
from pathlib import Path
import re
import shlex
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
LABEL = {"otterworks.run-token": "sfx-d1110"}


class InventoryTest(unittest.TestCase):
    def test_job_inventory(self):
        jobs = (ROOT / "jobs.txt").read_text().splitlines()
        self.assertEqual(len(jobs), 30)
        self.assertEqual(len(set(jobs)), 30)
        classifications = yaml.safe_load((ROOT / "classification.yaml").read_text())
        self.assertEqual(len(classifications), 30)
        classified = {entry["job"]: entry for entry in classifications}
        self.assertEqual(set(classified), set(jobs))
        self.assertEqual({path.stem for path in (ROOT / "submit").glob("*.sh")}, set(jobs))
        applications = {}
        for path in (ROOT / "k8s").glob("*.yaml"):
            obj = yaml.safe_load(path.read_text())
            self.assertEqual(obj["metadata"]["labels"], LABEL, path.name)
            if obj["kind"] == "SparkApplication":
                applications[path.stem] = obj
        self.assertEqual(set(applications), set(jobs))
        crontab = (ROOT.parent / "crontab").read_text().splitlines()
        for job in jobs:
            with self.subTest(job=job):
                path = ROOT / "submit" / f"{job}.sh"
                self.assertTrue(os.access(path, os.X_OK))
                script = path.read_text()
                tokens = shlex.split(script.replace("\\\n", " "), comments=True)
                def option(flag):
                    return tokens[tokens.index(flag) + 1]
                lines = [line for line in crontab if f"/{job}.sh " in line]
                self.assertEqual(len(lines), 1)
                self.assertEqual(lines[0].lstrip().startswith("#"), job == "docs_folder_legacy_report")
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
                text = (ROOT / "k8s" / f"{job}.yaml").read_text()
                self.assertEqual(text.count("# gitleaks:allow"), 2 * len(inline))

    def test_kustomization(self):
        directory = ROOT / "k8s"
        kustomization = yaml.safe_load((directory / "kustomization.yaml").read_text())
        expected = {path.name for path in directory.glob("*.yaml")} - {"kustomization.yaml"}
        self.assertEqual(set(kustomization["resources"]), expected)
        self.assertEqual(len(kustomization["resources"]), len(expected))


if __name__ == "__main__":
    unittest.main()

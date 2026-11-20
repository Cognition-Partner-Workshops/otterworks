import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1]))

from warehouse.run_config import render


class SubmitCredentialsTest(unittest.TestCase):
    def run_submit(self, path, password, status=0):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "spark-submit"
            binary.write_text(
                '#!/usr/bin/env bash\n'
                '[[ "$TD_JDBC_PASSWORD" == "$EXPECTED_PASSWORD" ]] || exit 91\n'
                'printf "submitted\\n"\n'
                'exit "$SUBMIT_STATUS"\n'
            )
            binary.chmod(0o755)
            environment = {key: value for key, value in os.environ.items()
                           if key != "TD_JDBC_PASSWORD"}
            environment.update(EXPECTED_PASSWORD=password or "", SUBMIT_STATUS=str(status))
            if password is not None:
                environment["TD_JDBC_PASSWORD"] = password
            source = path.read_text().replace("/opt/spark/bin/spark-submit", str(binary))
            return subprocess.run(["bash", "-c", source], env=environment,
                                  capture_output=True, text=True)

    def test_submit_inherits_password(self):
        paths = sorted((ROOT / "submit").glob("*.sh"))
        self.assertEqual(len(paths), 30)
        for path in paths:
            with self.subTest(job=path.stem):
                password = secrets.token_urlsafe(24) + ' $() ; " '
                result = self.run_submit(path, password)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "submitted\n")
                self.assertNotIn(password, result.stdout + result.stderr)
                self.assertIn(': "${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"\n'
                              'export TD_JDBC_PASSWORD\n', path.read_text())

    def test_missing_and_empty_password_fail_before_submission(self):
        for path in sorted((ROOT / "submit").glob("*.sh")):
            for password in (None, ""):
                with self.subTest(job=path.stem, password=password):
                    result = self.run_submit(path, password)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("TD_JDBC_PASSWORD is required", result.stderr)
                    self.assertNotIn("submitted", result.stdout)

    def test_submission_error_propagates(self):
        for path in sorted((ROOT / "submit").glob("*.sh")):
            with self.subTest(job=path.stem):
                result = self.run_submit(path, secrets.token_urlsafe(24), status=23)
                self.assertEqual(result.returncode, 23, result.stderr)

    def test_kubernetes_passwords_use_secret(self):
        for path in sorted((ROOT / "k8s/jobs").glob("*/application.yaml")):
            spec = yaml.safe_load(render(path.read_text()))["spec"]
            for role in ("driver", "executor"):
                with self.subTest(job=path.parent.name, role=role):
                    password = next(entry for entry in spec[role]["env"]
                                    if entry["name"] == "TD_JDBC_PASSWORD")
                    self.assertNotIn("value", password)
                    self.assertEqual(password["valueFrom"]["secretKeyRef"],
                                     {"name": render("__RUN_TOKEN__-jdbc"), "key": "password"})

import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
JOBS = ("audit_daily_summary", "billing_payment_aging", "compliance_flag_rules")


class SubmitCredentialsTest(unittest.TestCase):
    def run_submit(self, job, value):
        source = (ROOT / "submit" / f"{job}.sh").read_text()
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "spark-submit"
            binary.write_text(
                '#!/usr/bin/env bash\n'
                '[[ "$TD_JDBC_PASSWORD" == "$EXPECTED_JDBC" ]] || exit 91\n'
                '[[ "$AWS_ACCESS_KEY_ID" == "$EXPECTED_ACCESS" ]] || exit 92\n'
                '[[ "$AWS_SECRET_ACCESS_KEY" == "$EXPECTED_SECRET" ]] || exit 93\n'
                'echo submitted\n'
            )
            binary.chmod(0o755)
            env = {k: v for k, v in os.environ.items() if k != "TD_JDBC_PASSWORD"}
            env.update(EXPECTED_JDBC=value or "", EXPECTED_ACCESS=secrets.token_urlsafe(24),
                       EXPECTED_SECRET=secrets.token_urlsafe(24))
            env.update(AWS_ACCESS_KEY_ID=env["EXPECTED_ACCESS"],
                       AWS_SECRET_ACCESS_KEY=env["EXPECTED_SECRET"])
            if value is not None:
                env["TD_JDBC_PASSWORD"] = value
            return subprocess.run(
                ["bash", "-c", source.replace("/opt/spark/bin/spark-submit", str(binary))],
                env=env, capture_output=True, text=True,
            )

    def test_inherits_credentials_without_printing_them(self):
        for job in JOBS:
            with self.subTest(job=job):
                value = secrets.token_urlsafe(24)
                result = self.run_submit(job, value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "submitted\n")
                self.assertNotIn(value, result.stdout + result.stderr)

    def test_missing_and_empty_password_fail_before_submission(self):
        for job in JOBS:
            for value in (None, ""):
                with self.subTest(job=job, value=value):
                    result = self.run_submit(job, value)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("TD_JDBC_PASSWORD is required", result.stderr)
                    self.assertNotIn("submitted", result.stdout)

#!/usr/bin/env python3
"""Exercise deployment argument builders without contacting infrastructure."""
import os
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_ROLE",
        "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_PRIVATE_KEY"]


class WarehouseWiringTest(unittest.TestCase):
    def build(self, script, settings):
        source = (ROOT / script).read_text()
        functions = "\n".join(re.search(r"^" + name + r"\(\) \{.*?^\}", source,
                                      re.M | re.S).group() for name in ["build_helm_args"])
        env = {k: v for k, v in os.environ.items() if k not in KEYS + ["FINANCE_WAREHOUSE_ENABLED"]}
        env.update(settings)
        return subprocess.run(["bash", "-c", """
set -e
declare -A CONTAINER_PORT=([report-service]=8091)
irsa_arn() { :; }
add_secret() { SECRET_KV+=("$1" "$2"); }
err() { echo "$*" >&2; }
DB_PASSWORD=db-password
""" + functions + """
build_helm_args report-service
printf 'ARG:%s\n' "${EXTRA_ARGS[@]}"
printf 'SECRET:%s\n' "${SECRET_KV[@]}"
"""], env=env, text=True, capture_output=True)

    def test_builders(self):
        for script in ["scripts/deploy-dev.sh", "scripts/lib/tenant-common.sh"]:
            with self.subTest(script=script):
                result = self.build(script, dict.fromkeys(KEYS, "throwaway"))
                self.assertEqual(result.returncode, 0, result.stderr)
                for key in KEYS[:-1]:
                    self.assertIn("ARG:config." + key + "=throwaway", result.stdout)
                self.assertIn("SECRET:SNOWFLAKE_PRIVATE_KEY\nSECRET:throwaway", result.stdout)
                self.assertNotIn("ARG:config.SNOWFLAKE_PRIVATE_KEY", result.stdout)
                missing = self.build(script, {})
                self.assertNotEqual(missing.returncode, 0)
                for key in KEYS:
                    self.assertIn(key, missing.stderr)
                self.assertIn("FINANCE_WAREHOUSE_ENABLED=false", missing.stderr)
                partial = self.build(script, {"SNOWFLAKE_USER": "never-print-this"})
                self.assertNotEqual(partial.returncode, 0)
                self.assertNotIn("never-print-this", partial.stderr)
                disabled = self.build(script, {"FINANCE_WAREHOUSE_ENABLED": "false"})
                self.assertEqual(disabled.returncode, 0, disabled.stderr)
                self.assertIn("ARG:config.FINANCE_WAREHOUSE_ENABLED=false", disabled.stdout)
                self.assertNotIn("SECRET:SNOWFLAKE_PRIVATE_KEY", disabled.stdout)

    def test_compose(self):
        compose = (ROOT / "docker-compose.yml").read_text().split("  report-service:\n", 1)[1]
        compose = re.split(r"\n  [a-zA-Z][\w-]*:", compose)[0]
        for key in KEYS:
            self.assertIn(key + ": ${" + key + ":-}", compose)
        self.assertIn("FINANCE_WAREHOUSE_ENABLED: ${FINANCE_WAREHOUSE_ENABLED:-true}", compose)

    def test_secret_serialization_uses_stdin(self):
        for script in ["scripts/deploy-dev.sh", "scripts/deploy-tenant.sh"]:
            with self.subTest(script=script):
                source = (ROOT / script).read_text()
                serialization = re.search(r"    printf '%s\\0'.*?> \"\$\{secret_file\}\"",
                                          source, re.S).group()
                self.assertNotIn("--args", serialization)
                self.assertEqual(serialization.count('"${SECRET_KV[@]}"'), 1)
                secret = '-----BEGIN PRIVATE KEY-----\nthrowaway "quoted" \\ key\n-----END PRIVATE KEY-----\n'
                result = subprocess.run(["bash", "-c", """
set -e
SECRET_KV=(SNOWFLAKE_PRIVATE_KEY "$TEST_KEY" DB_PASSWORD dummy)
secret_file=/dev/stdout
""" + serialization], env={**os.environ, "TEST_KEY": secret}, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {
                    "secrets": {"SNOWFLAKE_PRIVATE_KEY": secret, "DB_PASSWORD": "dummy"}})

    def test_runner_references(self):
        jobs = (ROOT / "demo-platform/dashboard/lib/jobs.ts").read_text()
        keys = re.search(r"const RUNNER_SECRET_ENV_KEYS = \[(.*?)\]", jobs, re.S).group(1)
        template = (ROOT / "demo-platform/helm/demo-platform/templates/secret.yaml").read_text()
        for key in KEYS:
            self.assertIn('"' + key + '"', keys)
            self.assertIn('"' + key + '"', template)


if __name__ == "__main__":
    unittest.main()

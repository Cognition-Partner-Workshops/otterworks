#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploySecretSerializationTest(unittest.TestCase):
    def test_secret_serialization_uses_stdin(self):
        for script in ["scripts/deploy-dev.sh", "scripts/deploy-tenant.sh"]:
            with self.subTest(script=script):
                source = (ROOT / script).read_text()
                serialization = re.search(r"    \{ printf '%s\\0'.*?> \"\$\{secret_file\}\"",
                                          source, re.S).group()
                self.assertNotIn("--args", serialization)
                self.assertEqual(serialization.count('"${SECRET_KV[@]}"'), 1)
                secret = 'throwaway multiline value\n"quoted" \\ text\n'
                result = subprocess.run(["bash", "-c", """
set -e
SECRET_KV=(TEST_SECRET "$TEST_VALUE" DB_PASSWORD dummy EMPTY_VALUE "")
secret_file=/dev/stdout
""" + serialization], env={**os.environ, "TEST_VALUE": secret}, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {
                    "secrets": {"TEST_SECRET": secret, "DB_PASSWORD": "dummy", "EMPTY_VALUE": ""}})


if __name__ == "__main__":
    unittest.main()

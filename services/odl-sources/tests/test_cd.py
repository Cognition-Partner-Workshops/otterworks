import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class CDTests(unittest.TestCase):
    def test_deployment_selection(self):
        workflow = (ROOT / ".github/workflows/cd-tenant.yml").read_text()
        fragment = workflow.split("          deploy=false", 1)[1].split('          echo "deploy=${deploy}"', 1)[0]
        for branch, prefix, deployable, expected in [
            ("demo-odl", "", "true", "false"),
            ("demo-other", "", "true", "true"),
            ("demo-odl", "fork", "true", "true"),
            ("demo-other", "", "false", "false"),
        ]:
            with self.subTest(branch=branch, prefix=prefix, deployable=deployable):
                result = subprocess.check_output(["bash", "-c", 'deploy=false\n'+fragment+'\nprintf "%s" "$deploy"'],
                    env={**os.environ, "GITHUB_REF_NAME": branch, "TENANT_PREFIX": prefix,
                         "DEPLOYABLE": deployable, "REBUILD_ALL": "false"}, text=True)
                self.assertEqual(result.splitlines()[-1], expected)

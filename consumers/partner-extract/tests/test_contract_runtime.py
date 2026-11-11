"""Contract CI wiring and missing emulator runtime regression checks."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContractRuntimeTest(unittest.TestCase):
    def test_live_workflow(self):
        workflow = (ROOT.parents[1] / ".github/workflows/consumer-partner-extract.yml").read_text()
        live = workflow.split("\n  contract:\n", 1)[1]
        self.assertIn("WAREHOUSE_CONTRACT_TARGET: snowflake", live)
        self.assertIn("actions/setup-python@", live)
        self.assertRegex(live, r"actions/setup-python@[0-9a-f]{40} # v5")
        self.assertIn("python -m pip install -r consumers/partner-extract/requirements.txt", live)

    def test_no_emulator_endpoint(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("TD_PG_")}
        env["WAREHOUSE_CONTRACT_TARGET"] = "teradata-emulator"
        result = subprocess.run(["bash", str(ROOT / "contract/run.sh")], env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(),
                         "SKIP teradata-emulator contract: set TD_PG_DSN or TD_PG_HOST for the emulator endpoint")


if __name__ == "__main__":
    unittest.main()

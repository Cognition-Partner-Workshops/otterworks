import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class ControlTests(unittest.TestCase):
    def run_helper(self, command, status=0):
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "args.json"
            script = '''source demo-platform/lib/control-common.sh
aws() {
  python3 -c 'import json,os,sys; from pathlib import Path; Path(os.environ["CAPTURE"]).write_text(json.dumps(sys.argv[1:]))' "$@"
  return "$AWS_STATUS"
}
''' + command
            result = subprocess.run(["bash", "-c", script], cwd=ROOT, capture_output=True, text=True,
                                    env={**os.environ, "CAPTURE": str(capture), "AWS_STATUS": str(status)})
            return result, json.loads(capture.read_text())

    def test_register(self):
        result, args = self.run_helper("ctl_register_run_tenant test-one branch run-123")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(args[args.index("--expression-attribute-values") + 1])
        item = {key[1:]: value for key, value in values.items()}
        self.assertEqual(json.loads(args[args.index("--key") + 1])["PK"], {"S": "TENANT#test-one"})
        self.assertEqual(item["status"], {"S": "deploying"})
        self.assertEqual(item["run_token"], {"S": "run-123"})
        self.assertEqual(item["db_name"], {"S": "otterworks_test_one"})
        self.assertEqual(int(item["expires_at"]["N"]) - int(item["created_at"]["N"]), 315360000)
        self.assertIn("attribute_not_exists(PK) OR run_token = :run_token", args)
        update = args[args.index("--update-expression") + 1]
        self.assertNotIn("pinned", update)
        self.assertIn("#created_at = if_not_exists(#created_at, :created_at)", update)
        self.assertEqual(args[:2], ["dynamodb", "update-item"])

    def test_missing_record(self):
        result, _ = self.run_helper("ctl_tenant_exists absent")
        self.assertEqual(result.returncode, 1)

    def test_register_failure(self):
        result, _ = self.run_helper("ctl_register_run_tenant test branch run", status=1)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()

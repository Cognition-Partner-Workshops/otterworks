import json
import os
from pathlib import Path
import secrets
import subprocess
import unittest


WAVE = Path(__file__).resolve().parents[1]
KEY = "BANK_ACCOUNT_REFERENCE_SECRET"


class ReferenceConfigTest(unittest.TestCase):
    def compose(self, env):
        return subprocess.run(
            ["docker", "compose", "-p", "fs09-otterworks", "-f", "vm/compose.yaml",
             "config", "--format", "json"],
            cwd=WAVE, env=env, capture_output=True, text=True)

    def test_both_services_receive_the_supplied_secret(self):
        env = dict(os.environ, **{KEY: secrets.token_hex(32)})
        result = self.compose(env)
        self.assertEqual(result.returncode, 0, result.stderr)
        services = json.loads(result.stdout)["services"]
        for service in ("stmt-web-01", "notify-01"):
            self.assertTrue(services[service].get("environment", {}).get(KEY) == env[KEY],
                            service + " must receive the reference secret")

    def test_direct_compose_rejects_missing_and_empty_secrets(self):
        for value in (None, ""):
            env = dict(os.environ)
            env.pop(KEY, None)
            if value is not None:
                env[KEY] = value
            self.assertNotEqual(self.compose(env).returncode, 0)

    def test_make_generates_a_local_secret_and_preserves_an_override(self):
        for value in (None, secrets.token_hex(32)):
            env = dict(os.environ)
            env.pop(KEY, None)
            if value is not None:
                env[KEY] = value
            check = ("import os; v=os.environ.get('" + KEY + "', ''); "
                     "assert len(v)>=32; "
                     "assert not os.environ.get('EXPECTED') or v==os.environ['EXPECTED']")
            env["EXPECTED"] = value or ""
            result = subprocess.run(
                ["make", "--no-print-directory", "-s",
                 "--eval=check-secret:\n\t@python3 -c \"" + check + "\"",
                 "check-secret"], cwd=WAVE, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_ci_exports_a_masked_key_for_direct_compose_steps(self):
        workflow = (WAVE.parents[2] / ".github/workflows/bank-wave1.yml").read_text()
        self.assertIn("::add-mask::", workflow)
        self.assertIn("BANK_ACCOUNT_REFERENCE_SECRET=%s", workflow)
        self.assertIn('"$GITHUB_ENV"', workflow)

    def test_make_accepts_empty_command_line_secrets_and_preserves_nonempty_ones(self):
        for value in ("", "   ", secrets.token_hex(32)):
            env = dict(os.environ, EXPECTED=value.strip())
            env.pop(KEY, None)
            check = (
                "import os,json,subprocess; "
                "v=os.environ.get('" + KEY + "', ''); assert len(v)>=32; "
                "assert not os.environ['EXPECTED'] or v==os.environ['EXPECTED']; "
                "r=subprocess.run(['docker','compose','-p','fs09-otterworks',"
                "'-f','vm/compose.yaml','config','--format','json'],"
                "check=True,capture_output=True,text=True); "
                "s=json.loads(r.stdout)['services']; "
                "assert all(s[n]['environment']['" + KEY + "']==v "
                "for n in ['stmt-web-01','notify-01'])"
            )
            result = subprocess.run(
                ["make", "--no-print-directory", "-s", KEY + "=" + value,
                 "--eval=check-secret:\n\t@python3 -c \"" + check + "\"", "check-secret"],
                cwd=WAVE, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

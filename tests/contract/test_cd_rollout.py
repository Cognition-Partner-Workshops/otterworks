"""Offline CD safety checks; external commands are stubs, never cluster calls."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "scripts/deploy-tenant.sh"
TENANT = ROOT / "demo-platform/scripts/tenant.sh"


def function(path, name):
    text = path.read_text()
    return re.search(rf"^{name}\(\) \{{\n.*?^\}}", text, re.M | re.S)[0]


class CDTests(unittest.TestCase):
    def run_shell(self, script, env=None, args=()):
        return subprocess.run(
            ["bash", "-c", "set -euo pipefail\n" + script, str(DEPLOY), *args],
            cwd=ROOT, env={**os.environ, **(env or {})},
            text=True, capture_output=True,
        )

    def test_deploy_flags(self):
        prefix = DEPLOY.read_text().split("require_bins aws kubectl helm terraform jq")[0]
        for args, env, expected in [
            (("demo",), {}, "false false"),
            (("demo", "--atomic", "--strict"), {}, "true true"),
            (("demo",), {"HELM_ATOMIC": "true"}, "true false"),
        ]:
            with self.subTest(args=args, env=env):
                result = self.run_shell(prefix + '\nprintf "%s %s" "$ATOMIC" "$STRICT"', env, args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)

    def test_helm_safety_flags(self):
        for atomic in ("true", "false"):
            script = f'''
source scripts/lib/tenant-common.sh
{function(DEPLOY, 'deploy_service')}
REPO_ROOT="$PWD"; NS=otterworks-test; ATTENDEE_ID=test
IMAGE_TAG_OVERRIDE=main; TENANT_BRANCH_ARG=""; ATOMIC={atomic}
ECR_REGISTRY=registry; SECRET_KV=(); EXTRA_ARGS=()
aws() {{ echo sha256:abc; }}
build_helm_args() {{ :; }}
helm() {{ printf 'ARG=%s\\n' "$@"; }}
deploy_service api-gateway
'''
            result = self.run_shell(script)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("ARG=--history-max\nARG=10", result.stdout)
            self.assertIn("ARG=image.tag=main@sha256:abc", result.stdout)
            self.assertEqual("ARG=--atomic\n" in result.stdout, atomic == "true")
            self.assertEqual("ARG=--wait\n" in result.stdout, atomic == "true")

    def test_rollout_summary(self):
        for deployments, ignore, expected in [
            ("web-app", "", 0),
            ("web-app\nadmin-service", "", 1),
            ("web-app\nadmin-service", "admin-service", 0),
            ("", "", 1),
            ("LIST_ERROR", "", 1),
        ]:
            script = '''
source scripts/lib/tenant-rollout.sh
kubectl() {
  if [ "$3" = get ]; then
    [ "$DEPLOYMENTS" != LIST_ERROR ] || return 1
    printf '%s' "$DEPLOYMENTS"
  else
    [ "$5" != deployment/admin-service ]
  fi
}
verify_tenant_rollouts otterworks-test
'''
            result = self.run_shell(script, {"DEPLOYMENTS": deployments, "VERIFY_IGNORE": ignore})
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            self.assertIn("ROLLOUT", result.stdout)
            if ignore:
                self.assertIn("IGNORED", result.stdout)

    def wait_script(self, detail):
        return f'''
log() {{ echo "$*"; }}
{function(TENANT, 'cd_summary')}
{function(TENANT, 'wait_for_deploy')}
api() {{ printf '%s' "$DETAIL"; }}
wait_for_deploy test 100
''', {"DETAIL": json.dumps(detail), "CD_WAIT_TIMEOUT": "1", "CD_POLL_INTERVAL": "0"}

    def test_wait_uses_new_runner_audit_not_active_status(self):
        for detail, expected, marker in [
            ({"status": "active", "audit": [{"ts": 101, "action": "deploy_ok"}]}, 0, "PASS"),
            ({"status": "active", "audit": [{"ts": 101, "action": "deploy_fail"}]}, 1, "FAIL"),
            ({"status": "active", "audit": [{"ts": 100, "action": "deploy_ok"}]}, 1, "TIMEOUT"),
            ({"status": "active", "audit": []}, 1, "TIMEOUT"),
        ]:
            script, env = self.wait_script(detail)
            result = self.run_shell(script, env)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertIn(marker, result.stdout)

    def test_default_verification_is_advisory_and_strict_is_fatal(self):
        text = DEPLOY.read_text()
        verify = text.split("# ---------- Rollout verification ----------")[1].split("# ---------- Summary ----------")[0]
        final = text[text.rindex('if [ "${STRICT}"'):]
        for strict, expected in [("false", 0), ("true", 1)]:
            result = self.run_shell(
                f'verify_tenant_rollouts() {{ return 1; }}\nNS=test; STRICT={strict}\n' + verify + final
            )
            self.assertEqual(result.returncode, expected, result.stderr)

    def test_sync_wait_and_smoke_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            curl = directory / "curl"
            curl.write_text('''#!/usr/bin/env bash
if [[ "$*" == *--data-binary* ]]; then cat >/dev/null; fi
case "$*" in
  */api/auth/login*) echo 200 ;;
  *' -X POST '*) echo '{"ok":true,"job":"deploy-test-123"}'; echo 200 ;;
  */api/tenants/test*)
    if [ -f "$STATE" ]; then
      printf '{"status":"active","url":"https://t-test.example","apiUrl":"https://api-t-test.example","audit":[{"ts":%s,"action":"%s"}]}\\n200\\n' "$TERMINAL_TS" "$EVENT"
    else
      touch "$STATE"
      echo '{"id":"test","status":"active","pinned":true,"branch":"workshop-test","audit":[{"ts":100,"action":"deploy_ok"}]}'
      echo 200
    fi ;;
  *) echo 200 ;;
esac
''')
            curl.chmod(0o755)
            for event, expected in [("deploy_ok", 0), ("deploy_fail", 1)]:
                state = directory / "state"
                state.unlink(missing_ok=True)
                summary = directory / "summary"
                result = subprocess.run(
                    ["bash", str(TENANT), "sync", "workshop-test", "--wait", "--smoke"], cwd=ROOT,
                    env={**os.environ, "PATH": f"{directory}:{os.environ['PATH']}", "STATE": str(state),
                         "DASHBOARD_PASSCODE": "offline-test", "EVENT": event,
                         "TERMINAL_TS": str(int(time.time() * 1000) + 10000),
                         "GITHUB_STEP_SUMMARY": str(summary), "CD_POLL_INTERVAL": "0"},
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertIn("Runner deploy for test:", summary.read_text())
                if expected == 0:
                    self.assertIn("https://api-t-test.example/health: HTTP 200", summary.read_text())

    def test_smoke_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            script = f'''
log() {{ echo "$*"; }}
{function(TENANT, 'cd_summary')}
{function(TENANT, 'smoke_tenant')}
curl() {{
  if [ -f "$MARK" ]; then echo 200; else touch "$MARK"; echo 503; fi
}}
smoke_tenant '{{"url":"https://web.example","apiUrl":"https://api.example"}}'
'''
            result = self.run_shell(script, {"MARK": str(Path(directory) / "mark"), "CD_POLL_INTERVAL": "0", "CD_SMOKE_ATTEMPTS": "2"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("HTTP 200"), 2)

    def test_wait_api_error_is_failure(self):
        script, env = self.wait_script({})
        result = self.run_shell(script.replace('printf \'%s\' "$DETAIL"', 'return 1'), env)
        self.assertNotEqual(result.returncode, 0)

    def test_smoke_root_and_gateway_health_only(self):
        script = f'''
log() {{ echo "$*"; }}
{function(TENANT, 'cd_summary')}
{function(TENANT, 'smoke_tenant')}
curl() {{ echo "$CODE"; }}
smoke_tenant "$DETAIL"
'''
        detail = json.dumps({"url": "https://t-main.otterworks.app", "apiUrl": "https://api-t-main.otterworks.app"})
        for code, value, expected in [("200", detail, 0), ("503", detail, 1), ("200", "{}", 1)]:
            result = self.run_shell(script, {"CODE": code, "DETAIL": value, "CD_SMOKE_ATTEMPTS": "1"})
            self.assertEqual(result.returncode, expected, result.stderr)
            if value == detail:
                self.assertIn("https://t-main.otterworks.app/:", result.stdout)
                self.assertIn("https://api-t-main.otterworks.app/health:", result.stdout)
                self.assertNotIn("admin-service", result.stdout)

    def test_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            helm = directory / "helm"
            helm.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
case "$1" in
  list)
    if [ "${NO_RELEASES:-}" = true ]; then echo '[]'
    else echo '[{"name":"api-gateway"},{"name":"not-an-app"}]'; fi ;;
  history)
    if [[ " $* " == *" -o json "* ]]; then
      if [ "${EMPTY:-}" = true ]; then echo '[{"revision":1}]'
      else echo '[{"revision":2},{"revision":5}]'; fi
    else echo 'REVISION STATUS'; fi ;;
  rollback) [ "${HELM_FAIL:-}" != true ] ;;
esac
''')
            kubectl = directory / "kubectl"
            kubectl.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALLS"
if [ "$3" = get ]; then echo api-gateway; else [ "${ROLLOUT_FAIL:-}" != true ]; fi
''')
            helm.chmod(0o755)
            kubectl.chmod(0o755)
            for args, extra, expected, target in [
                (["test", "all"], {}, 0, "2"),
                (["test", "api-gateway", "--to-revision", "3"], {}, 0, "3"),
                (["test", "all", "--dry-run"], {}, 0, None),
                (["test", "all"], {"EMPTY": "true"}, 1, None),
                (["test", "all"], {"NO_RELEASES": "true"}, 1, None),
                (["test", "all"], {"HELM_FAIL": "true"}, 1, "2"),
                (["test", "all"], {"ROLLOUT_FAIL": "true"}, 1, "2"),
                (["test", "all", "--to-revision", "bad"], {}, 1, None),
            ]:
                calls = directory / "calls"
                calls.write_text("")
                result = subprocess.run(
                    ["bash", "scripts/rollback-tenant.sh", *args], cwd=ROOT,
                    env={**os.environ, "PATH": f"{directory}:{os.environ['PATH']}", "CALLS": str(calls), **extra},
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                text = calls.read_text()
                if target:
                    self.assertIn(f"rollback api-gateway {target} -n otterworks-test --wait", text)
                    self.assertLess(text.index("history"), text.index("rollback"))
                else:
                    self.assertNotIn("rollback ", text)
                self.assertNotIn("not-an-app -n", text)


if __name__ == "__main__":
    unittest.main()

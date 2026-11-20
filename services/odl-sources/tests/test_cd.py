import os
import subprocess
import unittest
from pathlib import Path

import yaml

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

    def test_odl_web_monitor_override_uses_existing_tenant_deploy_path(self):
        wrapper = (ROOT / "scripts/odl/deploy-odl.sh").read_text()
        self.assertIn('"${ROOT}/scripts/deploy-tenant.sh" "$ID"', wrapper)
        deploy = (ROOT / "scripts/deploy-tenant.sh").read_text()
        fragment = deploy.split('  local overlay\n', 1)[1].split('  # Alerts', 1)[0]
        for tenant in ('odl', 'odl-before', 'main', 'unrelated'):
            with self.subTest(tenant=tenant):
                args = subprocess.check_output(['bash', '-ec', '''
sanitize_id() { printf '%s' "$1"; }
log() { :; }
EXTRA_ARGS=()
''' + fragment + '\nprintf "%s\\n" "${EXTRA_ARGS[@]}"'], cwd=ROOT, text=True,
                    env={**os.environ, 'REPO_ROOT': str(ROOT), 'ATTENDEE_ID': tenant, 'service': 'web-app'})
                overlay_args = args.split()
                self.assertEqual(bool(overlay_args), tenant in ('odl', 'odl-before'))
                objects = list(yaml.safe_load_all(subprocess.check_output([
                    'helm', 'template', 'web-app', 'infrastructure/helm/web-app',
                    '--namespace', 'otterworks-' + tenant, '--set', 'image.tag=test',
                    '--api-versions', 'monitoring.coreos.com/v1', *overlay_args], cwd=ROOT, text=True)))
                self.assertEqual(any(o and o['kind'] == 'ServiceMonitor' for o in objects),
                                 tenant not in ('odl', 'odl-before'))

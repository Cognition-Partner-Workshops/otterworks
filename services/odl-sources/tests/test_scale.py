import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
LABEL = 'otterworks.io/scale-with-tenant'


class ScaleTests(unittest.TestCase):
    def helper(self, command, sets='statefulset.apps/oracle', jobs='cronjob.batch/odl-refresh-oracle', fail=''):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'trace'
            script = '''source scripts/lib/tenant-workloads.sh
kubectl() {
  echo "$*" >> "$TRACE"
  [[ "$*" != *"$FAIL"* ]] || [ -z "$FAIL" ] || return 1
  case "$*" in
    *"get cronjobs"*) printf '%s' "$JOBS" ;;
    *"get statefulsets"*"-o name"*) printf '%s' "$SETS" ;;
    *"get statefulsets"*) printf '0\\n1\\n' ;;
    *"get deploy"*) printf '0\\n0\\n' ;;
  esac
}
''' + command
            result = subprocess.run(['bash', '-ec', script], cwd=ROOT, capture_output=True, text=True,
                                    env={**os.environ, 'TRACE': str(trace), 'SETS': sets, 'JOBS': jobs, 'FAIL': fail})
            return result, trace.read_text()

    def test_down_up(self):
        result, trace = self.helper('tenant_scale_workloads otterworks-test 0; tenant_scale_workloads otterworks-test 1')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('scale statefulset -l ' + LABEL + '=true --replicas=0', trace)
        self.assertIn('scale statefulset -l ' + LABEL + '=true --replicas=1', trace)
        self.assertIn('"suspend":true', trace)
        self.assertIn('"suspend":false', trace)
        self.assertNotIn('statefulset --all', trace)

    def test_empty_and_errors(self):
        result, trace = self.helper('tenant_scale_workloads ns 0', sets='', jobs='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('scale statefulset', trace)
        for fail in ('get cronjobs', 'scale deployment', 'get statefulsets', 'scale statefulset', 'patch cronjob'):
            result, _ = self.helper('tenant_scale_workloads ns 0', fail=fail)
            self.assertNotEqual(result.returncode, 0, fail)

    def test_running_includes_statefulsets_and_errors(self):
        result, _ = self.helper('tenant_running_workloads ns')
        self.assertEqual(result.stdout.strip(), '1')
        result, _ = self.helper('tenant_running_workloads ns', fail='get statefulsets')
        self.assertNotEqual(result.returncode, 0)

    def test_chart_opt_in(self):
        for mode in ('emptyDir', 'persistentVolumeClaim'):
            objects = list(yaml.safe_load_all(subprocess.check_output([
                'helm', 'template', 'db2-archive', 'infrastructure/helm/db2-archive',
                '--set', 'dbName=ODL', '--set', 'pv.volumeName=test-volume',
                '--set', 'storage.mode=' + mode], cwd=ROOT, text=True)))
            sts = next(o for o in objects if o and o['kind'] == 'StatefulSet')
            self.assertEqual(sts['metadata']['labels'].get(LABEL), 'true' if mode == 'emptyDir' else None)
        objects = list(yaml.safe_load_all(subprocess.check_output([
            'helm', 'template', 'sources', 'services/odl-sources/oracle'], cwd=ROOT, text=True)))
        opted = [o for o in objects if o and o['kind'] in ('StatefulSet', 'CronJob')]
        self.assertEqual(len(opted), 3)
        self.assertTrue(all(o['metadata']['labels'][LABEL] == 'true' for o in opted))

    def test_idle_and_wake_paths(self):
        source = (ROOT / 'demo-platform/reaper/idle-suspend.sh').read_text()
        suspend = 'suspend_tenant() {' + source.split('suspend_tenant() {', 1)[1].split('\n}', 1)[0] + '\n}'
        result, trace = self.helper('''
idle_log() { :; }
idle_warn() { :; }
ctl_audit() { :; }
IDLE_AFTER_SECONDS=3600
''' + suspend + '\nsuspend_tenant test ns')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('scale statefulset -l ' + LABEL + '=true --replicas=0', trace)
        self.assertIn('"${REPO_DIR}/scripts/tenant-scale.sh" "${TENANT_ID}" up',
                      (ROOT / 'demo-platform/runner/entrypoint.sh').read_text())
        objects = list(yaml.safe_load_all(subprocess.check_output([
            'helm', 'template', 'platform', 'demo-platform/helm/demo-platform',
            '--set-string', 'awsAccountId=123456789012', '--set', 'secret.create=false'], cwd=ROOT, text=True)))
        role = next(o for o in objects if o and o['kind'] == 'ClusterRole')
        self.assertTrue(any('statefulsets/scale' in r['resources'] and 'patch' in r['verbs']
                            for r in role['rules']))

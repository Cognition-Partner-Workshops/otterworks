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
        self.assertIn("attribute_not_exists(PK) OR run_token = :run_token OR (attribute_not_exists(run_token) AND #status = :free)", args)
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

    def test_checkin_then_redeploy(self):
        program = '''
import json,os,sys
from pathlib import Path
p=Path(os.environ['STATE']); item=json.loads(p.read_text()); args=sys.argv
if args[2]=='delete-item':
    item={}
else:
    values=json.loads(args[args.index('--expression-attribute-values')+1])
    names=json.loads(args[args.index('--expression-attribute-names')+1])
    if '--condition-expression' in args:
        condition=args[args.index('--condition-expression')+1]
        assert 'attribute_not_exists(run_token) AND #status = :free' in condition
        allowed=not item or item.get('run_token')==values[':run_token'] or ('run_token' not in item and item.get('status')==values[':free'])
        if not allowed: sys.exit(1)
        for key,value in values.items():
            key=key[1:]
            if key=='free': continue
            if key in ('created_at','checked_out_at','expires_at','persistent') and key in item: continue
            item[key]=value
    else:
        item[names['#s']]=values[':s']
p.write_text(json.dumps(item))
'''
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / 'state.json'
            env = {**os.environ, 'STATE': str(state), 'FAKE_AWS': program}
            setup = '''source demo-platform/lib/control-common.sh
aws() { python3 -c "$FAKE_AWS" "$@"; }
'''
            state.write_text(json.dumps({'run_token': {'S': 'run-123'}}))
            result = subprocess.run(['bash', '-ec', setup + '''
ctl_delete_tenant test
ctl_update_status test free
ctl_register_run_tenant test branch run-123
'''], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(state.read_text())['run_token'], {'S': 'run-123'})
            for item, expected in [({'status': {'S': 'free'}, 'pinned': {'BOOL': True}}, 0),
                                   ({'status': {'S': 'active'}}, 1),
                                   ({'status': {'S': 'free'}, 'run_token': {'S': 'other'}}, 1)]:
                with self.subTest(item=item):
                    state.write_text(json.dumps(item))
                    result = subprocess.run(['bash', '-ec', setup + 'ctl_register_run_tenant test branch run-123'],
                                            cwd=ROOT, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    if expected:
                        self.assertEqual(json.loads(state.read_text()), item)
                    else:
                        self.assertTrue(json.loads(state.read_text())['pinned']['BOOL'])

    def test_keep_db_retains_record(self):
        tail = (ROOT / 'scripts/teardown-tenant.sh').read_text().split(
            'source "${REPO_ROOT}/demo-platform/lib/control-common.sh"', 1)[1]
        setup = '''ATTENDEE_ID=test NS=otterworks-test
log() { :; }
ctl_get() { echo '{"Item":{"run_token":{"S":"odl-1795112287"}}}'; }
ctl_delete_tenant() { echo deleted; }
'''
        for keep, expected in [('true', ''), ('false', 'deleted')]:
            result = subprocess.run(['bash', '-ec', setup + 'KEEP_DB=' + keep + '\n' + tail],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), expected)


if __name__ == "__main__":
    unittest.main()

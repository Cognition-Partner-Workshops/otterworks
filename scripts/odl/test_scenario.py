import base64
import importlib.util
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('scenario', Path(__file__).with_name('scenario.py'))
scenario = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scenario)


class ScenarioTests(unittest.TestCase):
    def test_cli_refuses_other_scenarios_tenants_and_unbounded_durations(self):
        for args in ([], ['arm', 'main'], ['arm', 'odl'], ['arm', scenario.SCENARIO, 'main'],
                     ['status', scenario.SCENARIO, 'odl'], ['disarm', scenario.SCENARIO, '1'],
                     ['arm', scenario.SCENARIO, '0'], ['arm', scenario.SCENARIO, '1801'],
                     ['arm', scenario.SCENARIO, '-1'], ['arm', scenario.SCENARIO, 'nan']):
            with self.subTest(args=args):
                result = subprocess.run(['bash', str(scenario.HERE / 'scenario.sh'), *args],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
        with patch.object(scenario, 'locked') as locked:
            with self.assertRaises(scenario.ScenarioError):
                scenario.main(['arm', scenario.SCENARIO, '1801'])
            locked.assert_not_called()

    def test_real_key_families_are_interleaved_without_raw_customer_data(self):
        queries = scenario.filter_keys([{'source_keys': {'db2_cust_no': 'C0000001',
            'oracle_account_ids': [7000000, 7000017], 'crm_contact_id': 'fixture-contact'}, 'name': 'not-used'}])
        self.assertEqual(len(queries), 6)
        self.assertEqual(queries[:3], [{'db2_cust_no': 'C0000001'}, {'oracle_account_id': 7000000},
                                      {'crm_contact_id': 'fixture-contact'}])
        self.assertEqual(queries[4], {'oracle_account_id': 7000017})
        for rows in ([], [{}], [{'source_keys': {'db2_cust_no': 'C0000001'}}]):
            with self.assertRaises(scenario.ScenarioError):
                scenario.filter_keys(rows)

    def test_token_uses_only_fixed_tenant_key_and_does_not_print_it(self):
        with patch.object(scenario, 'kubectl', return_value=base64.b64encode(b'fixture-key').decode()) as kube, \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            encoded = scenario.token(150)
        self.assertEqual(kube.call_args.args, ('get', 'secret', 'api-gateway-secrets',
                                             '-o', 'jsonpath={.data.JWT_SECRET}'))
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('fixture-key', encoded)
        claims = json.loads(base64.urlsafe_b64decode(encoded.split('.')[1] + '=='))
        self.assertEqual(claims['sub'], 'odl-read-latency-scenario')
        with patch.object(scenario, 'kubectl', return_value=''):
            with self.assertRaises(scenario.ScenarioError):
                scenario.token(150)

    def test_pid_reuse_and_unrelated_process_groups_are_not_load(self):
        record = {'pid': 123, 'start': '42', 'marker': 'fixture-marker'}
        args = ('python\0' + str(scenario.HERE / 'scenario.py') + '\0--worker\0fixture-marker\0').encode()
        with patch.object(scenario, 'process_start', return_value='42') as start, \
                patch.object(Path, 'read_bytes', return_value=args), patch.object(scenario.os, 'getpgid', return_value=123) as group:
            self.assertTrue(scenario.running(record))
            self.assertFalse(scenario.running({**record, 'marker': 'other'}))
            start.return_value = '43'
            self.assertFalse(scenario.running(record))
            start.return_value = '42'
            group.return_value = 99
            self.assertFalse(scenario.running(record))
            start.side_effect = ProcessLookupError()
            self.assertFalse(scenario.running(record))

    def test_ingress_target_is_fixed_and_redirects_cannot_forward_tenant_token(self):
        with patch.object(scenario, 'build_opener') as build:
            response = build.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"items": []}'
            self.assertEqual(scenario.get({'db2_cust_no': 'fixture'}, 'fixture-token'), (200, {'items': []}))
        build.assert_called_once_with(scenario.NoRedirect)
        request = build.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, scenario.URL + '?db2_cust_no=fixture')
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(scenario.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid'))

    def test_disarm_sends_sigterm_and_waits_for_own_load_only(self):
        with tempfile.TemporaryDirectory() as directory:
            pidfile = Path(directory) / 'load.pid'
            pidfile.write_text(json.dumps({'pid': 123, 'start': '42', 'marker': 'fixture-marker'}))
            with patch.object(scenario, 'PIDFILE', pidfile), \
                    patch.object(scenario, 'running', side_effect=[True, True, False]), \
                    patch.object(scenario.os, 'killpg') as kill, patch.object(scenario.time, 'sleep'), \
                    patch('sys.stdout', new_callable=io.StringIO):
                scenario.stop_load()
            kill.assert_called_once_with(123, signal.SIGTERM)
            self.assertFalse(pidfile.exists())
            with patch.object(scenario, 'PIDFILE', pidfile), patch.object(scenario, 'running', return_value=False), \
                    patch.object(scenario.os, 'killpg') as kill, patch('sys.stdout', new_callable=io.StringIO):
                scenario.stop_load()
            kill.assert_not_called()

    def test_load_is_bounded_drains_and_does_not_log_credentials_or_bodies(self):
        stop = threading.Event()
        with patch.object(scenario, 'get', return_value=(200, {'private': 'not-logged'})), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            result = scenario.drive(stop, .03, 'private-token', [{'db2_cust_no': 'fixture'}], rate=100)
        self.assertGreater(result['completed'], 0)
        self.assertEqual(set(result['statuses']), {'200'})
        self.assertLess(result['elapsed_seconds'], 1)
        self.assertNotIn('private-token', json.dumps(result) + output.getvalue())
        self.assertNotIn('not-logged', json.dumps(result) + output.getvalue())
        stop.set()
        with patch.object(scenario, 'get') as get:
            self.assertEqual(scenario.drive(stop, 30, 'token', [{}])['completed'], 0)
        get.assert_not_called()
        with patch.object(scenario, 'get', side_effect=RuntimeError('sensitive failure')):
            result = scenario.drive(threading.Event(), .01, 'token', [{}], rate=100)
        self.assertGreater(result['statuses']['transport-error'], 0)
        self.assertNotIn('sensitive failure', json.dumps(result))

    def test_status_reports_values_pending_and_empty_without_claiming_idle_latency(self):
        values = {'p95_seconds': [{'value': [0, '3']}], 'p99_seconds': [{'value': [0, '5']}],
                  'requests_per_second': [{'value': [0, '4']}], 'alerts': [
                      {'metric': {'alertname': 'ODLReadLatencyCritical', 'alertstate': 'pending'}}]}
        with patch.object(scenario, 'prometheus', return_value=values), \
                patch.object(scenario, 'running', return_value=True), patch('sys.stdout', new_callable=io.StringIO) as output:
            scenario.status()
        self.assertIn('load=running', output.getvalue())
        self.assertIn('p99_seconds=5', output.getvalue())
        self.assertIn('ODLReadLatencyCritical=pending', output.getvalue())
        with patch.object(scenario, 'prometheus', return_value={k: [] for k in values}), \
                patch.object(scenario, 'running', return_value=False), patch('sys.stdout', new_callable=io.StringIO) as output:
            scenario.status()
        self.assertIn('p99_seconds=no-data', output.getvalue())
        self.assertIn('ODLReadLatencyCritical=inactive', output.getvalue())

    def test_cluster_errors_are_redacted_and_duplicate_arm_is_refused(self):
        result = subprocess.CompletedProcess([], 1, stdout='private-value', stderr='private-value')
        with patch.object(scenario.subprocess, 'run', return_value=result):
            with self.assertRaises(scenario.ScenarioError) as raised:
                scenario.kubectl('get', 'secret', 'api-gateway-secrets')
        self.assertNotIn('private-value', str(raised.exception))
        with patch.object(scenario, 'running', return_value=True), patch.object(scenario.subprocess, 'Popen') as popen:
            with self.assertRaises(scenario.ScenarioError):
                scenario.arm(150)
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()

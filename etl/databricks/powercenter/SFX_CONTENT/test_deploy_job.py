import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import deploy_job
from dbx import ROOT


class DeployTests(unittest.TestCase):
    @patch.dict('os.environ', {'DATABRICKS_WAREHOUSE_ID': 'warehouse'})
    def test_create_or_reset_same_job(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'job.json').write_text((ROOT / 'job.json').read_text())
                (root / 'reserved_role_grant_dependency.sql').write_text((ROOT / 'reserved_role_grant_dependency.sql').read_text())
                if existing:
                    (root / 'job-created.json').write_text(json.dumps({'job_id': 42}))
                def api(method, path, body=None):
                    if path.endswith('/create'):
                        return {'job_id': 42}
                    if path.endswith('/run-now'):
                        return {'run_id': 1}
                    if '/runs/get?' in path:
                        return {'state': {'life_cycle_state': 'TERMINATED'}, 'tasks': []}
                    return {}
                with patch.object(deploy_job, 'ROOT', root), patch.object(deploy_job, 'EVIDENCE', root), patch.object(
                        deploy_job, 'api', side_effect=api) as calls:
                    deploy_job.deploy()
                creates = [c for c in calls.call_args_list if c.args[1].endswith('/create')]
                resets = [c for c in calls.call_args_list if c.args[1].endswith('/reset')]
                self.assertEqual(len(creates), 0 if existing else 1)
                self.assertEqual(len(resets), 1 if existing else 0)
                body = resets[0].args[2]['new_settings'] if existing else creates[0].args[2]
                self.assertEqual(body['tags'], {'run_token': 'dbx-d1111', 'expires': '2026-11-24', 'act': 'scale'})
                if existing:
                    self.assertEqual(resets[0].args[2]['job_id'], 42)

    @patch.dict('os.environ', {'DATABRICKS_WAREHOUSE_ID': 'warehouse'})
    def test_reset_failure_does_not_create_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'job.json').write_text((ROOT / 'job.json').read_text())
            (root / 'reserved_role_grant_dependency.sql').write_text((ROOT / 'reserved_role_grant_dependency.sql').read_text())
            (root / 'job-created.json').write_text('{"job_id":42}')
            with patch.object(deploy_job, 'ROOT', root), patch.object(deploy_job, 'EVIDENCE', root), patch.object(
                    deploy_job, 'api', side_effect=[{}, {}, RuntimeError('reset failed')]) as api:
                with self.assertRaisesRegex(RuntimeError, 'reset failed'):
                    deploy_job.deploy()
                self.assertFalse(any(c.args[1].endswith('/create') for c in api.call_args_list))

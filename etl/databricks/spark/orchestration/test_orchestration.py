import json
import unittest
from unittest.mock import patch
import deploy


class OrchestrationTests(unittest.TestCase):
    def test_definitions(self):
        daily = json.loads((deploy.ROOT / 'daily.json').read_text())
        hourly = json.loads((deploy.ROOT / 'hourly.json').read_text())
        self.assertEqual(len(daily['tasks']), 15)
        self.assertEqual(len(hourly['tasks']), 1)
        edges = {t['task_key']: t['depends_on'][0]['task_key']
                 for t in daily['tasks'] if t.get('depends_on')}
        self.assertEqual(edges, {'lake_compaction_audit': 'audit_daily_summary',
                                'lake_compaction_documents': 'docs_event_export_hourly'})
        for settings in (daily, hourly):
            self.assertEqual(settings['schedule']['pause_status'], 'PAUSED')
            self.assertNotIn('job_clusters', settings)
            for task in settings['tasks']:
                self.assertEqual(task['max_retries'], 2)
                self.assertEqual(task['min_retry_interval_millis'], 60000)
                self.assertFalse(task['retry_on_timeout'])
                self.assertEqual(task['timeout_seconds'], 1800)
                self.assertNotIn('new_cluster', task)

    def test_empty_workspace_creates(self):
        def response(method, path, body=None):
            if 'jobs/list?' in path:
                return {}
            if path.endswith('jobs/create'):
                return {'job_id': 1}
            return {'settings': {'schedule': {'pause_status': 'PAUSED'}}}
        with patch.object(deploy, 'api', side_effect=response) as api, patch.object(deploy, 'save'):
            self.assertEqual(len(deploy.deploy()), 2)
            self.assertEqual(sum(c.args[1].endswith('jobs/create') for c in api.call_args_list), 2)

    def test_duplicate_names_rejected(self):
        name = 'dbx-d1111-spark-daily'
        with patch.object(deploy, 'api', return_value={'jobs': [
                {'settings': {'name': name}}, {'settings': {'name': name}}]}):
            with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
                deploy.deploy()


if __name__ == '__main__':
    unittest.main()

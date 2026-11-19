import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch


spec = importlib.util.spec_from_file_location(
    'snowflake_export', Path(__file__).resolve().parents[1] / 'bin/snowflake_export.py'
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.env = {'SNOWFLAKE_' + key: 'test-' + key for key in (
            'ACCOUNT', 'USER', 'ROLE', 'PRIVATE_KEY'
        )}
        self.connector = MagicMock()
        self.serialization = MagicMock()
        self.modules = {
            'snowflake': SimpleNamespace(connector=self.connector),
            'snowflake.connector': self.connector,
            'cryptography': SimpleNamespace(),
            'cryptography.hazmat': SimpleNamespace(),
            'cryptography.hazmat.primitives': SimpleNamespace(serialization=self.serialization),
        }

    def test_session_scope_and_tag(self):
        for warehouse in (None, 'UNRELATED_WAREHOUSE'):
            with self.subTest(warehouse=warehouse):
                env = dict(self.env)
                if warehouse:
                    env['SNOWFLAKE_WAREHOUSE'] = warehouse
                with patch.dict('os.environ', env, clear=True), patch.dict('sys.modules', self.modules):
                    self.assertIs(exporter.connect(), self.connector.connect.return_value)
                kwargs = self.connector.connect.call_args.kwargs
                self.assertEqual(kwargs['warehouse'], 'SFX_D1110_PARITY_WH')
                self.assertEqual(kwargs['database'], 'SFX_D1110_AFTER')
                self.assertEqual(kwargs['schema'], 'COMPAT')
                self.assertEqual(kwargs['role'], 'test-ROLE')
                self.assertEqual(kwargs['authenticator'], 'SNOWFLAKE_JWT')
                self.assertEqual(kwargs['session_parameters']['TIMEZONE'], 'UTC')
                tag = json.loads(kwargs['session_parameters']['QUERY_TAG'])
                self.assertEqual({key: tag[key] for key in (
                    'run', 'run_token', 'workload', 'phase', 'act', 'consumer')}, {
                    'run': 'sfx1119', 'run_token': 'sfx1119', 'workload': 'parity',
                    'phase': 'export', 'act': 'consumers', 'consumer': 'partner-extract'})
                self.assertTrue(tag['commit'])
                self.assertTrue(tag['run_id'])

    def test_tag_resolves_run_at_connection_time(self):
        for scope, expected in (({'RUN_TOKEN': 'sfx2220'}, 'sfx2220'),
                                ({'SNOWFLAKE_RUN_TOKEN': 'sfx-d1110'}, 'sfx-d1110'),
                                ({'RUN_TOKEN': 'sfx3330', 'SNOWFLAKE_RUN_TOKEN': 'sfx-d1110'}, 'sfx3330'),
                                ({'SNOWFLAKE_RUN_TOKEN': "free-text'quote"}, 'sfx1119')):
            with self.subTest(scope=scope), patch.dict('os.environ', {**self.env, **scope}, clear=True), \
                    patch.dict('sys.modules', self.modules):
                exporter.connect()
                tag = json.loads(self.connector.connect.call_args.kwargs['session_parameters']['QUERY_TAG'])
                self.assertEqual(tag['run'], expected)
                self.assertEqual(tag['run_token'], expected)

    def test_missing_or_empty_credentials(self):
        for key in self.env:
            for value in (None, ''):
                with self.subTest(key=key, value=value):
                    env = dict(self.env)
                    if value is None:
                        del env[key]
                    else:
                        env[key] = value
                    with patch.dict('os.environ', env, clear=True):
                        with self.assertRaisesRegex(ValueError, 'missing ' + key):
                            exporter.connect()

    def test_invalid_key_does_not_connect(self):
        self.serialization.load_pem_private_key.side_effect = ValueError('invalid key')
        with patch.dict('os.environ', self.env, clear=True), patch.dict('sys.modules', self.modules):
            with self.assertRaisesRegex(ValueError, 'invalid key'):
                exporter.connect()
        self.connector.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

import ast
import os
import re
import subprocess
import sys
import unittest

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app'))
WAVE_DIR = os.path.abspath(os.path.join(APP_DIR, '..', '..'))


class SettingsTest(unittest.TestCase):
    def load_settings(self, value):
        env = os.environ.copy()
        env.pop('BRANCH_LOCATOR_DB_PASSWORD', None)
        if value is not None:
            env['BRANCH_LOCATOR_DB_PASSWORD'] = value
        return subprocess.Popen(
            [sys.executable, '-c',
             'import settings; assert settings.DB_PASSWORD == "synthetic-test-only"'],
            cwd=APP_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_reads_environment(self):
        process = self.load_settings('synthetic-test-only')
        stdout, stderr = process.communicate()
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(stdout, b'')

    def test_missing_and_empty_fail_closed(self):
        for value in (None, ''):
            process = self.load_settings(value)
            stdout, stderr = process.communicate()
            self.assertNotEqual(process.returncode, 0)
            self.assertIn(b'BRANCH_LOCATOR_DB_PASSWORD must be set and non-empty', stderr)
            self.assertEqual(stdout, b'')

    def test_no_hardcoded_branch_password(self):
        with open(os.path.join(APP_DIR, 'settings.py')) as source:
            tree = ast.parse(source.read())
        assignments = [node.value for node in ast.walk(tree)
                       if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'DB_PASSWORD'
                               for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        value = assignments[0]
        self.assertIsInstance(value, ast.Call)
        self.assertIsInstance(value.func, ast.Attribute)
        self.assertEqual(value.func.attr, 'get')
        self.assertEqual(value.args[0].s, 'BRANCH_LOCATOR_DB_PASSWORD')
        self.assertEqual(len(value.args), 1)
        self.assertEqual(value.keywords, [])
        with open(os.path.join(WAVE_DIR, 'vm', 'db-roles.sql')) as source:
            sql = source.read()
        self.assertIsNone(re.search(r"CREATE\s+ROLE\s+branch_app\b[^;]*PASSWORD\s+(?:E)?'", sql, re.IGNORECASE))
        self.assertIn("PASSWORD :'branch_password'", sql)
        self.assertIn(r'\getenv branch_password BRANCH_LOCATOR_DB_PASSWORD', sql)


if __name__ == '__main__':
    unittest.main()

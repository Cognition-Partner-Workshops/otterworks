import ast
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "app"))
import server  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as f:
        return f.read()


class ServeTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        fake = types.ModuleType("waitress")
        fake.serve = lambda app, **kw: self.calls.append((app, kw))
        self._saved = sys.modules.get("waitress")
        sys.modules["waitress"] = fake

    def tearDown(self):
        if self._saved is None:
            del sys.modules["waitress"]
        else:
            sys.modules["waitress"] = self._saved

    def test_serve_uses_bounded_pool_and_idle_timeout(self):
        app = object()
        server.serve(app, "0.0.0.0", 5000)
        got_app, kw = self.calls[0]
        self.assertIs(got_app, app)
        self.assertEqual((kw["host"], kw["port"]), ("0.0.0.0", 5000))
        self.assertEqual(kw["threads"], 4)
        self.assertLessEqual(kw["connection_limit"], 100)
        self.assertLessEqual(kw["channel_timeout"], 30)

    def test_overrides_do_not_mutate_defaults(self):
        server.serve(object(), "127.0.0.1", 1, threads=2)
        self.assertEqual(self.calls[0][1]["threads"], 2)
        self.assertEqual(server.SERVE_OPTIONS["threads"], 4)


class EntrypointTest(unittest.TestCase):
    def test_main_does_not_use_flask_dev_server(self):
        tree = ast.parse(read("app", "locator.py"))
        attrs = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)]
        self.assertNotIn("run", attrs)
        self.assertIn("serve", attrs)

    def test_systemd_unit_runs_unprivileged(self):
        unit = read("vm", "branch-locator.service")
        user = re.search(r"^User=(\S+)$", unit, re.MULTILINE)
        self.assertIsNotNone(user)
        self.assertNotIn(user.group(1), ("root", "0"))

    def test_standin_runs_as_numeric_non_root(self):
        users = re.findall(r"^USER\s+(\S+)", read("vm", "Dockerfile"), re.MULTILINE)
        self.assertTrue(users)
        uid = users[-1].split(":")[0]
        self.assertTrue(uid.isdigit() and int(uid) != 0)


if __name__ == "__main__":
    unittest.main()

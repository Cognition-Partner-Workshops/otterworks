# run_token=dbx-d1111 expires=2026-11-24
import importlib.util
import pathlib
import sys
import types
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ORIGINAL = HERE.parents[2] / "spark" / "jobs" / "py" / "users_login_useragent_parse.py"


def load_original():
    source = ORIGINAL.read_text().split("\n\nspark = ")[0]
    module = types.ModuleType("original_users_login_useragent_parse")
    stub = types.ModuleType("common.runtime")
    stub.landing = stub.save = stub.session = None
    sys.modules.setdefault("common", types.ModuleType("common"))
    sys.modules["common.runtime"] = stub
    exec(compile(source, str(ORIGINAL), "exec"), module.__dict__)
    return module.browser.func


spec = importlib.util.spec_from_file_location("migrated", HERE / "users_login_useragent_parse.py")
migrated = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrated)


def outcome(function, args):
    try:
        return ("value", function(*args))
    except Exception as error:
        return ("error", type(error).__name__)


class OriginalParityTest(unittest.TestCase):
    CASES = [None, "", "Mozilla/5.0 Chrome/119.0.1 Safari/537.36", "Firefox/120.0", "Safari/17", "Chrome/", "Edge/1", "curl/8", "Chrome/1\tx"]

    def test_matches_original_udf(self):
        original = load_original()
        for case in self.CASES:
            args = case if isinstance(case, tuple) else (case,)
            self.assertEqual(outcome(migrated.browser, args), outcome(original, args), repr(case))


if __name__ == "__main__":
    unittest.main()

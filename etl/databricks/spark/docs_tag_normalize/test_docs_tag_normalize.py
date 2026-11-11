# run_token=dbx-d1111 expires=2026-11-24
import importlib.util
import pathlib
import sys
import types
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ORIGINAL = HERE.parents[2] / "spark" / "jobs" / "py" / "docs_tag_normalize.py"


def load_original_normalize():
    source = ORIGINAL.read_text().split("\n\nspark = ")[0]
    module = types.ModuleType("original_docs_tag_normalize")
    stub = types.ModuleType("common.runtime")
    stub.landing = stub.save = stub.session = None
    sys.modules.setdefault("common", types.ModuleType("common"))
    sys.modules["common.runtime"] = stub
    exec(compile(source, str(ORIGINAL), "exec"), module.__dict__)
    return module.normalize.func


spec = importlib.util.spec_from_file_location("migrated", HERE / "docs_tag_normalize.py")
migrated = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrated)


class NormalizeTagTest(unittest.TestCase):
    CASES = [None, "", "   ", "Finance", "  Review   Required ", "a\tb\nc", "x\u00a0y", "\u2003Signed\u2003",
             "Customer-Facing", "ÄÖ Ü", "İstanbul", "ß", "multi  -  dash"]

    def test_matches_original_udf(self):
        original = load_original_normalize()
        for case in self.CASES:
            self.assertEqual(migrated.normalize_tag(case), original(case), repr(case))


if __name__ == "__main__":
    unittest.main()

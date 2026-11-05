import contextlib
import io
import json
from pathlib import Path
import shlex
import tempfile
import unittest

import harness


class HarnessTests(unittest.TestCase):
    def test_first_difference_including_newline(self):
        self.assertIsNone(harness.difference(b"same\n", b"same\n"))
        self.assertEqual(harness.difference(b"a\nb\n", b"a\nc\n")["line"], 2)
        self.assertEqual(harness.difference(b"a\n", b"a")["line"], 1)
        self.assertEqual(harness.difference(None, b"")["legacy"], "missing")

    def test_comparison_missing_extra_and_report_stamp(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            for root, stamp in ((a, "20250101"), (b, "20250102")):
                (root / "reports").mkdir(parents=True)
                for ext in ("csv", "xls"):
                    (root / f"reports/finance_billing_{stamp}.{ext}").write_bytes(b"header\n")
            self.assertTrue(all(r["byte_identical"] for r in harness.compare("empty", a, b)))
            (b / "parsed").mkdir()
            (b / "parsed/extra.psv").write_bytes(b"extra")
            (b / "reports/finance_billing_20250103.csv").write_bytes(b"header\n")
            rows = harness.compare("empty", a, b)
            self.assertFalse(next(r for r in rows if r["stage"] == "parse")["byte_identical"])
            self.assertFalse(next(r for r in rows if r["stage"] == "report/csv")["byte_identical"])

    def test_wrong_candidate_and_execution_error_go_red(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            # The deliberately wrong candidate exists only inside this test.
            command = (f"bash {shlex.quote(str(harness.ESTATE / 'run_all.sh'))}; "
                       'for f in "$OTTERWORKS_LEGACY_ROOT"/parsed/*.psv; do '
                       'printf "WRONG\\n" >> "$f"; done')
            with contextlib.redirect_stdout(io.StringIO()):
                rc = harness.run(command, out / "wrong", cases=("edges",))
                error_rc = harness.run("exit 7", out / "error", cases=("empty",))
            self.assertEqual(rc, 1)
            self.assertEqual(error_rc, 1)
            report = json.loads((out / "wrong/parity.json").read_text())
            parse = next(r for r in report["rows"] if r["stage"] == "parse")
            self.assertFalse(parse["byte_identical"])
            self.assertTrue(any(f["first_difference"] for f in parse["files"]))
            errors = json.loads((out / "error/parity.json").read_text())["rows"][-1]["errors"]
            self.assertIn("exit 7", errors[1])
            print("red proof: mutated candidate exit=1; failing candidate exit=1 (exit 7 recorded)")


if __name__ == "__main__":
    unittest.main()

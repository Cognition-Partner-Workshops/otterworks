import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from compare import compare, normalise
from parity import FIXTURES, cases


class ParityTest(unittest.TestCase):
    def test_only_permitted_normalisations(self):
        text = '{"timestamp":"2026-11-05T01:02:03.456+00:00","file":"passport-1793884619833.pdf","bytes":123}'
        self.assertEqual('{"timestamp":"0000-00-00T00:00:00.000+00:00","file":"passport-<millis>.pdf","bytes":123}',
                         normalise(text))
        self.assertNotEqual(normalise(text), normalise(text.replace("+00:00", "Z")))
        self.assertEqual("other-1793884619833.pdf passport-123.pdf", normalise("other-1793884619833.pdf passport-123.pdf"))

    def test_case_order_and_distinct_fixture_sizes(self):
        self.assertEqual(23, len(cases()))
        self.assertEqual("HG611000001-passport", cases()[0][0])
        self.assertEqual("trailing-slash", cases()[-1][0])
        self.assertEqual(len(FIXTURES), len(set(FIXTURES.values())))
        self.assertEqual(4, len({len(FIXTURES[name]) for name in
                                ("passport.pdf", "id-card.jpg", "address.png", "payslip.JPEG")}))

    def test_equal_different_and_missing_cases(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            a, b = Path(directory) / "a", Path(directory) / "b"
            a.mkdir()
            b.mkdir()
            record = dict(case="test", method="GET", path="/documents/A", status=200,
                          content_type="application/json", body='["a","b"]')
            for folder in (a, b):
                (folder / "cases.json").write_text(json.dumps(["01-test.json"]))
                (folder / "01-test.json").write_text(json.dumps(record))
            self.assertEqual(0, compare(a, b))
            record["body"] = '["b","a"]'
            (b / "01-test.json").write_text(json.dumps(record))
            self.assertEqual(1, compare(a, b))
            (b / "cases.json").write_text("[]")
            self.assertEqual(1, compare(a, b))


if __name__ == "__main__":
    unittest.main()

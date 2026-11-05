import base64
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import parity


class ParityTests(unittest.TestCase):
    def test_normalization_preserves_other_bytes(self):
        body = b'[{"text":"Caf\\u00e9", "at":"2026-11-05T12:34:56.789Z"}]'
        self.assertEqual(parity.normalize("GET", "/outbox/x", body),
                         (body.replace(b"2026-11-05T12:34:56.789Z", b"<AT>"), 1))
        self.assertEqual(parity.normalize("POST", "/notify", body), (body, 0))
        self.assertEqual(parity.normalize("GET", "/outbox/x", b"[]"), (b"[]", 0))

    def test_compare_detects_each_contract_difference(self):
        record = dict(name="case", method="GET", path="/outbox/x", status=200,
                      content_type="application/json", body_base64="W10=")
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            a.mkdir()
            b.mkdir()
            (a / "cases.json").write_text(json.dumps([record]))
            variants = [(record, 0), (dict(record, status=400), 1),
                        (dict(record, content_type="text/plain"), 1),
                        (dict(record, body_base64=base64.b64encode(b"[]\n").decode()), 1)]
            for changed, expected in variants:
                with self.subTest(changed=changed):
                    (b / "cases.json").write_text(json.dumps([changed]))
                    with redirect_stdout(io.StringIO()):
                        self.assertEqual(parity.compare(a, b), expected)
            (b / "cases.json").write_text("[]")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(parity.compare(a, b), 1)


if __name__ == "__main__":
    unittest.main()

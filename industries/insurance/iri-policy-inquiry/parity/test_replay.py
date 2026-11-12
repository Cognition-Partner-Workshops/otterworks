"""Offline drift, transport and report contracts."""
import hashlib
from http.client import HTTPException, IncompleteRead
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from replay import field_diff, main, replay, write_report
from capture import OPERATIONS


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.frozen = self.root / "frozen"
        self.frozen.mkdir()
        (self.frozen / "manifest.json").write_text(json.dumps({"contracts": ["42"]}))
        self.body = {"RTN_CD": "00", "CNTR_NO": "42", "VALUE": "000123"}
        self.raw = json.dumps(self.body).encode()
        for op in OPERATIONS:
            (self.frozen / op).mkdir()
            (self.frozen / op / "42.json").write_text(json.dumps(dict(
                operation=op, contract="42", status=200,
                rawSha256=hashlib.sha256(self.raw).hexdigest(), body=self.body)))
        self.before = {str(p): p.read_bytes() for p in self.frozen.rglob("*.json")}

    def fake_fetch(self, url):
        if url.endswith("/contracts"):
            return 200, json.dumps({"RTN_CD": "00", "CNTR_CNT": "1", "CNTR_NO_001": "42"}).encode()
        return 200, self.raw

    def test_no_drift_and_read_only(self):
        with patch("replay.fetch", side_effect=self.fake_fetch):
            report, code = replay(self.frozen, "http://legacy/pinq/v1")
        self.assertEqual(code, 0)
        self.assertTrue(report["complete"])
        self.assertEqual(report["operations"]["summary"], dict(checked=1, unchanged=1, drifted=0))
        self.assertEqual(self.before, {str(p): p.read_bytes() for p in self.frozen.rglob("*.json")})

    def test_fake_body_status_and_raw_drift(self):
        def fetch(url):
            status, raw = self.fake_fetch(url)
            if "/summary/" in url:
                return 404, json.dumps(dict(self.body, VALUE="999999")).encode()
            return status, raw
        with patch("replay.fetch", side_effect=fetch):
            report, code = replay(self.frozen, "http://legacy/pinq/v1")
        self.assertEqual(code, 1)
        self.assertEqual(len(report["driftedRecords"]), 1)
        paths = {d["path"] for d in report["driftedRecords"][0]["differences"]}
        self.assertEqual(paths, {"$.status", "$.rawSha256", "$.body.VALUE"})
        write_report(report, self.root / "drift")
        self.assertIn("$.body.VALUE", (self.root / "drift.md").read_text())
        self.assertEqual(json.loads((self.root / "drift.json").read_text()), report)

    def test_raw_only_drift(self):
        def fetch(url):
            status, raw = self.fake_fetch(url)
            return status, raw + b" " if "/funds/" in url else raw
        with patch("replay.fetch", side_effect=fetch):
            report, code = replay(self.frozen, "http://legacy")
        self.assertEqual(code, 1)
        self.assertEqual([d["path"] for d in report["driftedRecords"][0]["differences"]], ["$.rawSha256"])

    def test_added_removed_contracts(self):
        def fetch(url):
            if url.endswith("/contracts"):
                return 200, b'{"RTN_CD":"00","CNTR_CNT":"1","CNTR_NO_001":"43"}'
            return 200, self.raw
        with patch("replay.fetch", side_effect=fetch):
            report, code = replay(self.frozen, "http://legacy")
        self.assertEqual(code, 1)
        self.assertEqual(report["contractsAdded"], ["43"])
        self.assertEqual(report["contractsRemoved"], ["42"])
        self.assertTrue(all(c["drifted"] == 2 for c in report["operations"].values()))

    def test_unreachable_writes_report_and_exits_two(self):
        out = self.root / "unreachable"
        with patch("replay.fetch", side_effect=OSError("connection refused")), patch(
                "sys.argv", ["replay.py", "--frozen-dir", str(self.frozen), "--out", str(out)]):
            self.assertEqual(main(), 2)
        self.assertFalse(json.loads(out.with_suffix(".json").read_text())["complete"])

    def test_empty_baseline_writes_incomplete_report(self):
        (self.frozen / "manifest.json").write_text('{"contracts":[]}')
        out = self.root / "empty-baseline"
        with patch("replay.fetch") as fetch, patch("sys.argv", [
                "replay.py", "--frozen-dir", str(self.frozen), "--out", str(out)]):
            self.assertEqual(main(), 3)
        fetch.assert_not_called()
        report = json.loads(out.with_suffix(".json").read_text())
        self.assertFalse(report["complete"])
        self.assertEqual(report["errors"][0]["kind"], "invalid-baseline")
        self.assertIn("Empty contracts", out.with_suffix(".md").read_text())

    def test_missing_and_malformed_records_write_incomplete_report(self):
        path = self.frozen / "summary/42.json"
        original = path.read_text()
        for content in (None, "not json", "[]", "{}", original.replace('"status": 200,', "")):
            with self.subTest(content=content):
                if content is None:
                    path.unlink()
                else:
                    path.write_text(content)
                out = self.root / "bad-baseline"
                with patch("replay.fetch") as fetch, patch("sys.argv", [
                        "replay.py", "--frozen-dir", str(self.frozen), "--out", str(out)]):
                    self.assertEqual(main(), 3)
                fetch.assert_not_called()
                report = json.loads(out.with_suffix(".json").read_text())
                self.assertFalse(report["complete"])
                self.assertEqual(report["errors"][0]["kind"], "invalid-baseline")
                self.assertEqual(report["errors"][0]["path"], str(path))
                self.assertIn("invalid-baseline", out.with_suffix(".md").read_text())
                path.write_text(original)

    def test_http_exceptions_preserve_partial_report(self):
        for error in (IncompleteRead(b"partial body", 100), HTTPException("broken HTTP")):
            with self.subTest(error=error):
                def fetch(url):
                    if "/values/" in url:
                        raise error
                    return self.fake_fetch(url)
                out = self.root / "partial"
                with patch("replay.fetch", side_effect=fetch), patch("sys.argv", [
                        "replay.py", "--frozen-dir", str(self.frozen), "--out", str(out)]):
                    self.assertEqual(main(), 2)
                report = json.loads(out.with_suffix(".json").read_text())
                self.assertFalse(report["complete"])
                self.assertEqual(report["operations"]["summary"]["unchanged"], 1)
                self.assertEqual(report["operations"]["values"]["checked"], 0)
                self.assertTrue(report["errors"][0]["url"].endswith("/values/42"))
                self.assertIn("Complete: False", out.with_suffix(".md").read_text())

    def test_output_cannot_touch_frozen(self):
        with patch("sys.argv", ["replay.py", "--frozen-dir", str(self.frozen),
                                "--out", str(self.frozen / "manifest.json")]), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.before, {str(p): p.read_bytes() for p in self.frozen.rglob("*.json")})

    def test_nested_added_removed_fields(self):
        differences = field_diff({"a": [1, {"b": 2}], "removed": None}, {"a": [1, {"c": 3}]})
        self.assertEqual({d["path"] for d in differences}, {"$.a[1].b", "$.a[1].c", "$.removed"})


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import run


class ParityTest(unittest.TestCase):
    def test_accounts_cover_all_seed_accounts(self):
        self.assertEqual(24, len(run.accounts()))
        self.assertEqual(24, len(set(run.accounts())))
        cases = list(run.requests_for("statements-web"))
        self.assertEqual(26, len(cases))
        self.assertEqual(24, sum(key.startswith("statement:") for key, _, _ in cases))

    def test_every_http_app_has_requests(self):
        for app in run.APPS:
            if app != "rates-batch":
                self.assertGreater(len(list(run.requests_for(app))), 0)

    def test_json_key_order_is_not_a_value_diff(self):
        self.assertEqual(
            run.comparable(b'{"a":1,"b":2}', {}), run.comparable(b'{"b":2,"a":1}', {})
        )

    def test_only_declared_timestamp_is_omitted(self):
        spec = {"omit_json_keys": ["at"]}
        a = b'[{"account":"X","at":"yesterday","text":"ready"}]'
        b = b'[{"account":"X","at":"today","text":"ready"}]'
        self.assertNotEqual(run.digest(a), run.digest(b))
        self.assertEqual(run.comparable(a, spec), run.comparable(b, spec))
        self.assertNotEqual(
            run.comparable(a, spec), run.comparable(b.replace(b"ready", b"wrong"), spec)
        )

    def test_document_name_normalization_keeps_size_and_kind(self):
        spec = {"generated_document_names": True}
        a = b'{"file":"passport-1793800000000.pdf","bytes":42}'
        b = b'{"file":"passport-1793900000000.pdf","bytes":42}'
        self.assertEqual(run.comparable(a, spec), run.comparable(b, spec))
        self.assertNotEqual(
            run.comparable(a, spec), run.comparable(b.replace(b"42", b"41"), spec)
        )

    def test_matching_errors_cannot_pass(self):
        with patch.object(run, "fetch", return_value=(500, b"same error")):
            rows = run.compare_http("fx-report", "http://vm", "http://kind", None)
        result = run.report("fx-report", rows)
        self.assertFalse(result["pass"])
        self.assertEqual("0/1", result["depth"]["HTTP status"])

    def test_network_failure_cannot_pass_or_leak_exception(self):
        with patch.object(run, "fetch", side_effect=OSError("password=secret")):
            rows = run.compare_http("fx-report", "http://vm", "http://kind", None)
        self.assertFalse(run.report("fx-report", rows)["pass"])
        self.assertNotIn("password", json.dumps(rows))

    def test_value_diffs_only_when_hash_differs(self):
        with patch.object(run, "fetch", return_value=(200, b"same")):
            rows = run.compare_http("fx-report", "http://vm", "http://kind", None)
        self.assertTrue(run.report("fx-report", rows)["pass"])
        self.assertNotIn("sample_diff", rows[0])
        with patch.object(
            run, "fetch", side_effect=[(200, b"before"), (200, b"after")]
        ):
            rows = run.compare_http("fx-report", "http://vm", "http://kind", None)
        self.assertFalse(run.report("fx-report", rows)["pass"])
        self.assertIn("sample_diff", rows[0])

    def test_all_business_days_required(self):
        with tempfile.TemporaryDirectory() as temp:
            vm, kind = Path(temp) / "vm", Path(temp) / "kind"
            vm.mkdir()
            kind.mkdir()
            self.assertFalse(
                run.report("rates-batch", run.compare_batch(vm, kind))["pass"]
            )
            for day in run.APPS["rates-batch"]["business_days"]:
                for folder in (vm, kind):
                    (folder / f"rates-{day}.csv").write_text("pair,close\nUSDGBP,0.7\n")
            result = run.report("rates-batch", run.compare_batch(vm, kind))
            self.assertTrue(result["pass"])
            self.assertEqual("3/3", result["depth"]["batch file hash per business day"])
            (kind / "rates-2026-10-16.csv").write_text("pair,close\nUSDGBP,0.8\n")
            rows = run.compare_batch(vm, kind)
            self.assertFalse(run.report("rates-batch", rows)["pass"])
            self.assertIn("sample_diff", rows[-1])

    def test_empty_batch_output_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "rates-2026-10-14.csv").touch()
            rows = run.compare_batch(root, root)
            self.assertFalse(run.report("rates-batch", rows)["pass"])

    def test_http_transport_integration(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if self.path == "/fx/fx-report.cgi" else 404)
                self.end_headers()
                self.wfile.write(b"fixture report")

            def log_message(self, *args):
                pass

        servers = [ThreadingHTTPServer(("127.0.0.1", 0), Handler) for _ in range(2)]
        threads = [
            threading.Thread(target=s.serve_forever, daemon=True) for s in servers
        ]
        try:
            for thread in threads:
                thread.start()
            bases = [f"http://127.0.0.1:{s.server_port}" for s in servers]
            rows = run.compare_http("fx-report", bases[0], bases[1], None)
            self.assertTrue(run.report("fx-report", rows)["pass"])
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()

    def test_no_empty_report_passes(self):
        self.assertFalse(run.report("fx-report", [])["pass"])
        self.assertFalse(run.report("rates-batch", [])["pass"])


if __name__ == "__main__":
    unittest.main()

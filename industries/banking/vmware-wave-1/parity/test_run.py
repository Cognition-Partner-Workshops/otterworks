import csv
import io
import json
import re
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import run

FX_BODY = b"Business date 2026-10-16<table><tr><th>Pair</th></tr><tr><td>EURUSD</td><td>1.2</td></tr></table>"


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

    def test_document_uploads_expect_created(self):
        def response(base, spec, fields, context):
            return (201 if spec.get("multipart") else 200), b'{"bytes":42}'

        with patch.object(run, "fetch", side_effect=response):
            rows = run.compare_http("kyc-docs", "http://vm", "http://kind", None)
        uploads = [row for row in rows if row["case"].startswith("upload:")]
        self.assertEqual(24, len(uploads))
        self.assertTrue(all(row["expected_status"] == 201 for row in uploads))
        self.assertTrue(run.report("kyc-docs", rows)["pass"])
        with patch.object(run, "fetch", return_value=(200, b'{"bytes":42}')):
            rows = run.compare_http("kyc-docs", "http://vm", "http://kind", None)
        self.assertFalse(run.report("kyc-docs", rows)["pass"])

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
        with patch.object(run, "fetch", return_value=(200, FX_BODY)):
            rows = run.compare_http("fx-report", "http://vm", "http://kind", None)
        self.assertTrue(run.report("fx-report", rows)["pass"])
        self.assertNotIn("sample_diff", rows[0])
        with patch.object(
            run,
            "fetch",
            side_effect=[(200, FX_BODY), (200, FX_BODY.replace(b"1.2", b"1.3"))],
        ):
            rows = run.compare_http("fx-report", "http://vm", "http://kind", None)
        self.assertFalse(run.report("fx-report", rows)["pass"])
        self.assertIn("sample_diff", rows[0])

    def test_fx_request_uses_seeded_date_and_requires_rates(self):
        spec = run.APPS["fx-report"][0]
        day = run.APPS["rates-batch"]["business_days"][-1]
        self.assertEqual(
            [day],
            run.urllib.parse.parse_qs(run.urllib.parse.urlsplit(spec["path"]).query)[
                "day"
            ],
        )
        with (run.HERE.parent / f"data/rates/in/ticks-{day}.csv").open() as source:
            pairs = {row["pair"] for row in csv.DictReader(source)}
        required_pairs = set(
            re.findall(r"<td>([A-Z]{6})</td>", "".join(spec["required_text"]))
        )
        self.assertTrue(required_pairs)
        self.assertLessEqual(required_pairs, pairs)
        for body in (
            b"No rates file for this day yet.",
            b"Business date 2026-10-16<table><th>Pair</th></table>",
        ):
            with (
                self.subTest(body=body),
                patch.object(run, "fetch", return_value=(200, body)),
            ):
                result = run.report(
                    "fx-report",
                    run.compare_http("fx-report", "http://vm", "http://kind", None),
                )
                self.assertFalse(result["pass"])
                self.assertEqual("1/1", result["depth"]["HTTP status"])
                self.assertEqual(
                    "1/1", result["depth"]["body hash per endpoint/account"]
                )
                self.assertEqual("0/1", result["depth"]["required response content"])

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

    def test_shared_batch_files_cannot_pass(self):
        for alias in ("symlink", "hardlink"):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as temp:
                vm, kind = Path(temp) / "vm", Path(temp) / "kind"
                vm.mkdir()
                kind.mkdir()
                for day in run.APPS["rates-batch"]["business_days"]:
                    source = vm / f"rates-{day}.csv"
                    source.write_text("pair,close\nEURUSD,1.2\n")
                    target = kind / source.name
                    if alias == "symlink":
                        target.symlink_to(source)
                    else:
                        target.hardlink_to(source)
                rows = run.compare_batch(vm, kind)
                self.assertFalse(run.report("rates-batch", rows)["pass"])
                self.assertTrue(all("independence_error" in row for row in rows))

    def test_loopback_aliases_cannot_compare_one_endpoint(self):
        for vm, kind in (
            ("http://localhost:8086", "http://127.0.0.1:8086/"),
            ("http://LOCALHOST.:8086", "http://[::1]:8086"),
            ("http://127.0.0.2:8086", "http://[::ffff:127.0.0.1]:8086"),
            ("http://localhost", "http://127.0.0.1:80"),
            ("https://localhost", "https://127.0.0.1:443"),
            ("http://localhost:8086/app/..", "http://127.0.0.1:8086/"),
        ):
            with (
                self.subTest(vm=vm, kind=kind),
                patch.object(
                    sys,
                    "argv",
                    [
                        "run.py",
                        "--app",
                        "fx-report",
                        "--vm-base",
                        vm,
                        "--kind-base",
                        kind,
                        "--output",
                        "unused-parity.json",
                    ],
                ),
                patch.object(run, "fetch") as fetch,
                redirect_stderr(io.StringIO()),
            ):
                with self.assertRaises(SystemExit) as raised:
                    run.main()
                self.assertEqual(2, raised.exception.code)
                fetch.assert_not_called()
        self.assertNotEqual(
            run.endpoint_key("http://localhost:8086"),
            run.endpoint_key("http://127.0.0.1:18086"),
        )

    def test_http_transport_integration(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(
                    200 if self.path == "/fx/fx-report.cgi?day=2026-10-16" else 404
                )
                self.end_headers()
                self.wfile.write(FX_BODY)

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

    def test_equivalent_non_loopback_ips_have_one_endpoint_key(self):
        for vm, kind in (
            ("http://[2001:db8::1]:8086", "http://[2001:0db8:0:0:0:0:0:1]:8086"),
            ("http://[::ffff:192.0.2.1]:8086", "http://[0:0:0:0:0:ffff:c000:201]:8086"),
            ("http://192.0.2.1:8086", "http://[::ffff:192.0.2.1]:8086"),
        ):
            with self.subTest(vm=vm, kind=kind):
                self.assertEqual(run.endpoint_key(vm), run.endpoint_key(kind))


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("reconciliation_report.py")
SPEC = importlib.util.spec_from_file_location("reconciliation_report", SCRIPT)
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)
FLEET = SCRIPT.parents[1]


def fixture_data():
    catalog = {
        "rules": [
            {
                "id": "GF01",
                "title": "First rule",
                "verdict": "agree",
                "decision": {
                    "status": "decided",
                    "option": "A",
                    "decision": "Keep the shared rule.",
                    "decided_by": "Owner",
                    "decided_on": "2026-10-27",
                    "open_items": [],
                },
                "expected_changes": [{"scope": "UK", "count": 3, "of": 10}],
                "tests": [{
                    "name": "GF01_serviceCheck",
                    "layer": "fleet-service",
                    "proves": "The service uses the shared rule.",
                }],
            },
            {
                "id": "GF02",
                "title": "Second rule",
                "verdict": "differ",
                "decision": {"status": "not-required"},
                "expected_changes": [],
                "tests": [{
                    "name": "GF02_webCheck",
                    "layer": "fleet-web",
                    "proves": "The web rule is visible.",
                }],
            },
        ],
    }
    provenance = {
        "rules": {
            ident: [{
                "role": "decision",
                "pr": 2258,
                "pr_url": f"https://example.test/pull/{ident}",
                "title": f"Decision {ident}",
                "session_url": f"https://example.test/session/{ident}",
            }]
            for ident in ("GF01", "GF02")
        },
    }
    results = {
        "generated_at": "2026-10-27T15:00:00Z",
        "commit": "abc123",
        "sources": ["uk", "de", "vitest"],
        "rules": {
            "GF01": {
                "status": "covered",
                "tests": [{
                    "name": "GF01_serviceCheck",
                    "layer": "fleet-service",
                    "results": {
                        "uk": "passed",
                        "de": "passed",
                        "vitest": "not-applicable",
                    },
                }],
            },
        },
    }
    return catalog, provenance, results


class ReconciliationReportTest(unittest.TestCase):
    def test_valid_run_preserves_catalog_order_and_missing_status(self):
        catalog, provenance, results = fixture_data()

        data = report.report_data(catalog, provenance, results)

        self.assertEqual(["GF01", "GF02"], [rule["id"] for rule in data["rules"]])
        self.assertEqual("covered", data["rules"][0]["status"])
        self.assertEqual("missing", data["rules"][1]["status"])
        self.assertEqual({
            "scope": "UK",
            "count": 3,
            "total": 10,
        }, data["rules"][0]["expected_changes"][0])
        self.assertEqual("The service uses the shared rule.", data["rules"][0]["tests"][0]["proves"])
        self.assertEqual("https://example.test/pull/GF02", data["rules"][1]["links"][0]["pr_url"])
        self.assertEqual("2026-10-27T15:00:00Z", data["generated_at"])

    def test_main_writes_valid_report(self):
        catalog, provenance, results = fixture_data()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for name, value in (
                ("catalog.json", catalog),
                ("provenance.json", provenance),
                ("results.json", results),
            ):
                path = root / name
                path.write_text(json.dumps(value))
                paths.append(path)
            destination = root / "out" / "report.json"

            exit_code = report.main([
                "--catalog", str(paths[0]),
                "--provenance", str(paths[1]),
                "--results", str(paths[2]),
                "--output", str(destination),
            ])

            self.assertEqual(0, exit_code)
            self.assertEqual(
                json.dumps(report.report_data(catalog, provenance, results), indent=2, sort_keys=True) + "\n",
                destination.read_text(),
            )

    def test_fails_for_missing_decision_status(self):
        catalog, provenance, results = fixture_data()
        catalog["rules"][0]["decision"]["status"] = ""
        with self.assertRaisesRegex(ValueError, "GF01 lacks a decision status"):
            report.report_data(catalog, provenance, results)

    def test_fails_for_catalog_rule_without_tests(self):
        catalog, provenance, results = fixture_data()
        catalog["rules"][1]["tests"] = []
        with self.assertRaisesRegex(ValueError, "GF02 has no tests"):
            report.report_data(catalog, provenance, results)

    def test_fails_for_missing_status_in_results_entry(self):
        catalog, provenance, results = fixture_data()
        results["rules"]["GF01"] = {"tests": []}
        with self.assertRaisesRegex(ValueError, "GF01 lacks a status"):
            report.report_data(catalog, provenance, results)

    def test_fails_for_missing_provenance_links(self):
        catalog, provenance, results = fixture_data()
        provenance["rules"]["GF01"] = []
        with self.assertRaisesRegex(ValueError, "GF01 lacks provenance links"):
            report.report_data(catalog, provenance, results)

    def test_fails_for_unknown_provenance_rule(self):
        catalog, provenance, results = fixture_data()
        provenance["rules"]["GF99"] = []
        with self.assertRaisesRegex(ValueError, "provenance names rule"):
            report.report_data(catalog, provenance, results)

    def test_fails_for_unknown_results_rule(self):
        catalog, provenance, results = fixture_data()
        results["rules"]["GF99"] = {"status": "missing", "tests": []}
        with self.assertRaisesRegex(ValueError, "results names rule"):
            report.report_data(catalog, provenance, results)

    def test_committed_report_matches_committed_inputs(self):
        output = FLEET / "frontend" / "fleet" / "src" / "routes" / "admin" / "reconciliation-report.json"
        actual = report.render_report()
        self.assertEqual(actual, output.read_text())


if __name__ == "__main__":
    unittest.main()

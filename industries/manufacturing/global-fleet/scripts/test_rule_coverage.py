import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("rule_coverage.py")
SPEC = importlib.util.spec_from_file_location("rule_coverage", SCRIPT)
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class RuleCoverageTest(unittest.TestCase):
    def run_coverage_with_extra(self, root, extra_statuses, strict=False):
        catalog = root / "catalog.json"
        catalog.write_text(json.dumps({
            "rules": [{
                "id": "GF01",
                "tests": [{"name": "GF01_catalogTest", "layer": "fleet-service"}],
            }],
        }))
        profile_dirs = {}
        for profile in ("uk", "de"):
            report_dir = root / profile
            report_dir.mkdir()
            status = extra_statuses.get(profile)
            extra_result = (
                f"<failure message=\"failed\"/>" if status == "failed" else
                "<skipped/>" if status == "skipped" else ""
            )
            extra_case = (
                f'<testcase name="GF01_extraCheck">{extra_result}</testcase>'
                if status
                else ""
            )
            (report_dir / "TEST-fixture.xml").write_text(
                "<testsuite>"
                '<testcase name="GF01_catalogTest"/>'
                f"{extra_case}"
                "</testsuite>"
            )
            profile_dirs[profile] = report_dir

        arguments = [
            "--catalog", str(catalog),
            "--junit", f"uk={profile_dirs['uk']}",
            "--junit", f"de={profile_dirs['de']}",
        ]
        if strict:
            arguments.append("--strict")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = coverage.main(arguments)
        return exit_code, output.getvalue()

    def test_parameterized_service_case_matches_catalog_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "TEST-service.xml"
            report.write_text(
                '<testsuite><testcase name="GF01_countryParametersComeFromProfile(uk)[1]"/>'
                "</testsuite>"
            )
            found = coverage.testcase_statuses([report])
            self.assertEqual(
                "passed",
                coverage.service_status("GF01_countryParametersComeFromProfile", found),
            )

    def test_vitest_last_segment_matches_catalog_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "vitest.xml"
            report.write_text(
                '<testsuite><testcase name="Fleet &gt; GF18_returnFunctionIsReachable renders"/>'
                "</testsuite>"
            )
            found = coverage.testcase_statuses([report])
            self.assertEqual("passed", coverage.web_status("GF18_returnFunctionIsReachable", found))

    def test_vitest_identifier_continuation_does_not_match_catalog_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "vitest.xml"
            report.write_text(
                '<testsuite><testcase name="GF18_returnFunctionIsReachableButFails"/>'
                "</testsuite>"
            )
            found = coverage.testcase_statuses([report])
            self.assertEqual("missing", coverage.web_status("GF18_returnFunctionIsReachable", found))

    def test_vitest_non_identifier_suffix_matches_catalog_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "vitest.xml"
            report.write_text(
                '<testsuite><testcase name="GF18_returnFunctionIsReachable (route)"/>'
                "</testsuite>"
            )
            found = coverage.testcase_statuses([report])
            self.assertEqual("passed", coverage.web_status("GF18_returnFunctionIsReachable", found))

    def test_failed_extra_rule_test_fails_the_rule(self):
        with tempfile.TemporaryDirectory() as temporary:
            exit_code, output = self.run_coverage_with_extra(
                Path(temporary), {"uk": "failed"})

        self.assertEqual(1, exit_code)
        self.assertIn("GF01\tGF01_extraCheck\textra\tfailed\tmissing\tnot-applicable", output)
        self.assertIn("failed: GF01", output)

    def test_passing_extra_rule_test_missing_in_de_makes_partial(self):
        with tempfile.TemporaryDirectory() as temporary:
            exit_code, output = self.run_coverage_with_extra(
                Path(temporary), {"uk": "passed"}, strict=True)

        self.assertEqual(1, exit_code)
        self.assertIn("GF01\tGF01_extraCheck\textra\tpassed\tmissing\tnot-applicable", output)
        self.assertIn("partial: GF01", output)
        self.assertIn("failed: -", output)

    def test_passing_extra_rule_test_in_both_profiles_is_covered(self):
        with tempfile.TemporaryDirectory() as temporary:
            exit_code, output = self.run_coverage_with_extra(
                Path(temporary), {"uk": "passed", "de": "passed"}, strict=True)

        self.assertEqual(0, exit_code)
        self.assertIn("GF01\tGF01_extraCheck\textra\tpassed\tpassed\tnot-applicable", output)
        self.assertIn("covered 1/1: GF01", output)
        self.assertIn("partial: -", output)
        self.assertIn("failed: -", output)

    def test_failed_case_is_not_covered(self):
        self.assertEqual("failed", coverage.aggregate(["passed", "failed"]))


if __name__ == "__main__":
    unittest.main()

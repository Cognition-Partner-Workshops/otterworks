import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("rule_coverage.py")
SPEC = importlib.util.spec_from_file_location("rule_coverage", SCRIPT)
coverage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(coverage)


class RuleCoverageTest(unittest.TestCase):
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

    def test_failed_case_is_not_covered(self):
        self.assertEqual("failed", coverage.aggregate(["passed", "failed"]))


if __name__ == "__main__":
    unittest.main()

"""Regression checks for mixed dependency-remediation states."""

import contextlib
import io
import json
import unittest
from dataclasses import replace
from unittest.mock import call, patch

import deps_check as harness


class TranscriptStateTests(unittest.TestCase):
    def setUp(self):
        self.module = harness.Module(
            id="report-service", path=harness.REPO_ROOT / "services/report-service",
            build="maven", tool="mvn", test="test", java_home=None,
            cases=harness.DEPS_DIR / "cases/report-service.json",
        )
        self.evidence = harness.REPO_ROOT / "security/evidence/report-commons-text"

    def run_auto(self, modules, trees):
        with (
            patch.object(harness, "collect_trees", return_value=trees),
            patch.object(harness, "write_report", return_value=harness.REPORT_DIR / "test.json"),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return harness.command_transcript(modules, "auto", None)

    def test_mixed_versions_get_their_own_contract_and_clean_modules_are_remediated(self):
        modules = [replace(self.module, id=name) for name in ["old", "fixed", "removed"]]
        trees = [
            harness.ModuleTree(module=modules[0], status=harness.PASS, occurrences=[
                harness.Occurrence(version="1.9", depth=1, parent=None, vulnerable=True)]),
            harness.ModuleTree(module=modules[1], status=harness.PASS, occurrences=[
                harness.Occurrence(version="1.10.0", depth=1, parent=None, vulnerable=False)]),
            harness.ModuleTree(module=modules[2], status=harness.PASS),
        ]

        def passed(module, stage):
            return {"module": module.id, "status": harness.PASS, "cases": [], "failed": []}

        with patch.object(harness, "grade_module", side_effect=passed) as grade:
            self.assertEqual(self.run_auto(modules, trees), 0)
            self.assertEqual(grade.call_args_list, [
                call(modules[0], "baseline"), call(modules[1], "remediated"),
                call(modules[2], "remediated"),
            ])

    def test_unmeasured_tree_never_gets_a_contract_or_a_pass(self):
        tree = harness.ModuleTree(module=self.module, status=harness.UNMEASURED,
                                  detail="dependency resolution failed")
        with patch.object(harness, "grade_module") as grade:
            self.assertEqual(self.run_auto([self.module], [tree]), 2)
            grade.assert_not_called()

    def grade_fixed_observation(self, observed):
        occurrences, unreadable = harness.parse_tree(
            (self.evidence / "after-tree.txt").read_text().splitlines(),
            harness.load_advisory(), "maven",
        )
        self.assertFalse(unreadable)
        self.assertTrue(occurrences)
        tree = harness.ModuleTree(module=self.module, status=harness.PASS,
                                  occurrences=occurrences)
        with patch.object(harness, "emit_transcript", return_value=observed):
            return self.run_auto([self.module], [tree])

    def test_fixed_tree_still_rejects_attack_lookup_resolution(self):
        before = json.loads((self.evidence / "report-text-before-observed.json").read_text())
        self.assertEqual(self.grade_fixed_observation(before), 1)

    def test_fixed_tree_still_rejects_a_changed_contract(self):
        after = json.loads((self.evidence / "report-text-after-observed.json").read_text())
        after["cases"][0]["value"] = "unexpectedly changed report banner"
        self.assertEqual(self.grade_fixed_observation(after), 1)

    def test_fixed_tree_accepts_the_actual_safe_captured_transcript(self):
        after = json.loads((self.evidence / "report-text-after-observed.json").read_text())
        self.assertEqual(self.grade_fixed_observation(after), 0)


if __name__ == "__main__":
    unittest.main()

import sys
from pathlib import Path

import pytest

from tests.check_coverage import main as check_coverage, read_counts
from tests.summarize_junit import main as summarize_junit


@pytest.mark.parametrize(
    ("report_format", "contents"),
    [
        ("go", "mode: atomic\napp.go:1.1,2.2 3 4\napp.go:3.1,4.2 1 0\n"),
        ("lcov", "LF:2\nLH:2\nend_of_record\nLF:2\nLH:1\nend_of_record\n"),
        ("cobertura", '<coverage lines-covered="3" lines-valid="4"/>'),
        (
            "jacoco",
            '<report><package><counter type="LINE" missed="6" covered="0"/></package>'
            '<counter type="LINE" missed="1" covered="3"/></report>',
        ),
    ],
)
def test_coverage_counts(report_format: str, contents: str, tmp_path: Path):
    report = tmp_path / "report"
    report.write_text(contents)
    assert read_counts(report_format, report) == (3, 4)


@pytest.mark.parametrize(("hit", "status", "exit_code"), [(1, "success", 0), (0, "success", 1), (1, "failure", 1)])
def test_coverage_floor_and_test_status(hit, status, exit_code, tmp_path, monkeypatch):
    report = tmp_path / "go.out"
    report.write_text(f"mode: atomic\napp.go:1.1,2.2 2 {hit}\n")
    monkeypatch.setattr(sys, "argv", ["check_coverage", "api-gateway", str(report), "--tests", status])
    assert check_coverage() == exit_code


@pytest.mark.parametrize(
    ("cases", "exit_code"),
    [
        ("", 1),
        ("<testcase><skipped/></testcase>", 1),
        ("<testcase/><testcase><skipped/></testcase>", 0),
        ("<testcase/><testcase><error/></testcase>", 1),
        ("<testcase><failure/></testcase>", 1),
    ],
)
def test_junit_requires_executed_and_successful_tests(cases, exit_code, tmp_path, monkeypatch):
    report = tmp_path / "suite.xml"
    report.write_text(f"<testsuites><testsuite>{cases}</testsuite></testsuites>")
    monkeypatch.setattr(sys, "argv", ["summarize_junit", str(report)])
    assert summarize_junit() == exit_code

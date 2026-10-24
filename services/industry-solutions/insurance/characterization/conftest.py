from __future__ import annotations

import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

import pytest

from harness import HERE, Harness, connect, connect_warehouse, dump_json, reset_to_seed, reset_warehouse
from rules import RULES

GOLDEN_DIR = HERE / "golden"
OUT_DIR = HERE / "out"


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden",
        action="store_true",
        help="rewrite golden/*.json from the live Oracle fixture instead of comparing",
    )


@pytest.fixture(scope="session")
def connections():
    caller, observer = connect(), connect()
    with observer.cursor() as cur:
        cur.execute(
            "SELECT parameter, value FROM nls_session_parameters"
            " WHERE parameter IN ('NLS_NUMERIC_CHARACTERS', 'NLS_LANGUAGE', 'NLS_TERRITORY')"
        )
        nls = dict(cur.fetchall())
    # R38 messages depend on the session's decimal separator.
    assert nls["NLS_NUMERIC_CHARACTERS"] == ".,", nls
    warehouse = connect_warehouse()
    reset_to_seed(caller)
    reset_warehouse(warehouse)
    yield caller, observer
    caller.rollback()
    reset_to_seed(caller)
    reset_warehouse(warehouse)
    caller.close()
    observer.close()
    warehouse.close()


@pytest.fixture
def h(connections) -> Harness:
    caller, observer = connections
    caller.rollback()
    reset_to_seed(caller)
    return Harness(caller, observer)


def golden_path(item) -> Path:
    module = Path(item.fspath).stem.removeprefix("test_")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", item.name).strip("_")
    return GOLDEN_DIR / f"{module}__{name}.json"


@pytest.hookimpl(wrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    result = yield
    harness = pyfuncitem.funcargs.get("h")
    if harness is None:
        return result
    rules = sorted({r for m in pyfuncitem.iter_markers("rule") for r in m.args}, key=lambda r: int(r[1:]))
    record = {"test": pyfuncitem.nodeid, "rules": rules, "steps": harness.steps}
    path = golden_path(pyfuncitem)
    actual = dump_json(record)
    if pyfuncitem.config.getoption("--update-golden"):
        path.parent.mkdir(exist_ok=True)
        path.write_text(actual)
        return result
    if not path.exists():
        pytest.fail(f"no golden file {path.relative_to(HERE)}; run with --update-golden to create it")
    expected = path.read_text()
    if expected != actual:
        delta = "".join(difflib.unified_diff(
            expected.splitlines(keepends=True), actual.splitlines(keepends=True),
            fromfile=f"golden/{path.name}", tofile="live Oracle"))
        pytest.fail(f"behaviour drifted from the pinned baseline:\n{delta}", pytrace=False)
    return result


# --------------------------------------------------------------------------
# Rule report: one row per RULE_LEDGER rule with the tests that pin it.
# --------------------------------------------------------------------------

_results: dict[str, str] = {}
_rules_by_test: dict[str, list[str]] = {}


# tryfirst: record every collected test before -k/-m/--deselect drop any, so a
# partial run reports the rules it did not fully exercise as INCOMPLETE.
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    for item in items:
        _rules_by_test[item.nodeid] = [r for m in item.iter_markers("rule") for r in m.args]
        unknown = set(_rules_by_test[item.nodeid]) - RULES.keys()
        if unknown:
            raise pytest.UsageError(f"{item.nodeid} marks unknown rule(s) {sorted(unknown)}")


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and not report.passed):
        _results[report.nodeid] = "skipped" if report.skipped else report.outcome


def pytest_sessionfinish(session, exitstatus):
    if not _results:
        return
    by_rule: dict[str, list[str]] = defaultdict(list)
    for nodeid, rules in _rules_by_test.items():
        for r in rules:
            by_rule[r].append(nodeid)

    rows = []
    for rid, (area, text, legacy) in RULES.items():
        tests = by_rule.get(rid, [])
        passed = sum(_results.get(t) == "passed" for t in tests)
        failed = sum(_results.get(t) == "failed" for t in tests)
        not_run = sum(t not in _results for t in tests)
        if not tests:
            verdict = "NOT COVERED"
        elif failed:
            verdict = "FAIL"
        elif passed == len(tests):
            verdict = "PASS"
        else:
            verdict = "INCOMPLETE"
        rows.append({
            "rule": rid, "area": area, "text": text, "legacy": legacy,
            "tests": len(tests), "passed": passed, "failed": failed, "not_run": not_run, "verdict": verdict,
            "test_ids": tests,
        })

    totals = {
        "rules": len(rows),
        "rules_pass": sum(r["verdict"] == "PASS" for r in rows),
        "tests": len(_rules_by_test),
        "tests_not_run": sum(t not in _results for t in _rules_by_test),
        "tests_passed": sum(v == "passed" for v in _results.values()),
        "tests_failed": sum(v == "failed" for v in _results.values()),
        "tests_skipped": sum(v == "skipped" for v in _results.values()),
    }
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "rule_report.json").write_text(json.dumps({"rules": rows, "totals": totals}, indent=2) + "\n")

    def short(nodeid: str) -> str:
        return nodeid.split("::", 1)[1]

    lines = [
        "| Rule | Procedure | Behaviour | Legacy run_tests.sql | Harness tests passed | Result |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        legacy = r["legacy"] if r["legacy"].startswith("covered") else f"**{r['legacy']}**"
        lines.append(
            f"| {r['rule']} | `{r['area']}` | {r['text']} | {legacy} | "
            f"{r['passed']}/{r['tests']} | {r['verdict']} |"
        )
    lines.append(
        f"| **Total** | | {totals['rules_pass']}/{totals['rules']} rules PASS | | "
        f"{totals['tests_passed']}/{totals['tests']} tests passed | |"
    )
    lines += ["", "### Tests per rule", ""]
    for r in rows:
        lines.append(f"- **{r['rule']}**: " + ", ".join(f"`{short(t)}`" for t in r["test_ids"]))
    (OUT_DIR / "rule_report.md").write_text("\n".join(lines) + "\n")

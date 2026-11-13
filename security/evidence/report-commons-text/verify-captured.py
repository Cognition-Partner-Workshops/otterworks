"""Grade archived real Java-8 Maven outputs with the unchanged repository grader.

This verifies captured evidence; it does not rerun Maven or claim an estate gate.
"""
import importlib.util
import json
import pathlib
import sys

evidence = pathlib.Path(__file__).resolve().parent
root = evidence.parents[2]
spec = importlib.util.spec_from_file_location(
    "deps_check", root / "security/deps/harness/deps_check.py"
)
harness = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = harness
spec.loader.exec_module(harness)
advisory = harness.load_advisory()
module = harness.Module(
    id="report-service",
    path=root / "services/report-service",
    build="maven",
    tool="mvn in Java 8 local/report-builder:baseline (captured)",
    test="test",
    cases=root / "security/deps/cases/report-service.json",
    java_home=None,
)
for phase, stage, version in [
    ("before", "baseline", "1.9"),
    ("after", "remediated", "1.10.0"),
]:
    occurrences, unreadable = harness.parse_tree(
        (evidence / f"{phase}-tree.txt").read_text().splitlines(), advisory, "maven"
    )
    assert not unreadable and occurrences
    assert {occurrence.version for occurrence in occurrences} == {version}
    assert all(occurrence.vulnerable == (phase == "before") for occurrence in occurrences)
    observed = json.loads((evidence / f"report-text-{phase}-observed.json").read_text())
    # Only replace process invocation with its archived emitted JSON. All policy,
    # fingerprint and contract/attack comparisons remain in the original grader.
    harness.emit_transcript = lambda module: observed
    result = harness.grade_module(module, stage)
    assert result["status"] == "pass", result
    print(f"{phase}: version {version}; {len(result['cases'])} transcript cases PASS")

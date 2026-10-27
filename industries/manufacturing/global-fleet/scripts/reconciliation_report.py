#!/usr/bin/env python3
"""Build the deterministic admin reconciliation report from discovery inputs."""

import argparse
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
FLEET = HERE.parent
DEFAULT_CATALOG = FLEET / "discovery" / "catalog.json"
DEFAULT_PROVENANCE = FLEET / "discovery" / "provenance.json"
DEFAULT_RESULTS = FLEET / "discovery" / "test-results.json"
DEFAULT_OUTPUT = FLEET / "frontend" / "fleet" / "src" / "routes" / "admin" / "reconciliation-report.json"
VALID_STATUSES = {"covered", "partial", "failed", "missing"}


def report_data(catalog, provenance, results):
    catalog_rules = catalog.get("rules")
    provenance_rules = provenance.get("rules")
    result_rules = results.get("rules")
    if not isinstance(catalog_rules, list):
        raise ValueError("catalog rules must be a list")
    if not isinstance(provenance_rules, dict):
        raise ValueError("provenance rules must be an object")
    if not isinstance(result_rules, dict):
        raise ValueError("test results rules must be an object")

    catalog_ids = [rule.get("id") for rule in catalog_rules]
    if any(not ident for ident in catalog_ids) or len(set(catalog_ids)) != len(catalog_ids):
        raise ValueError("catalog rule ids must be present and unique")
    catalog_id_set = set(catalog_ids)
    for source, source_rules in (("provenance", provenance_rules), ("results", result_rules)):
        unknown = sorted(set(source_rules) - catalog_id_set)
        if unknown:
            raise ValueError(f"{source} names rule(s) not in catalog: {', '.join(unknown)}")

    sources = results.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("test result sources must be a list")

    report = {}
    for metadata_key in ("generated_at", "commit"):
        if metadata_key in results:
            report[metadata_key] = results[metadata_key]

    report_rules = []
    for rule in catalog_rules:
        ident = rule["id"]
        rule_results = result_rules.get(ident)
        if rule_results is None:
            status = "missing"
            tested = []
        else:
            if not isinstance(rule_results, dict) or not isinstance(rule_results.get("status"), str):
                raise ValueError(f"{ident} lacks a status")
            status = rule_results["status"]
            if status not in VALID_STATUSES:
                raise ValueError(f"{ident} has invalid status {status!r}")
            tested = rule_results.get("tests", [])
            if not isinstance(tested, list):
                raise ValueError(f"{ident} tests must be a list")

        decision = rule.get("decision")
        if not isinstance(decision, dict) or not isinstance(decision.get("status"), str) or not decision["status"].strip():
            raise ValueError(f"{ident} lacks a decision status")

        catalog_tests = rule.get("tests", [])
        if not isinstance(catalog_tests, list):
            raise ValueError(f"{ident} catalog tests must be a list")
        catalog_test_map = {
            (test.get("name"), test.get("layer")): test
            for test in catalog_tests
        }
        if not tested:
            tested = [
                {
                    "name": test["name"],
                    "layer": test["layer"],
                    "results": {source: "missing" for source in sources},
                }
                for test in catalog_tests
            ]
        if not tested:
            raise ValueError(f"{ident} has no tests")

        tests = []
        for test in tested:
            if not isinstance(test, dict) or not test.get("name") or not test.get("layer"):
                raise ValueError(f"{ident} has an invalid test entry")
            catalog_test = catalog_test_map.get((test["name"], test["layer"]), {})
            tests.append({
                "name": test["name"],
                "layer": test["layer"],
                "proves": catalog_test.get("proves", ""),
                "results": test.get("results", {}),
            })

        links = provenance_rules.get(ident)
        if not isinstance(links, list) or not links or not any(
            link.get("pr_url") and link.get("session_url")
            for link in links
            if isinstance(link, dict)
        ):
            raise ValueError(f"{ident} lacks provenance links")

        expected_changes = [
            {
                "scope": change.get("scope"),
                "count": change.get("count"),
                **({"total": change["of"]} if "of" in change else {}),
            }
            for change in rule.get("expected_changes", [])
        ]
        report_rules.append({
            "id": ident,
            "title": rule.get("title", ""),
            "verdict": rule.get("verdict", ""),
            "status": status,
            "decision": {
                "status": decision.get("status"),
                "option": decision.get("option"),
                "decision": decision.get("decision"),
                "decided_by": decision.get("decided_by"),
                "decided_on": decision.get("decided_on"),
                "open_items": decision.get("open_items", []),
            },
            "expected_changes": expected_changes,
            "tests": tests,
            "links": links,
        })
    report["rules"] = report_rules
    return report


def render_report(catalog_path=DEFAULT_CATALOG, provenance_path=DEFAULT_PROVENANCE, results_path=DEFAULT_RESULTS):
    catalog = json.loads(Path(catalog_path).read_text())
    provenance = json.loads(Path(provenance_path).read_text())
    results = json.loads(Path(results_path).read_text())
    return json.dumps(report_data(catalog, provenance, results), indent=2, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        output = render_report(args.catalog, args.provenance, args.results)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"reconciliation report: {error}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())

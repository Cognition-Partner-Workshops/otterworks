#!/usr/bin/env python3
"""Compare catalog test names with Maven and Vitest JUnit XML reports."""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CATALOG = HERE.parent / "discovery" / "catalog.json"
PARAMETER_SUFFIX = re.compile(r"(?:\([^()]*\)|\[\d+\])$")


def normalize_testcase_name(name):
    while True:
        normalized = PARAMETER_SUFFIX.sub("", name)
        if normalized == name:
            return normalized
        name = normalized


def testcase_statuses(xml_files):
    statuses = {}
    for xml_file in xml_files:
        root = ET.parse(xml_file).getroot()
        for case in root.iter("testcase"):
            name = case.attrib.get("name", "")
            if case.find("failure") is not None or case.find("error") is not None:
                status = "failed"
            elif case.find("skipped") is not None:
                status = "skipped"
            else:
                status = "passed"
            statuses.setdefault(name, []).append(status)
    return statuses


def service_status(name, testcases):
    matched = [
        status
        for testcase, results in testcases.items()
        if normalize_testcase_name(testcase) == name
        for status in results
    ]
    return aggregate(matched)


def extra_test_name(name):
    return normalize_testcase_name(name).rsplit(" > ", 1)[-1]


def extra_test_names(rule_id, sources, catalog_names):
    prefix = f"{rule_id}_"
    return sorted({
        candidate
        for testcases in sources
        for testcase in testcases
        for candidate in [extra_test_name(testcase)]
        if candidate.startswith(prefix) and candidate not in catalog_names
    })


def extra_test_status(name, testcases):
    matched = [
        status
        for testcase, results in testcases.items()
        if extra_test_name(testcase) == name
        for status in results
    ]
    return aggregate(matched)


def web_status(name, testcases):
    matched = []
    for testcase, results in testcases.items():
        last_segment = testcase.rsplit(" > ", 1)[-1]
        if (
            testcase == name
            or testcase.startswith(name)
            or last_segment == name
            or last_segment.startswith(name)
        ):
            matched.extend(results)
    return aggregate(matched)


def aggregate(statuses):
    if not statuses:
        return "missing"
    if "failed" in statuses:
        return "failed"
    if all(status == "passed" for status in statuses):
        return "passed"
    return "skipped" if "skipped" in statuses else "missing"


def parse_junit_arguments(values):
    result = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("--junit must use NAME=DIR")
        name, directory = value.split("=", 1)
        if not name or not directory:
            raise argparse.ArgumentTypeError("--junit must use NAME=DIR")
        result[name] = testcase_statuses(sorted(Path(directory).glob("TEST-*.xml")))
    return result


def rule_status(test_statuses):
    if test_statuses and all(status == "passed" for status in test_statuses):
        return "covered"
    if "failed" in test_statuses:
        return "failed"
    if "passed" in test_statuses:
        return "partial"
    return "missing"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--junit", action="append", default=[], metavar="NAME=DIR")
    parser.add_argument("--vitest", type=Path)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    catalog = json.loads(args.catalog.read_text())
    profiles = parse_junit_arguments(args.junit)
    web = testcase_statuses([args.vitest]) if args.vitest else {}

    sources = list(profiles) + ["vitest"]
    source_testcases = list(profiles.values()) + [web]
    catalog_names = {
        normalize_testcase_name(test["name"])
        for rule in catalog["rules"]
        for test in rule.get("tests", [])
    }
    print("rule\ttest\tlayer\t" + "\t".join(sources))
    per_rule = {}
    any_failed = False
    for rule in catalog["rules"]:
        statuses_for_rule = []
        for test in rule.get("tests", []):
            if test["layer"] == "fleet-service":
                statuses = [service_status(test["name"], values) for values in profiles.values()]
                if not profiles:
                    statuses = ["missing"]
                display_statuses = statuses + ["not-applicable"]
            else:
                statuses = [web_status(test["name"], web)]
                display_statuses = ["not-applicable"] * len(profiles) + statuses
            any_failed |= "failed" in statuses
            statuses_for_rule.append(statuses)
            print(
                f'{rule["id"]}\t{test["name"]}\t{test["layer"]}\t'
                + "\t".join(display_statuses)
            )
        for test_name in extra_test_names(rule["id"], source_testcases, catalog_names):
            statuses = [
                extra_test_status(test_name, testcases)
                for testcases in source_testcases
            ]
            any_failed |= "failed" in statuses
            statuses_for_rule.append([status for status in statuses if status != "missing"])
            display_statuses = [
                status if status != "missing" else "not-applicable"
                for status in statuses
            ]
            print(
                f'{rule["id"]}\t{test_name}\textra\t'
                + "\t".join(display_statuses)
            )
        flattened = [status for test_statuses in statuses_for_rule for status in test_statuses]
        per_rule[rule["id"]] = rule_status(flattened)

    covered = [ident for ident, status in per_rule.items() if status == "covered"]
    partial = [ident for ident, status in per_rule.items() if status == "partial"]
    failed = [ident for ident, status in per_rule.items() if status == "failed"]
    missing = [ident for ident, status in per_rule.items() if status == "missing"]
    print(f"covered {len(covered)}/{len(catalog['rules'])}: {', '.join(covered) or '-'}")
    print("partial: " + (", ".join(partial) or "-"))
    print("failed: " + (", ".join(failed) or "-"))
    print("missing: " + (", ".join(missing) or "-"))
    if any_failed or (args.strict and (partial or missing)):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

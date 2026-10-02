#!/usr/bin/env python3
"""Verify migration/billing/access_patterns.md: every `path:line[-line]` cite
resolves to an existing line, and the per-package table sets match the
DBA_DEPENDENCIES edges captured in migration/billing/census.json. Stdlib only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "migration/billing/access_patterns.md"
SIDECAR = Path(__file__).with_name("access_patterns.json")
CENSUS = ROOT / "migration/billing/census.json"

CITE = re.compile(r"`((?:[\w.-]+/)+[\w.-]+\.(?:py|sql|yaml|json|go|ts|md)):(\d+)(?:-(\d+))?`")


def check_cites(text, verbose):
    bad = 0
    seen = 0
    cache = {}
    for match in CITE.finditer(text):
        path, start, end = match.group(1), int(match.group(2)), match.group(3)
        end = int(end) if end else start
        seen += 1
        lines = cache.get(path)
        if lines is None:
            file = ROOT / path
            lines = file.read_text().splitlines() if file.is_file() else None
            cache[path] = lines
        if lines is None:
            print(f"MISSING FILE {path}:{start}")
            bad += 1
            continue
        if not (1 <= start <= end <= len(lines)):
            print(f"OUT OF RANGE {path}:{start}-{end} (file has {len(lines)} lines)")
            bad += 1
            continue
        if verbose:
            print(f"{path}:{start}-{end} | {lines[start - 1].strip()[:90]}")
    return seen, bad


def check_dependencies(sidecar, census):
    edges = {}
    for dep in census["dependencies"]["internal"]:
        if dep["type"] == "PACKAGE BODY" and dep["referenced_type"] == "TABLE":
            edges.setdefault(dep["name"], set()).add(dep["referenced_name"])
    bad = 0
    for package, tables in sidecar["package_tables"].items():
        stated = set(tables["static"])
        actual = edges.get(package, set())
        status = "ok" if stated == actual else "MISMATCH"
        bad += status != "ok"
        extra = f" dynamic-only={sorted(tables['dynamic_sql_only'])}" if tables["dynamic_sql_only"] else ""
        print(f"{package}: doc={sorted(stated)} dictionary={sorted(actual)} {status}{extra}")
    unknown = set(edges) - set(sidecar["package_tables"])
    if unknown:
        print(f"packages in census not covered by the doc: {sorted(unknown)}")
        bad += 1
    return bad


def main(argv):
    verbose = "--verbose" in argv
    text = DOC.read_text()
    sidecar = json.loads(SIDECAR.read_text())
    census = json.loads(CENSUS.read_text())
    seen, bad_cites = check_cites(text, verbose)
    print(f"cites: {seen} checked, {bad_cites} unresolved")
    bad_deps = check_dependencies(sidecar, census)
    missing = [name for name in sidecar["entrypoints"] if f"`{name}(" not in text]
    if missing:
        print(f"entrypoints without a section: {missing}")
    census_tables = {t["name"].lower() for t in census["tables"] if t["bucket"] == "migrate"}
    uncounted = sorted(census_tables - set(sidecar["table_sites"]))
    if uncounted:
        print(f"migrate-bucket tables without a read/write row: {uncounted}")
    failed = bad_cites or bad_deps or missing or uncounted
    print("access_patterns check:", "FAIL" if failed else "PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Verify migration/billing/units.md + units/units.json against the merged
inputs: every spec collection, migrate-bucket table, access-pattern entrypoint
and facade-contract route lands in exactly one unit; the 21 secondary indexes
sum across units; every atomic unit is intra-unit or declared in cross_unit;
every `path:line` cite in units.md resolves; open decisions match the spec.
Stdlib only, read-only."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "migration/billing/units.md"
MODEL = Path(__file__).with_name("units.json")
SPEC = ROOT / "migration/billing/mapping_spec.json"
CENSUS = ROOT / "migration/billing/census.json"
BUCKETS = ROOT / "migration/billing/census/buckets.json"
ACCESS = ROOT / "migration/billing/access_patterns/access_patterns.json"
CONTRACT = ROOT / "docs/tech-partnerships/contracts/billing-facade.contract.json"

CITE = re.compile(r"`((?:[\w.-]+/)+[\w.-]+\.(?:py|sql|yaml|yml|json|md)|Makefile):(\d+)(?:-(\d+))?`")


def partition(label, expected, units, key, verbose, allow_extra=False):
    owners = {}
    for unit in units:
        for item in unit.get(key, []):
            owners.setdefault(item, []).append(unit["id"])
    bad = 0
    extra = set(owners) - set(expected)
    if allow_extra:
        for item in sorted(extra):
            if len(owners[item]) != 1:
                print(f"{label} {item}: owned by {owners[item]}")
                bad += 1
        owners = {item: who for item, who in owners.items() if item in expected}
    for item in sorted(expected):
        who = owners.get(item, [])
        if len(who) != 1:
            print(f"{label} {item}: owned by {who or 'nobody'}")
            bad += 1
        elif verbose:
            print(f"{label} {item} -> {who[0]}")
    for item in sorted(set(owners) - set(expected)):
        print(f"{label} {item}: assigned by {owners[item]} but not in the input")
        bad += 1
    print(f"{label}: {len(expected)} expected, {len(owners)} assigned, {bad} problems")
    return bad


def check_cites(text, verbose):
    bad = seen = 0
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
        elif not (1 <= start <= end <= len(lines)):
            print(f"OUT OF RANGE {path}:{start}-{end} (file has {len(lines)} lines)")
            bad += 1
        elif verbose:
            print(f"{path}:{start}-{end} | {lines[start - 1].strip()[:90]}")
    print(f"cites: {seen} checked, {bad} problems")
    return bad


def main(argv):
    verbose = "--verbose" in argv
    model = json.loads(MODEL.read_text())
    spec = json.loads(SPEC.read_text())
    census = json.loads(CENSUS.read_text())
    buckets = json.loads(BUCKETS.read_text())
    access = json.loads(ACCESS.read_text())
    contract = json.loads(CONTRACT.read_text())
    doc = DOC.read_text()
    units = model["units"]
    bad = 0

    if model["run_branch"] != spec["run_branch"]:
        print(f"run_branch mismatch: {model['run_branch']} vs spec {spec['run_branch']}")
        bad += 1

    by_name = {c["name"]: c for c in spec["collections"]}
    bad += partition("collection", set(by_name), units, "collections", verbose)

    # source tables follow their collection; the union must be the migrate bucket
    migrate_tables = {
        key.split(":", 1)[1]
        for key, value in buckets.get("objects", buckets).items()
        if isinstance(value, dict) and key.startswith("TABLE:") and value["bucket"] == "migrate"
    }
    tables_by_unit = {}
    for unit in units:
        unit_tables = set()
        for name in unit["collections"]:
            unit_tables.update(by_name[name]["source_tables"])
        tables_by_unit[unit["id"]] = unit_tables
    covered = set().union(*tables_by_unit.values())
    for table in sorted(migrate_tables ^ covered):
        print(f"table {table}: {'not covered by any unit' if table in migrate_tables else 'not in the migrate bucket'}")
        bad += 1
    overlaps = [
        (a, b, sorted(tables_by_unit[a] & tables_by_unit[b]))
        for a in tables_by_unit for b in tables_by_unit if a < b and tables_by_unit[a] & tables_by_unit[b]
    ]
    for a, b, shared in overlaps:
        print(f"tables {shared} owned by both {a} and {b}")
        bad += 1
    print(f"tables: {len(migrate_tables)} in migrate bucket, {len(covered)} covered, spec says {spec['stats']['migrate_tables']}")

    # indexes and live rows roll up per unit
    rows = {t["name"]: t["rows"] for t in census["tables"]}
    total_idx = 0
    for unit in units:
        idx = sum(len(by_name[n]["indexes"]) for n in unit["collections"])
        live = sum(rows.get(t, 0) for t in tables_by_unit[unit["id"]])
        total_idx += idx
        print(f"{unit['id']} {unit['name']}: {len(unit['collections'])} collections, "
              f"{len(tables_by_unit[unit['id']])} tables, {idx} indexes, {live} live rows")
    if total_idx != spec["stats"]["secondary_indexes"]:
        print(f"indexes: units sum to {total_idx}, spec has {spec['stats']['secondary_indexes']}")
        bad += 1

    bad += partition("entrypoint", set(access["entrypoints"]), units, "entrypoints", verbose)
    routes = {f"{r['method']} {r['path']}" for r in contract["routes"]}
    bad += partition("contract route", routes, units, "routes", verbose, allow_extra=True)

    # atomic units: intra-unit, or every foreign collection is a declared cross_unit edge
    owner = {name: unit["id"] for unit in units for name in unit["collections"]}
    embedded = {"rating_results": "rating_periods", "invoice_lines": "invoices"}  # table names the spec keeps in atomic_unit
    declared = {(edge["from"], edge["to"], c) for edge in model["cross_unit"] for c in edge["collections"]}
    for name, pattern in spec["access_pattern_coverage"].items():
        atomic = pattern.get("atomic_unit")
        if not atomic:
            continue
        home = next(u["id"] for u in units if name in u["entrypoints"])
        for coll in (embedded.get(c, c) for c in atomic):
            coll_owner = owner[coll]
            if coll_owner != home and (home, coll_owner, coll) not in declared:
                print(f"atomic unit {name} writes {coll} ({coll_owner}) from {home} without a cross_unit edge")
                bad += 1
        if verbose:
            print(f"atomic {name}: {home} -> {sorted(set(owner[embedded.get(c, c)] for c in atomic))}")

    # waves: each unit in exactly one wave, wave 2 after wave 1
    wave_of = {}
    for wave in model["waves"]:
        for uid in wave["units"]:
            wave_of.setdefault(uid, []).append(wave["wave"])
    for unit in units:
        if wave_of.get(unit["id"]) != [unit["wave"]]:
            print(f"{unit['id']}: wave {unit['wave']} in the unit, {wave_of.get(unit['id'])} in waves[]")
            bad += 1
    for edge in model["cross_unit"]:
        if edge["from"] == "*" or edge.get("deferred_to_wave"):
            continue
        if wave_of[edge["from"]][0] < wave_of[edge["to"]][0]:
            print(f"cross_unit {edge['from']} -> {edge['to']} points at a later wave")
            bad += 1

    # open decisions: same set as the spec, none resolved here
    spec_open = set(spec["decisions"]["open"])
    model_open = set(model["decisions"]["open"])
    if spec_open != model_open:
        print(f"open decisions differ: model {sorted(model_open)} vs spec {sorted(spec_open)}")
        bad += 1
    if set(model["decisions"]["applied"]) & spec_open:
        print("an open decision is marked applied")
        bad += 1

    # the markdown names every unit, collection and open decision
    for token in [u["id"] for u in units] + sorted(by_name) + sorted(spec_open):
        if f"`{token}`" not in doc and f"**{token}" not in doc and f"## {token}" not in doc and f"| {token} " not in doc:
            print(f"units.md does not mention {token}")
            bad += 1
    bad += check_cites(doc, verbose)

    print("OK" if not bad else f"FAIL ({bad} problems)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

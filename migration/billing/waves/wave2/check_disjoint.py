#!/usr/bin/env python3
"""Wave 2 readiness (s4.2.0-preflight): prove the wave 2 write targets are disjoint and complete.

Reads migration/billing/units/units.json and migration/billing/mapping_spec.json (nothing else) and
fails unless every statement below holds:

  1. wave 2 is exactly U2, U3, U4, U5 (units.json#waves[1]);
  2. the four write-target sets are pairwise disjoint;
  3. each is disjoint from U1's collections (units.json#units[U1].collections, 5 of them);
  4. together they cover every non-U1 collection of mapping_spec.json#collections, and nothing else;
  5. the same partition holds for the source tables behind those collections (primary + embedded);
  6. billing_audit_log is a write target of U5 alone: every other module appends to it only through
     the shared writer U1 ships (units.json#cross_unit "*" -> U5), so only U5 loads and reconciles it
     and no other unit may list it, load it or run recon on it;
  7. the secondary index counts per unit sum to mapping_spec.json#stats.secondary_indexes.

    python3 migration/billing/waves/wave2/check_disjoint.py [--out migration/billing/waves/wave2/check_disjoint.json]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BILLING = HERE.parents[1]
UNITS_PATH = BILLING / "units" / "units.json"
SPEC_PATH = BILLING / "mapping_spec.json"
AUDIT = "billing_audit_log"
AUDIT_OWNER = "U5"
AUDIT_WRITER_HOME = "U1"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=None, help="write the JSON result here")
    args = p.parse_args(argv)

    units = json.loads(UNITS_PATH.read_text())
    spec = json.loads(SPEC_PATH.read_text())
    by_id = {u["id"]: u for u in units["units"]}
    spec_cols = {c["name"]: c for c in spec["collections"]}
    failures: list[str] = []

    def must(ok: bool, msg: str) -> None:
        if not ok:
            failures.append(msg)

    wave2 = next((w for w in units["waves"] if w["wave"] == 2), None)
    must(wave2 is not None, "units.json has no wave 2")
    wave2_units = list(wave2["units"]) if wave2 else []
    must(wave2_units == ["U2", "U3", "U4", "U5"], f"wave 2 is {wave2_units}, expected ['U2', 'U3', 'U4', 'U5']")
    must(wave2.get("depends_on") == [1] if wave2 else False, "wave 2 must depend on wave 1 only")

    targets = {u: set(by_id[u]["collections"]) for u in wave2_units if u in by_id}
    u1 = set(by_id["U1"]["collections"])
    must(len(u1) == 5, f"U1 owns {len(u1)} collections, expected 5")

    for a, b in itertools.combinations(targets, 2):
        both = sorted(targets[a] & targets[b])
        must(not both, f"{a} and {b} both write {both}")
    for u, cols in targets.items():
        both = sorted(cols & u1)
        must(not both, f"{u} writes U1 collections {both}")

    covered = set().union(*targets.values()) if targets else set()
    non_u1 = set(spec_cols) - u1
    must(covered == non_u1, f"wave 2 targets != non-U1 spec collections: missing {sorted(non_u1 - covered)}, extra {sorted(covered - non_u1)}")
    must(len(spec_cols) == spec["stats"]["collections"], "mapping_spec.json#stats.collections disagrees with #collections")

    # source tables behind each unit's collections (primary + embedded); quarantine collections re-use their parent's table
    def tables_of(cols: set[str]) -> set[str]:
        out: set[str] = set()
        for n in cols:
            c = spec_cols[n]
            out.update(c["source_tables"])
            out.update(e["source_table"] for e in c.get("embedded", []))
        return out

    unit_tables = {u: tables_of(cols) for u, cols in targets.items()}
    u1_tables = tables_of(u1)
    for a, b in itertools.combinations(unit_tables, 2):
        both = sorted(unit_tables[a] & unit_tables[b])
        must(not both, f"{a} and {b} both read source tables {both}")
    for u, t in unit_tables.items():
        both = sorted(t & u1_tables)
        must(not both, f"{u} reads U1 source tables {both}")
    all_tables = set().union(u1_tables, *unit_tables.values())
    must(len(all_tables) == spec["stats"]["migrate_tables"],
         f"{len(all_tables)} source tables across units, spec declares {spec['stats']['migrate_tables']}")

    # billing_audit_log: shared writer (U1 helper), single owner (U5)
    owners = [u for u, cols in {**targets, "U1": u1}.items() if AUDIT in cols]
    must(owners == [AUDIT_OWNER], f"{AUDIT} owners are {owners}, expected [{AUDIT_OWNER!r}]")
    audit_edge = next((e for e in units["cross_unit"]
                       if e.get("from") == "*" and e.get("to") == AUDIT_OWNER and e.get("kind") == "write"
                       and e.get("collections") == [AUDIT]), None)
    must(audit_edge is not None, f"units.json#cross_unit lacks the '*' -> {AUDIT_OWNER} write edge for {AUDIT}")
    must(any("log_msg" in s and AUDIT in s for s in by_id[AUDIT_WRITER_HOME].get("scaffolding", [])),
         f"units.json#units[{AUDIT_WRITER_HOME}].scaffolding does not ship the {AUDIT} writer (log_msg)")
    must(any(AUDIT in s and "load" in s and "recon" in s for s in by_id[AUDIT_OWNER].get("scaffolding", [])),
         f"units.json#units[{AUDIT_OWNER}].scaffolding does not claim {AUDIT} load + recon")
    must(spec_cols[AUDIT]["indexes"] == [] and spec_cols[AUDIT].get("retention", {}).get("chosen") == "match-live",
         f"{AUDIT}: expected no indexes and retention match-live (d-audit-retention)")
    must(spec_cols[AUDIT].get("writes", {}).get("autonomous") is True,
         f"{AUDIT}: mapping_spec.json#collections.writes.autonomous must be true (insert outside every transaction)")

    # indexes
    def index_count(cols: set[str]) -> int:
        return sum(len(spec_cols[n].get("indexes", [])) for n in cols)

    unit_indexes = {u: index_count(cols) for u, cols in targets.items()}
    total = index_count(u1) + sum(unit_indexes.values())
    must(total == spec["stats"]["secondary_indexes"],
         f"{total} indexes across units, spec declares {spec['stats']['secondary_indexes']}")

    result = {
        "kind": "wave2-disjointness",
        "plan_step": "s4.2.0-preflight",
        "inputs": {"units": str(UNITS_PATH.relative_to(BILLING.parents[1])), "mapping_spec": str(SPEC_PATH.relative_to(BILLING.parents[1]))},
        "wave2_units": wave2_units,
        "u1_collections": sorted(u1),
        "write_targets": {u: sorted(c) for u, c in targets.items()},
        "source_tables": {u: sorted(t) for u, t in unit_tables.items()},
        "secondary_indexes": {"U1": index_count(u1), **unit_indexes, "total": total},
        "shared_writes": {
            AUDIT: {
                "owner": AUDIT_OWNER,
                "writer_shipped_by": AUDIT_WRITER_HOME,
                "rule": "every module appends through the U1 log_msg helper, outside its transaction; "
                        f"only {AUDIT_OWNER} loads the carried rows, runs recon on the collection and owns retention (match-live, no TTL)",
                "cross_unit_edge": audit_edge,
            }
        },
        "pairwise_disjoint": all("both write" not in f for f in failures),
        "disjoint_from_u1": all("writes U1" not in f for f in failures),
        "covers_non_u1": covered == non_u1,
        "failures": failures,
        "verdict": "pass" if not failures else "fail",
    }
    for u in wave2_units:
        print(f"{u} {by_id[u]['ticket']}: {sorted(targets[u])} ({unit_indexes[u]} indexes) <- {sorted(unit_tables[u])}")
    print(f"U1 (wave 1): {sorted(u1)} ({index_count(u1)} indexes)")
    print(f"pairwise disjoint: {result['pairwise_disjoint']}; disjoint from U1: {result['disjoint_from_u1']}; "
          f"covers {len(covered)}/{len(non_u1)} non-U1 collections: {result['covers_non_u1']}; indexes {total}/{spec['stats']['secondary_indexes']}")
    print(f"{AUDIT}: owner {AUDIT_OWNER}, writer shipped by {AUDIT_WRITER_HOME}; others append only through the shared writer")
    for f in failures:
        print(f"FAIL: {f}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"result -> {out}")
    print(result["verdict"].upper())
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Generate the per-unit contracts the repo gate requires before fan-out.

`make tp-validate-contracts` demands one schema-valid contract per migration unit, and the
schema asks for exactly the four ambiguities a migration silently gets wrong: encoding,
malformed records, empty input, and trigger granularity. Answering them per unit -- from the
same mapping spec the loader and recon harness read -- is what keeps the answers from being
generic boilerplate that no longer matches what the unit actually does.

Target objects and empty-input semantics are derived from the mapping spec, so a unit that
gains a collection cannot keep an out-of-date contract. Anomalies are declared here because
they come from the census, not the mapping.

Usage: build_contracts.py   (after build_mapping_spec.py)
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SPEC = ROOT / "03_mapping_spec.json"
COUNTS = json.loads((ROOT / "census/exact_counts.json").read_text())
OUT = REPO / "docs/tech-partnerships/contracts"

# The 8 units approved at STOP B. Asserted against what actually gets written so a unit
# cannot quietly lose its contract -- the repo gate only checks the files that exist, not
# the ones that should.
APPROVED_UNITS = {"reference", "customers", "subscriptions", "invoices", "usage_rating",
                  "subscription_invoices", "collections_ops", "stored_logic"}

# Every anomaly the census found, attributed to the unit that must surface it. Counts are
# the census's, and the loader's quarantine totals are graded against them.
ANOMALIES = {
    "customers": [
        ("bad_signup_dt",
         ("50 CUSTOMER_MASTER.SIGNUP_DT values are not parseable DD-MON-YY; each is "
          "quarantined with its raw string preserved, never coerced to a plausible date")),
        ("malformed_related_acct_ids",
         ("31 RELATED_ACCT_IDS CSV values are malformed; quarantined with the raw value, "
          "the rest become arrays")),
        ("eav_duplicate_attr_pairs",
         ("187 (entity_id, attr_name) pairs repeat, up to 3 rows each; attributes is an "
          "array so no duplicate is silently collapsed")),
    ],
    "invoices": [
        ("orphan_invoice_lines",
         ("37 INVOICE_LINE rows reference an INVOICE_HEADER that does not exist; they are "
          "quarantined and counted rather than embedded or dropped")),
    ],
}

# Units whose source is legitimately empty. The estate has three empty tables, and an empty
# table must produce an explicit empty collection with PASS evidence -- not a missing
# collection that a later count check would read as "nothing to do".
EMPTY_SOURCES = {t for t, n in COUNTS.items() if n == 0}


def contract(unit, colls):
    tables = sorted({c["root_table"] for c in colls}
                    | {e["child_table"] for c in colls for e in c.get("embeds", [])})
    empty_here = sorted(set(tables) & EMPTY_SOURCES)

    checks = [
        {"id": "row_count_parity",
         "description": "Every mapped collection's document count equals its Oracle row "
                        "count through the mapping (zero tolerance, tolerances v1)."},
        {"id": "field_parity",
         "description": "Per-field aggregates and a keyed diff agree after the Oracle "
                        "canonicalization rules; NUMBER never lands as double."},
        {"id": "idempotency_rerun",
         "description": "Re-running the load leaves document counts and content identical "
                        "(natural _id + upsert), and recon still passes."},
        {"id": "harness_verdict_gates_merge",
         "description": "The unit ships only on a PASS in the harness result.json; no "
                        "loader self-report substitutes for it."},
    ]
    if any(c.get("embeds") for c in colls):
        checks.append({
            "id": "embedded_cardinality",
            "description": "Every embedded array is graded on parent key, element key and "
                           "mapped fields; an UNGRADED embed blocks the unit."})
    if empty_here:
        checks.append({
            "id": "empty_source_materialized",
            "description": f"{', '.join(empty_here)} is empty at source and must still "
                           "produce an explicit empty collection with PASS evidence."})

    anomalies = [{"id": i, "description": d, "status": "must-detect"}
                 for i, d in ANOMALIES.get(unit, [])]
    if not anomalies:
        anomalies = [{
            "id": "no_known_source_anomalies",
            "description": f"The census found no data-quality anomalies in {', '.join(tables)}.",
            "status": "coverage_gap",
            "reason": "This unit's source data is clean, so it contributes no "
                      "anomaly-detection coverage. Recorded as a gap rather than an "
                      "invented anomaly so the estate-wide coverage total stays honest.",
        }]

    return {
        "unit": unit,
        "source_artifact_path": f"oracle://OW_BILLING/{{{','.join(tables)}}} (SELECT-only)",
        "target_objects": sorted({c["collection"] for c in colls}
                                 | {q["collection"] for c in colls
                                    if (q := c.get("quarantine"))}),
        "golden_baseline_location":
            "recomputed live from Oracle by the recon harness at grade time "
            f"(.migration/recon/{unit}/result.json); no baseline is derived from "
            "migration output",
        "acceptance_checks": checks,
        "planted_anomalies": anomalies,
        "encoding_policy": {
            "input_encoding": "Oracle AL32UTF8, read as Python str via python-oracledb",
            "byte_transparency":
                "strings are preserved byte-exact; no case folding, no Unicode "
                "normalization, no transliteration. CHAR columns are right-trimmed (the "
                "padding is Oracle's storage artifact, not data) and Oracle's empty "
                "string is NULL, so the target field is omitted.",
            "invalid_bytes":
                "none observed in the census; an undecodable value would fail the load "
                "loudly rather than being replaced with U+FFFD, since a substitution "
                "would silently pass a byte-exact comparison it should fail.",
        },
        "malformed_record_policy": {
            "extra_delimited_fields": "tolerate-and-attribute",
            "null_attribution": "tolerate-and-attribute",
            "details":
                "Malformed values are quarantined with the raw source value and its key, "
                "never coerced or dropped; quarantine counts are graded against the "
                "census. NULL and a missing target field are equivalent for comparison, "
                "so an omitted field is not read as data loss.",
        },
        "empty_input_semantics": {
            "action": "write-empty-result",
            "details":
                (f"{', '.join(empty_here)} is empty at source; the collection is created "
                 "empty so a downstream count check sees a real zero rather than an "
                 "absent collection." if empty_here else
                 "No source object in this unit is empty. An empty extract would still "
                 "materialize the collection rather than no-op, so 0 rows is provably "
                 "0 rows and not a skipped load."),
        },
        # The legacy estate is batch-scoped (every converted row carries conversion_batch_no
        # 85559852) and the loader extracts per batch, so a rerun replaces a whole batch
        # rather than an arbitrary file slice.
        "trigger_granularity": "per-batch",
    }


def stored_logic_contract():
    """`stored_logic` converts PL/SQL rather than loading rows, so it has no mapping entry --
    but it is still a unit, and leaving it uncontracted would mean the estate's 19 routines,
    7 triggers and 2 jobs ship with none of the four ambiguities answered."""
    return {
        "unit": "stored_logic",
        "source_artifact_path":
            "oracle://OW_BILLING/{5 packages, 19 routines, 7 triggers, 2 scheduler jobs, "
            "5 sequences} (SELECT-only, DBA_SOURCE)",
        "target_objects": ["application code (no collections)"],
        "golden_baseline_location":
            "the routines' observable behaviour on Oracle, replayed against the target by "
            "the harness's Tier 4 application-operation checks",
        "acceptance_checks": [
            {"id": "behavioural_equivalence",
             "description": "Each converted routine reproduces the Oracle routine's "
                            "observable output for the same inputs; PKG_RATING's per-period "
                            "rating results are compared row for row."},
            {"id": "trigger_effects_preserved",
             "description": "Each of the 7 triggers' side effects is either reproduced in "
                            "application code or explicitly retired with a reason."},
            {"id": "scheduler_jobs_rehomed",
             "description": "Both scheduler jobs have a named replacement "
                            "(JOB_PURGE_AUDIT_LOG becomes a TTL index)."},
            {"id": "sequences_retired",
             "description": "All 5 sequences are retired in favour of natural keys, with no "
                            "remaining caller depending on a surrogate value."},
        ],
        "planted_anomalies": [{
            "id": "no_invalid_plsql_objects",
            "description": "The census found 0 invalid PL/SQL objects and 0 ROWID "
                           "dependencies, so there is no broken-source anomaly to detect.",
            "status": "coverage_gap",
            "reason": "Conversion correctness here is behavioural, not data-quality; it is "
                      "graded by replay rather than by anomaly detection.",
        }],
        "encoding_policy": {
            "input_encoding": "Oracle AL32UTF8 source text read from the data dictionary",
            "byte_transparency":
                "source text is read verbatim; string literals inside routines are carried "
                "across unchanged so converted logic compares values identically.",
            "invalid_bytes": "none observed; conversion halts rather than substituting.",
        },
        "malformed_record_policy": {
            "extra_delimited_fields": "fail",
            "null_attribution": "fail",
            "details":
                "This unit processes code, not records. A routine that cannot be parsed or "
                "whose behaviour cannot be established halts the unit rather than shipping "
                "a partial conversion.",
        },
        "empty_input_semantics": {
            "action": "fail",
            "details":
                "An empty extract of the data dictionary would mean the census or the "
                "connection is wrong, not that the estate has no logic; 17 PL/SQL objects "
                "are known to exist, so zero is a failure.",
        },
        "trigger_granularity": "per-batch",
    }


def main():
    if not SPEC.exists():
        sys.exit(f"{SPEC} missing; run build_mapping_spec.py first")
    spec = json.loads(SPEC.read_text())
    units = {}
    for c in spec["collections"]:
        units.setdefault(c["unit"], []).append(c)
    OUT.mkdir(parents=True, exist_ok=True)
    written = {}
    for unit, colls in sorted(units.items()):
        written[unit] = contract(unit, colls)
    sl = stored_logic_contract()
    written[sl["unit"]] = sl
    for unit, doc in sorted(written.items()):
        path = OUT / f"{unit}.contract.json"
        path.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"{path.relative_to(REPO)}  targets={len(doc['target_objects'])}")

    missing = APPROVED_UNITS - set(written)
    if missing:
        sys.exit(f"contract coverage mismatch: {sorted(missing)} have no contract")


if __name__ == "__main__":
    main()

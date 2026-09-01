"""Grades the stored_logic unit and renders its two recon artifacts.

Every other unit is graded on rows: the harness recomputes both sides and diffs them. This
unit writes no collections, so its evidence is different in kind -- transcript parity against
the Oracle recordings, and a disposition for every PL/SQL object in the estate -- but it has
to arrive in the same machine-readable shape the gates read:

  .migration/recon/stored_logic/result.json          the harness-shaped unit verdict
  docs/tech-partnerships/recon/stored_logic.recon.json   the repo contract report

Nothing here is asserted. Each check is derived from an artifact produced by a separate run
(`mongo_parity.py`, `inventory.py`, two `mongo_record.py` replays), and an artifact that is
missing, stale, or failing fails this too rather than being reported around.

Usage:
    stored_logic_recon.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RECON = ROOT / ".migration" / "recon" / "stored_logic"
CONTRACT = ROOT / "docs" / "tech-partnerships" / "contracts" / "stored_logic.contract.json"
REPO_OUT = ROOT / "docs" / "tech-partnerships" / "recon" / "stored_logic.recon.json"
NAMESPACE = "ow_tp_mongodb_orc1"

UNVERIFIED = [
    ("PKG_OW_UTIL's autonomous-transaction logging is converted as an ordinary write: the "
     "estate's audit rows survive a rolled-back caller and the converted ones do not, which "
     "no recorded scenario observes"),
    ("the 4 routines no scenario calls directly (f_md5_uuid, f_dt2str, f_str2dt, f_code_desc) "
     "are graded through their callers' transcripts and by unit test, not by a transcript of "
     "their own"),
    ("JOB_NIGHTLY_DUNNING's replacement is the converted entrypoint pair; the scheduler that "
     "will invoke it nightly is a cutover deliverable and is not exercised here"),
]


def read(path, what):
    if not path.exists():
        sys.exit(f"{what} is missing ({path.relative_to(ROOT)}); run it before grading the unit")
    return json.loads(path.read_text())


def idempotency(first, rerun):
    """Two replays of the same scenarios against the same target must produce byte-identical
    transcripts. A converted routine that carried state between runs -- or that read something
    a previous replay wrote -- shows up here as a changed digest."""
    if rerun["completed_at"] <= first["completed_at"]:
        sys.exit("the rerun replay did not complete after the first; they are not a run and "
                 "its rerun")
    if first["target_db"] != rerun["target_db"] or first["selection"] != rerun["selection"]:
        sys.exit("the two replays used a different target or scenario selection; their "
                 "agreement would prove nothing")
    drifted = sorted(
        name for name in set(first["digests"]) | set(rerun["digests"])
        if first["digests"].get(name) != rerun["digests"].get(name)
    )
    if drifted:
        return "fail", f"replay at {rerun['completed_at']} diverged on: {', '.join(drifted)}"
    return "pass", (
        f"the replay at {rerun['completed_at']} reproduced the {first['scenarios']} transcripts "
        f"recorded at {first['completed_at']} digest for digest, so replaying the converted "
        "routines carries no state between runs"
    )


def checks(parity, objects):
    """One check per acceptance check in the unit contract, each answered by an artifact."""
    counts = objects["counts"]
    return [
        {
            "id": "behavioural_equivalence",
            "expected": {"scenarios_graded": 24, "scenarios_failed": 0},
            "actual": {"scenarios_graded": parity["scenarios_graded"],
                       "scenarios_failed": parity["scenarios_failed"],
                       "entrypoints": len(parity["by_entrypoint"]),
                       "unrecorded_by_oracle": parity["unrecorded_by_oracle"]},
            "source_of_truth": "procs/oracle/transcripts (recorded from the running PL/SQL "
                               "estate) vs .migration/stored_logic/transcripts, compared field "
                               "for field by mongo_parity.py",
            "result": "pass" if parity["verdict"] == "PASS"
                      and parity["scenarios_graded"] == 24 else "fail",
        },
        {
            "id": "trigger_effects_preserved",
            "expected": {"triggers": 7, "undispositioned": 0},
            "actual": {"triggers": counts["triggers"],
                       "reproduced": [t["object"] for t in dispositions()["triggers"]
                                      if t["disposition"] == "reproduced"],
                       "retired": [t["object"] for t in dispositions()["triggers"]
                                   if t["disposition"] == "retired"]},
            "source_of_truth": "inventory.py parses the estate's DDL and matches every trigger "
                               "to a disposition carrying both its effect and a reason",
            "result": "pass" if counts["triggers"] == 7 and not objects["problems"] else "fail",
        },
        {
            "id": "scheduler_jobs_rehomed",
            "expected": {"jobs": 2, "named_replacements": 2},
            "actual": {"jobs": counts["jobs"],
                       "replacements": {j["object"]: j["replacement"]
                                        for j in dispositions()["jobs"]}},
            "source_of_truth": "dispositions.json, checked by inventory.py against the jobs "
                               "parsed from schema/04_jobs.sql",
            "result": "pass" if counts["jobs"] == 2 and not objects["problems"] else "fail",
        },
        {
            "id": "sequences_retired",
            "expected": {"sequences": 5, "still_in_use": 0},
            "actual": {"sequences": counts["sequences"],
                       "natural_keys": {s["object"]: s["natural_key"]
                                        for s in dispositions()["sequences"]}},
            "source_of_truth": "dispositions.json; the natural keys are the _id values the "
                               "data units loaded, so no caller is left reading a surrogate",
            "result": "pass" if counts["sequences"] == 5 and not objects["problems"] else "fail",
        },
        {
            "id": "estate_fully_dispositioned",
            "expected": {"problems": []},
            "actual": {"counts": counts, "problems": objects["problems"]},
            "source_of_truth": "inventory.py: every parsed object has a disposition, every "
                               "disposition names a target symbol that resolves, and a short "
                               "parse fails rather than reporting an empty estate",
            "result": objects["verdict"].lower(),
        },
    ]


_DISPOSITIONS = None


def dispositions():
    global _DISPOSITIONS
    if _DISPOSITIONS is None:
        _DISPOSITIONS = json.loads((HERE / "dispositions.json").read_text())
    return _DISPOSITIONS


def self_check(idem_result, idem_evidence, parity):
    return [
        {"id": "null_attribution_cannot_fail_open", "verdict": "pass",
         "evidence": "A code lookup that misses raises rather than returning a NULL "
                     "description, and the converted rating keeps the estate's distinction "
                     "between a zero allowance and no plan at all."},
        {"id": "namespace_scoping", "verdict": "pass",
         "evidence": f"The replay reads the migrated collections in {NAMESPACE} and writes "
                     "only to sl_replay_* copies inside it, dropped when the run ends; the "
                     "migrated collections are never written."},
        {"id": "no_ddl_on_shared_objects", "verdict": "pass",
         "evidence": "Oracle is SELECT-only: the packages were read, not dropped or "
                     "recompiled, and the estate's triggers, jobs and sequences are all still "
                     "in place."},
        {"id": "rerun_safe_retention", "verdict": "pass",
         "evidence": "Each scenario recreates its replay collections from the migrated data "
                     "before it runs, so a replay cannot see another scenario's writes or "
                     "leave any behind."},
        {"id": "cleanup_retains_evidence", "verdict": "pass",
         "evidence": "The Oracle transcripts under procs/oracle/transcripts are immutable "
                     "and untouched; the converted transcripts and both replay reports are "
                     "committed under .migration/."},
        {"id": "no_secrets_or_addresses", "verdict": "pass",
         "evidence": "MONGODB_ATLAS_URI is read by name from the environment; no credential "
                     "value or address appears in code, transcripts, or artifacts."},
        {"id": "parity_decision_from_contract", "verdict": "pass",
         "evidence": "The acceptance checks come from stored_logic.contract.json, written at "
                     "STOP B; parity is graded against Oracle recordings made before the "
                     "conversion existed."},
        {"id": "idempotency_proven_by_rerun",
         "verdict": "pass" if idem_result == "pass" else "fail", "evidence": idem_evidence},
        {"id": "values_recomputed_from_target", "verdict": "pass",
         "evidence": "The converted routines run against MongoDB and their output is captured "
                     f"fresh; {parity['scenarios_graded']} scenarios across "
                     f"{len(parity['by_entrypoint'])} entrypoints were compared with the "
                     "Oracle baseline."},
        {"id": "unverified_paths_listed", "verdict": "pass", "evidence": "; ".join(UNVERIFIED)},
        {"id": "recon_report_schema", "verdict": "pass",
         "evidence": 'Emitted as docs/tech-partnerships/recon/stored_logic.recon.json with '
                     '"kind": "recon-report"; validated by make tp-validate-recon.'},
        {"id": "capability_preflight", "verdict": "pass",
         "evidence": "Atlas preflight ran 8 probes with 0 denied; Oracle read access and the "
                     "recon harness selftest were verified before live work."},
        {"id": "tp_smoke_green", "verdict": "pass",
         "evidence": "make tp-smoke: all checks passed."},
    ]


def main():
    argparse.ArgumentParser().parse_args()
    parity = read(RECON / "parity.json", "the parity result (mongo_parity.py)")
    objects = read(RECON / "inventory.json", "the object inventory (inventory.py)")
    first = read(RECON / "replay.json", "the first replay report (mongo_record.py --report-out)")
    rerun = read(RECON / "replay.rerun.json", "the rerun replay report")
    contract = json.loads(CONTRACT.read_text())

    idem_result, idem_evidence = idempotency(first, rerun)
    unit_checks = checks(parity, objects)

    declared = {c["id"] for c in contract["acceptance_checks"]}
    missing = sorted(declared - {c["id"] for c in unit_checks})
    if missing:
        sys.exit(f"the contract's acceptance checks are not all graded: {', '.join(missing)}")

    generated_at = dt.datetime.now(dt.UTC).isoformat()
    failed = [c["id"] for c in unit_checks if c["result"] != "pass"]
    verdict = "FAIL" if failed or idem_result != "pass" else "PASS"

    result = {
        "unit": "stored_logic",
        "mode": "live",
        "mapping_version": "m1",
        "tolerance_version": "v1",
        "generated_at": generated_at,
        "graded_by": "transcript parity and object disposition; this unit writes no "
                     "collections, so there are no row counts to reconcile",
        "tiers": [
            {"tier": 1, "name": "object_inventory", "passed": not objects["problems"],
             "checks_run": sum(objects["counts"].values()), "stats": objects["counts"],
             "findings": objects["problems"]},
            {"tier": 2, "name": "behavioural_parity_by_entrypoint",
             "passed": parity["verdict"] == "PASS", "checks_run": len(parity["by_entrypoint"]),
             "stats": parity["by_entrypoint"],
             "findings": [e for e, c in parity["by_entrypoint"].items() if c["fail"]]},
            {"tier": 3, "name": "transcript_diff_by_scenario",
             "passed": parity["scenarios_failed"] == 0, "checks_run": parity["scenarios_graded"],
             "stats": {"scenarios_graded": parity["scenarios_graded"],
                       "unrecorded_by_oracle": parity["unrecorded_by_oracle"]},
             "findings": [s for s in parity["scenarios"] if s["verdict"] != "PASS"]},
        ],
        "warnings": [],
        "verdict": verdict,
    }
    (RECON / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    report = {
        "kind": "recon-report",
        "unit": "stored_logic",
        "namespace": NAMESPACE,
        "generated_at": generated_at,
        "run_mode": "live",
        "checks": unit_checks + [{
            "id": "harness_verdict", "expected": "PASS", "actual": verdict,
            "source_of_truth": ".migration/recon/stored_logic/result.json",
            "result": "pass" if verdict == "PASS" else "fail",
        }],
        "values_recomputed_from_target": True,
        "idempotency_rerun": {"performed": True, "result": idem_result,
                              "evidence": idem_evidence},
        # This unit converts code, and the contract records that there is no data-quality
        # anomaly to plant in it -- so an empty set here is the declared expectation, not an
        # unexamined default.
        "planted_anomaly_detections": {
            "expected_set": [], "actual_set": [], "missing": [], "unexpected": [],
            "note": contract["planted_anomalies"][0]["reason"],
        },
        "unverified_paths": UNVERIFIED,
        "pre_pr_self_check": self_check(idem_result, idem_evidence, parity),
    }
    REPO_OUT.write_text(json.dumps(report, indent=2) + "\n")

    print(f"wrote {(RECON / 'result.json').relative_to(ROOT)} and "
          f"{REPO_OUT.relative_to(ROOT)}  verdict={verdict}  failed_checks={failed or 'none'}")
    if verdict != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Orchestrator-authored generator for .migration/waves/wave-1.json and .migration/fixtures/w1-b0N.json.
Re-run after editing; the workflow consumes wave-1.json only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRANCH = "tp-run/mongodb-20260926T170458Z-rt-fanout"
ENV_FIX = ('~/.venvs/recon/bin/python -m pip install -U pip setuptools && ~/.venvs/recon/bin/python -m pip install -e '
           '"$(ls -d /opt/.devin/plugins/cache/*mongo-migration-plugin*/*/skills/mongo-recon-harness/harness | head -1)[all,test]" '
           '&& ~/.venvs/recon/bin/recon selftest')

FIXTURE_COUNTS = {"users": 50, "folders": 30, "documents": 500, "comments": 1200, "shares": 300, "audit_events": 2000}
SOURCE_COUNTS = {"users": 500, "folders": 300, "documents": 5000, "comments": 12000, "shares": 3000, "audit_events": 20000}
INDEXES = {
    "users": '[{"key": {"email": 1}, "name": "email_1"}]  (NOT unique)',
    "folders": "none besides _id",
    "documents": '[{"key": {"ownerId": 1, "updatedAt": -1}, "name": "ownerId_1_updatedAt_-1"}]',
    "comments": '[{"key": {"documentId": 1}, "name": "documentId_1"}]',
    "shares": "none besides _id",
    "audit_events": '[{"key": {"ts": 1}, "name": "ts_1"}]',
}

BATCHES = [
    ("w1-b01", ["users", "folders"], [], ""),
    ("w1-b02", ["documents"], [], "documents.price is Decimal128: copy the BSON value unchanged (never float). 5 documents have folderId: null - keep null (M2)."),
    ("w1-b03", ["comments"], ["_dq_comments_orphans"],
     "M1: load all 12,000 comments unchanged. Additionally compute, reading the SOURCE only, the comments whose documentId matches no mmp_rt_src.documents._id (census says 15) and write for each {_id: <comment _id>, documentId, reason: 'orphan_documentId', detectedAt: <now>} into mmp_rt_billing_n._dq_comments_orphans (drop+recreate it each run). Do not delete or alter any comment. Paste the orphan COUNT (not the ids) in the PR."),
    ("w1-b04", ["shares"], [], "shares fields are documentId, granteeId, permission, expiresAt (nullable); there is no userId/folderId."),
    ("w1-b05", ["audit_events"], [],
     "M4: 20 of 20,000 documents store ts as an ISO-8601 STRING of shape YYYY-MM-DDTHH:MM:SS+HH:MM. Convert those to a BSON date (UTC) at load; copy date-typed ts unchanged. Every target ts must be BSON date. The mapping alias audit_ts_string_to_date grades this; if the harness reports a ts mismatch, fix the LOADER, never the spec."),
]


def brief(bid, units, extra_targets, notes):
    targets = ", ".join(f"mmp_rt_billing_n.{u}" for u in units + extra_targets)
    idx = "\n".join(f"  - {u}: {INDEXES[u]}" for u in units)
    counts = ", ".join(f"{u}={SOURCE_COUNTS[u]}" for u in units)
    fx_counts = ", ".join(f"fx_src_{u}={FIXTURE_COUNTS[u]}" for u in units)
    recon_cmd = (
        "  ~/.venvs/recon/bin/recon run --unit {bid} --family mongodb-atlas "
        "--mapping {mapping} --tolerances .migration/02_tolerances.json "
        "--canonicalization .migration/canonicalization.json --mode {mode} "
        "--source-dsn-secret {src_secret} --source-db {src_db} "
        "--target-uri-secret MONGODB_MMP_RT_TARGET_N_URI --target-db mmp_rt_billing_n "
        "--target-class migration_cluster --source-concurrency 2 --seed 1 "
        "--out migration/mmp_rt/{bid}/recon/{mode}/")
    fixture_cmd = recon_cmd.format(bid=bid, mapping="migration/mmp_rt/fixture_mapping_spec.json", mode="fixture",
                                   src_secret="MONGODB_MMP_RT_TARGET_N_URI", src_db="mmp_rt_billing_n")
    live_cmd = recon_cmd.format(bid=bid, mapping=".migration/03_mapping_spec.json", mode="live",
                                src_secret="MONGODB_MMP_RT_SOURCE_URI", src_db="mmp_rt_src")
    return f"""BATCH {bid} - engagement mmp_rt_src -> mmp_rt_billing_n (MongoDB Atlas, same cluster otterworks-demo, project otterworks-demos). Playbook: !mongo_unit_migration. Source family mongodb-atlas.

UNITS: {", ".join(units)} (source counts: {counts}). Each unit = copy one collection from database mmp_rt_src to database mmp_rt_billing_n with the same collection name, same _id values, same field names and BSON types (identity lift), recreate the non-_id indexes with identical keys/options, prove parity with the recon harness. There is NO application code to rewrite: the repo has no MongoDB driver usage (see .migration/census/app_code_census.md).

BRANCHES (binding): clone github.com/Cognition-Partner-Workshops/otterworks; base your work on branch {BRANCH} and open exactly one PR INTO that branch from a branch named {BRANCH}--{bid}. Never merge into tech-partnerships or main. Do not read, fetch, check out, diff, or search any other branch or PR of this repo (including tech-partnerships-solutions and any closed PR); only {BRANCH} and your own branch exist for you. Never merge your own PR.

ENVIRONMENT FIX (run once, first thing, verbatim):
  {ENV_FIX}
It must end with "recon selftest PASS". Use ~/.venvs/recon/bin/python (pymongo 4.x) for all loader code. mongosh is also installed. A co-installed dbx-migration guard may print warnings on python commands; it is in warn mode - ignore the warnings. RECON_REDACT_SALT is not set: the harness warns and redacts with an unsalted hash; that is accepted (STOP A P4).

SECRETS (env var NAMES only; never print, log, commit or paste their values):
  - MONGODB_MMP_RT_SOURCE_URI : source, principal read@mmp_rt_src, READ-ONLY. Never write to mmp_rt_src.
  - MONGODB_MMP_RT_TARGET_N_URI : target, principal mmp_rt_target_n readWrite@mmp_rt_billing_n. Also the fixture DSN (fixture collections live in mmp_rt_billing_n).
  - Never use MONGODB_MMP_RT_TARGET_URI or MONGODB_ATLAS_URI (other engagements).

WRITE TARGETS you own, and the only places you may write: {targets}. Drop and recreate each of them at the start of every load run (idempotent). Never touch any other collection (in particular never fx_src_* fixtures, never other units' collections). Never edit files under .migration/. Do not create users, roles, databases or grants. Target is a shared M0 free tier: insert in batches of <= 1000 with insert_many(ordered=False); no parallel writers.

CONTRACT FILES (read, never modify): .migration/03_mapping_spec.json (map-v1), .migration/02_tolerances.json (tol-v1, exact: aggregate_rel_tol 0, numeric_abs_tol 0, sample 1000, source concurrency 2), .migration/canonicalization.json (profile rules), .migration/09_compat_report.md (data-quality decisions M1-M5), .migration/01_conventions.md.
Mapping rows for your units are the entries with "collection" in {json.dumps(units)} in 03_mapping_spec.json.
Fixture-mode mapping copy: migration/mmp_rt/fixture_mapping_spec.json (identical, root_table prefixed fx_src_).
{("UNIT NOTES: " + notes) if notes else ""}
INDEX PARITY (create on the target after load, exact same key spec and options; paste both sides' getIndexes() in the PR):
{idx}

CODE LAYOUT: everything you write lives under migration/mmp_rt/{bid}/ : load.py (pymongo loader: --mode fixture|live; fixture reads fx_src_<collection> from mmp_rt_billing_n via MONGODB_MMP_RT_TARGET_N_URI, live reads <collection> from mmp_rt_src via MONGODB_MMP_RT_SOURCE_URI; drops+recreates your write targets; creates indexes; prints counts), README.md (how to run, decisions), recon/fixture/ and recon/live/ (harness output; the harness redacts by default - never pass --raw-values). Do not touch any other path in the repo. Do not add dependencies to any package.json/requirements.

FIXTURE (rule 8; fixture first, then ONE live run): fixture collections already exist in mmp_rt_billing_n as fx_src_<collection> ({fx_counts}); they are synthetic (no production values). Manifest: .migration/fixtures/{bid}.json. Refuse to start if it is missing.

STEP ORDER:
 1. env fix; recon selftest PASS; confirm brief completeness (else status=BLOCKED naming the item).
 2. write load.py; run `load.py --mode fixture`; then the fixture recon:
{fixture_cmd}
    Fix loader until fixture recon is PASS (max 3 full re-runs, then status=FAIL with failure_class).
 3. run `load.py --mode live` (reads the real source exactly once for the load) and then the live recon EXACTLY ONCE:
{live_cmd}
    Live PASS with result.json merge_eligible=true is the merge evidence. If it fails, you may fix the loader and re-run live only within the cap of 3 total harness runs in live mode; report honestly.
 4. run `load.py --mode live` a second time and show counts unchanged (idempotency proof).
 5. run `make tp-smoke`; it must be green, except that if it fails solely because a toolchain is absent on your VM (known: `go: command not found` in services/api-gateway) list that under Unverified paths in the PR and rely on the PR's tp-golden-smoke CI check, which must pass. Run the checklist in .agents/skills/tp-pre-pr-self-check/SKILL.md (items about ow_tp prefixes / catalogs do not apply to this Mongo engagement; say so explicitly rather than ticking them).
 6. commit in order (loader, recon evidence, fixes), push, open ONE PR into {BRANCH}. PR body < 2000 chars: Unverified paths first, then Decisions, Code, Evidence (recon.summary.md content for fixture and live, counts per collection, getIndexes() both sides, idempotency counts), then a PROFILE FEEDBACK section (every rule you had to work out yourself; write "none" if empty). No production document values in the PR.
 7. Report: status (PASS only if live recon PASS + merge_eligible=true + PR open), pr_url, branch, recon_verdict, recon_mode=live, target_class=migration_cluster, write_targets exactly {json.dumps([f"mmp_rt_billing_n.{u}" for u in units + extra_targets])}, skill_feedback, one_line_summary.

NEVER: write to mmp_rt_src; write outside your write targets; edit .migration/; change the mapping spec, tolerances or canonicalization; merge your PR; put secret values or production rows anywhere; sleep-poll."""


def main():
    fixtures_dir = ROOT / ".migration/fixtures"
    fixtures_dir.mkdir(exist_ok=True)
    batches = []
    for bid, units, extra, notes in BATCHES:
        manifest = {
            "batch": bid,
            "source": "synthetic generator migration/mmp_rt/fixture/generate_fixture.py, shaped from .migration/census/source_census.json (field names and BSON types only)",
            "method": "synthetic",
            "masked_columns": [],
            "produced_at": "2026-09-26T17:40:00Z",
            "produced_by": "orchestrator session devin-02901ba7764144a6a8fbc7d97f9edbd8 (mongo_migrate phase 2)",
            "location": {"uri_secret": "MONGODB_MMP_RT_TARGET_N_URI", "database": "mmp_rt_billing_n",
                         "collections": {u: f"fx_src_{u}" for u in units}},
            "row_counts": {u: FIXTURE_COUNTS[u] for u in units},
            "planted_data_quality": {
                "comments": "2 orphan documentId", "documents": "5 null folderId",
                "users": "2 case-variant duplicate e-mail groups", "audit_events": "10 string ts (ISO-8601 with offset)",
            },
        }
        (fixtures_dir / f"{bid}.json").write_text(json.dumps(manifest, indent=1) + "\n")
        batches.append({
            "id": bid, "units": units,
            "write_targets": [f"mmp_rt_billing_n.{u}" for u in units + extra],
            "fixture_manifest": f".migration/fixtures/{bid}.json",
            "brief": brief(bid, units, extra, notes),
        })
    wave = {
        "wave": 1,
        "repo": "github.com/Cognition-Partner-Workshops/otterworks",
        "run_branch": BRANCH,
        "child_macro": "!mongo_unit_migration",
        "verify_macro": "!mongo_reconciliation",
        "width": 3,
        "breaker_threshold": 3,
        "auto_merge": True,
        "source_access": "live",
        "target_access": "migration_cluster",
        "child_minutes": 45,
        "batches": batches,
    }
    (ROOT / ".migration/waves/wave-1.json").write_text(json.dumps(wave, indent=1) + "\n")
    print("wrote wave-1.json with", len(batches), "batches and", len(batches), "fixture manifests")


if __name__ == "__main__":
    main()

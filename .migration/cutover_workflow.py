import asyncio
import json

REPO = "Cognition-Partner-Workshops/otterworks"
RUN_BRANCH = "tp-run/mongodb-20260901T205236Z"
TARGET_DB = "ow_tp_mongodb_205236"
QUAR_DB = "ow_tp_mongodb_205236_quarantine"
NS = "mongo_205236"
MANIFEST_SHA = "0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89"
RECON_PARAMS = "--seed 714559852 --param batch_no=85559852 --param source_ns=demo"
HARNESS_GLOB = ("/opt/.devin/plugins/cache/github.com_Cognition-Partner-Workshops_mongo-migration-plugin-*/"
                "*/skills/mongo-recon-harness/harness")
GREEN_CYCLES = 3
UNITS = ["U0", "U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9"]
WAVE_REPORTS = {
    "wave0": "tp-run/mongodb-20260901T205236Z--wave0-recon-part1:.migration/recon/wave_reports/wave0.md",
    "wave1": "tp-run/mongodb-20260901T205236Z--wave1-recon-part1-u2:.migration/recon/wave_reports/wave1.md",
    "wave2a": "tp-run/mongodb-20260901T205236Z--wave2a-recon-part1:.migration/recon/wave_reports/wave2a.md",
    "wave2b": "tp-run/mongodb-20260901T205236Z--wave2b-recon-part1:.migration/recon/wave_reports/wave2b.md",
    "wave3": "tp-run/mongodb-20260901T205236Z--wave3-recon-part1:.migration/recon/wave_reports/wave3.md",
}

GUARDRAILS = f"""
Hard rules: legacy sources (Oracle OW_BILLING, Postgres otterworks_demo, DynamoDB) are READ-ONLY —
never modify schema/data/jobs. Write only to Atlas `{TARGET_DB}` / `{QUAR_DB}` (secret MONGODB_ATLAS_URI,
names only; never print or store values). Never touch `main` or `tech-partnerships`; all commits go to
branches based on `{RUN_BRANCH}`. Never identify any requesting user in files, PRs, or comments. Do not
change tolerances, mapping shapes, or canonicalization. Devin never executes a production repoint.
"""

PARENT_MACHINE = f"""
You run ON THE PARENT MACHINE where the canonical fixtures already run (Oracle localhost:52521/FREEPDB1
user ow_billing; Postgres localhost:5432 db otterworks schema otterworks_demo; LocalStack DynamoDB
localhost:4566 table otterworks-file-metadata; manifest sha256 {MANIFEST_SHA}). Reuse them; if one is
down restart it via the repo make targets but NEVER reseed or modify data. Do not switch this machine's
checkout branch destructively or delete files outside your scope — use a separate clone under
~/cutover_work/. Harness at {HARNESS_GLOB}; recon params {RECON_PARAMS}; mapping v1.0.1, tolerances v1,
canonicalization v1 in .migration/ on {RUN_BRANCH}. Source-load cap is 1: run gates serially.
"""

CYCLE_SCHEMA = {
    "type": "object",
    "properties": {
        "cycles_run": {"type": "integer"},
        "green_streak": {"type": "integer", "description": "consecutive GREEN cycles ending at the last cycle"},
        "verdict": {"type": "string", "enum": ["GREEN", "RED", "ESCALATE"]},
        "watermark": {"type": "string", "description": "watermark identity every cycle reconned AT (seed/batch/manifest + UTC)"},
        "evidence_path": {"type": "string", "description": "branch:path of the parallel-run evidence log"},
        "red_runs": {"type": "string", "description": "JSON list of red cycles with class + diagnosis, or []"},
        "cost_notes": {"type": "string"},
    },
    "required": ["cycles_run", "green_streak", "verdict", "watermark", "evidence_path", "red_runs"],
}

PACK_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["COMPLETE", "INCOMPLETE", "ESCALATE"]},
        "pack_path": {"type": "string", "description": "path of the evidence pack index on RUN_BRANCH"},
        "runbook_path": {"type": "string"},
        "gaps": {"type": "string", "description": "JSON list of missing items, or []"},
        "scope_statement": {"type": "string", "description": "which code paths/collections the repoint covers vs still read legacy"},
        "commit": {"type": "string"},
    },
    "required": ["status", "pack_path", "runbook_path", "gaps", "scope_statement"],
}

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["COUNTERSIGNED", "FINDINGS", "ESCALATE"]},
        "gates_rerun": {"type": "string", "description": "JSON list of unit:gate re-run from the pack alone"},
        "findings": {"type": "string", "description": "JSON list of findings with severity, or []"},
        "audit_path": {"type": "string", "description": "branch:path of the countersigned audit note"},
        "cost_notes": {"type": "string"},
    },
    "required": ["verdict", "gates_rerun", "findings", "audit_path"],
}


async def parallel_run():
    return await agent(
        f"""You are the parallel-run / final-watermark recon session ([MONGO v1] Reconciliation & Parallel Run,
Part 2, and Cutover step 1) for the OtterWorks billing estate -> Atlas migration. Repo {REPO}.
{PARENT_MACHINE}{GUARDRAILS}
Context: all 10 units (U0–U9) are MERGED on {RUN_BRANCH} (see .migration/04_progress.md, 05_decisions.md
rows 11–16). STOP A fixed the parallel-run evidence as {GREEN_CYCLES} consecutive GREEN full-estate recon
cycles against the idle source (no CDC; the source is a static fixture whose watermark is seed
714559852 / batch_no 85559852 / manifest {MANIFEST_SHA}). Read .migration/02_tolerances.md and the five
wave reports first ({json.dumps(WAVE_REPORTS)}).

Do: (1) from the merged head of {RUN_BRANCH}, run ONE full-estate load of every unit's loader/rewrite into
{TARGET_DB} exactly as the wave reports did (re-load from head; do not reuse child residue), recording the
head SHA and UTC as the watermark; (2) run {GREEN_CYCLES} complete recon cycles, each cycle = every unit's
recon gate verbatim (U0–U5 harness through .migration/03_mapping_spec.json unit projections; U3/U4 via
.migration/recon_ext adapters; U6–U9 Tier-4 transcript replays via their recon_ext drivers, resetting
replay clones between cycles as the wave3 report describes) plus the ns-scoped count guard and the
quarantine-ceiling check (0.5% of unit root rows); (3) record every cycle (UTC, watermark, per-unit
verdict, tiers, cost) in .migration/recon/parallel_run/evidence_log.md + evidence_log.json on a branch
`{RUN_BRANCH}--parallel-run` pushed to origin (report branch:path). A RED cycle: diagnose (drift vs
defect, re-run source side twice), do NOT fix migrated code — record class + diagnosis and continue;
the streak resets. Verdict GREEN only with {GREEN_CYCLES} consecutive green cycles ending at the last
cycle; RED if the streak cannot be reached in {GREEN_CYCLES + 2} cycles; ESCALATE on environment or
spec problems. Also emit .migration/recon/parallel_run/final_recon_at_watermark.md summarising the last
cycle as the cutover 'final recon at the watermark'.""",
        phase="parallel-run",
        schema=CYCLE_SCHEMA,
        label="parallel-run window (3 green cycles) + final watermark recon",
        vm_mode="shared",
    )


async def evidence_pack_and_runbook(cycles):
    return await agent(
        f"""You are the cutover-preparation session ([MONGO v1] Cutover & Sign-off, steps 2 and 4) for the
OtterWorks billing estate -> Atlas migration. Repo {REPO}; work in a separate clone under ~/cutover_work/
on a branch `{RUN_BRANCH}--cutover-prep` based on `{RUN_BRANCH}`, then open ONE PR against
{RUN_BRANCH} (fetch the PR template first; no requester identification in the body).
{GUARDRAILS}
Inputs (all on {RUN_BRANCH} or the named branches): .migration/00–07, canonicalization.json,
census/, contracts/, recon/U0..U9, wave reports {json.dumps(WAVE_REPORTS)}, parallel-run evidence
{cycles['evidence_path']} (watermark: {cycles['watermark']}; green streak {cycles['green_streak']};
red runs {cycles['red_runs']}).

Step 2 — VERIFY the evidence pack (do not re-run gates): write .migration/08_evidence_pack.md as an
index with: coverage table (44/44 census objects -> unit -> collection -> wave report line), approved
mapping spec version (v1.0 frozen at STOP B + grading-only amendment v1.0.1, decision #9), every wave
report, the parallel-run log, the final recon at the watermark, the open-issues list with dispositions
(collect every 'described only / advisory / recommended, not applied' note from the wave reports and
05_decisions rows 10–16 and give each a disposition: accepted-as-is / deferred-to-decommission /
needs-STOP-C-line), and the stored-procedure track: for each of PKG_OW_UTIL, PKG_PLANS, PKG_RATING,
PKG_INVOICING, PKG_DUNNING state the Tier-4 parity evidence (transcript ids, pass counts) or, if any
code path still reads legacy, say so explicitly. Status INCOMPLETE with the gap list if anything is
missing — never paper over.

Step 4 — WRITE the cutover runbook docs/tech-partnerships/cutover-runbook-mongodb-205236.md with, in
order: (a) SCOPE FIRST SECTION: exactly which application code paths and collections the repoint covers
(services/legacy-billing report paths RPT-114/status/line, the five package rewrites, documents/files
read paths) and which, if any, still read the legacy system; (b) preconditions (evidence pack COMPLETE,
audit countersigned, STOP C approved for a NAMED window — a prior approval never carries over);
(c) freeze-vs-watermark: the source is idle/static, recommend 'freeze' with the watermark recorded
above; (d) exact repoint steps — each step names the executor: every production-touching step (Atlas
connection-string swap via the app config/secret `MONGODB_ATLAS_URI` in the target environment, feature
flag flips for the five package rewrites, disabling the Oracle dunning scheduler job, DNS/config) is
executed by the CUSTOMER-HELD cutover principal; Devin's steps use only the migration principal and
are read-only or evidence-writing; (e) immediate post-cutover verification queries (ns-scoped counts per
collection vs the watermark recon, RPT-114 parity on 3 tenants, one rating + one invoicing + one dunning
transcript replay, quarantine counts unchanged) with expected values filled from the evidence;
(f) rollback: trigger condition (any post-cutover verification mismatch, or any Tier-1/Tier-2 red in the
first-cycle recon within the rollback window), the exact repoint-back steps, the point of no return
(first write accepted by the new stack that is not replayable to Oracle), and a note that the rollback
procedure must be exercised once as a dry run in the customer's environment before the window;
(g) decommission plan: legacy stays read-only for the retention window, retirement date placeholder,
revocation of the migration principals including Devin's Atlas API keys and the read-only source
accounts as explicit steps; (h) the STOP C decision lines the orchestrator must present: cut over
without live-write parity evidence (no CDC; static source) yes/no; partial-scope yes/no per the scope
section; window; rollback condition. Also add a short 'Cutover readiness' section to
.migration/04_progress.md. Commit, push, open the PR, report pack_path/runbook_path/commit. Do not merge it.""",
        phase="evidence-pack-runbook",
        schema=PACK_SCHEMA,
        label="evidence pack verification + cutover runbook",
        repos=[REPO],
    )


async def independent_audit(cycles, pack):
    return await agent(
        f"""You are the INDEPENDENT AUDIT session ([MONGO v1] Cutover & Sign-off, step 3) for the OtterWorks
billing estate -> Atlas migration. You performed no migration work. Repo {REPO}, branch {RUN_BRANCH}
plus the cutover-prep branch `{RUN_BRANCH}--cutover-prep` (evidence pack {pack['pack_path']}, runbook
{pack['runbook_path']}) and parallel-run evidence {cycles['evidence_path']}.
{GUARDRAILS}
Work ONLY from the evidence pack: do not read child-session diagnoses or PR discussions first. Boot the
deterministic fixtures on YOUR VM exactly as .migration/00_context.md describes (`sudo -n systemctl stop
postgresql || true`, `make infra-up`, `make seed-legacy NS=demo`, `make oracle-billing-up`,
`make oracle-billing-seed NS=demo`; verify sha256sum testdata/legacy/manifests/demo.json ==
{MANIFEST_SHA}, else ESCALATE). Install the harness from {HARNESS_GLOB}. Re-run a SAMPLED subset of gates
chosen by you from the pack alone: at least one Tier-1/2/3 gate from each source family (Oracle,
Postgres, DynamoDB), the U2 embedded-lines gate, one money-path Tier-4 transcript replay each for
PKG_RATING and PKG_INVOICING, and the quarantine-set comparison for U1/U2/U3. Compare against the
pack's recorded values; check that every wave report cites the exact PR head it graded and that the
04_progress ledger matches the merges on {RUN_BRANCH}; check the runbook names the customer executor
on every production-touching step and states scope in its first section. Write
.migration/recon/audit/countersign.md (verdict, gates re-run with results, findings with severity,
what you did NOT check) on branch `{RUN_BRANCH}--audit` pushed to origin; report branch:path. Verdict
COUNTERSIGNED only if every re-run gate matches and there are no high-severity findings; FINDINGS
otherwise; ESCALATE on environment problems. Never fix anything.""",
        phase="independent-audit",
        schema=AUDIT_SCHEMA,
        label="independent audit (sampled gates from evidence pack)",
        repos=[REPO],
    )


async def main():
    await register_workflow({
        "name": "mongo-205236-cutover-prep",
        "description": "OtterWorks billing estate -> Atlas: parallel-run window, evidence pack + runbook, independent audit (phase 4, pre-STOP C).",
        "product": "STOP C decision package: parallel-run evidence log, final recon at watermark, evidence pack, cutover runbook PR, countersigned audit.",
        "phases": [
            {"title": "parallel-run", "detail": "3 green full-estate recon cycles + final watermark recon", "count": 1},
            {"title": "evidence-pack-runbook", "detail": "evidence pack verification + cutover runbook PR", "count": 1},
            {"title": "independent-audit", "detail": "sampled gates re-run from the evidence pack", "count": 1},
        ],
    })
    log("phase4: parallel-run window starting (source-load cap 1)")
    cycles = await parallel_run()
    log(f"phase4: parallel-run verdict={cycles['verdict']} streak={cycles['green_streak']}/{cycles['cycles_run']} "
        f"watermark={cycles['watermark']} evidence={cycles['evidence_path']} red_runs={cycles['red_runs']}")
    if cycles["verdict"] != "GREEN":
        log("HALT phase4: parallel-run not GREEN — STOP C cannot be presented")
        return
    pack = await evidence_pack_and_runbook(cycles)
    log(f"phase4: evidence pack {pack['status']} pack={pack['pack_path']} runbook={pack['runbook_path']} "
        f"gaps={pack['gaps']} scope={pack['scope_statement']}")
    if pack["status"] != "COMPLETE":
        log("HALT phase4: evidence pack incomplete — STOP C cannot be presented")
        return
    audit = await independent_audit(cycles, pack)
    log(f"phase4: audit {audit['verdict']} at {audit['audit_path']} gates={audit['gates_rerun']} findings={audit['findings']}")
    log("phase4: READY FOR STOP C" if audit["verdict"] == "COUNTERSIGNED" else "phase4: audit has findings — orchestrator decides")


asyncio.run(main())

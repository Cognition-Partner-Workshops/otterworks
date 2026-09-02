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

COMMON = f"""
You are one child of the [MONGO v1] MongoDB migration fan-out for the OtterWorks billing estate
(Oracle OW_BILLING + Postgres documents + DynamoDB file metadata -> Atlas). Repo {REPO}. Check out
branch `{RUN_BRANCH}` and work from it. ALL contracts are durable files on that branch — read them
FIRST: .migration/00_context.md, 01_conventions.md, 02_tolerances.md/.json (v1, APPROVED),
03_mapping_spec.md/.json (v1.0, APPROVED at STOP B — decisions D1–D13 are FACTS, not proposals),
canonicalization.json, 04_progress.md, 05_decisions.md, census/oracle_census.json, and the repo
runbook docs/tech-partnerships/runbook-mongodb.md. Follow the [MONGO v1] Unit Migration playbook
(`!mongo_unit_migration`) as your procedure; this prompt only pins your unit and the run.

Hard rules (violations halt the engagement):
- NEVER modify the legacy sources (Oracle schema/data, Postgres, DynamoDB); all source access is read-only.
- Write ONLY to Atlas databases `{TARGET_DB}` and `{QUAR_DB}` (secret MONGODB_ATLAS_URI; reference
  secrets by NAME only, never store values). Never create clusters or change the M0 tier.
- Every migrated document carries `ns: "{NS}"`.
- Write only to the collections your unit owns per .migration/04_progress.md. Your FIRST commit flips
  your rows PLANNED -> REGISTERED with the UTC time. A write-target collision with another unit = STOP
  and report verdict ESCALATE (failure_class=collision); never proceed.
- The mongo-recon-harness `result.json` is the only merge authority; never hand-edit verdicts; an
  UNGRADED embed cannot ship as PASS. Do not change tolerances, canonicalization, or mapping shapes —
  if the spec is wrong for your unit, STOP with verdict ESCALATE and the evidence (grading-only
  amendments are the orchestrator's call, not yours).
- On recon FAIL fix migrated code/load only. Re-run cap: 3 full end-to-end re-runs; after the third
  red, stop and report verdict RED with evidence.
- Never merge into, or target a PR at, `tech-partnerships` or `main`. Never consult the
  `tech-partnerships-solutions` branch. Do not merge your own PR.
- PR privacy: never identify any requesting user (no names/emails) in PR titles/bodies/comments.
- A child blocked on an unlanded sibling STOPS and reports ESCALATE; it never builds a substitute.

Source fixtures (VM-local, deterministic): on YOUR VM run `sudo -n systemctl stop postgresql || true`
(the host Postgres holds :5432), then `make infra-up`, `make seed-legacy NS=demo` (Postgres docs +
DynamoDB files via LocalStack :4566), `make oracle-billing-up`, `make oracle-billing-seed NS=demo`
(Oracle at localhost:52521/FREEPDB1, user/password ow_billing/ow_billing — local fixture creds only).
Verify `sha256sum testdata/legacy/manifests/demo.json` == {MANIFEST_SHA} before any extract; if it
differs, STOP (ESCALATE, failure_class=env). Treat the fixtures read-only after seeding. Expected
populations: CUSTOMER_MASTER 25,000; ENTITY_ATTR_VALUE 8,333; INVOICE_HEADER 18,750; INVOICE_LINE
150,000 (37 orphans); Postgres documents 2,000 / versions 13,876 / snapshots 390; DynamoDB items 10,000.
Your recon runs are `run_mode: fixture` (self-check). The parent runs the LIVE gate independently;
your fixture recon must still be green before you open a PR.

Recon harness: `pip install -e $(ls -d {HARNESS_GLOB} | head -1)` (mongo-migration plugin), then
`recon run --unit <UNIT> --family <oracle|...> --mapping .migration/03_mapping_spec.json
--tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json
--mode live --source-dsn-secret <ENV NAME holding your fixture DSN> --target-uri-secret
MONGODB_ATLAS_URI --target-db {TARGET_DB} {RECON_PARAMS} --out .migration/recon/<UNIT>/`.
Also validate machine-readable artifacts with `make tp-validate-recon FILE=<path>`.

Deliverable: ONE pull request into `{RUN_BRANCH}` from branch `{RUN_BRANCH}--<unit lower>` (never a
stack; ordered semantic commits: registration+contract, code, load, recon evidence, fix rounds). PR
body <= ~2000 chars, sections in order Decisions -> Code -> Evidence, with "Unverified paths /
declared-unexercised" as the TOP block; render recon.summary.md, link result.json/report.md; cite
mapping v1.0 and tolerance v1; a PROFILE FEEDBACK section (may be empty); idempotency proof (your
loads drop+recreate ONLY your unit's collections and were actually re-run). Run the repo skill
.agents/skills/tp-pre-pr-self-check and `make tp-smoke` before opening the PR. Update your unit's row
in .migration/04_progress.md (RECON_GREEN only with a green fixture result.json) in the PR.
"""

# Units whose ORIGINAL child was resumed by orchestrator message after an escalation (never relaunched).
# The workflow re-ingests that child's finished evidence via a lightweight verifier instead of redoing work.
RESUMED = {
    "U0": {"session": "devin-4a712cd3cdda4e22add668ce6fa915ca",
           "pr_url": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/1423",
           "branch": "tp-run/mongodb-20260901T205236Z--u0"},
    "U2": {"session": "devin-663f09e932ba4eacbed5b0635a1ba5d4",
           "pr_url": "https://github.com/Cognition-Partner-Workshops/otterworks/pull/1432",
           "branch": "tp-run/mongodb-20260901T205236Z--u2"},
}

UNIT_SCHEMA = {
    "type": "object",
    "properties": {
        "unit": {"type": "string"},
        "verdict": {"type": "string", "description": "GREEN | RED | ESCALATE"},
        "pr_url": {"type": "string", "description": "empty if none opened"},
        "branch": {"type": "string"},
        "failure_class": {"type": "string", "description": "empty if GREEN; else one of types|null_missing|timezone|embed_cardinality|proc_semantics|load|env|collision|other"},
        "escalation": {"type": "string", "description": "what needs a human decision, with evidence paths; empty if none"},
        "profile_feedback": {"type": "string"},
        "cost_notes": {"type": "string"},
    },
    "required": ["unit", "verdict", "pr_url", "branch", "failure_class", "escalation"],
}

WAVE_SCHEMA = {
    "type": "object",
    "properties": {
        "wave": {"type": "string"},
        "wave_verdict": {"type": "string", "description": "PASS | FAIL | DRIFT-EXPLAINED"},
        "unit_verdicts": {"type": "string", "description": "JSON object unit->PASS|FAIL|DRIFT-EXPLAINED"},
        "report_path": {"type": "string", "description": "branch:path of the wave report"},
        "attested_heads": {"type": "string", "description": "JSON object unit->exact PR head SHA the LIVE recon ran against"},
        "findings": {"type": "string"},
        "grading_amendments": {"type": "string", "description": "grading-only amendments applied (none if empty)"},
    },
    "required": ["wave", "wave_verdict", "unit_verdicts", "report_path", "attested_heads"],
}

MERGE_SCHEMA = {
    "type": "object",
    "properties": {
        "merged": {"type": "string", "description": "JSON list of PR URLs merged into the run branch"},
        "status": {"type": "string", "description": "OK | BLOCKED"},
        "detail": {"type": "string"},
    },
    "required": ["merged", "status"],
}

UNITS = {
    "U0": {
        "title": "U0 reference: codes, tenants, plans",
        "deps": [],
        "spec": """Unit U0 (wave 0, reference, S). Migrate Oracle CODES -> codes (D1: `_key = "TYPE:VAL"`,
comparison key per spec), TENANTS (69 rows) -> tenants, PLANS -> plans. Indexes per the spec's
`indexes` arrays. No app rewrite. Every later unit reads these — correctness is load-bearing.""",
    },
    "U1": {
        "title": "U1 customers (XL): CUSTOMER_MASTER + EAV + history + counters",
        "deps": ["U0"],
        "spec": """Unit U1 (wave 1, XL, wide-embed calibration). Migrate CUSTOMER_MASTER (155 cols, 25,000 rows,
root_where conversion_batch_no=${batch_no}) -> customers with ENTITY_ATTR_VALUE folded into
attributes[] per D5 (element key eav_id; 8,333 rows); CUSTOMER_MASTER_HIST -> customers_history
(0 rows — grade the empty collection); sequences -> `counters` docs seeded at LAST_NUMBER (D11);
TRG_CUSTOMER_MASTER_SEQ/_HIST behaviour -> app write path. String dates verbatim (graded) plus
derived BSON-date twins; unparseable -> quarantine class dirty_signup_dt (50 expected). CSV lists
verbatim plus derived arrays; malformed -> bad_csv_list (31 expected) (D3/D4). Rewrite the RPT-114
BALANCES_SQL path in services/legacy-billing/app/reports.py as an aggregation pipeline. XL protocol:
first commit is the ~100-line decision-first contract excerpt at .migration/contracts/U1.md (content
already approved at STOP B; proceed to implementation in the same PR).""",
    },
    "U2": {
        "title": "U2 invoices (bulk): INVOICE_HEADER + INVOICE_LINE + orphan quarantine",
        "deps": ["U0"],
        "spec": """Unit U2 (wave 1, bulk-load calibration, L). Migrate INVOICE_HEADER (18,750, root_where
batch_no=${batch_no}) -> invoices with INVOICE_LINE embedded as lines[] (D6, element key line_id).
The 37 orphan lines go to {quar}.invoice_feed_orphan_lines — never dropped; embedded + quarantined
must equal 150,000. Rewrite RPT-114 STATUS_SQL and LINE_SQL report paths in
services/legacy-billing/app/reports.py against MongoDB. Indexes per spec. Loads bulk + idempotent.""".replace("{quar}", QUAR_DB),
    },
    "U3": {
        "title": "U3 documents + document_snapshots (Postgres)",
        "deps": [],
        "spec": """Unit U3 (wave 1, M). Source: Postgres database `otterworks`, schema `otterworks_demo`
(localhost:5432 after `make infra-up`; fixture creds from docker-compose.yml). Migrate documents
(2,000) -> documents with document_versions embedded as versions[] (13,876; element key per spec),
document_snapshots (390) -> document_snapshots referenced by document_id; 6 orphan snapshots ->
{quar}.orphan_document_snapshots; 10 version gaps REPORTED in the PR, not repaired (D7). Recon via
D13: implement `.migration/recon_ext/postgres_source.py` (PostgresSourceAdapter implementing the
harness SourceAdapter protocol; engine/tiers/report unchanged) and record it as PROFILE FEEDBACK.""".replace("{quar}", QUAR_DB),
    },
    "U4": {
        "title": "U4 files (DynamoDB otterworks-file-metadata)",
        "deps": [],
        "spec": """Unit U4 (wave 1, S). Source: LocalStack DynamoDB table `otterworks-file-metadata`
(localhost:4566, 10,000 items, source attribute ns='demo'). Item-per-document 1:1 -> files;
source `ns` -> `source_ns`, migration ns = the run namespace (D8). 40 orphaned S3 markers reported as
a named class in the PR. Indexes per spec. Recon via D13: `.migration/recon_ext/dynamo_source.py`
(DynamoSourceAdapter); PROFILE FEEDBACK.""",
    },
    "U5": {
        "title": "U5 billing core: 9 package-owned collections + validator/TTL",
        "deps": ["U0"],
        "spec": """Unit U5 (wave 2a, M). Migrate the package-owned tables: SUBSCRIPTIONS -> subscriptions,
SUBSCRIPTIONS_HIST -> subscriptions_history (0 rows; grade empty), USAGE_EVENTS (814) ->
usage_events with a $jsonSchema validator replacing the check trigger (D11), RATING_PERIODS +
RATING_RESULTS -> rating_periods.results[] (D9), INVOICES + INVOICE_LINES -> billing_invoices.lines[]
(D9; NOT the bulk `invoices` collection, which is U2's), CREDIT_NOTES -> credit_notes,
DUNNING_ATTEMPTS -> dunning_attempts (unique (invoice_id, attempt_no)), NOTIFICATIONS ->
notifications (unique (tenant_id, kind_cd, sent_at)), BILLING_AUDIT_LOG -> billing_audit_log
(0 rows; TTL index on logged_at 90d replacing the disabled purge job). No package rewrite here —
U6–U9 own the PL/SQL; ship a `services/legacy-billing/app/ow_billing/__init__.py` skeleton with the
Mongo client factory and collection names only.""",
    },
    "U6": {
        "title": "U6 PKG_OW_UTIL + PKG_PLANS -> Python (proc-class calibration)",
        "deps": ["U5"],
        "spec": """Unit U6 (wave 2b, M, calibration unit for the stored-procedure class). Rewrite PKG_OW_UTIL
(f_md5_uuid, f_code_desc via codes lookup, date helpers, log_msg -> unconditional independent audit
write with its own write concern, never inside a caller's transaction) and PKG_PLANS
(fn_list_plans, fn_entitlement, sp_change_plan: FOR UPDATE -> transaction with findOneAndUpdate,
deterministic md5 ids, DECODE tier names) as app-side Python in
services/legacy-billing/app/ow_billing/ per D10, wired to the `billing.*` entrypoints in
procs/routes.yaml. Tier-4 grading = the recorded Oracle transcripts under procs/oracle/transcripts
for module plans (5 scenarios), replayed by the harness against your OWN registered clone
`replay_u6_*` of the U5 collections (load it with U5's merged loader from your fixture; never
replay against the golden loaded set). Pull the latest run branch — U5 is merged.""",
    },
    "U7": {
        "title": "U7 PKG_RATING -> Python/pipeline",
        "deps": ["U5"],
        "spec": """Unit U7 (wave 2b, M). Rewrite PKG_RATING (compute_rating's YYYYMMDD string-window filter and
NVL/LEAST/GREATEST rollover arithmetic reproduced EXACTLY incl. NULL propagation; 101-unit first
tier, 1.5x second tier, ROUND(...,2); suspension proration for status 20; fn_usage_rating,
fn_usage_summary, sp_finalize_rating upsert into rating_periods.results[]) as app-side Python with
the usage sum as an aggregation pipeline (D10). Package globals become return values. Tier-4 grading
= transcripts module rating (8 scenarios) replayed against your own clone `replay_u7_*`. Pull the
latest run branch — U5 is merged.""",
    },
    "U8": {
        "title": "U8 PKG_INVOICING -> Python (calls rating)",
        "deps": ["U6", "U7"],
        "spec": """Unit U8 (wave 3, L). Rewrite PKG_INVOICING (compute_preview's 5-line shape incl. tax split
into two halves at TAX_RATE 0.0825 and DECODE exempt; sp_issue_invoice: deterministic period/invoice
ids via the U6 md5 helper, finalize rating via the U7 module, delete+rebuild lines as ONE
single-document write on billing_invoices; fn_invoice_lines; credit-note application) as app-side
Python per D10, calling the merged U6/U7 modules — never re-implementing them. Tier-4 grading =
transcripts module invoicing (6 scenarios) against your own clone `replay_u8_*`. Pull the latest
run branch — U5/U6/U7 are merged.""",
    },
    "U9": {
        "title": "U9 PKG_DUNNING -> Python + disabled scheduler",
        "deps": ["U5", "U6"],
        "spec": """Unit U9 (wave 3, M). Rewrite PKG_DUNNING (fn_overdue_accounts with outer join to tenants and
YYYYMMDD string compare; sp_schedule_dunning where `WHEN OTHERS THEN NULL` narrows to an explicit
DuplicateKeyError no-op ONLY — other errors surface; sp_suspend_overdue's tenant + subscription
status 20 updates and conditional notification insert) as app-side Python per D10 using the merged
U6 util module. Replace the disabled nightly scheduler job with a runnable, shipped-DISABLED job
entrypoint (no schedule activation). Tier-4 grading = transcripts module dunning (5 scenarios)
against your own clone `replay_u9_*`. Pull the latest run branch — U5/U6 are merged.""",
    },
}

WAVE_RECON_COMMON = f"""
You are the INDEPENDENT wave reconciliation session ([MONGO v1] Reconciliation & Parallel Run,
Part 1) for the OtterWorks billing-estate -> MongoDB migration. You converted nothing in this wave;
do not read the children's diagnoses before re-running. You run ON THE PARENT MACHINE where the
canonical fixtures already run (Oracle localhost:52521/FREEPDB1 user ow_billing; Postgres
localhost:5432 db otterworks schema otterworks_demo; LocalStack DynamoDB localhost:4566 table
otterworks-file-metadata; manifest sha256 {MANIFEST_SHA}). Reuse them; if one is down restart it via
the repo make targets but NEVER reseed or modify data; leave them running. Do not switch this
machine's checkout branch destructively, restart its shells, or delete files outside your scope —
use a separate clone under ~/wave_recon/ for checkouts. Repo {REPO}, run branch {RUN_BRANCH},
mapping v1.0, tolerances v1, canonicalization v1 (files in .migration/). Target db {TARGET_DB}
(quarantine {QUAR_DB}), secret MONGODB_ATLAS_URI (names only). Harness at {HARNESS_GLOB}. Recon
params: {RECON_PARAMS}. Source-load cap is 1: you are the single LIVE window — run gates serially.

For each unit in the wave: (1) re-run its recon gate VERBATIM from the spec in LIVE mode against the
canonical fixtures (authoritative live proof; on mismatch triage drift-vs-defect by re-running the
source side twice); (2) probe adversarially beyond the gate: null/missing distributions per field,
duplicate keys, min/max boundary docs, empty-collection behaviour, embed-array length distribution
vs child rows, spot doc-level checks on aggregate-only fields, quarantine classes compared as SETS
against the expected counts; (3) cross-unit consistency on shared references (codes/tenants/plans);
(4) replay representative app-level queries/transcripts against both stacks. Write the wave report
+ a one-page wave-close brief to .migration/recon/wave_reports/<wave>.md on a branch pushed to
origin (report `branch:path`) with per-unit PASS/FAIL/DRIFT-EXPLAINED, probe results, findings, a
per-unit cost line, and any grading-only amendment you believe is warranted (describe it; do NOT
apply it — the orchestrator decides). Never fix migrated code, touch legacy, or adjust tolerances.
"""

MERGE_PROMPT = f"""
You are the merge/ledger agent for the OtterWorks MongoDB migration, running ON THE PARENT MACHINE
(do not disturb its running state; use a separate clone under ~/merge_work/). Repo {REPO}. Merge
ONLY the PRs listed below into `{RUN_BRANCH}` (never tech-partnerships or main), in order, using the
PR merge API or plain git (fetch head, merge, push). Then on {RUN_BRANCH} update
.migration/04_progress.md (each merged unit: Status=MERGED, Parity=GREEN per the wave report, PR
column, quarantine rate, unverified paths from the PR's top block) and append ONE wave-close row
to .migration/05_decisions.md (`| <next #> | <UTC> | orchestrator | Wave <w> CLOSED: <units> merged
on independent LIVE recon PASS (report <branch:path>); grading amendments: <list or none> |`).
Commit 'migration(205236): wave <w> close — merge + ledger' and push. If a merge conflicts or a PR
is missing/closed: status BLOCKED, report; never force-push or resolve substantive conflicts.
Always list EVERY PR whose head is reachable from {RUN_BRANCH} after your run in `merged` (including ones
merged on an earlier pass). IDEMPOTENCY: if a PR head is already reachable from {RUN_BRANCH}, treat it as merged and skip;
never duplicate ledger/decision rows; if all done, verify and return OK.
"""


async def run_unit(uid):
    u = UNITS[uid]
    if uid in RESUMED:
        r = RESUMED[uid]
        return await agent(
            f"Repo {REPO}. Unit {uid} ({u['title']}) of the OtterWorks MongoDB migration was completed by its "
            f"original child session {r['session']} after an orchestrator-approved resume; PR: {r['pr_url']} "
            f"(branch {r['branch']}, base {RUN_BRANCH}). Do NOT redo or re-run the migration. Verify only: the PR is "
            f"open against {RUN_BRANCH}; its head contains .migration/recon/{uid}/result.json with verdict PASS/GREEN, "
            f"mapping_version v1.0.1, tolerance v1 (the harness has no fixture mode: result.json mode=live run against the "
            f"local fixture DSN is expected; the fixture label lives in the repo-schema wrapper .migration/recon/{uid}/"
            f"{uid.lower()}.recon.json run_mode=fixture); the PR body sections the child wrote contain no requester "
            f"identification (ignore the platform-appended 'Requested by' footer, which no child controls). Report verdict "
            f"GREEN with pr_url/branch if all hold, else ESCALATE with what is missing.",
            phase=f"convert-{uid}", schema=UNIT_SCHEMA, label=f"{u['title']} (resumed-evidence check)",
        )
    return await agent(
        COMMON + "\n## Your unit\n" + u["spec"] +
        f"\n\nPR branch: `{RUN_BRANCH}--{uid.lower()}`. Report verdict GREEN only with a green fixture "
        "result.json on disk and an open PR; RED if the re-run cap was hit; ESCALATE if a human decision "
        "is needed (spec ambiguity, collision, blocked on an unlanded sibling, fixture mismatch).",
        phase=f"convert-{uid}",
        schema=UNIT_SCHEMA,
        label=u["title"],
        repos=[REPO],
    )


async def wave_recon(wave_name, unit_results):
    prs = json.dumps({r["unit"]: {"pr": r["pr_url"], "branch": r["branch"],
                                  "resumed_from": RESUMED.get(r["unit"], {}).get("session", "")}
                      for r in unit_results}, sort_keys=True)
    return await agent(
        WAVE_RECON_COMMON + f"\n## Wave under review: {wave_name}\nUnit PRs/branches:\n{prs}\n"
        "Fetch each PR branch at its CURRENT head, record the exact head SHA per unit in attested_heads, and run the "
        "gates against THAT code+load state (re-run the unit loader from the PR head into the target first if the "
        "loaded data predates the head). Units whose PR is already merged into the run branch: attest the merged head and carry the PASS from the prior wave report for that head (cite it) instead of re-grading; spend the LIVE window on the unmerged units.",
        phase=f"recon-{wave_name}",
        schema=WAVE_SCHEMA,
        label=f"independent LIVE recon {wave_name}",
        vm_mode="shared",
    )


async def merge_wave(wave_name, unit_results, recon):
    order = json.dumps([r["pr_url"] for r in unit_results])
    return await agent(
        MERGE_PROMPT + f"\nWave: {wave_name}\nPRs in merge order: {order}\n"
        f"Wave report: {recon['report_path']}\nUnit verdicts: {recon['unit_verdicts']}\n"
        f"Attested heads (merge a PR ONLY if its current head equals the attested SHA; otherwise BLOCKED for that unit): {recon['attested_heads']}\n"
        f"Grading amendments: {recon.get('grading_amendments') or 'none'}",
        phase=f"merge-{wave_name}",
        schema=MERGE_SCHEMA,
        label=f"merge {wave_name}",
        vm_mode="shared",
    )


HALTED = {}          # unit -> reason (this unit / failure class paused; others continue)
FAILURE_COUNTS = {}
MERGED_UNITS = set()


def _halt(uid, reason):
    HALTED[uid] = reason
    log(f"HALT {uid}: {reason}")


async def run_wave(wave_name, unit_ids):
    runnable = [u for u in unit_ids if all(d in MERGED_UNITS for d in UNITS[u]["deps"])]
    for u in unit_ids:
        if u not in runnable:
            _halt(u, f"dependency not merged ({[d for d in UNITS[u]['deps'] if d not in MERGED_UNITS]}) — deferred")
    if not runnable:
        log(f"{wave_name}: nothing runnable")
        return
    log(f"{wave_name}: launching {runnable}")
    raw = await asyncio.gather(*[run_unit(u) for u in runnable], return_exceptions=True)
    green = []
    for uid, r in zip(runnable, raw):
        if isinstance(r, Exception):
            _halt(uid, f"child died/no output: {r}")
            continue
        fc = r.get("failure_class") or ""
        if fc:
            FAILURE_COUNTS[fc] = FAILURE_COUNTS.get(fc, 0) + 1
        if r["verdict"] != "GREEN":
            _halt(uid, f"verdict={r['verdict']} class={fc} escalation={r['escalation']}")
            continue
        green.append(r)
    for fc, n in FAILURE_COUNTS.items():
        if n >= 3:
            log(f"CIRCUIT BREAKER: 3 same-class failures ({fc}) — class paused; human decision required")
    if not green:
        log(f"{wave_name}: no GREEN units — wave not closed")
        return
    log(f"{wave_name}: GREEN(fixture) {[r['unit'] for r in green]} — independent LIVE recon")
    recon = await wave_recon(wave_name, green)
    verdicts = json.loads(recon["unit_verdicts"]) if recon["unit_verdicts"].strip().startswith("{") else {}
    passed = [r for r in green if verdicts.get(r["unit"], recon["wave_verdict"]) in ("PASS", "DRIFT-EXPLAINED")]
    for r in green:
        if r not in passed:
            _halt(r["unit"], f"independent recon FAIL: {recon.get('findings','')}")
    if not passed:
        log(f"{wave_name}: recon FAIL for all units — wave not closed")
        return
    merged = await merge_wave(wave_name, passed, recon)
    merged_urls = merged["merged"] if isinstance(merged["merged"], list) else json.loads(merged["merged"] or "[]")
    for r in passed:
        if r["pr_url"] in merged_urls:
            MERGED_UNITS.add(r["unit"])
        else:
            _halt(r["unit"], f"merge BLOCKED: {merged.get('detail','')}")
    if merged["status"] != "OK":
        log(f"{wave_name}: merge status {merged['status']} — merged {merged_urls}; wave not closed")
        return
    log(f"WAVE CLOSED {wave_name}: merged {merged['merged']} | recon {recon['report_path']} | "
        f"amendments: {recon.get('grading_amendments') or 'none'}")


async def main():
    order = ["U0", "U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9"]
    await register_workflow({
        "name": "mongo-205236-fanout",
        "description": "OtterWorks billing estate (Oracle OW_BILLING + Postgres docs + DynamoDB files) -> "
                       "MongoDB Atlas migration fan-out: waves 0-3, LIVE-recon-gated, one PR per unit.",
        "product": "OtterWorks billing estate (Cognition-Partner-Workshops/otterworks)",
        "phases": (
            [{"title": f"convert-{u}", "detail": UNITS[u]["title"], "count": 1, "labels": [UNITS[u]["title"]]} for u in order]
            + [{"title": f"recon-{w}", "detail": f"independent LIVE recon {w}", "count": 1} for w in ["wave0", "wave1", "wave2a", "wave2b", "wave3"]]
            + [{"title": f"merge-{w}", "detail": f"merge + ledger {w}", "count": 1} for w in ["wave0", "wave1", "wave2a", "wave2b", "wave3"]]
        ),
    })
    await run_wave("wave0", ["U0"])
    await run_wave("wave1", ["U1", "U2", "U3", "U4"])
    await run_wave("wave2a", ["U5"])
    await run_wave("wave2b", ["U6", "U7"])
    await run_wave("wave3", ["U8", "U9"])
    if HALTED:
        log("HALTED UNITS (need human decision / resume): " + json.dumps(HALTED, sort_keys=True))
    else:
        log("All waves closed — engagement ready for phase 4 (cutover preparation).")

asyncio.run(main())

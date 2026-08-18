# Run of Show — MongoDB Atlas + Devin Showcase (run `tp-run/mongodb-20260817T233337Z`)

**Narrative:** MongoDB catches it, Devin fixes it, the PR proves it.
**Run branch:** `tp-run/mongodb-20260817T233337Z` (cut from `tech-partnerships` via
`make tp-run-branch TRACK=mongodb`). All migration PRs merged into the run branch only —
nothing into `main` or `tech-partnerships`.
**Namespaces:** `demo` (persistent showcase, left up and green) · `rehearsal1`
(failure-beat rehearsal, torn down and verified absent).
**Schedules:** none anywhere; every step is hand-triggered.

Demo-day model: everything below is pre-staged. On the day you only re-run the green
beats against `NS=demo` and trigger the drift + recon-failure beat live in a fresh
rehearsal namespace.

## Beat 0 — Preflight and shared infrastructure (parent, pre-staged)

```bash
make tp-preflight PLATFORM=atlas     # capability probes, not just auth
```

Capability manifest: `.tp-preflight/atlas-capabilities.json` — 13 probes, 0 denied
(project/cluster/db-user/access-list read, access-list create+delete, VM IP
allow-listing, wire-protocol write, collMod/validator DDL). The `otterworks-app` user
carries `readWriteAnyDatabase` + `dbAdminAnyDatabase` (granted during preflight to enable
`collMod`). The optional Atlas alert-webhook garnish is out of scope for this run — the
failure loop rides the Devin automation webhook instead.

Shared run-scoped Atlas infrastructure is parent-owned Terraform under
`infrastructure/terraform-atlas/` (run db `ow_tp_mongodb_demo`, quarantine
`ow_tp_mongodb_demo_quarantine`, scoped run user; the shared `otterworks-demo` cluster is
consumed as a data source, never managed). Verified apply → destroy → re-apply, and
`terraform plan -detailed-exitcode` clean (exit 0) at rollup.

## Beat 1 — Before-state (immutable baseline)

```bash
make infra-up
make oracle-billing-up && make oracle-billing-seed NS=demo
make seed-legacy NS=demo
make seed-legacy-validate NS=demo    # 15/15 PASS
```

Baseline manifest: `testdata/legacy/manifests/demo.json` (seed `714559852`) — 25,000
customers, 8,333 EAV rows, 18,750 invoices / 150,000 lines, 2,000 documents / 13,876
versions, 10,000 file-metadata items, with exactly enumerated planted anomalies
(37 orphan lines, 50 dirty dates, 31 malformed CSV lists, 10 version gaps, 6 orphaned
snapshots, 40 orphaned metadata items). Estate tour beats live in
`runbook-mongodb.md` (Beats 1–2).

## Beat 2 — Wave 1: data migration (one child per workload)

PRs (all merged into the run branch): customers
[#1162](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1162) ·
documents [#1163](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1163) ·
invoices [#1164](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1164) ·
files [#1166](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1166) ·
live recon evidence + rollup
[#1171](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1171).

Live target-side proof: recon recomputed from Atlas, idempotency re-run, and exact
planted-anomaly-set equality; evidence under `docs/tech-partnerships/recon/`
(`ROLLUP-mongodb-demo.md`). `make tp-validate-recon` and `make tp-smoke` green.

## Beat 3 — Wave 2: stored procs → billing service (hard cutover)

PRs (all merged): compose Mongo document-store fixture
[#1172](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1172) ·
rating extraction (8/8 scenarios)
[#1174](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1174) ·
invoicing extraction (6/6)
[#1177](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1177) ·
wave rollup [#1179](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1179).

```bash
make procs-up NS=demo
make procs-rules-gate ALL=1    # PASS: plans, rating, invoicing
make procs-parity NS=demo      # Parity PASS=19 FAIL=0 SKIP=5 (dunning SKIP)
```

Zero re-recorded transcripts; rules ledgers `procs/rules/rating.rules.yaml` and
`procs/rules/invoicing.rules.yaml`; routing in `procs/routes.yaml`. CI uses the compose
fixture only — no live-target dependency. Known caveat: `make test` carries 9
pre-existing document-service auth failures from a reverted JWT-auth-headers commit on
the branch base (`4f6a6638` reverting `a31b8bff`) — unrelated to this run, tests left
untouched.

## Beat 4 — Wave 3: platform showcase

PRs (all merged): `$jsonSchema` validators
[#1180](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1180) ·
finance report as one aggregation pipeline (cent-exact vs golden)
[#1181](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1181) ·
recon + failure-to-Devin loop, drift staging, teardown
[#1182](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1182) ·
run-of-show + final evidence
[#1186](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1186).

Stage commands, expected outputs, and per-beat artifacts:
`docs/tech-partnerships/showcase/RUN-OF-SHOW.md` (validators demo, aggregation report,
hard-cutover read path, recon/run-job).

## Beat 5 — The failure loop (rehearsed end to end, never remediated by hand)

Green path first (webhook not fired): `recon.demo.green.json`,
`run_job.demo.green.json`, then in the rehearsal namespace
`recon.rehearsal1.green.json` (all under `docs/tech-partnerships/showcase/`).

Red path (`rehearsal1`):

1. Real drift staged: `make mongo-showcase CMD=drift NS=rehearsal1 ARGS="--kind corrupt --n 100"`.
2. `make mongo-run-job NS=rehearsal1 ...` → recon **FAILED** with named check
   `customers-checksum` (`recon.rehearsal1.red.json`).
3. Webhook fired (HTTP 200) to the Devin recon-failure automation
   (payload `{namespace, failing_checks, run_url, base_branch}`, secret from
   `OW_TP_MONGO_RECON_WEBHOOK_SECRET`, never inline).
4. Devin session spawned:
   <https://partner-workshops.devinenterprise.com/sessions/e4336a940196415f971b0106dba75d9d>
   — diagnosed the +0.01 `balances.current` corruption on 100 customers, remediated via
   an idempotent migration re-run, recon back to GREEN.
5. Audit PR opened against the run branch:
   [#1184](https://github.com/Cognition-Partner-Workshops/otterworks/pull/1184)
   (CI green, left open as demo evidence).

Reset: `make tp-atlas-teardown NS=rehearsal1` — `ow_tp_mongodb_rehearsal1` and
`ow_tp_mongodb_rehearsal1_quarantine` dropped; absence re-verified live at rollup (no
rehearsal databases or database users remain in the project).

## Beat 6 — Parent rollup (uncontended, parent-run)

```bash
make tp-validate-recon                 # PASS (8 recon files)
make mongo-showcase CMD=recon NS=demo  # recon demo: GREEN (11 checks)
make procs-rules-gate ALL=1            # PASS: plans, rating, invoicing
make procs-parity NS=demo              # Parity PASS=19 FAIL=0 SKIP=5
terraform plan -detailed-exitcode      # exit 0 (clean) in infrastructure/terraform-atlas/
make tp-smoke                          # green
```

Final state: `NS=demo` up and browsable — migrated collections with enforced validators,
billing service serving from the target, aggregation report reproducible, recon 11/11
GREEN (`recon.demo.final.json`). Rehearsal namespaces gone. Nothing scheduled.

## Orchestration sessions

- Wave 1 (data): <https://partner-workshops.devinenterprise.com/sessions/e3f0867610ae42a881e09b8eb8cc4a6a>
- Wave 2 (procs): <https://partner-workshops.devinenterprise.com/sessions/bbb04f2edda9462a93e6831914877ff3>
- Wave 3 (showcase): <https://partner-workshops.devinenterprise.com/sessions/a16fb33c4a024efcb8fa806ffc332680>
- Remediation (spawned by the automation): <https://partner-workshops.devinenterprise.com/sessions/e4336a940196415f971b0106dba75d9d>

# Databricks: Redshift marts in waves

Devin converts a Redshift mart estate of 20 units to Databricks SQL in waves, one child session per unit, each validated against a golden snapshot on its own machine. The Databricks persona owns the plan, the fan-out and the independent review.

| Field | Value |
|---|---|
| `runAs` | Databricks (`user-c3478f949c414221a740236d07764e68`) |
| Field Kit | Area `ISV and platform`, Identity `Databricks` |
| Delegation shape | Scalable. 18 mart units in two waves of 5 and 13 children, each with the same contract. |
| Repository | `Cognition-Partner-Workshops/dbx-redshift-migration`, run branch `migration-run-2`; prompts and readiness notes on `devin/1791186818-viewonly-run2-prompts` (pull request 29) |
| Read only | `legacy/`, `golden/`, `data/seed/`, `validation/`, `.migration/units.yaml`, `.migration/06_decisions.md` |
| Writable per child | `databricks/units/<unit>/`, `.migration/evidence/<unit>.json`, one row of `.migration/coverage.md` |
| Child branches | `unit/run-2/<unit>`, pull requests into `migration-run-2`; the `unit/<unit>` names belong to run 1 |
| Mode | Fusion |

## Preflight, the day before

1. Secrets, by name, set in the `Partner Demo - ViewOnly` org: `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_WAREHOUSE_ID`. As of 2026-10-05 the token in the environment is rejected by both candidate workspaces (`Invalid access token`), there is no `~/.databrickscfg`, and no warehouse id is set. Until a human provides all three, the live path below stays unrun and the readiness path is what the audience sees.
2. Databricks CLI 0.292.0 or newer in the snapshot. The build machine had 1.19.0.
3. `make check` on `migration-run-2`: ruff clean, 23 tests, `manifest OK`. The branch points at the same commit as `main`, so the first commit of the run comes from the orchestrator.
4. Read `demo-ops/viewonly/READINESS.md` for the four places where the record and the repository disagree, so you are not surprised when Devin measures a truncation where the record expected a rounding difference.

## Live, readiness path (what exists today)

1. Sign in as the Databricks persona and start a session with the prompt in `/home/ubuntu/prompts/aws-native/prompts/dbx-plan-readiness.md`. The prompt names the repository, which matters because the composer's repository picker in `Partner Demo - ViewOnly` offers only `otterworks`. Devin runs `make check`, posts a plan table with one row per unit (wave, legacy files, outputs, golden row counts, Redshift features that behave differently on Databricks, expected fix pattern), posts the fan-out plan, and probes the workspace with `databricks current-user me`, printing the error and the three secret names it needs.
2. Start a second session with `/home/ubuntu/prompts/aws-native/prompts/dbx-run1-audit.md`. Devin audits `migration-run-1` as an independent reviewer: one row per evidence file, the pull request per unit with its CI state and whether it stayed inside the writable paths, and the determinism checks (`GETDATE`, `CURRENT_DATE`, `SYSDATE`, `RANDOM`, as-of dates other than `2025-12-31`).
3. Close on the two tables and the honest line in the first session: the workspace is not reachable with the secrets at hand, and no workspace object was created or changed.

## Live, full path (once the secrets exist)

1. Orchestrator session as the Databricks persona on `migration-run-2` with `demo-ops/viewonly/orchestrator.md`: `make db-setup`, Lakebridge analyze and transpile, drafts committed to the run branch, wave 0 `foundation`.
2. Wave 1a: 5 child sessions, then wave 1b: 13, each from `demo-ops/viewonly/unit-customer-ltv.md` with its unit name, each on `unit/run-2/<unit>`, each ending with `make validate` and an evidence file.
3. The live unit: `customer_ltv`. The first validation fails on `aov`; Devin measures the rounding rules and names the cause from the table it builds.
4. Verifier session with `demo-ops/viewonly/verifier.md`: `make validate-all`, the summary table, and the screenshots from Catalog Explorer and the job run.
5. Wave 2 and the merge into `main` are human steps.

## Expected state after

| Path | Expected |
|---|---|
| Readiness | `make check` green; plan table with 20 rows and 48 outputs; the probe error and the three secret names; nothing changed in any workspace |
| Full | 18 evidence files PASS, 18 pull requests into `migration-run-2` each inside the writable paths, verifier summary 48 of 48 outputs |

## Reset

The readiness path leaves the workspace and the branches as it found them. The full path is reset by deleting the catalog `mig_redshift_dev` in the workspace and the `unit/run-2/*` branches; `migration-run-2` goes back to the `main` commit with a force push by a human.

## Fallback

- Token rejected mid-demo: the sessions stop before any write, as the readiness run did. Show the probe output and move to the run 1 audit.
- Lakebridge install fails on the child: the drafts are already on the run branch; the child converts from them.

## Talk track

Twenty units, the same contract each, one child per unit on its own machine, and a golden snapshot that says pass or fail without a human reading SQL. The review session is the other half: Devin checks Devin's run and says where the evidence is thin.

## Evidence from the recorded sessions

| Item | Where |
|---|---|
| Plan and readiness session, Databricks, Fusion | https://partner-workshops.devinenterprise.com/sessions/cf5822ffaa724b798f867f67ab1cf3b0 |
| Run 1 audit session, Databricks, Fusion | https://partner-workshops.devinenterprise.com/sessions/d851ed3368444edfaab7b4a4ea83f78b |
| Prompts and readiness pull request | https://github.com/Cognition-Partner-Workshops/dbx-redshift-migration/pull/29 |
| Sidebar as the Databricks persona | `evidence/devin/viewonly-sidebar-databricks-2-sessions.png` |

## Rerun log

| Date | Who | Session | What the runbook had not said |
|---|---|---|---|
| 2026-10-05 | Databricks persona | `cf5822ff`, `d851ed33` | Both candidate workspaces reject the token, so the runbook needs the readiness path as a first-class route; added. |
| 2026-10-05 | Databricks persona, readiness path, second run | `2c603394` | The repository picker in the ViewOnly composer lists only `otterworks`, so the prompt has to name `dbx-redshift-migration` itself; it does. The session VM had no Databricks CLI (the repo blueprint dropped it in commit `229d566`) and `Partner Demo - ViewOnly` holds none of the three secrets, so the verdict was NOT READY with the CLI install and the three names as the blockers; both added to Preflight. |

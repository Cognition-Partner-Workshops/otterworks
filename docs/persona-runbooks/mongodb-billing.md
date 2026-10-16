# MongoDB: Oracle billing to Atlas

Devin migrates the customer module of a legacy Oracle billing estate (19 tables in scope, 25,000 demo customers) to MongoDB, with a write-scope gate before any connection, a loader that is safe to run twice, and a reconciliation gate that decides whether the result counts as merge evidence.

| Field | Value |
|---|---|
| `runAs` | MongoDB (`user-5aded87015e641c5867bf64246f0e452`) |
| Field Kit | Area `ISV and platform`, Identity `MongoDB` |
| Delegation shape | Repetitive with a gate. The loader runs the same way for every unit and every rerun; the recon says when it is done. |
| Repository | `Cognition-Partner-Workshops/otterworks`, branch `devin/1791186817-mongodb-billing-run-prep`; the U2 fixture fix on `devin/1791188392-mongodb-u2-fallback` (pull request 1808) |
| Harness | `migration/billing/` (`README.md`, `scripts/atlas-scope-check.sh`, `recon/recon.py`, `tolerances.json`), Make targets `tp-*` |
| Fixture | Oracle Free container from `services/legacy-billing/db/oracle/`, `mongo:7` as the local fallback |
| Mode | Fusion |

## Preflight, the day before

1. Secrets, by name: `MONGODB_ATLAS_URI` (a dedicated user holding exactly `readWrite@ow_tp_billing_<timestamp>`), optional `MONGODB_ATLAS_PROJECT_ID`, `MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY` for the Atlas CLI, and `OW_TP_ORACLE_RO_DSN` only when a live Oracle is wanted. As of 2026-10-05 none of these exist in the org, so every session uses the fixtures and says so.
2. Snapshot: the worker venv at `/home/ubuntu/.venvs/ow-billing` (`oracledb`, `pymongo`), the `mongo:7` image (pull from `mirror.gcr.io/library/mongo:7` when Docker Hub rate limits) and the Oracle Free image. `migration/billing/env/blueprint-proposal.diff` holds the proposal.
3. `OW_BILLING_ENV_MODE=auto migration/billing/env/postsetup-check.sh all` prints `mongo PASS fallback`, `oracle PASS fallback`, `schemas PASS`.
4. `make tp-validate-schemas` prints `ok`.
5. `uv --version` answers. The Makefile targets run Python through `uv run`, and a fresh VM without it stops at the first gate command.

## Live

1. Sign in as the MongoDB persona. Session 1, the plan: start on the run-prep branch and ask for the census and the plan. Devin names the 19 tables in scope, the 25,001 rows in `CUSTOMER_MASTER` with 155 columns, the 8,337 attribute rows that become `customers.attributes[]`, the 5 PL/SQL packages and the 12 Flask entry points.
2. Session 2, the gate and the loader: paste `/home/ubuntu/prompts/aws-native/prompts/mongo-atlas-gate.md`. With `MONGODB_ATLAS_URI` unset, `make tp-atlas-scope-check DB=ow_tp_billing_demo` fails with exit 2 before any connection, and Devin explains from the script why. `make tp-recon-selftest` shows the faithful copy passing and the three planted defects failing with their check ids. Then the fixture path: `make tp-u2-load` twice (pass 1 upserts 25,001 customers, pass 2 matches 25,001 and modifies 0), `make tp-u2-recon` (28 checks, 26 pass, 2 fail on the customer collection) and `make tp-u2-parity` (`/customer` differs for the tenant with attributes).
3. The fix: Devin reads the recon report, finds the loader coercing `attributes[].value`, keeps the value verbatim, reruns the loader and the recon, and opens a pull request. Say nothing about the cause before it does.
4. Session 3, the readiness check: Devin reads the harness, lists the secrets by name and the gate sequence a live run follows (scope check, two loader passes, `recon.py run --mode live`, `tp-validate-recon`), and states that a fixture result is never merge evidence.
5. Close on the recon table and the scope-check output.

## Expected state after

| Check | Expected |
|---|---|
| `make tp-atlas-scope-check DB=...` without the URI | `FAIL`, exit 2, no connection attempted |
| `make tp-recon-selftest` | faithful copy PASS, three planted defects FAIL |
| `make tp-u2-load` second pass | `25001 matched, 0 modified` |
| `make tp-u2-recon` after the fix | 28 checks PASS in local mode; `merge_evidence: false` because it ran against the fixture |
| Pull request | open against the run-prep branch and left open for the presenter |

## Reset

```bash
make tp-mongodb-reset                                         # drops the fallback databases
make tp-mongodb-reset TARGET=atlas DB=ow_tp_billing_<timestamp> RESEED=1   # once Atlas exists
```

Then delete the run's Atlas user with the command in `migration/billing/README.md` and serve the billing service with `BILLING_BACKEND=oracle` again. A new run starts from `main` with `make tp-run-branch TRACK=mongodb`.

## Fallback

- Docker Hub answers `429`: pull `mirror.gcr.io/library/mongo:7` and tag it `mongo:7`.
- Oracle Free takes longer than 3 minutes to open: `make oracle-billing-up` prints the healthcheck; wait for `DATABASE IS READY TO USE`.
- Atlas becomes available during the demo: set `MONGODB_ATLAS_URI` in the session, rerun the scope check, and run the loader and the live recon. Only then does `merge_evidence` turn true.

## Talk track

The gate comes first and it refuses before it connects: Devin cannot write to Atlas with a principal that holds more than one database. Then a loader that is safe to run twice, and a recon that says pass or fail per check. The fixture result shows the method; a live result with the same output is the evidence.

## Evidence from the recorded sessions

| Item | Where |
|---|---|
| Plan session, MongoDB, Fusion | https://partner-workshops.devinenterprise.com/sessions/5b01fbf33ade48908b565d74bbabbd27 |
| Gate and loader session, with the pull request | https://partner-workshops.devinenterprise.com/sessions/9e56cebaf84040ba9f1ed6affdbc05ab |
| Readiness session | https://partner-workshops.devinenterprise.com/sessions/910ac7c80059469284ff63afdd4a87fa |
| U2 fixture pull request | https://github.com/Cognition-Partner-Workshops/otterworks/pull/1808 |
| Measured numbers | `docs/mongodb-billing/viewonly/READINESS.md` on the run-prep branch |
| Sidebar as the MongoDB persona | `evidence/devin/viewonly-sidebar-mongodb-3-sessions.png` |

## Rerun log

| Date | Who | Session | What the runbook had not said |
|---|---|---|---|
| 2026-10-05 | MongoDB persona | `5b01bf3`, `9e56ceba`, `910ac7c8` | The scope check must fail closed without the URI (it used to skip); fixed in the harness and written above. |
| 2026-10-05 | MongoDB persona, gate proof, second run | `d4665ccb` | Both gates held in 3 min 21 s with no Atlas connection and no file change. The session VM had no `uv` and installed it under `~/.local/bin`; Preflight now lists it. The session also read `recon.py` closely: `row_diff_threshold` in `tolerances.json` is never read (row counts are compared exactly in code) and the date and string tolerances sit under a key the code does not look at. A human decides whether to change those two gate files; Fallback says so. |

# UNT-11: Delivery handoff (eight migrations-page mappings + wf_SFX_AUDIT_DAILY)

Scope: the five SFX_AUDIT mappings, the daily audit workflow, and SFX_CONTENT `m_SFX_LOGIN_EVENT`,
`m_SFX_ROLE_GRANT`, `m_SFX_TEAM_MEMBER`. Billing and the other five SFX_CONTENT mappings
(`act3-workflow`) are not ours; their control rows, targets and the content branch (#2682) are untouched.
Nothing here retires PowerCenter, changes production scheduling or claims cutover.

Base: `devin/sfx-d1110-unt10-control-certify` @ `6b7bc8476` (accepted UNT-10). Ancestry: contains
`origin/demo-snowflake-dw-exit` @ `a48ea0e29` and harness `devin/sfx-d1110-act3-harness` @ `3347010b7`.
This commit adds only this document. No implementation changed after UNT-10, so no evidence is re-run and
no control row is re-marked. No Task DAG executed or redeployed.

## Nine-asset evidence index

Full matrix and raw QIDs: `UNT10.md`. Bundles: UNT-10 `8342b607…` and addendum `d8aa04a8…` (ticket resources).

| # | Asset | Accepted ticket @ impl | Oracle / dbt run1 / run2 | Dups | Control (UNT-11 readback) |
|---|---|---|---|---|---|
| 1 | SFX_AUDIT.m_SFX_STG_AUDIT_EVENT | UNT-3 @ 210fcda2a | 480 / 480 / 480 | 0 | VERIFIED, migrations-page |
| 2 | SFX_AUDIT.m_SFX_AUDIT_EVENT | UNT-3 @ 210fcda2a | 480 / 480 / 480 | 0 | VERIFIED, migrations-page |
| 3 | SFX_AUDIT.m_SFX_AUDIT_DAILY_SUMMARY | UNT-4 @ f0da29cb2 (live b64d903a3) | 118 / 118 / 118 | 0 | VERIFIED, migrations-page |
| 4 | SFX_AUDIT.m_SFX_AUDIT_EVENT_ARCHIVE | UNT-4 @ f0da29cb2 (standalone fixtures 8 / 11) | 0 / 0 / 0 | 0 | VERIFIED, migrations-page |
| 5 | SFX_AUDIT.m_SFX_SECURITY_ALERT | UNT-5 @ 2116dd9d9 (live b3a5ddc31) | 61 (+3 rejects) / 61 / 61 | 0 | VERIFIED, migrations-page |
| 6 | SFX_CONTENT.m_SFX_LOGIN_EVENT | UNT-6 @ ed22934c7 | 412 / 412 / 412 | 0 | VERIFIED, migrations-page |
| 7 | SFX_CONTENT.m_SFX_ROLE_GRANT | UNT-7 @ f0b4b995d | 149 / 149 / 149 | 0 | VERIFIED, migrations-page |
| 8 | SFX_CONTENT.m_SFX_TEAM_MEMBER | UNT-8 @ 2bcd80e28 | 126 / 126 / 126 | 0 | VERIFIED, migrations-page |
| 9 | wf_SFX_AUDIT_DAILY (Task DAG, no control row) | UNT-9 @ 39d817a38 | graph b35af49a-b056-4d33-b71a-b49a63520076, run 1794358031749: START + 4 children SUCCEEDED, run once | n/a | all 5 tasks suspended, no schedule |

## UNT-11 final read-only readback (2026-11-11)

| Capture | QID | Result |
|---|---|---|
| control `SELECT * … MAPPINGS` | 01c85456-030d-1e81-0035-065b001d332e | SHA256 `d6c325fc216f3e89c7c3eec46302c3754334a15b0ed4fd9c2f4a70c393e5d6d5` = accepted UNT-10 post/repeat; 20 rows; diff vs UNT-10 post: 0 keys changed, act3 rows unchanged; no `held: compute budget` reason |
| `parity licence` (Migrations view) | ops session | migrations-page total=8 VERIFIED=8 AMBER=0 PENDING=0; act3-workflow 12/12 VERIFIED (not ours) |
| SHOW TASKS | 01c85456-030d-1e5d-0035-065b001d2316 | 5 `SFX_D1110_PC_AUDIT_*` tasks, all `suspended`, `SCHEDULE` null, no archive task |
| TASK_HISTORY (PC_AUDIT) | 01c85456-030d-1e5e-0035-065b001ca3be | exactly 5 rows, all graph b35af49a…, run 1794358031749, SUCCEEDED; no other run |

## Proof limits carried forward

- Parity is on captured typed, unique event input, `EVENT_ID`-ordered sequence allocation, single writer.
  Not certified: malformed/duplicate event input, summary `NULL EVENT_TS`, alternate order, archive tuple
  collisions, another writer's independent sequence state.
- Legacy summary replay correction: summary and archive intentionally make reruns idempotent. The legacy
  runner appends on rerun; second-run legacy equality is not claimed (first-load parity + dbt run1 = run2).
- Security alert: within-route duplicate `ALERT_ID` fails closed by design (not runner parity);
  malformed/untyped input and account-wide no-foreign-writes are unproved.
- Archive and team-member stay disabled in the canonical PowerCenter workflow (archive because
  `wf_SFX_AUDIT_DAILY` disables it); their proof is standalone. TEAM_MEMBER is incremental MERGE; only
  ROLE_GRANT rebuilds.

## Repeatable migration (scoped, from `warehouse/`)

Per mapping, follow the owning UNT doc (UNT5–UNT9.md, EVIDENCE.md for UNT-3/4): dbt build with
`--select` limited to that mapping's models, twice on unchanged input, then the parity comparison against
the PowerCenter runner output in `PC_BEFORE`. Mark only with the shared command and the owner guard:
`python -m parity mark --folder <FOLDER> --mapping <MAPPING> --owner migrations-page --pr-url <PR>`
(it reads the gitignored evidence JSON and updates one row only if FOLDER+MAPPING and owner match). Never use the default owner, global setup/seed/load
or all-folder Make targets. Read-only checks:

```sh
.venv/bin/python -m parity.evidence_unt10 readback --label <label>
.venv/bin/python -m parity.evidence_unt10 diff --against <earlier-label> --label <label>
.venv/bin/python -m parity licence
```

## Rollback / recovery

- Code: revert this branch's merge commit on `demo-snowflake-dw-exit` with `git revert -m 1 <merge>` (no force-push,
  no history rewrite, `main` untouched).
- Control rows: restore only the eight migrations-page rows from `pre/control.json` in the UNT-10 bundle with
  a MERGE keyed on FOLDER+MAPPING and guarded by `OWNER_EFFORT='migrations-page'`. Never touch the twelve
  act3-workflow rows. Requires separate approval.
- Targets: `PC_AUDIT.*` and `PC_CONTENT.{LOGIN_EVENT,ROLE_GRANT,TEAM_MEMBER}` only. Event/summary disable
  full refresh; any drop/rebuild needs separate approval. PowerCenter stays the system of record (not retired).
- Tasks: stay suspended with no schedule; do not `EXECUTE TASK` or resume. `teardown.py` is run-wide and is not
  a recovery step for this scope.

## CI and SAST on PR #2739

Changes after UNT-10 are CI/test only. `sqlglot==28.0.0` was added to `warehouse/snowflake/requirements.txt`.
`fetch-depth: 0` was added for the `sfx-snowflake` job. Two history and Unicode-version tests now skip only when their
prerequisite is unavailable. No model, macro or mark code changed, so the accepted evidence still applies.

- Passing: `sfx-snowflake (3.10)`, `sfx-snowflake (3.11)`, `sfx-teradata`, `informatica-runner`, `api-flow-tests`,
  `migration-job`, `deps`, `detect-changes`, `incident-chart-sync`.
- Failing (shared, pre-existing, identical on harness PR #2677): `parity` fails because the pinned `psycopg-binary==3.2.9`
  has no cp314 wheel. `equivalence` fails because `asyncpg 0.29.0` does not compile on Python 3.14. Neither job tests this scope's code.
  The fix belongs to the owners of those workflows.
- SonarQube: no SonarQube/SAST check runs on PRs into `demo-**`. `sonarqube-banking.yml` covers `security/ingest/**`.
  `sast-auto-remediate.yml` runs only on PRs against `main`. A local scan used the same SonarQube Community image and
  scanner as `sonarqube-banking.yml` over the 217 changed paths. Gate OK, but no conditions were configured. 0 hotspots, 0 bugs.
  It found 7 `python:S2245` (non-crypto PRNG) in the deterministic synthetic fixture generator
  `warehouse/snowflake/fixtures/make_fixture.py`, which are not a security exposure. No SQL analyzer ran.

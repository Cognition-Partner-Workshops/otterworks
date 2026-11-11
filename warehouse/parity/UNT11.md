# UNT-11: Delivery handoff (eight migrations-page mappings + wf_SFX_AUDIT_DAILY)

Scope: the five SFX_AUDIT mappings, the daily audit workflow, and SFX_CONTENT `m_SFX_LOGIN_EVENT`,
`m_SFX_ROLE_GRANT`, `m_SFX_TEAM_MEMBER`. Billing and the other five SFX_CONTENT mappings
(`act3-workflow`) are not ours; their control rows, targets and the content branch (#2682) are untouched.
Nothing here retires PowerCenter, changes production scheduling or claims cutover.

Base: `devin/sfx-d1110-unt10-control-certify` @ `6b7bc8476` (accepted UNT-10). Ancestry: contains
`origin/demo-snowflake-dw-exit` @ `a48ea0e29` and harness `devin/sfx-d1110-act3-harness` @ `3347010b7`.
Post-UNT-10 changes are delivery documentation and CI/test dependency/provenance fixes only.
No model, macro or mark code changed; accepted live evidence was not re-run and no control row was
re-marked. No Task DAG executed or redeployed. Every PR remains open for human review; nothing is
merged. Delivery means this open PR plus its evidence, not cutover or approval of outstanding findings.

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
| `parity licence` (supporting CLI readback, not display proof) | ops session | migrations-page total=8 VERIFIED=8 AMBER=0 PENDING=0; act3-workflow 12/12 VERIFIED (not ours) |
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

## Migrations page display

The intended display is the Devin Migrations board **Plan** view, board
`board-b5c65f5504044b0e897f9a3abb6b5c6a`. Display capture is **BLOCKED**: the VM browser
redirects to `/auth/login` and no webapp credentials are available. Login-wall evidence:
`/home/ubuntu/screenshots/ss_5f88df79.png`. The board tag `held: compute budget` has **0 tickets**
per the `devin_board_manage get` readback. This board result is distinct from the Snowflake control table.
The paired control readback is QID `01c85456-030d-1e81-0035-065b001d332e`, SHA256
`d6c325fc216f3e89c7c3eec46302c3754334a15b0ed4fd9c2f4a70c393e5d6d5` above.
CLI licence output is retained only as supporting readback, not proof of the intended display.

## CI on PR #2739

`sqlglot==28.0.0` is installed from `warehouse/snowflake/requirements.txt`.
The `sfx-snowflake` job checks out full history and explicitly fetches
`devin/sfx-d1110-act3-content` into `refs/remotes/origin/devin/sfx-d1110-act3-content`.
The sibling-ref assertion fails if unavailable; it does not skip.

The committed macro is provenance-bound to **Unicode 13.0.0**, Python 3.10's `unicodedata`.
The matrix interpreter remains the default. On the 3.11 leg, regeneration runs under Python 3.10 via
`UNT8_UNICODE_PYTHON`, verifies the interpreter's Unicode version, and asserts byte-equality against
the committed macro. Missing or incompatible interpreters fail; neither provenance test skips.
Local full parity: Python 3.10 `301 passed, 3 skipped in 5.64s`; Python 3.11 with the pinned
interpreter `301 passed, 3 skipped in 5.07s`. The three skips concern absent local oracle artifacts.

**Provenance erratum:** `UNT8.md:62` says "14.0.0 in this environment", but the committed macro
header and bytes are Unicode **13.0.0**. Its sole file-history commit is `c10fd98a0`; the macro is
unchanged at this handoff HEAD. This matches the `UNT9.md:49` erratum. `UNT8.md` is not edited.

Implementation/test head `c83db7f58f0f07f18583eb92c914ad1e04ff5ce0`, settled:
**9 passed / 2 failed / 0 pending / 18 skipped**. CI checks, including all skipped service jobs:

| Check | Conclusion | Run ID | Job ID |
|---|---|---|---|
| sfx-snowflake (3.10) | success | 42944580215 | 130274243403 |
| sfx-snowflake (3.11) | success | 42944580215 | 130274243902 |
| api-flow-tests | success | 42944580215 | 130274243737 |
| detect-changes | success | 42944580215 | 130274184751 |
| incident-chart-sync | success | 42944580215 | 130274184694 |
| sfx-teradata | success | 42944580215 | 130274184647 |
| informatica-runner | success | 42944580215 | 130274184614 |
| migration-job | success | 42944580215 | 130274184342 |
| deps | success | 42944580137 | 130274184318 |
| parity | failure | 42944580130 | 130274184354 |
| equivalence | failure | 42944580134 | 130274183889 |
| workbench | skipped | 42944580215 | 130274246388 |
| notification-service | skipped | 42944580215 | 130274246341 |
| admin-dashboard | skipped | 42944580215 | 130274246095 |
| auth-service | skipped | 42944580215 | 130274246093 |
| search-service | skipped | 42944580215 | 130274246077 |
| analytics-service | skipped | 42944580215 | 130274246072 |
| api-gateway | skipped | 42944580215 | 130274246037 |
| web-app | skipped | 42944580215 | 130274246033 |
| demo-platform-terraform | skipped | 42944580215 | 130274246012 |
| demo-platform | skipped | 42944580215 | 130274245980 |
| legacy-portal | skipped | 42944580215 | 130274245927 |
| file-service | skipped | 42944580215 | 130274245901 |
| collab-service | skipped | 42944580215 | 130274245833 |
| report-service | skipped | 42944580215 | 130274245786 |
| document-service | skipped | 42944580215 | 130274245708 |
| admin-service | skipped | 42944580215 | 130274245672 |
| infrastructure | skipped | 42944580215 | 130274245385 |
| audit-service | skipped | 42944580215 | 130274245360 |

Documentation-commit CI is recorded below after completion; final-head raw checks and logs are
included in `unt11_ci` in the delivery archive.

## Known shared failures (not waived and not skipped)

Parity's verbatim error line:
```text
cause: Because psycopg-binary{implementation_name != 'pypy'}==3.2.9 has no wheels with a matching Python ABI tag (e.g., `cp314`) and psycopg[binary]==3.2.9 depends on psycopg-binary{implementation_name != 'pypy'}==3.2.9, we can conclude that psycopg[binary]==3.2.9 cannot be used.
```

Equivalence's verbatim error line (asyncpg 0.29.0):
```text
asyncpg/pgproto/pgproto.c:41809:27: error: too few arguments to function ‘_PyLong_AsByteArray’; expected 6, have 5
```
The logs identify asyncpg `(0.29.0)` and `/usr/include/python3.14`. Although
`equivalence-gate.yml` declares Python 3.12, the pipx/Poetry/uv toolchain resolved to Python 3.14;
parity also resolved to Python 3.14. These are failed dependency/environment steps, not successful
executions of this scope's tests. The shared workflows are intentionally untouched, per the user.

The same error lines are present on all four compared heads:

| Head | Parity run / job | Equivalence run / job |
|---|---|---|
| before `308443e94` | 42942474517 / 130267318604 | 42942474571 / 130267318927 |
| after `c83db7f58` | 42944580130 / 130274184354 | 42944580134 / 130274183889 |
| harness #2677 latest head `3347010b7` | 42902120034 / 130130521564 | 42902120250 / 130130522601 |
| unrelated `devin/sfx-d1110-spark-file_object_binary_extract` @ `97d5c61ab` | 42930668532 / 130228293370 | 42930668554 / 130228293777 |

## SAST coverage and limits

No SonarQube/SAST check ran on this PR. The local SonarQube Community scan over the 217 changed
paths returned gate `OK`, but the gate had **NO conditions** and **no SQL analyzer ran**.
This is **not a security pass**. It reported 0 hotspots, 0 bugs, and 7 `python:S2245` findings in
the deterministic synthetic fixture generator `warehouse/snowflake/fixtures/make_fixture.py`;
these non-cryptographic PRNG uses were assessed as not a security exposure. Raw evidence is retained.

Two existing Devin scans both use profile `csprof-d4f3a4d67cc54ba08cae928d5450c8f2` and were
judged at commit `19392116` (= main):

- Native Devin security scan `scan-4e8c92da906a45c7b74a5b3ac8d6401f`: **15 findings**,
  https://partner-workshops.devinenterprise.com/code-scan/4e8c92da906a45c7b74a5b3ac8d6401f
- SonarQube CSV ingestion scan `scan-092144f6d8594a8cb61baff0fad640b4`: **187 findings**,
  https://partner-workshops.devinenterprise.com/code-scan/092144f6d8594a8cb61baff0fad640b4

That commit precedes all `warehouse/` files (`git ls-tree -r --name-only 19392116 warehouse`
returns no paths). No finding references `warehouse/**`; neither scan covers these paths.
Executed `git diff --stat 19392116 HEAD -- warehouse` at `c83db7f58`; its summary was:
```text
342 files changed, 50688 insertions(+)
```
The full stat is retained in the delivery evidence. A rescan at the PR head is pending approval
and **has not been run**.

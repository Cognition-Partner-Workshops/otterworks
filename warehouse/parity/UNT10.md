# UNT-10: MIGRATION_CONTROL certification (eight migrations-page rows)

Control: `SFX_D1110_AFTER.MIGRATION_CONTROL.MAPPINGS`. 20 rows, 20 distinct FOLDER+MAPPING keys, 8 `migrations-page` / 12 `act3-workflow`.
No dbt build, PC_BEFORE capture, setup/seed or Task execution was run here. The values come only from accepted evidence bundles, each checked against its pinned SHA256.

## Certification matrix

| FOLDER.MAPPING | Accepted ticket @ impl commit | Bundle SHA256 (prefix) | Evidence file | Oracle (first load) | dbt run1 / run2 | Dups | Status |
|---|---|---|---|---|---|---|---|
| SFX_AUDIT.m_SFX_STG_AUDIT_EVENT | UNT-3 @ 210fcda2a | 5bcacf1f55dc | unt3/m_SFX_STG_AUDIT_EVENT/replay.json | 480 | 480 / 480 | 0 | VERIFIED |
| SFX_AUDIT.m_SFX_AUDIT_EVENT | UNT-3 @ 210fcda2a | 5bcacf1f55dc | unt3/m_SFX_AUDIT_EVENT/replay.json | 480 | 480 / 480 | 0 | VERIFIED |
| SFX_AUDIT.m_SFX_AUDIT_DAILY_SUMMARY | UNT-4 @ f0da29cb2 | 58ecf795d1ef | unt4/m_SFX_AUDIT_DAILY_SUMMARY/replay.json | 118 | 118 / 118 | 0 | VERIFIED |
| SFX_AUDIT.m_SFX_AUDIT_EVENT_ARCHIVE | UNT-4 @ f0da29cb2 | 58ecf795d1ef | unt4/m_SFX_AUDIT_EVENT_ARCHIVE/replay.json (+ unt4/fixture standalone) | 0 | 0 / 0 | 0 | VERIFIED |
| SFX_AUDIT.m_SFX_SECURITY_ALERT | UNT-5 executed/collector b3a5ddc31 (run1 built at 8e04db3c); delivered 2116dd9d9, no implementation diff | 9693f01958ed | production/comparison.json | 61 (3 rejects) | 61 / 61 | 0 | VERIFIED |
| SFX_CONTENT.m_SFX_LOGIN_EVENT | UNT-6 @ ed22934c7 | e939134a3f73 | production/comparison.json | 412 | 412 / 412 | 0 | VERIFIED |
| SFX_CONTENT.m_SFX_ROLE_GRANT | UNT-7 @ f0b4b995d | 6851d0dfe632 | production/comparison_attempts/52134f52.../comparison.json | 149 | 149 / 149 | 0 | VERIFIED |
| SFX_CONTENT.m_SFX_TEAM_MEMBER | UNT-8 @ 2bcd80e28 | 3cf8385ea759 | unt8/production/comparison/{parity1,parity2,dbt_replay}.json | 126 | 126 / 126 | 0 | VERIFIED |
| wf_SFX_AUDIT_DAILY (workflow, no row) | UNT-9 @ 39d817a38 | 07da14bc8b7f / addendum 2f6cbe2f2fc7 | UNT9.md | graph b35af49a-b056-4d33-b71a-b49a63520076, run 1794358031749, root + 4 children SUCCEEDED | not re-run | n/a | certified by Task DAG history |

Every comparison is a full typed multiset: `equal`, with no only_before/only_after rows and no duplicate keys. `rowcount_match` and `keyed_hash_match` come from the first-load oracle-vs-dbt1 and oracle-vs-dbt2 comparisons. `rerun_duplicates` is the duplicate-key count after run2 plus the count in run1-vs-run2. `PARITY_QUERY_TAG` stores the bundle SHA and file SHA prefixes. `PR_URL` is #2738.

Proof boundaries carried forward unchanged:
- Typed frozen inputs only.
- Duplicate-input fixtures fail closed and are not claimed as parity.
- Unicode and malformed cases are bounded to the accepted fixtures.
- Summary: first-load legacy parity plus the approved idempotent replay correction (d-summary-replay). The legacy second run appends; exact legacy rerun parity is not claimed.
- Archive and team member stay disabled in the canonical workflow. Their standalone evidence is their own and is not inherited from the workflow.
- Only ROLE_GRANT rebuilds the table on each run (truncate-and-load semantics); its object identity is not preserved. TEAM_MEMBER uses incremental MERGE (Update-else-Insert, no truncate), preserving unmentioned rows and target identity; see UNT8.md.
- ROLE_GRANT's original production/comparison.json (passed=false, a false intervening-write signal) is superseded by the read-only retry, per UNT7.md.

## Live control evidence (QIDs)

| Step | QID | Control SHA256 | Result |
|---|---|---|---|
| pre readback | 01c85440-030d-1e7f-0035-065b001bbade | 36035640ebee71b8... (= UNT-9 post) | 8 PENDING, 12 VERIFIED, no `held: compute budget` reason |
| mark run 1 (8 MERGEs) | 01c85441-030d-1e7f-0035-065b001bbae6, -1e61-...cc246, -1e73-...cd1ee, -1e82-...d51d2, -1e73-...cd1f2, -1e7a-...c92e6, -1e7a-...c92ea, -1e5e-...ca2ba | | each `cursor.rowcount == 1` |
| post readback | 01c85441-030d-1e6e-0035-065b001dc20a | d6c325fc216f3e89... | 8 PENDING to VERIFIED; AMBER_REASON null to null; the 12 act3 rows are byte-identical |
| mark run 2 (8 MERGEs) | 01c85441-030d-1e73-...cd1f6 through 01c85442-030d-1e5d-...d21ea (history/writes.json) | | each `cursor.rowcount == 1` |
| repeat readback | 01c85442-030d-2128-0035-065b001b4e9a | d6c325fc216f3e89... | no keys changed (VERIFIED_AT kept) |
| SHOW TASKS (read-only) | 01c85442-030d-1e5d-0035-065b001d21f6 | | all 5 SFX_D1110_PC_AUDIT_* suspended, no schedule |

Query history for the window shows only the 16 MERGEs above as non-read statements. ROWS_PRODUCED=20 is observed only, not a proven scanned-row count. The affected-row proof is ACCOUNT_USAGE ROWS_UPDATED=1 / ROWS_INSERTED=0 / ROWS_DELETED=0 and RESULT_SCAN "number of rows updated"=1 for each of the 16 MERGEs, alongside the per-key row-hash diff and original rowcount==1 guard.

## Addendum (Fusion re-verification, read-only, 2026-11-11)

**HISTORICAL:** the previous worker performed the two mark runs and pre/post/repeat
readbacks listed above. The MERGE QIDs below identify those historical writes, not
new writes. The historical Task DAG run is 1794358031749, graph
`b35af49a-b056-4d33-b71a-b49a63520076`.

**NEW:** `parity.evidence_unt10_addendum` issued only guarded SELECT/SHOW statements.
No mapping rebuild, re-mark, task execution or predecessor recapture was done.
Raw captures are in ignored `warehouse/parity/out/evidence/unt10_addendum/`.

| New capture | QID | Result |
|---|---|---|
| control readback | 01c85449-030d-1e76-0035-065b001db10a | SHA256 `d6c325fc216f3e89c7c3eec46302c3754334a15b0ed4fd9c2f4a70c393e5d6d5` matches; 20 distinct keys, 8 migrations-page VERIFIED / 12 act3-workflow |
| boundary lookup | 01c85449-030d-1e5e-0035-065b001ca30e | pre start/end 01:04:33.121000/01:04:33.307000 UTC; repeat 01:06:07.279000/01:06:07.665000 UTC |
| query history | 01c85449-030d-1e6e-0035-065b001ddca2 | window 2026-11-11 01:04:32.121000–01:06:08.665000 UTC; 43 successful statements, END_TIME >= START_TIME; no other non-read touching MIGRATION_CONTROL |
| affected rows | 01c85449-030d-1e76-0035-065b001db10e | all 16: updated=1, inserted=0, deleted=0; all 16 RESULT_SCAN captures independently report updated=1 |
| SHOW TASKS | 01c8544a-030d-1e5e-0035-065b001ca31a | exactly five suspended, all schedules null, no archive task |
| TASK_HISTORY | 01c8544a-030d-1e63-0035-065b001d71c2 | START, STG_AUDIT_EVENT, SECURITY_ALERT, AUDIT_EVENT, AUDIT_DAILY_SUMMARY all SUCCEEDED for the historical graph run |

History is ACCOUNT_USAGE, bounded by the readback timestamps with one-second
margins, without a 10k-row cap. Full QUERY_TEXT, QUERY_TAG, START_TIME, END_TIME,
ROWS_PRODUCED and each capture's own QID are retained in JSON. Each historical
MERGE below passed: `ON t.FOLDER=s.FOLDER AND t.MAPPING=s.MAPPING`,
`WHEN MATCHED AND t.OWNER_EFFORT=s.OWNER_EFFORT`, and no WHEN NOT MATCHED/INSERT/DELETE.
The folder/mapping literals below and owner literal `migrations-page` appear in
every corresponding QUERY_TEXT (client-side binding rendered literals).

| Historical MERGE QID | Folder literal | Mapping literal | Guards |
|---|---|---|---|
| 01c85441-030d-1e7f-0035-065b001bbae6 | SFX_AUDIT | m_SFX_STG_AUDIT_EVENT | PASS |
| 01c85441-030d-1e61-0035-065b001cc246 | SFX_AUDIT | m_SFX_AUDIT_EVENT | PASS |
| 01c85441-030d-1e73-0035-065b001cd1ee | SFX_AUDIT | m_SFX_AUDIT_EVENT_ARCHIVE | PASS |
| 01c85441-030d-1e82-0035-065b001d51d2 | SFX_AUDIT | m_SFX_AUDIT_DAILY_SUMMARY | PASS |
| 01c85441-030d-1e73-0035-065b001cd1f2 | SFX_AUDIT | m_SFX_SECURITY_ALERT | PASS |
| 01c85441-030d-1e7a-0035-065b001c92e6 | SFX_CONTENT | m_SFX_LOGIN_EVENT | PASS |
| 01c85441-030d-1e7a-0035-065b001c92ea | SFX_CONTENT | m_SFX_ROLE_GRANT | PASS |
| 01c85441-030d-1e5e-0035-065b001ca2ba | SFX_CONTENT | m_SFX_TEAM_MEMBER | PASS |
| 01c85441-030d-1e73-0035-065b001cd1f6 | SFX_AUDIT | m_SFX_STG_AUDIT_EVENT | PASS |
| 01c85441-030d-21f3-0035-065b001c4662 | SFX_AUDIT | m_SFX_AUDIT_EVENT | PASS |
| 01c85441-030d-1e7d-0035-065b001cb282 | SFX_AUDIT | m_SFX_AUDIT_EVENT_ARCHIVE | PASS |
| 01c85441-030d-1e75-0035-065b001d90ee | SFX_AUDIT | m_SFX_AUDIT_DAILY_SUMMARY | PASS |
| 01c85441-030d-1e76-0035-065b001db08e | SFX_AUDIT | m_SFX_SECURITY_ALERT | PASS |
| 01c85442-030d-1e5e-0035-065b001ca2c2 | SFX_CONTENT | m_SFX_LOGIN_EVENT | PASS |
| 01c85442-030d-2214-0035-065b001c56aa | SFX_CONTENT | m_SFX_ROLE_GRANT | PASS |
| 01c85442-030d-1e5d-0035-065b001d21ea | SFX_CONTENT | m_SFX_TEAM_MEMBER | PASS |

### Predecessor provenance and standalone proof boundaries

Git confirms b3a5ddc31 is an ancestor of delivered 2116dd9d9. Their diff is only
`warehouse/parity/UNT5.md` (67 insertions); security-alert models, macros,
unt5 fixtures/analysis and `parity/mappings/sfx_audit.yml` have no diff.
UNT5.md records production run1 built at 8e04db3c, collected post hoc at
b3a5ddc31 after collector fixes; subsequent live steps executed at b3a5ddc31.
Thus delivered 2116dd9d9 is not claimed as the live-execution commit.

There is no UNT4.md: EVIDENCE.md's UNT-4 section names live candidate b64d903a3.
The diff to f0da29cb2 is only EVIDENCE.md and offline tests (165 insertions),
not model implementation. UNT6.md names live 9956fea7 and a document-only
follow-up; git confirms the diff to ed22934c7 changes only UNT6.md.
UNT9.md records its own workflow/DAG execution and collector fixes, not a
new execution of the predecessor captures.

- Archive nonempty/history/date-boundary proof: [UNT-4 bundle](https://partner-workshops.devinenterprise.com/attachments/a8fbc9fb-d04b-49ed-abec-7b668aa0b8a6/UNT-4-evidence.tar.gz),
  [index](https://partner-workshops.devinenterprise.com/attachments/ef72628f-f042-4228-8755-1d6d46ed0d9b/UNT-4_evidence_index.json).
  Paths `unt4/fixture/{empty,history}/replay.json`,
  `unt4/fixture/{empty,history}/runner/initial_state.json`, and
  `unt4/fixture/{empty,history}/runner/runner{1,2}/target.json` are generated by
  evidence_unt4.py. Models are
  `warehouse/dbt/models/pc/audit/unt4_fixture/pc_audit__unt4_fixture_archive_{history,empty}.sql`.
  EVIDENCE.md describes 13 events around the strict UTC cutoff (one second
  before/exactly at/after), NULLs and string cases; history starts with IDs 7–9
  and sequence 10, empty with sequence 1. These standalone fixtures, not the
  empty production archive comparison, cover nonempty/history behavior.
- Standalone TEAM_MEMBER proof: [UNT-8 bundle](https://partner-workshops.devinenterprise.com/attachments/3871dc0a-a9d3-4fb0-9540-517f7fb307bf/bundle.tar.gz),
  [index](https://partner-workshops.devinenterprise.com/attachments/c0860c99-7531-4ef6-b753-1410c5c8ca7f/evidence_index.json).
  `unt8/production/comparison/{parity1,parity2,dbt_replay}.json` is the accepted
  standalone production proof (126 rows), not inherited workflow coverage.
  UNT8.md describes standalone oracle/session and production/seeded/dup_key
  captures, with duplicate fixtures deliberately failing closed, not value parity.

Original attachment bundles (including UNT-10 bundle SHA256
`8342b607ba6d31a45ededef39340c0bc677d970fd357faf42ff0fc9874dc3148`)
are not downloadable from this VM (HTTP 401), so their member hashes were not
re-verified here; only the new captures are hashed. Paths above are documented
or source-defined references, not a new inspection of original archive members.
The initial bundle-check statement describes the historical worker's certification.

Read-only reproduction (requires an absent output directory to preserve evidence):

```sh
cd warehouse
.venv/bin/python -m parity.evidence_unt10_addendum
```

## Reproduce

```
cd warehouse
.venv/bin/python -m parity.evidence_unt10 stage --bundles <dir with unt3..unt8 bundles>
.venv/bin/python -m parity.evidence_unt10 readback --label pre
make -C .. sfx-pc-mark MAPPING=<mapping> OWNER=migrations-page PR_URL=https://github.com/Cognition-Partner-Workshops/otterworks/pull/2738
.venv/bin/python -m parity.evidence_unt10 readback --label post
.venv/bin/python -m parity.evidence_unt10 diff --against pre --label post
```

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
| SFX_AUDIT.m_SFX_SECURITY_ALERT | UNT-5 @ b3a5ddc31 | 9693f01958ed | production/comparison.json | 61 (3 rejects) | 61 / 61 | 0 | VERIFIED |
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
- Role grant and team member rebuild the table on each run (truncate-and-load semantics); object identity is not preserved.
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

Query history for the window shows only the 16 MERGEs above as non-read statements. INFORMATION_SCHEMA reports ROWS_PRODUCED=20 for each MERGE, which appears to be the scanned target rows. The authoritative scope proof is the per-key row-hash diff together with the rowcount==1 guard.

## Reproduce

```
cd warehouse
.venv/bin/python -m parity.evidence_unt10 stage --bundles <dir with unt3..unt8 bundles>
.venv/bin/python -m parity.evidence_unt10 readback --label pre
make -C .. sfx-pc-mark MAPPING=<mapping> OWNER=migrations-page PR_URL=https://github.com/Cognition-Partner-Workshops/otterworks/pull/2738
.venv/bin/python -m parity.evidence_unt10 readback --label post
.venv/bin/python -m parity.evidence_unt10 diff --against pre --label post
```

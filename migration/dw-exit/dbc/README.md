# DBC owner-approved query-log contract

The owner accepts Snowflake query-log semantics for the six DBC compatibility
views. `decisions.json` records the approved missing fields: `AMPCPUTime`,
`TotalIOCount`, `ClientID` and `ProcID`. These must be NULL on the converted side.
Query-log `CollectTimeStamp` and TABLESV `LastAccessTimeStamp` may differ.
QRYLOGOBJECTS may omit only source rows satisfying `UsageType=EXECUTE` AND
`ObjectType` in M/P (810 fixture rows). TABLESV may omit only source M/P catalog
rows (10 fixture rows). No target rows are filtered.
`owner_decisions.missing_fields` compares complete row multisets after removing
only those fields and source rows, preserving multiplicity and every other column. The generic
`apply_deviation` gate promotes a raw mismatch only when that full comparison
passes and the DBC evidence gate passes. Raw legacy metrics remain on the board.
Empty matching relations pass; out-of-scope missing/extra rows, reordered columns, non-NULL
unavailable metrics and changes to any retained field fail closed.

StatementGroup is explicitly NOT approved. The two query-log views remain red;
the other four qualify as approved deviations, not green:

- `DBC_QRYLOG` / `QRYLOGV`: statement group still differs outside the approval.
- `DBC_QRYLOGOBJECTS` / `QRYLOGOBJECTSV`: EXECUTE rows and M/P attribution are
  absent from the ACCESS_HISTORY read/write arrays (810 fewer rows).
- `DBC_TABLESV` / `TABLESV`: M/P catalog objects are absent (10 fewer rows), and
  last-access timestamps differ under the read/write-only access contract.

Only statement group remains a residual difference; it is compared exactly.
The separately labelled mapped-column ladder is diagnostic only and does not
promote full-object parity. ACCOUNT_USAGE is synthesized from the same local
DBQL inputs; live Snowflake grants, latency, QUERY_TAG/AppID attribution and
error-code semantics remain unverified. This decision does not authorize
physical deletion, migration-status changes or cutover.

## sfg1120 local reproduction and retirement audit

Ported from `origin/devin/sfx1119-integration`, with only the DBC helper subset.
The original BEFORE commit `a48ea0e29c31ca5a5445e22074a99a0549d7d6b3` exists
in this repository and remains pinned. Inventory read counts and last-read times
match that snapshot. Current CSV read counts still match inventory (two for each
base relation, one for each view), all by `svc_report_recon` on 2026-08-12,
solely setup `COUNT(*)` sweeps in the inclusive 2026-08-12..2026-11-09 window.
Current object-log/table last-read times differ from inventory's older snapshot:
QRYLOGOBJECTS / QRYLOGOBJECTSV 06:03:54 versus 06:03:31;
TABLESV / DBC_TABLESV 06:05:35 versus 06:05:30. This does not establish deletion safety.

The supplied `RUN_TOKEN=sfg1120` is rejected by `warehouse/run_config.py`:
`ValueError: RUN_TOKEN must be a lowercase sfx-prefixed identifier`.
Without broadening shared configuration, the local stack and generated board use
`RUN_TOKEN=sfx-sfg1120`, namespace `sfx-sfg1120-before`. Provenance stays on branch
`devin/sfg1120-integration`; Snowflake always stays red with reason
`Snowflake login down; no connection attempted (sfg1120)`.

```sh
uv venv warehouse/.venv -p 3.11
uv pip install -p warehouse/.venv/bin/python -r warehouse/requirements.txt -r migration/dw-exit/requirements.txt
export RUN_TOKEN=sfx-sfg1120
eval "$(python3 warehouse/run_config.py env)"
export NS="$RUN_BEFORE_NAMESPACE"
make -o warehouse/.venv/.requirements sfx-teradata-up ROWS_PER_TABLE=200
make -o sfx-teradata-up -o warehouse/.venv/.billing-requirements sfx-manifest-board BOARD_ROWS=200 PARITY_TARGET=duckdb
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
```

The omitted dependency stamps above only skip pip installation, already completed
using uv; the documented board target generates both board.json and its DBC README section.

### Observed differences and countercheck

Raw query-log hash delta is 16160 (8080 old / 8080 new). Missing ProcID,
ClientID, CPU, IO and the one-second CollectTimeStamp shift are approved.
StatementGroup differs on 4770 rows: ETL→INSERT 3510, UTILITY→INSERT 450,
ETL→EXEC 450, ETL→CALL 360. The source generator assigns operational groups
(`warehouse/teradata/dbql/generate.py:198-200`); the shipped compatibility SQL
uses QUERY_TYPE for both StatementType and StatementGroup. Query 111000000000
is a sample UTILITY→INSERT. An independent diagnostic removing StatementGroup
in addition to the approved fields yields exact multiset parity, disproving other
retained-field differences in this fixture; this diagnostic is not an approval.
ErrorCode and AppID match exactly, including ErrorCode in the full owner gate.

Object usage loses exactly 810 M/P EXECUTE rows. Catalog loses six M and four P
rows; all retained AccessCount values match. Five retained catalog timestamps
differ for zero-access objects: the generator uses 2026-07-01 17:30:00 while the
replacement LEFT JOIN returns NULL (sample AUDIT_EVENT_ARCHIVE, AccessCount=0
on both sides). This yields full catalog hash delta 20: ten missing rows plus
five changed rows on each side. These are all within the approved scope.

The emulator cross-check remains separate: query logs have 8272 versus 8080 CSV
rows, object logs 20767 versus 20443; catalog relations match at 111. The daily
chain reaches `Runner.execute`'s `finally: self.log_statement(...)`, which writes
new 900000000000000000+ query IDs via a separate connection (`bteq/runner.py:194-228`).
These runtime rows are not filtered to turn drift green. They occur outside the
fixture window. Local CSV parity is not emulator or live Snowflake parity.

### External DBC references

`callers()` checks services and etl (no hits); a separate warehouse/scripts scan
is preserved as `retire_evidence.tooling_references`. Scripts have no hits.
Warehouse runtime callers must be migrated before any physical removal:

- `warehouse/exit/reads.py:61`: reads QRYLOGV for observed consumer activity.
- `warehouse/teradata/dbql/consumer_reads.bteq:3-10`: reads QRYLOGV, groups by
  username/AppID/ClientID; the shipped replacement has a raw ClientID deviation.
- `warehouse/teradata/bteq/runner.py:62-73,218-228`: creates/query-IDs and writes
  DBC_QRYLOG and DBC_QRYLOGOBJECTS, creates their views.
- `warehouse/teradata/dbql/schema.sql:44-53`: three alias view dependencies;
  `dbql/load.py` loads fixtures using dynamic DBC schema/table identifiers.
- `warehouse/teradata/tests/test_dbql.py:46-101` and
  `tests/test_read_logging.py:57-85`: catalog/query-log regression consumers.
- `warehouse/snowflake/tests/test_scope_f.py:324-337`: synthetic DBC.DBQLogTbl
  conversion input (not one of these six); warehouse READMEs document the views.

Tooling references do not veto the owner-approved local semantic comparison, but
they prevent interpreting its result as a blanket retirement authorization.

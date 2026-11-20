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

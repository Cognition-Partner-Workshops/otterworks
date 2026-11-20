# DBC owner-approved query-log contract

The owner accepts Snowflake query-log semantics for the six DBC compatibility
views. `decisions.json` records the approved missing fields: `AMPCPUTime`,
`TotalIOCount` and `ClientID`. These must be NULL on the converted side.
`owner_decisions.missing_fields` compares complete row multisets after removing
only those fields, preserving multiplicity and every other column. The generic
`apply_deviation` gate promotes a raw mismatch only when that full comparison
passes and the DBC evidence gate passes. Raw legacy metrics remain on the board.
Empty matching relations pass; missing/extra rows, reordered columns, non-NULL
unavailable metrics and changes to any retained field fail closed.

The existing local fixture contains additional differences, so the six views
remain red rather than misrepresenting this approval:

- `DBC_QRYLOG` / `QRYLOGV`: `ProcID`, collection timestamp and statement group
  differ in addition to the approved CPU/IO/client-id fields.
- `DBC_QRYLOGOBJECTS` / `QRYLOGOBJECTSV`: EXECUTE rows and M/P attribution are
  absent from the ACCESS_HISTORY read/write arrays (810 fewer rows).
- `DBC_TABLESV` / `TABLESV`: M/P catalog objects are absent (10 fewer rows), and
  last-access timestamps differ under the read/write-only access contract.

These are residual differences, not an open question about CPU/IO/client-id.
The separately labelled mapped-column ladder is diagnostic only and does not
promote full-object parity. ACCOUNT_USAGE is synthesized from the same local
DBQL inputs; live Snowflake grants, latency, QUERY_TAG/AppID attribution and
error-code semantics remain unverified. This decision does not authorize
physical deletion, migration-status changes or cutover.

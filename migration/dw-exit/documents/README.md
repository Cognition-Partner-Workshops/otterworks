# sfg1120 Documents warehouse exit

[Shared integration board](../board/README.md) · [machine-readable board](../board/board.json) · [full measurements](evidence.json)

**Snowflake: red.** No login or object creation was attempted. Local parity is not cutover approval.

The board covers exactly the 59 documents manifest objects and includes raw per-relation counts, column profiles, keyed row hashes, and samples of all differing fixture keys. Approved version deviations retain raw mismatches and include an independently calculated owner-decision scope proof. The documents share fixture matched the legacy output; a separate multi-match regression proves the approved highest-privilege rule. Storage remains amber pending finance confirmation of invoice impact.

## Reproduce through the shared generator

Run from the repository root on a fresh local fixture. Ensure the PostgreSQL and Spark images named in the Compose files are available locally.

```sh
export RUN_TOKEN=sfx-sfg1120
eval "$(python3 warehouse/run_config.py env)"
export NS="$RUN_BEFORE_NAMESPACE"
proof=migration/dw-exit/documents
snapshot=migration/dw-exit/.runs/documents-$RUN_TOKEN-pre-pc
make sfx-informatica-up NS="$NS" INFA_DB=teradata ROWS_PER_TABLE=200 BUSINESS_DATE=20261109
warehouse/.venv/bin/python "$proof/prove_local.py" --pre-pc "$snapshot" --capture-pre-pc
make sfx-informatica-run NS="$NS" INFA_DB=teradata \
  INFA_WORKFLOWS=SFX_CONTENT:wf_SFX_CONTENT_DAILY \
  MAPPINGS=m_SFX_STG_DOCUMENT,m_SFX_DOCUMENT,m_SFX_DOC_SHARE
make sfx-spark-up NS="$NS" ROWS_PER_TABLE=200
warehouse/.venv/bin/python -c 'import json; print("\n".join(x["name"] for x in json.load(open("migration/dw-exit/documents/spark_jobs.json"))))' |
while read -r job; do make sfx-spark-run NS="$NS" JOB="$job" || exit; done
warehouse/.venv/bin/python "$proof/replay_spark.py" \
  --dates 2026-11-19 2026-11-20 --output "$proof/spark-replay.json"
warehouse/.venv/bin/python migration/dw-exit/parity/object_board.py
warehouse/.venv/bin/python -m pytest -q migration/dw-exit/tests
```

- Do not recapture over the frozen post-BTEQ/pre-PowerCenter state. Proof requires all three session logs after that capture and reads the actual post-session targets. It separately runs the dbt session queries, session procedure bodies and mapping publishers in DuckDB.
- The TPT rewrite uses the original delimited inputs and checks empty strings versus numeric/date NULLs. Snowflake needs the external landing stage and file format in `05_tpt.sql`; those were not provisioned.
- `OPS."10_STORAGE_MONTHLY"` reads the deduplicated documents table, updates shared billing tables, and returns the storage summary. The local check replays the legacy script in a rolled-back transaction to compare at the storage boundary, before later billing steps mutate invoices. In the combined migration, schedule the billing side effects once, not both this procedure and the existing billing storage slice.
- The Spark proof uses actual local Spark outputs, including the audit JDBC output. The binary job replays two dates and compares the entire retained partition history on the date-inclusive key.

## Retirement and integration holds

| Manifest retire candidate | Pinned DBQL finding | Cutover action |
|---|---|---|
| `SFX_DOCUMENTS.SEARCH_INDEX_LOG` | No relation reads | Keep while the search-history view remains. |
| `SFX_DOCUMENTS.STG_SEARCH_INDEX_LOG` | Finance reconciliation count, QueryID `111000000071` pinned / `111000000072` in checkout | Keep until the finance caller is addressed. |
| `documents_search_index_log` | No independent job event; writes the staging relation that finance reads | Retain the load until the finance caller is addressed; preserve the Spark landing feed. |
| `SFX_DOCUMENTS.V_SEARCH_HISTORY` | No direct reads | No drop approval; confirm the view and table can be removed together. |

The pinned assessment spans 2026-08-12 through 2026-11-09. The board links to DBQL query and object-use rows; retire classifications are not authorizations to drop. The separate [owner decisions](decisions.json) preserve approved semantics and the pending storage check.

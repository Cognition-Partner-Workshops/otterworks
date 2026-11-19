# Documents subject area

Conversions for the 59 documents manifest objects. Parity results and click-through links are in
[`../board/README.md`](../board/README.md#documents-parity-provenance); they are produced by
[`../parity/local_documents.py`](../parity/local_documents.py) against the local DuckDB target only.
The Snowflake leg is not run: `SFX_D1110_ROLE` has no access to `SFX_1119`.

| File | Replaces |
|---|---|
| `00_tables.sql` | `warehouse/teradata/ddl/documents/00_tables.sql` (18 tables; the two search-index tables are retire candidates) |
| `05_stage.sql` | `warehouse/teradata/load/tpt/documents_*.tpt`, after `RAW_DOCUMENTS.LOAD_DOCUMENTS` |
| `10_load.sql` | BTEQ `01`–`05` |
| `20_routines.sql` | macro `M_STORAGE_TOTALS`, BTEQ `10_storage_monthly` export |
| `30_views.sql` | `V_DOCUMENT_VERSIONS`, `V_WORKSPACE_STORAGE` |
| `warehouse/dbt/models/pc/content/` | PowerCenter `m_SFX_STG_DOCUMENT`, `m_SFX_DOCUMENT`, `m_SFX_DOC_SHARE` and their sessions |
| `warehouse/dbt/models/spark/`, `warehouse/snowpark/` | Spark jobs |

## Open owner decisions

These objects stay red whatever the measurement says. Nothing in the conversion resolves them.

1. **SET-table dedupe** on `STORAGE_USAGE_DAILY`: Teradata drops exact-duplicate rows, the conversion keeps them.
   Affects the table, `05_load_sessions`, `M_STORAGE_TOTALS` and `10_storage_monthly` (billing storage charges).
2. **Tie-break** for equal latest `VERSION_TS` in `02_current_versions`. Affects `DOC_VERSION` and both views.
3. **Role precedence** for users with several grants in `m_SFX_DOC_SHARE` ("Use First Value"). The fixture has one
   grant per user, so the measured match does not settle it.

## Retire candidates

Confirmed against the query log in `warehouse/teradata/dbql`; evidence is on each board row under `retire`.
Nothing is dropped by this change.

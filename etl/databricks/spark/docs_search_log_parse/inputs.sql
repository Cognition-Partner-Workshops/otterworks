/* run=dbx-d1111 act=spark step=inputs consumer=docs_search_log_parse */
/* run_token=dbx-d1111 expires=2026-11-24
   Landing SEARCH_INDEX_LOG: SEARCH_INDEX_LOG_ID, DOCUMENT_ID, EVENT_AT, RAW_LINE, STATUS.
   Live SFX_DOCUMENTS.SEARCH_INDEX_LOG (warehouse/teradata/ddl/documents/00_tables.sql) has
   index_log_id, document_id, indexed_ts, status_cd, token_count. The core table is empty;
   stg_search_index_log has 2000 rows with the same columns. Neither carries RAW_LINE, the
   only column the job parses (regex action=(\w+)), so no defensible adapter exists.
   Mappable columns are listed for reference; RAW_LINE is NOT derived.
     SEARCH_INDEX_LOG_ID <- index_log_id, DOCUMENT_ID <- document_id,
     EVENT_AT <- indexed_ts, STATUS <- status_cd, RAW_LINE <- (none)
   Gap check (first failing result): */
SELECT 'search_index_log' AS live_table,
  (SELECT count(*) FROM cpw.dbx_d1111_before.documents__search_index_log) AS live_rows,
  (SELECT count(*) FROM cpw.dbx_d1111_before.documents__stg_search_index_log) AS stg_rows,
  (SELECT count(*) FROM cpw.information_schema.columns
    WHERE table_catalog='cpw' AND table_schema='dbx_d1111_before'
      AND table_name IN ('documents__search_index_log','documents__stg_search_index_log')
      AND lower(column_name) IN ('raw_line')) AS required_cols_found

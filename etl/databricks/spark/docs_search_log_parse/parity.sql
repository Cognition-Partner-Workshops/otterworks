/* run=dbx-d1111 act=spark step=parity consumer=docs_search_log_parse */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for docs_search_log_parse. Not executed: the job is RED (no live input, see README); neither table exists.
-- Same canonical formatting as the green jobs: concat_ws('|', coalesce(cast(col AS STRING),'<NULL>') ...).
SELECT 'before' AS side, count(*) AS row_count,
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(SEARCH_INDEX_LOG_ID AS STRING),'<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING),'<NULL>'), coalesce(cast(EVENT_AT AS STRING),'<NULL>'), coalesce(cast(RAW_LINE AS STRING),'<NULL>'), coalesce(cast(STATUS AS STRING),'<NULL>'), coalesce(cast(PARSED_ACTION AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash
FROM cpw.dbx_d1111_parity.documents__spark_docs_search_log_parse__spark_before
UNION ALL
SELECT 'after', count(*),
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(SEARCH_INDEX_LOG_ID AS STRING),'<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING),'<NULL>'), coalesce(cast(EVENT_AT AS STRING),'<NULL>'), coalesce(cast(RAW_LINE AS STRING),'<NULL>'), coalesce(cast(STATUS AS STRING),'<NULL>'), coalesce(cast(PARSED_ACTION AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0)))
FROM cpw.dbx_d1111_after.documents__spark_docs_search_log_parse;

/* run=dbx-d1111 act=spark step=parity consumer=docs_search_log_parse */
SELECT 'before_not_in_after' AS direction, * FROM (
  SELECT SEARCH_INDEX_LOG_ID, DOCUMENT_ID, EVENT_AT, RAW_LINE, STATUS, PARSED_ACTION FROM cpw.dbx_d1111_parity.documents__spark_docs_search_log_parse__spark_before
  EXCEPT ALL
  SELECT SEARCH_INDEX_LOG_ID, DOCUMENT_ID, EVENT_AT, RAW_LINE, STATUS, PARSED_ACTION FROM cpw.dbx_d1111_after.documents__spark_docs_search_log_parse) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=docs_search_log_parse */
SELECT 'after_not_in_before' AS direction, * FROM (
  SELECT SEARCH_INDEX_LOG_ID, DOCUMENT_ID, EVENT_AT, RAW_LINE, STATUS, PARSED_ACTION FROM cpw.dbx_d1111_after.documents__spark_docs_search_log_parse
  EXCEPT ALL
  SELECT SEARCH_INDEX_LOG_ID, DOCUMENT_ID, EVENT_AT, RAW_LINE, STATUS, PARSED_ACTION FROM cpw.dbx_d1111_parity.documents__spark_docs_search_log_parse__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=docs_search_log_parse */
DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_docs_search_log_parse;

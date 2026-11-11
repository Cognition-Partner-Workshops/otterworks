/* run=dbx-d1111 act=spark step=parity consumer=docs_tag_normalize */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for docs_tag_normalize. Each statement is sent on its own via the Statement Execution API;
-- the leading comment of each block is the required statement prefix.
-- Canonical row: concat_ws('|', coalesce(cast(col AS STRING),'<NULL>') ...) over
-- DOC_TAG_ID, DOCUMENT_ID, TAG, NORMALIZED_TAG; hash summed as DECIMAL(38,0) (no float rounding).
SELECT 'before' AS side, count(*) AS row_count,
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(DOC_TAG_ID AS STRING),'<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING),'<NULL>'), coalesce(cast(TAG AS STRING),'<NULL>'), coalesce(cast(NORMALIZED_TAG AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash
FROM cpw.dbx_d1111_parity.documents__spark_docs_tag_normalize__spark_before
UNION ALL
SELECT 'after', count(*),
  sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(DOC_TAG_ID AS STRING),'<NULL>'), coalesce(cast(DOCUMENT_ID AS STRING),'<NULL>'), coalesce(cast(TAG AS STRING),'<NULL>'), coalesce(cast(NORMALIZED_TAG AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0)))
FROM cpw.dbx_d1111_after.documents__spark_docs_tag_normalize;

/* run=dbx-d1111 act=spark step=parity consumer=docs_tag_normalize */
SELECT 'before_not_in_after' AS direction, * FROM (
  SELECT DOC_TAG_ID, DOCUMENT_ID, TAG, NORMALIZED_TAG FROM cpw.dbx_d1111_parity.documents__spark_docs_tag_normalize__spark_before
  EXCEPT ALL
  SELECT DOC_TAG_ID, DOCUMENT_ID, TAG, NORMALIZED_TAG FROM cpw.dbx_d1111_after.documents__spark_docs_tag_normalize) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=docs_tag_normalize */
SELECT 'after_not_in_before' AS direction, * FROM (
  SELECT DOC_TAG_ID, DOCUMENT_ID, TAG, NORMALIZED_TAG FROM cpw.dbx_d1111_after.documents__spark_docs_tag_normalize
  EXCEPT ALL
  SELECT DOC_TAG_ID, DOCUMENT_ID, TAG, NORMALIZED_TAG FROM cpw.dbx_d1111_parity.documents__spark_docs_tag_normalize__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=docs_tag_normalize */
DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_docs_tag_normalize;

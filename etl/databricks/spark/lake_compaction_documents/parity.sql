-- run_token=dbx-d1111 expires=2026-11-24
-- Parity of cpw.dbx_d1111_after.documents__spark_lake_compaction_documents against the original Spark output loaded into cpw.dbx_d1111_parity.documents__spark_lake_compaction_documents__spark_before.
-- Canonical row: concat_ws('|', DOCUMENT_ID, OWNER_USER_ID, FOLDER_ID, TITLE, date_format(CREATED_AT,'yyyy-MM-dd HH:mm:ss'), STATUS, EXPORT_BUCKET)
/* run=dbx-d1111 act=spark step=parity consumer=lake_compaction_documents */
SELECT 'spark_before' AS side, count(*) AS row_count,
       sum(CAST(conv(substr(md5(concat_ws('|', DOCUMENT_ID, OWNER_USER_ID, FOLDER_ID, TITLE, date_format(CREATED_AT,'yyyy-MM-dd HH:mm:ss'), STATUS, EXPORT_BUCKET)),1,15),16,10) AS DECIMAL(38,0))) AS row_hash
FROM cpw.dbx_d1111_parity.documents__spark_lake_compaction_documents__spark_before
UNION ALL
SELECT 'after', count(*),
       sum(CAST(conv(substr(md5(concat_ws('|', DOCUMENT_ID, OWNER_USER_ID, FOLDER_ID, TITLE, date_format(CREATED_AT,'yyyy-MM-dd HH:mm:ss'), STATUS, EXPORT_BUCKET)),1,15),16,10) AS DECIMAL(38,0)))
FROM cpw.dbx_d1111_after.documents__spark_lake_compaction_documents;

/* run=dbx-d1111 act=spark step=parity consumer=lake_compaction_documents */
(SELECT 'only_spark_before' AS side, * FROM (SELECT * FROM cpw.dbx_d1111_parity.documents__spark_lake_compaction_documents__spark_before EXCEPT ALL SELECT * FROM cpw.dbx_d1111_after.documents__spark_lake_compaction_documents) LIMIT 20)
UNION ALL
(SELECT 'only_after', * FROM (SELECT * FROM cpw.dbx_d1111_after.documents__spark_lake_compaction_documents EXCEPT ALL SELECT * FROM cpw.dbx_d1111_parity.documents__spark_lake_compaction_documents__spark_before) LIMIT 20);

/* run=dbx-d1111 act=spark step=idempotence consumer=lake_compaction_documents */
SELECT version, operation, operationMetrics.numOutputRows AS num_output_rows,
       operationMetrics.numFiles AS num_files
FROM (DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_lake_compaction_documents) ORDER BY version DESC LIMIT 4;

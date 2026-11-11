-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for docs_storage_by_owner: Spark before-result (cpw.dbx_d1111_parity.documents__spark_docs_storage_by_owner__spark_before) vs migrated target (cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner).
-- Each rung is introduced by "-- rung: <name>"; every statement is sent with the prefix
-- /* run=dbx-d1111 act=spark step=parity consumer=docs_storage_by_owner */ (step=idempotence after the second run).
-- Canonical columns: USER_ID, EMAIL, FILE_COUNT, SIZE_BYTES; canonical formatting coalesce(cast(col AS STRING),'~').

-- rung: count
SELECT (SELECT count(*) FROM cpw.dbx_d1111_parity.documents__spark_docs_storage_by_owner__spark_before) AS before_rows, (SELECT count(*) FROM cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner) AS after_rows;

-- rung: hash
SELECT (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_ID AS STRING),'~'), coalesce(cast(EMAIL AS STRING),'~'), coalesce(cast(FILE_COUNT AS STRING),'~'), coalesce(cast(SIZE_BYTES AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_parity.documents__spark_docs_storage_by_owner__spark_before) AS before_hash, (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_ID AS STRING),'~'), coalesce(cast(EMAIL AS STRING),'~'), coalesce(cast(FILE_COUNT AS STRING),'~'), coalesce(cast(SIZE_BYTES AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner) AS after_hash;

-- rung: before_except_after
SELECT * FROM (SELECT USER_ID, EMAIL, FILE_COUNT, SIZE_BYTES FROM cpw.dbx_d1111_parity.documents__spark_docs_storage_by_owner__spark_before EXCEPT ALL SELECT USER_ID, EMAIL, FILE_COUNT, SIZE_BYTES FROM cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner) LIMIT 20;

-- rung: after_except_before
SELECT * FROM (SELECT USER_ID, EMAIL, FILE_COUNT, SIZE_BYTES FROM cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner EXCEPT ALL SELECT USER_ID, EMAIL, FILE_COUNT, SIZE_BYTES FROM cpw.dbx_d1111_parity.documents__spark_docs_storage_by_owner__spark_before) LIMIT 20;

-- rung: history
SELECT version, operation, operationMetrics FROM (DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_docs_storage_by_owner) ORDER BY version DESC LIMIT 2;

/* run=dbx-d1111 act=spark step=parity consumer=docs_folder_legacy_report */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for docs_folder_legacy_report: Spark before-result (cpw.dbx_d1111_parity.documents__spark_docs_folder_legacy_report__spark_before) vs migrated target (cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report).
-- Each rung is introduced by "-- rung: <name>"; every statement is sent with the prefix
-- /* run=dbx-d1111 act=spark step=parity consumer=docs_folder_legacy_report */ (step=idempotence after the second run).
-- Canonical columns: FOLDER_ID, FOLDER_NAME, PARENT_FOLDER_ID, DOCUMENTS; canonical formatting coalesce(cast(col AS STRING),'~').

-- rung: count
SELECT (SELECT count(*) FROM cpw.dbx_d1111_parity.documents__spark_docs_folder_legacy_report__spark_before) AS before_rows, (SELECT count(*) FROM cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report) AS after_rows;

/* run=dbx-d1111 act=spark step=parity consumer=docs_folder_legacy_report */
-- rung: hash
SELECT (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(FOLDER_ID AS STRING),'~'), coalesce(cast(FOLDER_NAME AS STRING),'~'), coalesce(cast(PARENT_FOLDER_ID AS STRING),'~'), coalesce(cast(DOCUMENTS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_parity.documents__spark_docs_folder_legacy_report__spark_before) AS before_hash, (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(FOLDER_ID AS STRING),'~'), coalesce(cast(FOLDER_NAME AS STRING),'~'), coalesce(cast(PARENT_FOLDER_ID AS STRING),'~'), coalesce(cast(DOCUMENTS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report) AS after_hash;

/* run=dbx-d1111 act=spark step=parity consumer=docs_folder_legacy_report */
-- rung: before_except_after
SELECT * FROM (SELECT FOLDER_ID, FOLDER_NAME, PARENT_FOLDER_ID, DOCUMENTS FROM cpw.dbx_d1111_parity.documents__spark_docs_folder_legacy_report__spark_before EXCEPT ALL SELECT FOLDER_ID, FOLDER_NAME, PARENT_FOLDER_ID, DOCUMENTS FROM cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=docs_folder_legacy_report */
-- rung: after_except_before
SELECT * FROM (SELECT FOLDER_ID, FOLDER_NAME, PARENT_FOLDER_ID, DOCUMENTS FROM cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report EXCEPT ALL SELECT FOLDER_ID, FOLDER_NAME, PARENT_FOLDER_ID, DOCUMENTS FROM cpw.dbx_d1111_parity.documents__spark_docs_folder_legacy_report__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=docs_folder_legacy_report */
-- rung: history
DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_docs_folder_legacy_report LIMIT 2;

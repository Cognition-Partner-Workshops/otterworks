/* run=dbx-d1111 act=spark step=parity consumer=docs_share_activity */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for docs_share_activity: Spark before-result (cpw.dbx_d1111_parity.documents__spark_docs_share_activity__spark_before) vs migrated target (cpw.dbx_d1111_after.documents__spark_docs_share_activity).
-- Each rung is introduced by "-- rung: <name>"; every statement is sent with the prefix
-- /* run=dbx-d1111 act=spark step=parity consumer=docs_share_activity */ (step=idempotence after the second run).
-- Canonical columns: OWNER_USER_ID, PERMISSION, SHARES, RECIPIENTS; canonical formatting coalesce(cast(col AS STRING),'~').

-- rung: count
SELECT (SELECT count(*) FROM cpw.dbx_d1111_parity.documents__spark_docs_share_activity__spark_before) AS before_rows, (SELECT count(*) FROM cpw.dbx_d1111_after.documents__spark_docs_share_activity) AS after_rows;

/* run=dbx-d1111 act=spark step=parity consumer=docs_share_activity */
-- rung: hash
SELECT (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(OWNER_USER_ID AS STRING),'~'), coalesce(cast(PERMISSION AS STRING),'~'), coalesce(cast(SHARES AS STRING),'~'), coalesce(cast(RECIPIENTS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_parity.documents__spark_docs_share_activity__spark_before) AS before_hash, (SELECT sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(OWNER_USER_ID AS STRING),'~'), coalesce(cast(PERMISSION AS STRING),'~'), coalesce(cast(SHARES AS STRING),'~'), coalesce(cast(RECIPIENTS AS STRING),'~'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_after.documents__spark_docs_share_activity) AS after_hash;

/* run=dbx-d1111 act=spark step=parity consumer=docs_share_activity */
-- rung: before_except_after
SELECT * FROM (SELECT OWNER_USER_ID, PERMISSION, SHARES, RECIPIENTS FROM cpw.dbx_d1111_parity.documents__spark_docs_share_activity__spark_before EXCEPT ALL SELECT OWNER_USER_ID, PERMISSION, SHARES, RECIPIENTS FROM cpw.dbx_d1111_after.documents__spark_docs_share_activity) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=docs_share_activity */
-- rung: after_except_before
SELECT * FROM (SELECT OWNER_USER_ID, PERMISSION, SHARES, RECIPIENTS FROM cpw.dbx_d1111_after.documents__spark_docs_share_activity EXCEPT ALL SELECT OWNER_USER_ID, PERMISSION, SHARES, RECIPIENTS FROM cpw.dbx_d1111_parity.documents__spark_docs_share_activity__spark_before) LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=docs_share_activity */
-- rung: history
DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_docs_share_activity LIMIT 2;

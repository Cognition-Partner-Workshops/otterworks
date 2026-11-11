-- run_token=dbx-d1111 expires=2026-11-24
-- Parity of cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach against the original Spark output loaded into cpw.dbx_d1111_parity.documents__spark_doc_share_graph_reach__spark_before.
-- Canonical row: concat_ws('|') of columns cast to STRING (timestamps yyyy-MM-dd HH:mm:ss UTC), NULL as \N.
-- Hash: sum of the first 15 hex digits of md5 as DECIMAL(38,0) (sum of conv() as STRING would round through DOUBLE).

-- count+hash
/* run=dbx-d1111 act=spark step=parity consumer=doc_share_graph_reach */
SELECT b.row_count AS before_rows, a.row_count AS after_rows, b.row_hash AS before_hash, a.row_hash AS after_hash,
       b.row_count = a.row_count AND b.row_hash = a.row_hash AS parity
FROM (SELECT count(*) AS row_count, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_ID AS STRING),'\\N'), coalesce(cast(DISTANCE AS STRING),'\\N'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash FROM cpw.dbx_d1111_parity.documents__spark_doc_share_graph_reach__spark_before) b CROSS JOIN (SELECT count(*) AS row_count, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_ID AS STRING),'\\N'), coalesce(cast(DISTANCE AS STRING),'\\N'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash FROM cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach) a;

-- before-minus-after
/* run=dbx-d1111 act=spark step=parity consumer=doc_share_graph_reach */
SELECT 'before_only' AS side, * FROM (SELECT USER_ID, DISTANCE FROM cpw.dbx_d1111_parity.documents__spark_doc_share_graph_reach__spark_before EXCEPT ALL SELECT USER_ID, DISTANCE FROM cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach) LIMIT 20;

-- after-minus-before
/* run=dbx-d1111 act=spark step=parity consumer=doc_share_graph_reach */
SELECT 'after_only' AS side, * FROM (SELECT USER_ID, DISTANCE FROM cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach EXCEPT ALL SELECT USER_ID, DISTANCE FROM cpw.dbx_d1111_parity.documents__spark_doc_share_graph_reach__spark_before) LIMIT 20;

-- history
/* run=dbx-d1111 act=spark step=idempotence consumer=doc_share_graph_reach */
SELECT version, timestamp, operation, operationMetrics['numOutputRows'] AS num_output_rows, job.jobId AS job_id, job.runId AS run_id
FROM (DESCRIBE HISTORY cpw.dbx_d1111_after.documents__spark_doc_share_graph_reach) ORDER BY version DESC LIMIT 4;

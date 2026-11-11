-- run_token=dbx-d1111 expires=2026-11-24
-- Parity of cpw.dbx_d1111_after.users__spark_team_graph_components against the original Spark output loaded into cpw.dbx_d1111_parity.users__spark_team_graph_components__spark_before.
-- Canonical row: concat_ws('|') of columns cast to STRING (timestamps yyyy-MM-dd HH:mm:ss UTC), NULL as \N.
-- Hash: sum of the first 15 hex digits of md5 as DECIMAL(38,0) (sum of conv() as STRING would round through DOUBLE).

-- count+hash
/* run=dbx-d1111 act=spark step=parity consumer=team_graph_components */
SELECT b.row_count AS before_rows, a.row_count AS after_rows, b.row_hash AS before_hash, a.row_hash AS after_hash,
       b.row_count = a.row_count AND b.row_hash = a.row_hash AS parity
FROM (SELECT count(*) AS row_count, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_ID AS STRING),'\\N'), coalesce(cast(COMPONENT_ID AS STRING),'\\N'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash FROM cpw.dbx_d1111_parity.users__spark_team_graph_components__spark_before) b CROSS JOIN (SELECT count(*) AS row_count, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(USER_ID AS STRING),'\\N'), coalesce(cast(COMPONENT_ID AS STRING),'\\N'))),1,15),16,10) AS DECIMAL(38,0))) AS row_hash FROM cpw.dbx_d1111_after.users__spark_team_graph_components) a;

-- before-minus-after
/* run=dbx-d1111 act=spark step=parity consumer=team_graph_components */
SELECT 'before_only' AS side, * FROM (SELECT USER_ID, COMPONENT_ID FROM cpw.dbx_d1111_parity.users__spark_team_graph_components__spark_before EXCEPT ALL SELECT USER_ID, COMPONENT_ID FROM cpw.dbx_d1111_after.users__spark_team_graph_components) LIMIT 20;

-- after-minus-before
/* run=dbx-d1111 act=spark step=parity consumer=team_graph_components */
SELECT 'after_only' AS side, * FROM (SELECT USER_ID, COMPONENT_ID FROM cpw.dbx_d1111_after.users__spark_team_graph_components EXCEPT ALL SELECT USER_ID, COMPONENT_ID FROM cpw.dbx_d1111_parity.users__spark_team_graph_components__spark_before) LIMIT 20;

-- history
/* run=dbx-d1111 act=spark step=idempotence consumer=team_graph_components */
SELECT version, timestamp, operation, operationMetrics['numOutputRows'] AS num_output_rows, job.jobId AS job_id, job.runId AS run_id
FROM (DESCRIBE HISTORY cpw.dbx_d1111_after.users__spark_team_graph_components) ORDER BY version DESC LIMIT 4;

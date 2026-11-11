/* run=dbx-d1111 act=spark step=parity consumer=security_alert_anomaly */
-- run_token=dbx-d1111 expires=2026-11-24
-- Execute only after a genuine live-adapted original result exists. Never load fixture rows here.
WITH b AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(ALERT_ID AS STRING), '<NULL>'), coalesce(cast(USER_ID AS STRING), '<NULL>'), coalesce(cast(SCORE AS STRING), '<NULL>'), coalesce(cast(Z_SCORE AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_parity.audit__spark_security_alert_anomaly__spark_before),
a AS (SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(ALERT_ID AS STRING), '<NULL>'), coalesce(cast(USER_ID AS STRING), '<NULL>'), coalesce(cast(SCORE AS STRING), '<NULL>'), coalesce(cast(Z_SCORE AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_security_alert_anomaly)
SELECT b.n before_count, a.n after_count, b.h before_hash, a.h after_hash,
       b.n = a.n AND b.h <=> a.h AS parity FROM b CROSS JOIN a;

/* run=dbx-d1111 act=spark step=parity consumer=security_alert_anomaly */
SELECT ALERT_ID, USER_ID, SCORE, Z_SCORE FROM cpw.dbx_d1111_parity.audit__spark_security_alert_anomaly__spark_before EXCEPT ALL SELECT ALERT_ID, USER_ID, SCORE, Z_SCORE FROM cpw.dbx_d1111_after.audit__spark_security_alert_anomaly LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=security_alert_anomaly */
SELECT ALERT_ID, USER_ID, SCORE, Z_SCORE FROM cpw.dbx_d1111_after.audit__spark_security_alert_anomaly EXCEPT ALL SELECT ALERT_ID, USER_ID, SCORE, Z_SCORE FROM cpw.dbx_d1111_parity.audit__spark_security_alert_anomaly__spark_before LIMIT 20;

/* run=dbx-d1111 act=spark step=idempotence consumer=security_alert_anomaly */
-- Record after each of two successful runs; compare count/hash plus operationMetrics.
SELECT count(*) n, sum(cast(conv(substr(md5(concat_ws('|', coalesce(cast(ALERT_ID AS STRING), '<NULL>'), coalesce(cast(USER_ID AS STRING), '<NULL>'), coalesce(cast(SCORE AS STRING), '<NULL>'), coalesce(cast(Z_SCORE AS STRING), '<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) h FROM cpw.dbx_d1111_after.audit__spark_security_alert_anomaly;

/* run=dbx-d1111 act=spark step=idempotence consumer=security_alert_anomaly */
DESCRIBE HISTORY cpw.dbx_d1111_after.audit__spark_security_alert_anomaly LIMIT 2;

/* run=dbx-d1111 act=spark step=parity consumer=billing_usage_append_daily */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for billing_usage_append_daily: Spark output (cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before) vs migrated target (cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily).
-- Canonical: every column CAST AS STRING, NULL -> '<null>', joined by '|'. Order-independent hash.
-- Re-run the count-hash statement with step=idempotence after the second job run.

-- rung: parity-count-hash
SELECT b.n AS before_rows, a.n AS after_rows, b.h AS before_hash, a.h AS after_hash,
  b.n = a.n AND b.h = a.h AS pass
FROM (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(USAGE_ID AS STRING), '<null>'), coalesce(CAST(CUSTOMER_ID AS STRING), '<null>'), coalesce(CAST(USAGE_DATE AS STRING), '<null>'), coalesce(CAST(UNITS AS STRING), '<null>'), coalesce(CAST(AMOUNT AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before) b CROSS JOIN (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(USAGE_ID AS STRING), '<null>'), coalesce(CAST(CUSTOMER_ID AS STRING), '<null>'), coalesce(CAST(USAGE_DATE AS STRING), '<null>'), coalesce(CAST(UNITS AS STRING), '<null>'), coalesce(CAST(AMOUNT AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily) a;

/* run=dbx-d1111 act=spark step=parity consumer=billing_usage_append_daily */
-- rung: parity-diff-before-minus-after
SELECT USAGE_ID, CUSTOMER_ID, USAGE_DATE, UNITS, AMOUNT FROM cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before EXCEPT ALL SELECT USAGE_ID, CUSTOMER_ID, USAGE_DATE, UNITS, AMOUNT FROM cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=billing_usage_append_daily */
-- rung: parity-diff-after-minus-before
SELECT USAGE_ID, CUSTOMER_ID, USAGE_DATE, UNITS, AMOUNT FROM cpw.dbx_d1111_after.billing__spark_billing_usage_append_daily EXCEPT ALL SELECT USAGE_ID, CUSTOMER_ID, USAGE_DATE, UNITS, AMOUNT FROM cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=billing_usage_append_daily */
-- rung: idempotence-spark-before-run2
SELECT r1.n AS spark_run1_rows, r2.n AS spark_run2_rows, r1.h AS run1_hash, r2.h AS run2_hash,
  r1.n = r2.n AND r1.h = r2.h AS pass
FROM (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(USAGE_ID AS STRING), '<null>'), coalesce(CAST(CUSTOMER_ID AS STRING), '<null>'), coalesce(CAST(USAGE_DATE AS STRING), '<null>'), coalesce(CAST(UNITS AS STRING), '<null>'), coalesce(CAST(AMOUNT AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before) r1 CROSS JOIN (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(USAGE_ID AS STRING), '<null>'), coalesce(CAST(CUSTOMER_ID AS STRING), '<null>'), coalesce(CAST(USAGE_DATE AS STRING), '<null>'), coalesce(CAST(UNITS AS STRING), '<null>'), coalesce(CAST(AMOUNT AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_parity.billing__spark_billing_usage_append_daily__spark_before_run2) r2;


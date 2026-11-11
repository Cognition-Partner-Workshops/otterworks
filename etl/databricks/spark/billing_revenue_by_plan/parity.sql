/* run=dbx-d1111 act=spark step=parity consumer=billing_revenue_by_plan */
-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for billing_revenue_by_plan: Spark output (cpw.dbx_d1111_parity.billing__spark_billing_revenue_by_plan__spark_before) vs migrated target (cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan).
-- Canonical: every column CAST AS STRING, NULL -> '<null>', joined by '|'. Order-independent hash.
-- Re-run the count-hash statement with step=idempotence after the second job run.

-- rung: parity-count-hash
SELECT b.n AS before_rows, a.n AS after_rows, b.h AS before_hash, a.h AS after_hash,
  b.n = a.n AND b.h = a.h AS pass
FROM (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(PLAN_ID AS STRING), '<null>'), coalesce(CAST(PLAN_NAME AS STRING), '<null>'), coalesce(CAST(REVENUE AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_parity.billing__spark_billing_revenue_by_plan__spark_before) b CROSS JOIN (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(PLAN_ID AS STRING), '<null>'), coalesce(CAST(PLAN_NAME AS STRING), '<null>'), coalesce(CAST(REVENUE AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan) a;

/* run=dbx-d1111 act=spark step=parity consumer=billing_revenue_by_plan */
-- rung: parity-diff-before-minus-after
SELECT PLAN_ID, PLAN_NAME, REVENUE FROM cpw.dbx_d1111_parity.billing__spark_billing_revenue_by_plan__spark_before EXCEPT ALL SELECT PLAN_ID, PLAN_NAME, REVENUE FROM cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=billing_revenue_by_plan */
-- rung: parity-diff-after-minus-before
SELECT PLAN_ID, PLAN_NAME, REVENUE FROM cpw.dbx_d1111_after.billing__spark_billing_revenue_by_plan EXCEPT ALL SELECT PLAN_ID, PLAN_NAME, REVENUE FROM cpw.dbx_d1111_parity.billing__spark_billing_revenue_by_plan__spark_before LIMIT 20;


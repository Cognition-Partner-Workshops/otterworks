/* run=dbx-d1111 act=spark step=parity consumer=billing_churn_score */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT 'before' AS side, count(*) AS n, sum(cast(conv(substr(md5(concat_ws('|',coalesce(cast(SUBSCRIPTION_ID AS STRING),'<NULL>'), coalesce(cast(CUSTOMER_ID AS STRING),'<NULL>'), coalesce(cast(PLAN_ID AS STRING),'<NULL>'), coalesce(cast(START_DATE AS STRING),'<NULL>'), coalesce(cast(END_DATE AS STRING),'<NULL>'), coalesce(cast(STATUS AS STRING),'<NULL>'), coalesce(cast(CHURN_SCORE AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) AS hash FROM cpw.dbx_d1111_parity.billing__spark_billing_churn_score__spark_before UNION ALL SELECT 'after', count(*), sum(cast(conv(substr(md5(concat_ws('|',coalesce(cast(SUBSCRIPTION_ID AS STRING),'<NULL>'), coalesce(cast(CUSTOMER_ID AS STRING),'<NULL>'), coalesce(cast(PLAN_ID AS STRING),'<NULL>'), coalesce(cast(START_DATE AS STRING),'<NULL>'), coalesce(cast(END_DATE AS STRING),'<NULL>'), coalesce(cast(STATUS AS STRING),'<NULL>'), coalesce(cast(CHURN_SCORE AS STRING),'<NULL>'))),1,15),16,10) AS DECIMAL(38,0))) FROM cpw.dbx_d1111_after.billing__spark_billing_churn_score;

/* run=dbx-d1111 act=spark step=parity consumer=billing_churn_score */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT * FROM (SELECT * FROM cpw.dbx_d1111_parity.billing__spark_billing_churn_score__spark_before EXCEPT ALL SELECT * FROM cpw.dbx_d1111_after.billing__spark_billing_churn_score) LIMIT 20;

/* run=dbx-d1111 act=spark step=parity consumer=billing_churn_score */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT * FROM (SELECT * FROM cpw.dbx_d1111_after.billing__spark_billing_churn_score EXCEPT ALL SELECT * FROM cpw.dbx_d1111_parity.billing__spark_billing_churn_score__spark_before) LIMIT 20;

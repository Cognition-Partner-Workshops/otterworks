/* run=dbx-d1111 act=spark step=inputs consumer=billing_churn_score */
-- run_token=dbx-d1111 expires=2026-11-24
SELECT s.subscription_id AS SUBSCRIPTION_ID, s.customer_id AS CUSTOMER_ID, p.plan_id AS PLAN_ID,
 s.start_dt AS START_DATE, s.end_dt AS END_DATE, s.status_cd AS STATUS
FROM cpw.dbx_d1111_before.billing__subscription s
LEFT JOIN cpw.dbx_d1111_before.billing__plan_catalog p
  ON upper(rtrim(s.plan_code)) = upper(rtrim(p.plan_code));

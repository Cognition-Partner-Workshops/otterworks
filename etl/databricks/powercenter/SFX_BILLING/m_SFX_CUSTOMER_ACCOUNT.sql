/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_CUSTOMER_ACCOUNT */
MERGE INTO cpw.dbx_d1111_after.billing__sfx_customer_account t
USING (
 WITH lookup_snapshot AS (
 SELECT customer_id, row_number() OVER (PARTITION BY customer_id ORDER BY customer_id) AS rn
 FROM cpw.dbx_d1111_after.billing__sfx_customer_account)
 SELECT s.*, l.customer_id AS lkp_id
 FROM cpw.dbx_d1111_after.billing__sfx_stg_customer_account s
 LEFT JOIN lookup_snapshot l ON s.customer_id=l.customer_id AND l.rn=1
) s ON t.customer_id=s.customer_id
WHEN MATCHED AND s.lkp_id IS NOT NULL THEN UPDATE SET t.customer_id=s.customer_id, t.owner_user_id=s.owner_user_id, t.account_name=s.account_name, t.status_cd=s.status_cd, t.currency_cd=s.currency_cd, t.created_dt=s.created_dt, t.account_no=s.account_no
WHEN NOT MATCHED AND s.lkp_id IS NULL THEN INSERT (customer_id, owner_user_id, account_name, status_cd, currency_cd, created_dt, account_no)
VALUES (s.customer_id, s.owner_user_id, s.account_name, s.status_cd, s.currency_cd, s.created_dt, s.account_no);

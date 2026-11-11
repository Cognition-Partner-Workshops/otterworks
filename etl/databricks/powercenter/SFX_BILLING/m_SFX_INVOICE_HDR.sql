/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_INVOICE_HDR */
INSERT INTO cpw.dbx_d1111_after.billing__sfx_invoice_hdr__reject
WITH customer_snapshot AS (
 SELECT customer_id,row_number() OVER (PARTITION BY customer_id ORDER BY customer_id) rn
 FROM cpw.dbx_d1111_after.billing__sfx_customer_account)
SELECT s.*, 3, '${STEP}', '${LOAD_DATE}'
FROM cpw.dbx_d1111_after.billing__sfx_stg_invoice_hdr s
LEFT JOIN customer_snapshot c ON s.customer_id=c.customer_id AND c.rn=1
WHERE NOT coalesce(c.customer_id IS NOT NULL AND s.total_amount IS NOT NULL AND s.invoice_dt IS NOT NULL,false);

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_INVOICE_HDR */
MERGE INTO cpw.dbx_d1111_after.billing__sfx_invoice_hdr t
USING (
 WITH customer_snapshot AS (
 SELECT customer_id,row_number() OVER (PARTITION BY customer_id ORDER BY customer_id) rn
 FROM cpw.dbx_d1111_after.billing__sfx_customer_account),
 invoice_snapshot AS (
 SELECT invoice_id,row_number() OVER (PARTITION BY invoice_id ORDER BY invoice_id) rn
 FROM cpw.dbx_d1111_after.billing__sfx_invoice_hdr)
 SELECT s.*, i.invoice_id AS lkp_id
 FROM cpw.dbx_d1111_after.billing__sfx_stg_invoice_hdr s
 LEFT JOIN customer_snapshot c ON s.customer_id=c.customer_id AND c.rn=1
 LEFT JOIN invoice_snapshot i ON s.invoice_id=i.invoice_id AND i.rn=1
 WHERE coalesce(c.customer_id IS NOT NULL AND s.total_amount IS NOT NULL AND s.invoice_dt IS NOT NULL,false)
) s ON t.invoice_id=s.invoice_id
WHEN MATCHED AND s.lkp_id IS NOT NULL THEN UPDATE SET t.invoice_id=s.invoice_id, t.customer_id=s.customer_id, t.subscription_id=s.subscription_id, t.invoice_dt=s.invoice_dt, t.bill_dt=s.bill_dt, t.period_start_dt=s.period_start_dt, t.currency_cd=s.currency_cd, t.total_amount=s.total_amount, t.invoice_no=s.invoice_no
WHEN NOT MATCHED AND s.lkp_id IS NULL THEN INSERT (invoice_id, customer_id, subscription_id, invoice_dt, bill_dt, period_start_dt, currency_cd, total_amount, invoice_no)
VALUES (s.invoice_id, s.customer_id, s.subscription_id, s.invoice_dt, s.bill_dt, s.period_start_dt, s.currency_cd, s.total_amount, s.invoice_no);

/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_PAYMENT */
MERGE INTO cpw.dbx_d1111_after.billing__sfx_payment t
USING (
 SELECT CAST(CAST(payment_id AS STRING) AS BIGINT) payment_id,
 CAST(CAST(invoice_id AS STRING) AS BIGINT) invoice_id,
 CAST(CAST(customer_id AS STRING) AS BIGINT) customer_id,
 to_date(CAST(payment_dt AS STRING),'yyyy-MM-dd') payment_dt,
 CAST(CAST(amount AS STRING) AS DECIMAL(14,2)) amount,
 upper(ltrim(rtrim(CAST(method_cd AS STRING)))) method_cd
 FROM cpw.dbx_d1111_before.billing__stg_payment
 WHERE coalesce(payment_id IS NOT NULL AND amount IS NOT NULL,false)
) s ON t.payment_id=s.payment_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

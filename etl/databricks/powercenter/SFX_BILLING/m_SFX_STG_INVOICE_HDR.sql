/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_STG_INVOICE_HDR */
INSERT OVERWRITE cpw.dbx_d1111_after.billing__sfx_stg_invoice_hdr
SELECT CAST(CAST(invoice_id AS STRING) AS BIGINT), CAST(CAST(customer_id AS STRING) AS BIGINT),
 CAST(CAST(subscription_id AS STRING) AS BIGINT),
 to_date(CAST(invoice_dt AS STRING),'yyyy-MM-dd'),
 to_date(CAST(bill_dt AS STRING),'yyyy-MM-dd'),
 to_date(CAST(period_start_dt AS STRING),'yyyy-MM-dd'),
 coalesce(upper(ltrim(rtrim(CAST(currency_cd AS STRING)))), '${CURRENCY_DEFAULT}'),
 CAST(CAST(total_amount AS STRING) AS DECIMAL(14,2)),
 upper(ltrim(rtrim(CAST(invoice_number AS STRING))))
FROM cpw.dbx_d1111_before.billing__stg_invoice_hdr;

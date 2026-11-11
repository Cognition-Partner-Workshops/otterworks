/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_INVOICE_LINE */
MERGE INTO cpw.dbx_d1111_after.billing__sfx_invoice_line t
USING (
 SELECT CAST(CAST(invoice_line_id AS STRING) AS BIGINT) invoice_line_id,
 CAST(CAST(invoice_id AS STRING) AS BIGINT) invoice_id,
 CAST(CAST(line_no AS STRING) AS INT) line_no,
 ltrim(rtrim(CAST(description AS STRING))) description,
 CAST(CAST(quantity AS STRING) AS INT) quantity,
 CAST(CAST(unit_price AS STRING) AS DECIMAL(14,2)) unit_price,
 coalesce(CAST(CAST(line_amount AS STRING) AS DECIMAL(14,2)),
 CAST(round(CAST(quantity AS INT)*CAST(unit_price AS DECIMAL(14,2)),2) AS DECIMAL(14,2))) line_amount
 FROM cpw.dbx_d1111_before.billing__stg_invoice_line
 WHERE coalesce(invoice_id IS NOT NULL AND invoice_line_id IS NOT NULL,false)
) s ON t.invoice_line_id=s.invoice_line_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *;

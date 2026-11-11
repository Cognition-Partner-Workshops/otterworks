/* run=dbx-d1111 act=scale step=${STEP} consumer=m_SFX_GL_JOURNAL_LINE */
INSERT INTO cpw.dbx_d1111_after.billing__sfx_gl_journal_line
(journal_no,invoice_id,gl_account_id,posting_dt,debit_amount,credit_amount,currency_cd,line_desc)
REPLACE WHERE journal_no LIKE 'JE-${LOAD_DATE}-%'
WITH lookup_snapshot AS (
 SELECT account_number,gl_account_id,
 row_number() OVER (PARTITION BY account_number ORDER BY account_number) rn
 FROM cpw.dbx_d1111_before.billing__gl_account
), expanded AS (
 SELECT *, CAST(round(total_amount * CAST('${SALES_TAX_RATE}' AS DECIMAL(5,4)) /
 (1 + CAST('${SALES_TAX_RATE}' AS DECIMAL(5,4))),2) AS DECIMAL(14,2)) tax_amount,
 substring(concat('JE-','${LOAD_DATE}','-',coalesce(invoice_no,'')),1,30) journal_no
 FROM cpw.dbx_d1111_after.billing__sfx_stg_invoice_hdr
 WHERE coalesce(total_amount IS NOT NULL AND total_amount <> 0,false)
), branches AS (
 SELECT journal_no,invoice_id,'1200' code,invoice_dt posting_dt,
 total_amount debit_amount,CAST(0 AS DECIMAL(14,2)) credit_amount,currency_cd,
 concat('Accounts receivable ',coalesce(invoice_no,'')) line_desc FROM expanded
 UNION ALL
 SELECT journal_no,invoice_id,'2300',invoice_dt,CAST(0 AS DECIMAL(14,2)),
 CAST(total_amount-tax_amount AS DECIMAL(14,2)),currency_cd,
 concat('Deferred revenue ',coalesce(invoice_no,'')) FROM expanded
 UNION ALL
 SELECT journal_no,invoice_id,'2200',invoice_dt,CAST(0 AS DECIMAL(14,2)),
 tax_amount,currency_cd,concat('Sales tax payable ',coalesce(invoice_no,''))
 FROM expanded WHERE coalesce(tax_amount<>0,false)
)
SELECT b.journal_no,b.invoice_id,l.gl_account_id,b.posting_dt,b.debit_amount,b.credit_amount,
 rtrim(b.currency_cd),substring(b.line_desc,1,120)
FROM branches b LEFT JOIN lookup_snapshot l ON b.code=l.account_number AND l.rn=1;

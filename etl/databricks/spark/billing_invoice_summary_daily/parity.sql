-- run_token=dbx-d1111 expires=2026-11-24
-- Parity for billing_invoice_summary_daily: Spark output (cpw.dbx_d1111_parity.billing__spark_billing_invoice_summary_daily__spark_before) vs migrated target (cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily).
-- Canonical: every column CAST AS STRING, NULL -> '<null>', joined by '|'. Order-independent hash.
-- Re-run the count-hash statement with step=idempotence after the second job run.

-- rung: parity-count-hash
/* run=dbx-d1111 act=spark step=parity consumer=billing_invoice_summary_daily */
SELECT b.n AS before_rows, a.n AS after_rows, b.h AS before_hash, a.h AS after_hash,
  b.n = a.n AND b.h = a.h AS pass
FROM (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(CUSTOMER_ID AS STRING), '<null>'), coalesce(CAST(INVOICE_DATE AS STRING), '<null>'), coalesce(CAST(LINE_COUNT AS STRING), '<null>'), coalesce(CAST(AMOUNT AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_parity.billing__spark_billing_invoice_summary_daily__spark_before) b CROSS JOIN (SELECT count(*) AS n, sum(CAST(conv(substr(md5(concat_ws('|', coalesce(CAST(CUSTOMER_ID AS STRING), '<null>'), coalesce(CAST(INVOICE_DATE AS STRING), '<null>'), coalesce(CAST(LINE_COUNT AS STRING), '<null>'), coalesce(CAST(AMOUNT AS STRING), '<null>'))),1,15),16,10) AS DECIMAL(38,0))) AS h FROM cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily) a;

-- rung: parity-diff-before-minus-after
/* run=dbx-d1111 act=spark step=parity consumer=billing_invoice_summary_daily */
SELECT CUSTOMER_ID, INVOICE_DATE, LINE_COUNT, AMOUNT FROM cpw.dbx_d1111_parity.billing__spark_billing_invoice_summary_daily__spark_before EXCEPT ALL SELECT CUSTOMER_ID, INVOICE_DATE, LINE_COUNT, AMOUNT FROM cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily LIMIT 20;

-- rung: parity-diff-after-minus-before
/* run=dbx-d1111 act=spark step=parity consumer=billing_invoice_summary_daily */
SELECT CUSTOMER_ID, INVOICE_DATE, LINE_COUNT, AMOUNT FROM cpw.dbx_d1111_after.billing__spark_billing_invoice_summary_daily EXCEPT ALL SELECT CUSTOMER_ID, INVOICE_DATE, LINE_COUNT, AMOUNT FROM cpw.dbx_d1111_parity.billing__spark_billing_invoice_summary_daily__spark_before LIMIT 20;


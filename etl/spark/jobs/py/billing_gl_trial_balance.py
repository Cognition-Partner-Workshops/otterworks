from common.runtime import register, save, session

spark = session("billing_gl_trial_balance")
register(spark, "GL_ACCOUNT", "GL_JOURNAL_LINE", "CREDIT_NOTE")
result = spark.sql("""
WITH ledger AS (
    SELECT GL_ACCOUNT_ID, date_format(POSTING_DATE, 'yyyy-MM') PERIOD, CURRENCY_CODE,
           SUM(DEBIT_AMT) DEBITS, SUM(CREDIT_AMT) CREDITS,
           SUM(DEBIT_AMT - CREDIT_AMT) NET
    FROM GL_JOURNAL_LINE
    GROUP BY GL_ACCOUNT_ID, date_format(POSTING_DATE, 'yyyy-MM'), CURRENCY_CODE
), adjustments AS (
    SELECT GL_ACCOUNT_ID, date_format(POSTING_DATE, 'yyyy-MM') PERIOD, CURRENCY_CODE,
           SUM(AMOUNT) CREDIT_NOTE_ADJUSTMENTS
    FROM CREDIT_NOTE
    GROUP BY GL_ACCOUNT_ID, date_format(POSTING_DATE, 'yyyy-MM'), CURRENCY_CODE
), periods AS (
    SELECT GL_ACCOUNT_ID, PERIOD, CURRENCY_CODE FROM ledger
    UNION
    SELECT GL_ACCOUNT_ID, PERIOD, CURRENCY_CODE FROM adjustments
)
SELECT a.GL_ACCOUNT_ID, a.ACCOUNT_CODE, a.ACCOUNT_NAME, a.ACCOUNT_TYPE,
       p.PERIOD, p.CURRENCY_CODE, coalesce(l.DEBITS, 0) DEBITS,
       coalesce(l.CREDITS, 0) CREDITS, coalesce(l.NET, 0) NET,
       coalesce(c.CREDIT_NOTE_ADJUSTMENTS, 0) CREDIT_NOTE_ADJUSTMENTS
FROM periods p JOIN GL_ACCOUNT a ON p.GL_ACCOUNT_ID = a.GL_ACCOUNT_ID
LEFT JOIN ledger l ON p.GL_ACCOUNT_ID = l.GL_ACCOUNT_ID
  AND p.PERIOD = l.PERIOD AND p.CURRENCY_CODE = l.CURRENCY_CODE
LEFT JOIN adjustments c ON p.GL_ACCOUNT_ID = c.GL_ACCOUNT_ID
  AND p.PERIOD = c.PERIOD AND p.CURRENCY_CODE = c.CURRENCY_CODE
""")
save(result, "billing", "billing_gl_trial_balance", "sfx_billing.SPARK_GL_TRIAL_BALANCE")
spark.stop()

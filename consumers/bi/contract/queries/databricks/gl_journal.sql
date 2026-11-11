SELECT EXTRACT(YEAR FROM gl_journal.POSTING_DT) * 100 + EXTRACT(MONTH FROM gl_journal.POSTING_DT) AS LABEL,
  SUM(coalesce(gl_journal.DEBIT_AMOUNT, 0) - coalesce(gl_journal.CREDIT_AMOUNT, 0)) AS AMOUNT
FROM cpw.dbx_d1111_after.billing__gl_journal_line AS gl_journal
LEFT JOIN cpw.dbx_d1111_after.billing__gl_account AS gl_accounts ON gl_journal.GL_ACCOUNT_ID = gl_accounts.GL_ACCOUNT_ID
GROUP BY 1
ORDER BY 1

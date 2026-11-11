package com.otterworks.report.financewarehouse;

import org.springframework.jdbc.core.JdbcTemplate;

public class TeradataFinanceWarehouse implements FinanceWarehouse {
    public static final String UNRECONCILED_SQL =
            "LOCKING ROW FOR ACCESS SEL TOP 25 i.INVOICE_NUMBER, a.ACCOUNT_NUMBER, "
            + "CAST(i.INVOICE_DT AS DATE FORMAT 'YYYY-MM-DD') AS INVOICE_DATE, "
            + "CURRENT_DATE - (i.INVOICE_DT + 30) AS DAYS_OVERDUE, i.TOTAL_AMOUNT, ZEROIFNULL(p.PAID) AS PAID "
            + "FROM SFX_BILLING.INVOICE_HDR i JOIN SFX_BILLING.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID "
            + "LEFT JOIN (SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM SFX_BILLING.PAYMENT GROUP BY INVOICE_ID) p "
            + "ON p.INVOICE_ID = i.INVOICE_ID "
            + "WHERE ZEROIFNULL(p.PAID) < i.TOTAL_AMOUNT AND (i.INVOICE_DT + 30) < CURRENT_DATE - 30 "
            + "AND i.INVOICE_DT >= 1200101 "
            + "AND EXTRACT(YEAR FROM i.INVOICE_DT) * 100 + EXTRACT(MONTH FROM i.INVOICE_DT) = ? "
            + "ORDER BY DAYS_OVERDUE DESC, i.INVOICE_ID";

    public static final String SQL =
            "LOCKING ROW FOR ACCESS "
            + "SEL i.PERIOD_ID, i.INVOICED_TOTAL, p.PAID_TOTAL, g.AR_GL_BALANCE, "
            + "i.INVOICED_TOTAL - p.PAID_TOTAL - g.AR_GL_BALANCE AS VARIANCE "
            + "FROM (SEL CAST(? AS INTEGER) AS PERIOD_ID, ZEROIFNULL(SUM(TOTAL_AMOUNT)) AS INVOICED_TOTAL "
            + "FROM SFX_BILLING.INVOICE_HDR WHERE EXTRACT(YEAR FROM INVOICE_DT) * 100 "
            + "+ EXTRACT(MONTH FROM INVOICE_DT) = ?) i "
            + "CROSS JOIN (SEL ZEROIFNULL(SUM(AMOUNT)) AS PAID_TOTAL FROM SFX_BILLING.PAYMENT "
            + "WHERE EXTRACT(YEAR FROM PAYMENT_DT) * 100 + EXTRACT(MONTH FROM PAYMENT_DT) = ?) p "
            + "CROSS JOIN (SEL ZEROIFNULL(SUM(j.DEBIT_AMOUNT - j.CREDIT_AMOUNT)) AS AR_GL_BALANCE "
            + "FROM SFX_BILLING.GL_JOURNAL_LINE j JOIN SFX_BILLING.GL_ACCOUNT a "
            + "ON a.GL_ACCOUNT_ID = j.GL_ACCOUNT_ID "
            + "WHERE EXTRACT(YEAR FROM j.POSTING_DT) * 100 + EXTRACT(MONTH FROM j.POSTING_DT) = ? "
            + "AND a.ACCOUNT_NUMBER = '1200') g";

    private final JdbcTemplate jdbc;

    public TeradataFinanceWarehouse(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public FinanceReconciliation reconcile(int period) {
        FinanceReconciliation summary = jdbc.queryForObject(SQL, (rs, row) -> new FinanceReconciliation(
                rs.getInt("PERIOD_ID"), rs.getBigDecimal("INVOICED_TOTAL"),
                rs.getBigDecimal("PAID_TOTAL"), rs.getBigDecimal("AR_GL_BALANCE")),
                period, period, period, period);
        return new FinanceReconciliation(summary.period, summary.invoicedTotal, summary.paidTotal,
                summary.arGlBalance, jdbc.query(UNRECONCILED_SQL, (rs, row) -> new UnreconciledInvoice(
                        rs.getString("INVOICE_NUMBER"), rs.getString("ACCOUNT_NUMBER"), rs.getString("INVOICE_DATE"),
                        rs.getInt("DAYS_OVERDUE"), rs.getBigDecimal("TOTAL_AMOUNT"),
                        rs.getBigDecimal("PAID")), period));
    }
}

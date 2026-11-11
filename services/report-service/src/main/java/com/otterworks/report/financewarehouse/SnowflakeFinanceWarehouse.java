package com.otterworks.report.financewarehouse;

import org.springframework.jdbc.core.JdbcTemplate;

public class SnowflakeFinanceWarehouse implements FinanceWarehouse {
    public static final String UNRECONCILED_SQL =
            "SELECT i.INVOICE_NUMBER, a.ACCOUNT_NUMBER, "
            + "TO_CHAR(i.INVOICE_DT, 'YYYY-MM-DD') AS INVOICE_DATE, "
            + "DATEDIFF(day, DATEADD(day, 30, i.INVOICE_DT), CURRENT_DATE) AS DAYS_OVERDUE, "
            + "i.TOTAL_AMOUNT, COALESCE(p.PAID, 0) AS PAID "
            + "FROM SFX_D1110_AFTER.COMPAT.INVOICE_HDR i "
            + "JOIN SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT a ON a.CUSTOMER_ID = i.CUSTOMER_ID "
            + "LEFT JOIN (SELECT INVOICE_ID, SUM(AMOUNT) AS PAID "
            + "FROM SFX_D1110_AFTER.COMPAT.PAYMENT GROUP BY INVOICE_ID) p ON p.INVOICE_ID = i.INVOICE_ID "
            + "WHERE COALESCE(p.PAID, 0) < i.TOTAL_AMOUNT "
            + "AND DATEADD(day, 30, i.INVOICE_DT) < DATEADD(day, -30, CURRENT_DATE) "
            + "AND i.INVOICE_DT >= DATE '2020-01-01' "
            + "AND EXTRACT(YEAR FROM i.INVOICE_DT) * 100 + EXTRACT(MONTH FROM i.INVOICE_DT) = ? "
            + "ORDER BY DAYS_OVERDUE DESC, i.INVOICE_ID LIMIT 25";

    public static final String SQL =
            "SELECT i.PERIOD_ID, i.INVOICED_TOTAL, p.PAID_TOTAL, g.AR_GL_BALANCE, "
            + "i.INVOICED_TOTAL - p.PAID_TOTAL - g.AR_GL_BALANCE AS VARIANCE "
            + "FROM (SELECT CAST(? AS INTEGER) AS PERIOD_ID, COALESCE(SUM(TOTAL_AMOUNT), 0) AS INVOICED_TOTAL "
            + "FROM SFX_D1110_AFTER.COMPAT.INVOICE_HDR WHERE EXTRACT(YEAR FROM INVOICE_DT) * 100 "
            + "+ EXTRACT(MONTH FROM INVOICE_DT) = ?) i "
            + "CROSS JOIN (SELECT COALESCE(SUM(AMOUNT), 0) AS PAID_TOTAL FROM SFX_D1110_AFTER.COMPAT.PAYMENT "
            + "WHERE EXTRACT(YEAR FROM PAYMENT_DT) * 100 + EXTRACT(MONTH FROM PAYMENT_DT) = ?) p "
            + "CROSS JOIN (SELECT COALESCE(SUM(j.DEBIT_AMOUNT - j.CREDIT_AMOUNT), 0) AS AR_GL_BALANCE "
            + "FROM SFX_D1110_AFTER.COMPAT.GL_JOURNAL_LINE j JOIN SFX_D1110_AFTER.COMPAT.GL_ACCOUNT a "
            + "ON a.GL_ACCOUNT_ID = j.GL_ACCOUNT_ID "
            + "WHERE EXTRACT(YEAR FROM j.POSTING_DT) * 100 + EXTRACT(MONTH FROM j.POSTING_DT) = ? "
            + "AND UPPER(RTRIM(a.ACCOUNT_NUMBER)) = '1200') g";

    private final JdbcTemplate jdbc;

    public SnowflakeFinanceWarehouse(JdbcTemplate jdbc) {
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

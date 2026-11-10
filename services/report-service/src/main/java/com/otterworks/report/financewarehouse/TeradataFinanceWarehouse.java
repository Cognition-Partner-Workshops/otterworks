package com.otterworks.report.financewarehouse;

import org.springframework.jdbc.core.JdbcTemplate;

public class TeradataFinanceWarehouse implements FinanceWarehouse {
    public static final String UNRECONCILED_SQL =
            "LOCKING ROW FOR ACCESS SEL TOP 25 i.INVOICE_NO, a.ACCOUNT_NO, "
            + "CAST(i.INVOICE_DT AS DATE FORMAT 'YYYY-MM-DD') AS INVOICE_DATE, "
            + "CURRENT_DATE - i.DUE_DT AS DAYS_OVERDUE, i.AMOUNT_DUE, ZEROIFNULL(p.PAID) AS PAID "
            + "FROM FIN_DW.INVOICE i JOIN FIN_DW.ACCOUNT a ON a.ACCOUNT_ID = i.ACCOUNT_ID "
            + "LEFT JOIN (SEL INVOICE_ID, SUM(AMOUNT) AS PAID FROM FIN_DW.PAYMENT GROUP BY INVOICE_ID) p "
            + "ON p.INVOICE_ID = i.INVOICE_ID "
            + "WHERE ZEROIFNULL(p.PAID) < i.AMOUNT_DUE AND i.DUE_DT < CURRENT_DATE - 30 "
            + "AND i.INVOICE_DT >= 1200101 "
            + "AND EXTRACT(YEAR FROM i.INVOICE_DT) * 100 + EXTRACT(MONTH FROM i.INVOICE_DT) = ? "
            + "ORDER BY DAYS_OVERDUE DESC, i.INVOICE_ID";

    public static final String SQL =
            "LOCKING ROW FOR ACCESS "
            + "SEL i.PERIOD_ID, i.INVOICED_TOTAL, p.PAID_TOTAL, g.AR_GL_BALANCE, "
            + "i.INVOICED_TOTAL - p.PAID_TOTAL - g.AR_GL_BALANCE AS VARIANCE "
            + "FROM (SEL CAST(? AS INTEGER) AS PERIOD_ID, ZEROIFNULL(SUM(AMOUNT_DUE)) AS INVOICED_TOTAL "
            + "FROM FIN_DW.INVOICE WHERE EXTRACT(YEAR FROM INVOICE_DT) * 100 "
            + "+ EXTRACT(MONTH FROM INVOICE_DT) = ?) i "
            + "CROSS JOIN (SEL ZEROIFNULL(SUM(AMOUNT)) AS PAID_TOTAL FROM FIN_DW.PAYMENT "
            + "WHERE EXTRACT(YEAR FROM PAYMENT_DT) * 100 + EXTRACT(MONTH FROM PAYMENT_DT) = ?) p "
            + "CROSS JOIN (SEL ZEROIFNULL(SUM(DEBIT_AMT - CREDIT_AMT)) AS AR_GL_BALANCE "
            + "FROM FIN_DW.GL_JOURNAL WHERE PERIOD_ID = ? AND GL_ACCOUNT_CD = '112000') g";

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
                        rs.getString("INVOICE_NO"), rs.getString("ACCOUNT_NO"), rs.getString("INVOICE_DATE"),
                        rs.getInt("DAYS_OVERDUE"), rs.getBigDecimal("AMOUNT_DUE"), rs.getBigDecimal("PAID")), period));
    }
}

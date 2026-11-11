package com.otterworks.report.financewarehouse;

import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.Date;
import java.time.LocalDate;
import java.util.function.Supplier;

/**
 * Native Databricks SQL for the two report queries, reading the billing__* Delta tables in the
 * connection's default schema. Teradata CURRENT_DATE is replaced by an explicit as-of date bind.
 */
public class DatabricksFinanceWarehouse implements FinanceWarehouse {
    public static final String SQL =
            "SELECT i.PERIOD_ID, i.INVOICED_TOTAL, p.PAID_TOTAL, g.AR_GL_BALANCE, "
            + "i.INVOICED_TOTAL - p.PAID_TOTAL - g.AR_GL_BALANCE AS VARIANCE "
            + "FROM (SELECT CAST(? AS INT) AS PERIOD_ID, coalesce(SUM(TOTAL_AMOUNT), 0) AS INVOICED_TOTAL "
            + "FROM billing__invoice_hdr WHERE EXTRACT(YEAR FROM INVOICE_DT) * 100 "
            + "+ EXTRACT(MONTH FROM INVOICE_DT) = ?) i "
            + "CROSS JOIN (SELECT coalesce(SUM(AMOUNT), 0) AS PAID_TOTAL FROM billing__payment "
            + "WHERE EXTRACT(YEAR FROM PAYMENT_DT) * 100 + EXTRACT(MONTH FROM PAYMENT_DT) = ?) p "
            + "CROSS JOIN (SELECT coalesce(SUM(j.DEBIT_AMOUNT - j.CREDIT_AMOUNT), 0) AS AR_GL_BALANCE "
            + "FROM billing__gl_journal_line j JOIN billing__gl_account a ON a.GL_ACCOUNT_ID = j.GL_ACCOUNT_ID "
            + "WHERE EXTRACT(YEAR FROM j.POSTING_DT) * 100 + EXTRACT(MONTH FROM j.POSTING_DT) = ? "
            + "AND rtrim(a.ACCOUNT_NUMBER) = '1200') g";

    /** Binds: as-of date, as-of date, period. */
    public static final String UNRECONCILED_SQL =
            "SELECT i.INVOICE_NUMBER, a.ACCOUNT_NUMBER, date_format(i.INVOICE_DT, 'yyyy-MM-dd') AS INVOICE_DATE, "
            + "datediff(CAST(? AS DATE), date_add(i.INVOICE_DT, 30)) AS DAYS_OVERDUE, i.TOTAL_AMOUNT, "
            + "coalesce(p.PAID, 0) AS PAID "
            + "FROM billing__invoice_hdr i JOIN billing__customer_account a ON a.CUSTOMER_ID = i.CUSTOMER_ID "
            + "LEFT JOIN (SELECT INVOICE_ID, SUM(AMOUNT) AS PAID FROM billing__payment GROUP BY INVOICE_ID) p "
            + "ON p.INVOICE_ID = i.INVOICE_ID "
            + "WHERE coalesce(p.PAID, 0) < i.TOTAL_AMOUNT "
            + "AND date_add(i.INVOICE_DT, 30) < date_sub(CAST(? AS DATE), 30) "
            + "AND i.INVOICE_DT >= DATE '2020-01-01' "
            + "AND EXTRACT(YEAR FROM i.INVOICE_DT) * 100 + EXTRACT(MONTH FROM i.INVOICE_DT) = ? "
            + "ORDER BY DAYS_OVERDUE DESC, i.INVOICE_ID LIMIT 25";

    private final JdbcTemplate jdbc;
    private final Supplier<LocalDate> asOf;

    public DatabricksFinanceWarehouse(JdbcTemplate jdbc, Supplier<LocalDate> asOf) {
        this.jdbc = jdbc;
        this.asOf = asOf;
    }

    @Override
    public FinanceReconciliation reconcile(int period) {
        Date date = Date.valueOf(asOf.get());
        FinanceReconciliation summary = jdbc.queryForObject(DatabricksReadPath.tagged(SQL), (rs, row) ->
                new FinanceReconciliation(rs.getInt("PERIOD_ID"), rs.getBigDecimal("INVOICED_TOTAL"),
                        rs.getBigDecimal("PAID_TOTAL"), rs.getBigDecimal("AR_GL_BALANCE")),
                period, period, period, period);
        return new FinanceReconciliation(summary.period, summary.invoicedTotal, summary.paidTotal,
                summary.arGlBalance, jdbc.query(DatabricksReadPath.tagged(UNRECONCILED_SQL), (rs, row) ->
                        new UnreconciledInvoice(rs.getString("INVOICE_NUMBER"), rs.getString("ACCOUNT_NUMBER"),
                                rs.getString("INVOICE_DATE"), rs.getInt("DAYS_OVERDUE"),
                                rs.getBigDecimal("TOTAL_AMOUNT"), rs.getBigDecimal("PAID")), date, date, period));
    }
}

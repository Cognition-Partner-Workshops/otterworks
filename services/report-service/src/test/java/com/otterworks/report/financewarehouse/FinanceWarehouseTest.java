package com.otterworks.report.financewarehouse;

import org.junit.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.util.Collections;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

public class FinanceWarehouseTest {
    @Test
    public void dalBindsPeriodAndMapsDecimals() throws Exception {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        ResultSet rs = mock(ResultSet.class);
        when(rs.getInt("PERIOD_ID")).thenReturn(202601);
        when(rs.getBigDecimal("INVOICED_TOTAL")).thenReturn(new BigDecimal("18250.75"));
        when(rs.getBigDecimal("PAID_TOTAL")).thenReturn(new BigDecimal("12000.25"));
        when(rs.getBigDecimal("AR_GL_BALANCE")).thenReturn(new BigDecimal("6250.50"));
        when(rs.getString("INVOICE_NUMBER")).thenReturn("INV-2026-004812");
        when(rs.getString("ACCOUNT_NUMBER")).thenReturn("ACC-0000012");
        when(rs.getString("INVOICE_DATE")).thenReturn("2026-01-05");
        when(rs.getInt("DAYS_OVERDUE")).thenReturn(65);
        when(rs.getBigDecimal("TOTAL_AMOUNT")).thenReturn(new BigDecimal("4800.00"));
        when(rs.getBigDecimal("PAID")).thenReturn(new BigDecimal("1200.00"));
        when(jdbc.query(eq(TeradataFinanceWarehouse.UNRECONCILED_SQL), any(RowMapper.class), eq(202601)))
                .thenAnswer(call -> Collections.singletonList(((RowMapper<?>) call.getArgument(1)).mapRow(rs, 0)));
        when(jdbc.queryForObject(eq(TeradataFinanceWarehouse.SQL), any(RowMapper.class),
                eq(202601), eq(202601), eq(202601), eq(202601)))
                .thenAnswer(call -> ((RowMapper<?>) call.getArgument(1)).mapRow(rs, 0));
        FinanceReconciliation result = new TeradataFinanceWarehouse(jdbc).reconcile(202601);
        assertEquals(new BigDecimal("0.00"), result.variance);
        assertEquals(new BigDecimal("18250.75"), result.invoicedTotal);
        assertEquals(1, result.unreconciledInvoices.size());
        UnreconciledInvoice invoice = result.unreconciledInvoices.get(0);
        assertEquals("INV-2026-004812", invoice.invoiceNo);
        assertEquals("ACC-0000012", invoice.accountNo);
        assertEquals("2026-01-05", invoice.invoiceDate);
        assertEquals(65, invoice.daysOverdue);
        assertEquals(new BigDecimal("4800.00"), invoice.amountDue);
        assertEquals(new BigDecimal("1200.00"), invoice.paid);
    }

    @Test
    @SuppressWarnings("unchecked")
    public void databricksPathBindsPeriodAndAsOfDate() {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        java.sql.Date asOf = java.sql.Date.valueOf("2026-11-09");
        when(jdbc.queryForObject(eq(DatabricksReadPath.tagged(DatabricksFinanceWarehouse.SQL)), any(RowMapper.class),
                eq(202601), eq(202601), eq(202601), eq(202601)))
                .thenReturn(new FinanceReconciliation(202601, BigDecimal.ONE, BigDecimal.ZERO, BigDecimal.ZERO));
        when(jdbc.query(eq(DatabricksReadPath.tagged(DatabricksFinanceWarehouse.UNRECONCILED_SQL)),
                any(RowMapper.class), eq(asOf), eq(asOf), eq(202601))).thenReturn(Collections.emptyList());
        FinanceReconciliation result = new DatabricksFinanceWarehouse(jdbc,
                () -> java.time.LocalDate.of(2026, 11, 9)).reconcile(202601);
        assertEquals(BigDecimal.ONE, result.variance);
        assertEquals(0, result.unreconciledInvoices.size());
        org.junit.Assert.assertFalse(DatabricksFinanceWarehouse.UNRECONCILED_SQL.contains("CURRENT_DATE"));
    }

    @Test
    public void endpointReturnsReportAndEmptyPeriod() throws Exception {
        MockMvc mvc = mvc(period -> new FinanceReconciliation(period,
                new BigDecimal("0.00"), new BigDecimal("0.00"), new BigDecimal("0.00")));
        mvc.perform(get("/api/v1/reports/finance-reconciliation").param("period", "202602"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.period").value(202602))
                .andExpect(jsonPath("$.unreconciledInvoices").isEmpty())
                .andExpect(jsonPath("$.invoicedTotal").value(0)).andExpect(jsonPath("$.variance").value(0));
        MockMvc populated = mvc(period -> new FinanceReconciliation(period,
                new BigDecimal("100.00"), new BigDecimal("40.00"), new BigDecimal("59.00"),
                Collections.singletonList(new UnreconciledInvoice("INV-2026-004812", "ACC-0000012",
                        "2026-01-05", 65, new BigDecimal("100.00"), new BigDecimal("40.00")))));
        populated.perform(get("/api/v1/reports/finance-reconciliation").param("period", "202601"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.variance").value(1))
                .andExpect(jsonPath("$.unreconciledInvoices[0].invoiceNo").value("INV-2026-004812"));
    }

    @Test
    public void invalidPeriodsNeverReachWarehouse() throws Exception {
        MockMvc mvc = mvc(period -> {
            throw new AssertionError("warehouse must not be called");
        });
        for (String period : new String[]{"202613", "202600", "20261", "202601 OR 1=1", ""}) {
            mvc.perform(get("/api/v1/reports/finance-reconciliation").param("period", period))
                    .andExpect(status().isBadRequest());
        }
        mvc.perform(get("/api/v1/reports/finance-reconciliation")).andExpect(status().isBadRequest());
    }

    @Test
    public void warehouseErrorsReturn503WithoutDetails() throws Exception {
        mvc(period -> {
            throw new DataAccessResourceFailureException("private connection details");
        })
                .perform(get("/api/v1/reports/finance-reconciliation").param("period", "202601"))
                .andExpect(status().isServiceUnavailable());
    }

    @Test
    public void flagDisablesBeansAndDefaultDoesNotConnect() {
        new ApplicationContextRunner().withUserConfiguration(FinanceWarehouseConfig.class,
                FinanceReconciliationController.class).run(context ->
                        assertTrue(context.containsBean("financeWarehouse")));
        new ApplicationContextRunner().withUserConfiguration(FinanceWarehouseConfig.class,
                FinanceReconciliationController.class).withPropertyValues("finance.warehouse.enabled=false")
                .run(context -> assertEquals(0, context.getBeansOfType(FinanceWarehouse.class).size()));
    }

    private MockMvc mvc(FinanceWarehouse warehouse) {
        return MockMvcBuilders.standaloneSetup(new FinanceReconciliationController(warehouse)).build();
    }
}

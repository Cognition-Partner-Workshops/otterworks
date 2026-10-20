package com.bank.statements;

import static org.junit.Assert.assertTrue;

import java.math.BigDecimal;
import java.sql.Date;
import java.util.Arrays;
import java.util.Collections;
import org.junit.Test;

public class HtmlTest {
    @Test
    public void escapesHolderNames() {
        String out = Html.accounts("Bank", Collections.singletonMap("IT01W1000001", "<b>x</b>"), null);
        assertTrue(out.contains("&lt;b&gt;x&lt;/b&gt;"));
    }

    @Test
    public void statementShowsNetMovement() {
        String out = Html.statement("Bank", "IT01W1000001", Arrays.asList(
            new StatementLine(Date.valueOf("2026-09-02"), "SALARY", new BigDecimal("100.00"), new BigDecimal("100.00")),
            new StatementLine(Date.valueOf("2026-09-03"), "CARD PAYMENT", new BigDecimal("-30.50"), new BigDecimal("69.50"))));
        assertTrue(out.contains("2 lines, net movement 69.50"));
    }
}

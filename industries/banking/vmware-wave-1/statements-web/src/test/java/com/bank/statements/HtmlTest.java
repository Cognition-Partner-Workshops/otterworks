package com.bank.statements;

import static org.junit.Assert.assertTrue;
import static org.junit.Assert.assertFalse;

import java.math.BigDecimal;
import java.sql.Date;
import java.util.Arrays;
import java.util.Collections;
import org.junit.Test;

public class HtmlTest {
    @org.junit.Before
    public void configureReferenceSecret() {
        System.setProperty("bank.account.reference.secret", java.util.UUID.randomUUID().toString());
    }

    @org.junit.After
    public void clearReferenceSecret() {
        System.clearProperty("bank.account.reference.secret");
    }

    @Test
    public void masksAccountLinkTextAndLastViewedButKeepsNavigation() {
        String out = Html.accounts("Bank", Collections.singletonMap("HG611000001", "Avery"), "HG611000001");
        assertTrue(out.contains("href=\"statement?reference=" + Html.reference("HG611000001") + "\">****0001</a>"));
        String visible = out.replaceAll("<[^>]+>", "");
        assertTrue(visible.contains("Last viewed: ****0001"));
        assertFalse(visible.contains("HG611000001"));
    }

    @Test
    public void masksStatementHeadingAndBrowserTitle() {
        String out = Html.statement("Bank", "HG611000001", Collections.emptyList());
        assertTrue(out.contains("<title>Statement ****0001 - Bank</title>"));
        assertTrue(out.contains("<h2>Statement ****0001</h2>"));
        assertFalse(out.contains("HG611000001"));
    }

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

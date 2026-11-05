package com.bank.statements;

import static org.junit.Assert.*;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.*;
import java.sql.SQLException;
import java.util.*;
import java.util.regex.*;
import javax.servlet.ServletException;
import javax.servlet.http.*;
import javax.sql.DataSource;
import org.junit.Test;

public class DisclosureTest {
    @org.junit.Before
    public void configureReferenceSecret() {
        System.setProperty("bank.account.reference.secret", java.util.UUID.randomUUID().toString());
    }

    @org.junit.After
    public void clearReferenceSecret() {
        System.clearProperty("bank.account.reference.secret");
    }

    private final String account = "HG611000001";

    @Test
    public void linksAreOpaqueAndResolveTheOriginalAccount() throws Exception {
        String page = Html.accounts("Bank", Collections.singletonMap(account, "Avery"), account);
        assertFalse("HTML links must not disclose account numbers", page.contains(account));
        Matcher link = Pattern.compile("statement\\?reference=([a-f0-9-]+)").matcher(page);
        assertTrue(link.find());
        StatementServlet servlet = new StatementServlet();
        final List<String> lookedUp = new ArrayList<>();
        inject(servlet, new StatementDao((DataSource) null) {
            public Map<String, String> accounts() { return Collections.singletonMap(account, "Avery"); }
            public List<StatementLine> lines(String key, int limit) {
                lookedUp.add(key);
                return Collections.emptyList();
            }
        });
        StringWriter output = new StringWriter();
        servlet.doGet(request(Collections.singletonMap("reference", link.group(1))), response(output));
        assertEquals(Collections.singletonList(account), lookedUp);
        assertTrue(output.toString().contains("Statement ****0001"));
        assertFalse(output.toString().contains(account));
    }

    @Test
    public void unknownReferencesAndEmptyAccountsAreSafe() throws Exception {
        assertFalse(Html.accounts("Bank", Collections.emptyMap(), null).contains("reference="));
        StatementServlet servlet = new StatementServlet();
        inject(servlet, new StatementDao((DataSource) null) {
            public Map<String, String> accounts() { return Collections.emptyMap(); }
        });
        StringWriter output = new StringWriter();
        servlet.doGet(request(Collections.singletonMap("reference", "unknown")), response(output));
        assertTrue(output.toString().startsWith("400"));
    }

    @Test
    public void databaseErrorsDoNotReachCustomerErrorPages() throws Exception {
        StatementDao broken = new StatementDao((DataSource) null) {
            public Map<String, String> accounts() throws SQLException { throw new SQLException(account); }
            public List<StatementLine> lines(String key, int limit) throws SQLException { throw new SQLException(account); }
        };
        StringWriter output = new StringWriter();
        StatementServlet statement = new StatementServlet();
        inject(statement, broken);
        try {
            statement.doGet(request(Collections.singletonMap("account", account)), response(output));
        } catch (ServletException e) {
            fail("Database details must not be delegated to the customer error page: " + e.getCause().getMessage());
        }
        assertTrue(output.toString().startsWith("500"));
        assertFalse(output.toString().contains(account));
        AccountsServlet accounts = new AccountsServlet();
        inject(accounts, broken);
        output = new StringWriter();
        try {
            accounts.doGet(request(Collections.emptyMap()), response(output));
        } catch (ServletException e) {
            fail("Database details must not be delegated to the customer error page");
        }
        assertTrue(output.toString().startsWith("500"));
    }

    private void inject(HttpServlet servlet, StatementDao dao) throws Exception {
        Field field = servlet.getClass().getDeclaredField("dao");
        field.setAccessible(true);
        field.set(servlet, dao);
        Field config = AppConfig.class.getDeclaredField("props");
        config.setAccessible(true);
        config.set(null, new Properties());
    }

    private HttpServletRequest request(Map<String, String> parameters) {
        HttpSession session = (HttpSession) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class<?>[] {HttpSession.class}, (proxy, method, args) -> null);
        return (HttpServletRequest) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class<?>[] {HttpServletRequest.class}, (proxy, method, args) -> {
                    if (method.getName().equals("getParameter")) return parameters.get(args[0]);
                    if (method.getName().equals("getSession")) return session;
                    return null;
                });
    }

    private HttpServletResponse response(StringWriter output) {
        return (HttpServletResponse) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class<?>[] {HttpServletResponse.class}, (proxy, method, args) -> {
                    if (method.getName().equals("getWriter")) return new PrintWriter(output);
                    if (method.getName().equals("sendError")) output.write(args[0] + " " + args[1]);
                    return null;
                });
    }
}

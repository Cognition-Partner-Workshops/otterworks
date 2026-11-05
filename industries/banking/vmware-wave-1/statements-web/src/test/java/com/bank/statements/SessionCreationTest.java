package com.bank.statements;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.lang.reflect.Proxy;
import java.math.BigDecimal;
import java.sql.Date;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.junit.BeforeClass;
import org.junit.Test;

public class SessionCreationTest {
    private static final StatementDao DAO = new StatementDao((javax.sql.DataSource) null) {
        @Override
        public Map<String, String> accounts() {
            return Collections.singletonMap("HG611000001", "Test Holder");
        }

        @Override
        public List<StatementLine> lines(String accountId, int limit) {
            return Collections.singletonList(
                new StatementLine(Date.valueOf("2026-10-14"), "SALARY", new BigDecimal("10.00"), new BigDecimal("10.00")));
        }
    };

    @BeforeClass
    public static void stubConfig() throws Exception {
        Field f = AppConfig.class.getDeclaredField("props");
        f.setAccessible(true);
        f.set(null, new Properties());
    }

    @Test
    public void accountsPageDoesNotCreateSession() throws Exception {
        Exchange x = new Exchange(null, null, false);
        new AccountsServlet(DAO).doGet(x.request(), x.response());
        assertTrue(x.body().contains("HG611000001"));
        assertFalse(x.body().contains("id=\"last\""));
        assertTrue(x.cookies.isEmpty());
    }

    @Test
    public void accountsPageShowsLastViewedFromCookie() throws Exception {
        Exchange x = new Exchange(null, new Cookie[] {new Cookie(LastViewed.COOKIE, "HG631000003")}, false);
        new AccountsServlet(DAO).doGet(x.request(), x.response());
        assertTrue(x.body().contains("<p id=\"last\">Last viewed: <a href=\"statement?account=HG631000003\">"));
    }

    @Test
    public void accountsPageIgnoresMalformedLastViewedCookie() throws Exception {
        Exchange x = new Exchange(null, new Cookie[] {new Cookie(LastViewed.COOKIE, "x\"onmouseover=alert(1)")}, false);
        new AccountsServlet(DAO).doGet(x.request(), x.response());
        assertFalse(x.body().contains("id=\"last\""));
    }

    @Test
    public void statementPageDoesNotCreateSessionAndRemembersAccount() throws Exception {
        Exchange x = new Exchange("HG611000001", null, false);
        new StatementServlet(DAO).doGet(x.request(), x.response());
        assertTrue(x.body().contains("1 lines, net movement 10.00"));
        assertEquals(1, x.cookies.size());
        Cookie c = x.cookies.get(0);
        assertEquals(LastViewed.COOKIE, c.getName());
        assertEquals("HG611000001", c.getValue());
        assertEquals("/statements", c.getPath());
        assertTrue(c.isHttpOnly());
        assertFalse(c.getSecure());
        assertEquals(-1, c.getMaxAge());
    }

    @Test
    public void statementCookieIsSecureOverHttps() throws Exception {
        Exchange x = new Exchange("HG611000001", null, true);
        new StatementServlet(DAO).doGet(x.request(), x.response());
        assertTrue(x.cookies.get(0).getSecure());
    }

    @Test
    public void malformedAccountIsRejectedWithoutCookie() throws Exception {
        Exchange x = new Exchange("bad", null, false);
        new StatementServlet(DAO).doGet(x.request(), x.response());
        assertEquals(Integer.valueOf(HttpServletResponse.SC_BAD_REQUEST), x.error);
        assertTrue(x.cookies.isEmpty());
        assertNull(LastViewed.read(x.request()));
    }

    /** Request/response stand-ins that fail the test if a servlet asks for an HTTP session. */
    private static final class Exchange {
        private final String account;
        private final Cookie[] requestCookies;
        private final boolean secure;
        private final StringWriter out = new StringWriter();
        final List<Cookie> cookies = new ArrayList<>();
        Integer error;

        Exchange(String account, Cookie[] requestCookies, boolean secure) {
            this.account = account;
            this.requestCookies = requestCookies;
            this.secure = secure;
        }

        String body() {
            return out.toString();
        }

        HttpServletRequest request() {
            return (HttpServletRequest) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class<?>[] {HttpServletRequest.class}, (p, m, a) -> {
                    switch (m.getName()) {
                        case "getParameter":
                            return "account".equals(a[0]) ? account : null;
                        case "getCookies":
                            return requestCookies;
                        case "getContextPath":
                            return "/statements";
                        case "isSecure":
                            return secure;
                        case "getSession":
                            if (a == null || Boolean.TRUE.equals(a[0])) {
                                throw new AssertionError("servlet created an HTTP session");
                            }
                            return null;
                        default:
                            throw new UnsupportedOperationException(m.getName());
                    }
                });
        }

        HttpServletResponse response() {
            return (HttpServletResponse) Proxy.newProxyInstance(getClass().getClassLoader(),
                new Class<?>[] {HttpServletResponse.class}, (p, m, a) -> {
                    switch (m.getName()) {
                        case "setContentType":
                            return null;
                        case "getWriter":
                            return new PrintWriter(out, true);
                        case "addCookie":
                            cookies.add((Cookie) a[0]);
                            return null;
                        case "sendError":
                            error = (Integer) a[0];
                            return null;
                        default:
                            throw new UnsupportedOperationException(m.getName());
                    }
                });
        }
    }
}

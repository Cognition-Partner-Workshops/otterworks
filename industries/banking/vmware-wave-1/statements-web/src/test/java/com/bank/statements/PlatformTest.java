package com.bank.statements;

import static org.junit.Assert.*;
import java.lang.reflect.Proxy;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.sql.Connection;
import java.sql.SQLException;
import javax.sql.DataSource;
import javax.servlet.http.Cookie;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.junit.Test;

public class PlatformTest {
    @Test
    public void mountedSettingsAreRead() {
        assertEquals("Test Bank", AppConfig.bankName());
        assertEquals(50, AppConfig.pageSize());
    }

    @Test
    public void validatesAccountCookie() {
        assertNull(LastViewed.fromCookies(null));
        assertNull(LastViewed.fromCookies(new Cookie[] {new Cookie("other", "HG611000001")}));
        assertNull(LastViewed.fromCookies(new Cookie[] {new Cookie("statementsLastAccount", "<script>")}));
        assertNull(LastViewed.fromCookies(new Cookie[] {new Cookie("statementsLastAccount", "bad")}));
        assertEquals("HG611000001", LastViewed.fromCookies(new Cookie[] {
            new Cookie("statementsLastAccount", "HG611000001")}));
        assertFalse(LastViewed.valid(null));
        assertFalse(LastViewed.valid(""));
        assertFalse(LastViewed.valid("HG611000001'"));
    }

    @Test
    public void cookieSurvivesAnotherReplicaWithoutCreatingSession() {
        final String[] header = new String[1];
        HttpServletRequest first = (HttpServletRequest) Proxy.newProxyInstance(
            getClass().getClassLoader(), new Class<?>[] {HttpServletRequest.class}, (p, m, a) -> {
                if (m.getName().equals("getContextPath")) return "/statements";
                throw new AssertionError("unexpected request call: " + m.getName());
            });
        HttpServletResponse response = (HttpServletResponse) Proxy.newProxyInstance(
            getClass().getClassLoader(), new Class<?>[] {HttpServletResponse.class}, (p, m, a) -> {
                assertEquals("addHeader", m.getName());
                assertEquals("Set-Cookie", a[0]);
                header[0] = (String) a[1];
                return null;
            });
        LastViewed.write(first, response, "HG611000001");
        assertEquals("statementsLastAccount=HG611000001; Path=/statements; HttpOnly; SameSite=Lax; Secure", header[0]);
        Cookie cookie = new Cookie("statementsLastAccount", header[0].split("[=;]")[1]);
        HttpServletRequest second = (HttpServletRequest) Proxy.newProxyInstance(
            getClass().getClassLoader(), new Class<?>[] {HttpServletRequest.class}, (p, m, a) -> {
                if (m.getName().equals("getCookies")) return new Cookie[] {cookie};
                throw new AssertionError("must not create session: " + m.getName());
            });
        assertEquals("HG611000001", LastViewed.read(second));
    }

    private StatementDao database(boolean available) {
        DataSource ds = (DataSource) Proxy.newProxyInstance(
            getClass().getClassLoader(), new Class<?>[] {DataSource.class}, (p, m, a) -> {
                if (!available) throw new SQLException("database unavailable");
                return Proxy.newProxyInstance(getClass().getClassLoader(), new Class<?>[] {Connection.class},
                    (c, method, args) -> method.getName().equals("isValid") ? Boolean.TRUE : null);
            });
        return new StatementDao(ds);
    }

    @Test
    public void healthRequiresReachableDatabase() {
        assertTrue(HealthServlet.ready(database(true)));
        assertFalse(HealthServlet.ready(database(false)));
    }

    @Test
    public void badAndMissingAccountsKeepTheLegacyResponse() throws Exception {
        for (String account : new String[] {null, "", "bad", "<script>"}) {
            StringWriter body = new StringWriter();
            HttpServletRequest request = (HttpServletRequest) Proxy.newProxyInstance(
                getClass().getClassLoader(), new Class<?>[] {HttpServletRequest.class}, (p, m, a) -> {
                    assertEquals("getParameter", m.getName());
                    return account;
                });
            HttpServletResponse response = (HttpServletResponse) Proxy.newProxyInstance(
                getClass().getClassLoader(), new Class<?>[] {HttpServletResponse.class}, (p, m, a) -> {
                    switch (m.getName()) {
                        case "setStatus": assertEquals(400, a[0]); return null;
                        case "setContentType": assertEquals("text/html;charset=utf-8", a[0]); return null;
                        case "setHeader": assertEquals("Content-Language", a[0]); assertEquals("en", a[1]); return null;
                        case "getWriter": return new PrintWriter(body);
                        default: throw new AssertionError("unexpected response call: " + m.getName());
                    }
                });
            new StatementServlet().doGet(request, response);
            assertEquals(BadAccount.BODY, body.toString());
            assertTrue(body.toString().contains("account is required"));
        }
    }
}

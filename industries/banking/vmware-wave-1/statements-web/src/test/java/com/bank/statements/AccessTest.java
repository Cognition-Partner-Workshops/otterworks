package com.bank.statements;

import static org.mockito.Mockito.*;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.lang.reflect.Field;
import java.util.Collections;
import javax.servlet.http.*;
import org.junit.Test;

public class AccessTest {
    @org.junit.Before public void configureApplication() throws Exception {
        Field field = AppConfig.class.getDeclaredField("props");
        field.setAccessible(true);
        field.set(null, new java.util.Properties());
    }

    private HttpServletRequest request(boolean authenticated, boolean owner) {
        HttpServletRequest req = mock(HttpServletRequest.class);
        when(req.getParameter("account")).thenReturn("HG611000001");
        when(req.getUserPrincipal()).thenReturn(authenticated ? () -> "customer-a" : null);
        when(req.isUserInRole("ACCOUNT_HG611000001")).thenReturn(owner);
        when(req.getSession(true)).thenReturn(mock(HttpSession.class));
        return req;
    }

    private StatementServlet servlet() throws Exception {
        StatementDao dao = mock(StatementDao.class);
        when(dao.lines(anyString(), anyInt())).thenReturn(Collections.emptyList());
        StatementServlet servlet = new StatementServlet();
        Field field = StatementServlet.class.getDeclaredField("dao");
        field.setAccessible(true);
        field.set(servlet, dao);
        return servlet;
    }

    private HttpServletResponse response() throws Exception {
        HttpServletResponse resp = mock(HttpServletResponse.class);
        when(resp.getWriter()).thenReturn(new PrintWriter(new StringWriter()));
        return resp;
    }

    @Test public void rejectsAnonymousStatement() throws Exception {
        HttpServletResponse resp = response();
        servlet().doGet(request(false, false), resp);
        verify(resp).sendError(eq(401), anyString());
    }

    @Test public void rejectsAnotherCustomersAccount() throws Exception {
        HttpServletResponse resp = response();
        servlet().doGet(request(true, false), resp);
        verify(resp).sendError(eq(403), anyString());
    }

    @Test public void permitsOwnedStatement() throws Exception {
        HttpServletResponse resp = response();
        servlet().doGet(request(true, true), resp);
        verify(resp).setContentType("text/html;charset=UTF-8");
        verify(resp, never()).sendError(anyInt(), anyString());
    }
}

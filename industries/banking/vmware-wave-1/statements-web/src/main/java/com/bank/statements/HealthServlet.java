package com.bank.statements;

import java.io.IOException;
import java.sql.Connection;
import java.sql.SQLException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.sql.DataSource;
import org.apache.log4j.Logger;

/** 200 when a pooled connection to the statements database validates, 503 otherwise. */
public class HealthServlet extends HttpServlet {
    private static final Logger LOG = Logger.getLogger(HealthServlet.class);
    private static final int TIMEOUT_SECONDS = 2;

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        boolean up = databaseAnswers(StatementsContext.pool(getServletContext()));
        resp.setStatus(up ? HttpServletResponse.SC_OK : HttpServletResponse.SC_SERVICE_UNAVAILABLE);
        resp.setContentType("text/plain;charset=UTF-8");
        resp.setHeader("Cache-Control", "no-store");
        resp.getWriter().write(up ? "ok\n" : "database unavailable\n");
    }

    static boolean databaseAnswers(DataSource pool) {
        if (pool == null) {
            return false;
        }
        try (Connection c = pool.getConnection()) {
            return c.isValid(TIMEOUT_SECONDS);
        } catch (SQLException e) {
            LOG.warn("health check: " + e.getMessage());
            return false;
        }
    }
}

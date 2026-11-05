package com.bank.statements;

import java.io.IOException;
import java.sql.SQLException;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.log4j.Logger;

public class AccountsServlet extends HttpServlet {
    private static final Logger LOG = Logger.getLogger(AccountsServlet.class);
    private transient StatementDao dao;

    @Override
    public void init() {
        dao = new StatementDao();
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        if (req.getUserPrincipal() == null) {
            resp.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Authentication required");
            return;
        }
        if (!req.isUserInRole("BANK_ADMIN")) {
            resp.sendError(HttpServletResponse.SC_FORBIDDEN, "Administrator access required");
            return;
        }
        try {
            String last = (String) req.getSession(true).getAttribute("lastAccount");
            resp.setContentType("text/html;charset=UTF-8");
            resp.getWriter().write(Html.accounts(AppConfig.bankName(), dao.accounts(), last));
        } catch (SQLException e) {
            LOG.error("accounts query failed", e);
            throw new ServletException(e);
        }
    }
}

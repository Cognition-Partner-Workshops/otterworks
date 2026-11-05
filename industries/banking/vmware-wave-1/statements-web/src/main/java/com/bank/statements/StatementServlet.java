package com.bank.statements;

import java.io.IOException;
import java.sql.SQLException;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.log4j.Logger;

public class StatementServlet extends HttpServlet {
    private static final Logger LOG = Logger.getLogger(StatementServlet.class);
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
        String account = req.getParameter("account");
        if (account == null || !account.matches("[A-Z0-9]{8,20}")) {
            resp.sendError(HttpServletResponse.SC_BAD_REQUEST, "account is required");
            return;
        }
        if (!req.isUserInRole("ACCOUNT_" + account)) {
            resp.sendError(HttpServletResponse.SC_FORBIDDEN, "Account access denied");
            return;
        }
        try {
            req.getSession(true).setAttribute("lastAccount", account);
            LOG.info("statement viewed account=" + account);
            resp.setContentType("text/html;charset=UTF-8");
            resp.getWriter().write(Html.statement(AppConfig.bankName(), account, dao.lines(account, AppConfig.pageSize())));
        } catch (SQLException e) {
            LOG.error("statement query failed", e);
            throw new ServletException(e);
        }
    }
}

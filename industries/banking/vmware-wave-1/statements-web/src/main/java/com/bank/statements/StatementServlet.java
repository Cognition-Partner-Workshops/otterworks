package com.bank.statements;

import java.io.IOException;
import java.sql.SQLException;
import java.util.List;
import java.util.Set;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.log4j.Logger;

public class StatementServlet extends HttpServlet {
    private static final Logger LOG = Logger.getLogger(StatementServlet.class);
    private transient StatementDao dao;
    private transient StatementAccess access;

    @Override
    public void init() throws ServletException {
        try {
            access = StatementAccess.load();
        } catch (IOException | IllegalArgumentException e) {
            throw new ServletException("cannot load statements access mapping", e);
        }
        dao = new StatementDao();
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        Set<String> allowed = access.accounts(req, resp);
        if (allowed == null) {
            return;
        }
        String account = req.getParameter("account");
        if (account == null || !account.matches("[A-Z0-9]{8,20}")) {
            resp.sendError(HttpServletResponse.SC_BAD_REQUEST, "account is required");
            return;
        }
        if (!allowed.contains(account)) {
            resp.sendError(HttpServletResponse.SC_NOT_FOUND);
            return;
        }
        try {
            List<StatementLine> lines = dao.lines(account, AppConfig.pageSize());
            req.getSession(true).setAttribute("lastAccount", account);
            LOG.info("statement viewed account=" + account);
            resp.setContentType("text/html;charset=UTF-8");
            resp.getWriter().write(Html.statement(AppConfig.bankName(), account, lines));
        } catch (SQLException e) {
            LOG.error("statement query failed", e);
            throw new ServletException(e);
        }
    }
}

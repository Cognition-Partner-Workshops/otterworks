package com.bank.statements;

import java.io.IOException;
import java.sql.SQLException;
import java.util.Map;
import java.util.Set;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import org.apache.log4j.Logger;

public class AccountsServlet extends HttpServlet {
    private static final Logger LOG = Logger.getLogger(AccountsServlet.class);
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
        try {
            Map<String, String> accounts = dao.accounts(allowed);
            String last = (String) req.getSession(true).getAttribute("lastAccount");
            if (!accounts.containsKey(last)) {
                last = null;
            }
            resp.setContentType("text/html;charset=UTF-8");
            resp.getWriter().write(Html.accounts(AppConfig.bankName(), accounts, last));
        } catch (SQLException e) {
            LOG.error("accounts query failed", e);
            throw new ServletException(e);
        }
    }
}

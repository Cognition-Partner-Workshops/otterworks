package com.bank.statements;

import java.io.IOException;
import java.sql.SQLException;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.util.logging.Logger;
import java.util.logging.Level;

public class AccountsServlet extends HttpServlet {
    private static final Logger LOG = Logger.getLogger(AccountsServlet.class.getName());
    private transient StatementDao dao;

    @Override
    public void init() {
        dao = new StatementDao();
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        try {
            String last = (String) req.getSession(true).getAttribute("lastAccount");
            resp.setContentType("text/html;charset=UTF-8");
            resp.getWriter().write(Html.accounts(AppConfig.bankName(), dao.accounts(), last));
        } catch (SQLException e) {
            LOG.log(Level.SEVERE, "accounts query failed", e);
            throw new ServletException(e);
        }
    }
}

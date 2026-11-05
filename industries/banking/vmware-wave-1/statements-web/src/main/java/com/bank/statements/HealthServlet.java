package com.bank.statements;

import java.io.IOException;
import java.sql.SQLException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

public class HealthServlet extends HttpServlet {
    private transient StatementDao dao;

    @Override
    public void init() {
        dao = new StatementDao();
    }

    static boolean ready(StatementDao dao) {
        try {
            AppConfig.bankName();
            return dao.healthy();
        } catch (SQLException | RuntimeException e) {
            return false;
        }
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        boolean ready = ready(dao);
        resp.setStatus(ready ? 200 : 503);
        resp.setContentType("text/plain;charset=UTF-8");
        resp.getWriter().write(ready ? "ok\n" : "unavailable\n");
    }
}

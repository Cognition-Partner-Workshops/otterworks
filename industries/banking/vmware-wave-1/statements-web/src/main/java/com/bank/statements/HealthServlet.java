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
        AppConfig.get();
        dao = new StatementDao();
    }

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        resp.setContentType("text/plain;charset=UTF-8");
        try {
            boolean ready = dao.healthy();
            resp.setStatus(ready ? 200 : 503);
            resp.getWriter().println(ready ? "ok" : "unavailable");
        } catch (SQLException e) {
            resp.setStatus(503);
            resp.getWriter().println("unavailable");
        }
    }
}

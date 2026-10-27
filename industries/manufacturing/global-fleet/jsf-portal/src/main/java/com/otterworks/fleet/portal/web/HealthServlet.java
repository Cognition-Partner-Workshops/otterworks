package com.otterworks.fleet.portal.web;

import com.otterworks.fleet.portal.service.FleetService;
import java.io.IOException;
import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

@WebServlet("/health")
public class HealthServlet extends HttpServlet {
    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException {
        resp.setContentType("text/plain");
        try {
            new FleetService().rule();
            resp.getWriter().write("ok");
        } catch (RuntimeException e) {
            resp.setStatus(503);
            resp.getWriter().write("db unavailable");
        }
    }
}

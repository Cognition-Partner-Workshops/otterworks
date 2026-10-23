package com.otterworks.sharelinks;

import java.io.IOException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/** Resolves a public share token to the document it points at. */
public class ShareLinkServlet extends HttpServlet {

    @Override
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        String token = req.getPathInfo() == null ? "" : req.getPathInfo().substring(1);
        if (token.isEmpty()) {
            resp.sendError(HttpServletResponse.SC_BAD_REQUEST, "missing token");
            return;
        }
        Connection conn = null;
        PreparedStatement ps = null;
        ResultSet rs = null;
        try {
            conn = Db.connect();
            ps = conn.prepareStatement(
                "SELECT document_id FROM share_links WHERE token = ? AND expires_at > now()");
            ps.setString(1, token);
            rs = ps.executeQuery();
            if (!rs.next()) {
                resp.sendError(HttpServletResponse.SC_NOT_FOUND);
                return;
            }
            resp.sendRedirect("/documents/" + rs.getString(1));
        } catch (SQLException e) {
            throw new ServletException(e);
        } finally {
            Db.closeQuietly(rs, ps, conn);
        }
    }
}

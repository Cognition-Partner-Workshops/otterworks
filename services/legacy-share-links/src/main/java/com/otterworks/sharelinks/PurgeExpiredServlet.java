package com.otterworks.sharelinks;

import java.io.IOException;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/** Deletes share links that expired more than thirty days ago. */
public class PurgeExpiredServlet extends HttpServlet {

    @Override
    protected void doPost(HttpServletRequest req, HttpServletResponse resp) throws ServletException, IOException {
        Connection conn = null;
        PreparedStatement ps = null;
        try {
            conn = Db.connect();
            ps = conn.prepareStatement(
                "DELETE FROM share_links WHERE expires_at < now() - interval '30 days'");
            int purged = ps.executeUpdate();
            resp.setContentType("application/json");
            resp.getWriter().write("{\"purged\":" + purged + "}");
        } catch (SQLException e) {
            throw new ServletException(e);
        } finally {
            Db.closeQuietly(null, ps, conn);
        }
    }
}

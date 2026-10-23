package com.otterworks.sharelinks;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

final class Db {
    private Db() {
    }

    static Connection connect() throws SQLException {
        String url = System.getProperty("sharelinks.jdbc.url", "jdbc:postgresql://localhost:5432/otterworks");
        return DriverManager.getConnection(url,
            System.getProperty("sharelinks.jdbc.user", "otterworks"),
            System.getProperty("sharelinks.jdbc.password", ""));
    }

    static void closeQuietly(AutoCloseable... resources) {
        for (AutoCloseable r : resources) {
            if (r == null) {
                continue;
            }
            try {
                r.close();
            } catch (Exception ignored) {
                // nothing useful to do on close
            }
        }
    }
}

package com.bank.statements;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import javax.naming.InitialContext;
import javax.naming.NamingException;
import javax.sql.DataSource;
import org.postgresql.ds.PGSimpleDataSource;

public class StatementDao {
    private final DataSource ds;

    public StatementDao() {
        String url = System.getenv("JDBC_URL");
        if (url != null) {
            PGSimpleDataSource configured = new PGSimpleDataSource();
            configured.setURL(url);
            configured.setUser(requiredEnv("DB_USER"));
            configured.setPassword(requiredEnv("DB_PASSWORD"));
            ds = configured;
            return;
        }
        try {
            ds = (DataSource) new InitialContext().lookup("java:comp/env/jdbc/StatementsDB");
        } catch (NamingException e) {
            throw new IllegalStateException("datasource jdbc/StatementsDB not bound", e);
        }
    }

    private static String requiredEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isEmpty()) {
            throw new IllegalStateException(name + " is required");
        }
        return value;
    }

    public boolean healthy() throws SQLException {
        try (Connection c = ds.getConnection()) {
            return c.isValid(2);
        }
    }

    public StatementDao(DataSource ds) {
        this.ds = ds;
    }

    public Map<String, String> accounts() throws SQLException {
        Map<String, String> out = new LinkedHashMap<>();
        try (Connection c = ds.getConnection();
             PreparedStatement ps = c.prepareStatement("SELECT account_id, holder FROM accounts ORDER BY account_id");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                out.put(rs.getString(1), rs.getString(2));
            }
        }
        return out;
    }

    public List<StatementLine> lines(String accountId, int limit) throws SQLException {
        List<StatementLine> out = new ArrayList<>();
        try (Connection c = ds.getConnection();
             PreparedStatement ps = c.prepareStatement(
                 "SELECT booked, description, amount, balance FROM statement_lines WHERE account_id = ? ORDER BY booked, id LIMIT ?")) {
            ps.setString(1, accountId);
            ps.setInt(2, limit);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    out.add(new StatementLine(rs.getDate(1), rs.getString(2), rs.getBigDecimal(3), rs.getBigDecimal(4)));
                }
            }
        }
        return out;
    }
}

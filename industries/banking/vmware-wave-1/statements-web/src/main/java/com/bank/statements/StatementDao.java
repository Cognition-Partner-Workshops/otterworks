package com.bank.statements;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import javax.naming.InitialContext;
import javax.naming.NamingException;
import javax.sql.DataSource;

public class StatementDao {
    private final DataSource ds;

    public StatementDao() {
        try {
            ds = (DataSource) new InitialContext().lookup("java:comp/env/jdbc/StatementsDB");
        } catch (NamingException e) {
            throw new IllegalStateException("datasource jdbc/StatementsDB not bound", e);
        }
    }

    public StatementDao(DataSource ds) {
        this.ds = ds;
    }

    public Map<String, String> accounts(Set<String> allowed) throws SQLException {
        Map<String, String> out = new LinkedHashMap<>();
        if (allowed.isEmpty()) {
            return out;
        }
        String placeholders = String.join(",", Collections.nCopies(allowed.size(), "?"));
        try (Connection c = ds.getConnection();
             PreparedStatement ps = c.prepareStatement(
                 "SELECT account_id, holder FROM accounts WHERE account_id IN (" + placeholders + ") ORDER BY account_id")) {
            int index = 1;
            for (String account : allowed) {
                ps.setString(index++, account);
            }
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    out.put(rs.getString(1), rs.getString(2));
                }
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

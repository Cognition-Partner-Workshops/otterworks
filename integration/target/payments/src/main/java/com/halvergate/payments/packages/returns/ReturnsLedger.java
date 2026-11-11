package com.halvergate.payments.packages.returns;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.jdbc.core.JdbcTemplate;

/** Non-XA, auto-commit insert matching the legacy JDBC Update (commit mode AUTO_COMMIT). */
public class ReturnsLedger implements AutoCloseable {
    static final String INSERT =
        "INSERT INTO payment_returns (flow,request_id,account_id,amount,currency,status) VALUES (?,?,?,?,?,?)";
    private final HikariDataSource dataSource;
    private final JdbcTemplate jdbc;

    public ReturnsLedger(String url, String user, String password) {
        HikariConfig config = new HikariConfig();
        config.setPoolName("payment-returns");
        config.setJdbcUrl(url);
        config.setUsername(user);
        config.setPassword(password);
        config.setAutoCommit(true);
        config.setMaximumPoolSize(2);
        config.setInitializationFailTimeout(-1);
        this.dataSource = new HikariDataSource(config);
        this.jdbc = new JdbcTemplate(dataSource);
    }

    void ping() {
        jdbc.queryForObject("SELECT 1", Integer.class);
    }

    int insert(Object... values) {
        return jdbc.update(INSERT, values);
    }

    @Override
    public void close() {
        dataSource.close();
    }
}

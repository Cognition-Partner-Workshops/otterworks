package com.bank.statements;

import org.apache.tomcat.jdbc.pool.DataSource;
import org.apache.tomcat.jdbc.pool.PoolProperties;

/** Connection pool that replaces the jdbc/StatementsDB resource from the host's context.xml. */
final class Database {
    private Database() {
    }

    static DataSource create(AppConfig config) {
        PoolProperties p = new PoolProperties();
        p.setDriverClassName("org.postgresql.Driver");
        p.setUrl(config.dbUrl());
        p.setUsername(config.dbUser());
        p.setPassword(config.dbPassword());
        p.setMaxActive(20);
        p.setMaxIdle(5);
        p.setInitialSize(0);
        p.setMaxWait(10000);
        p.setValidationQuery("SELECT 1");
        p.setValidationQueryTimeout(2);
        p.setTestOnBorrow(true);
        return new DataSource(p);
    }
}

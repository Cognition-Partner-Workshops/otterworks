package com.otterworks.commission.common;

import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.LocalDateTime;

import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * Strangler fallback: until the rates group moves into this service, rate
 * resolution stays in Oracle and is read by calling COMMISSION_PKG.resolve_rate.
 * The rates group replaces this class with its own RateResolver.
 */
@Component
public class LegacyPackageRateResolver implements RateResolver {

    private final JdbcTemplate jdbc;

    public LegacyPackageRateResolver(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public long resolve(String productCode, Long agentId, LocalDateTime asOf) {
        try {
            Long id = jdbc.queryForObject(
                    "SELECT commission_pkg.resolve_rate(?, ?, ?) FROM dual", Long.class,
                    productCode, agentId, Timestamp.valueOf(asOf));
            return id;
        } catch (DataAccessException e) {
            if (e.getMostSpecificCause() instanceof SQLException sql) {
                throw OraErrorAdvice.fromSqlException(sql);
            }
            throw e;
        }
    }
}

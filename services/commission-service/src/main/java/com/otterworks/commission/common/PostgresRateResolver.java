package com.otterworks.commission.common;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/**
 * COMMISSION_PKG.resolve_rate on PostgreSQL, where there is no package to call:
 * the same query (agent-specific rate wins over the product default, latest
 * effective_from first, inclusive window) and the same ORA-20007 text.
 */
@Component
@Profile("postgres")
public class PostgresRateResolver implements RateResolver {

    static final String SQL = "SELECT rate_id FROM commission_rates"
            + " WHERE product_code = ? AND (agent_id = ? OR agent_id IS NULL)"
            + " AND effective_from <= ? AND (effective_to IS NULL OR effective_to >= ?)"
            + " ORDER BY agent_id NULLS LAST, effective_from DESC LIMIT 1";

    private final JdbcTemplate jdbc;

    public PostgresRateResolver(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Override
    public long resolve(String productCode, Long agentId, LocalDateTime asOf) {
        Timestamp ts = Timestamp.valueOf(asOf);
        List<Long> ids = jdbc.queryForList(SQL, Long.class, productCode, agentId, ts, ts);
        if (ids.isEmpty()) {
            throw new OraException(-20007, "No rate in force for " + productCode + "/agent "
                    + (agentId == null ? "default" : agentId.toString()) + " on " + asOf.toLocalDate());
        }
        return ids.get(0);
    }
}

package com.otterworks.commission.rates;

import java.math.BigDecimal;
import java.sql.PreparedStatement;
import java.sql.Timestamp;
import java.sql.Types;
import java.time.LocalDateTime;
import java.util.List;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.SqlParameterValue;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

/**
 * commission_rates access for the rates group. A rate scope is
 * (product_code, NVL(agent_id, -1)): agent_id NULL is the product default (R36).
 */
@Repository
public class RateRepository {

    private static final String SCOPE = " product_code = ? AND NVL(agent_id, -1) = NVL(?, -1)";

    private final JdbcTemplate jdbc;

    public RateRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** R5: amends the open rate of the scope that starts on effectiveFrom; its rate_id, or null if none. */
    public Long amendSameDay(String productCode, Long agentId, BigDecimal ratePct, LocalDateTime effectiveFrom,
            String actor) {
        int n = jdbc.update(
                "UPDATE commission_rates SET rate_pct = ?, created_by = ?"
                        + " WHERE" + SCOPE + " AND effective_to IS NULL AND effective_from = CAST(? AS DATE)",
                number(ratePct), text(actor), text(productCode), number(agentId), date(effectiveFrom));
        if (n == 0) {
            return null;
        }
        return jdbc.queryForObject(
                "SELECT rate_id FROM commission_rates"
                        + " WHERE" + SCOPE + " AND effective_to IS NULL AND effective_from = CAST(? AS DATE)",
                Long.class, text(productCode), number(agentId), date(effectiveFrom));
    }

    /** R6: closes the scope's open rate that started before effectiveFrom, at closeOn. */
    public int closeOpenStartedBefore(String productCode, Long agentId, LocalDateTime effectiveFrom,
            LocalDateTime closeOn) {
        return jdbc.update(
                "UPDATE commission_rates SET effective_to = CAST(? AS DATE)"
                        + " WHERE" + SCOPE + " AND effective_to IS NULL AND effective_from < CAST(? AS DATE)",
                date(closeOn), text(productCode), number(agentId), date(effectiveFrom));
    }

    /** R7: inserts a new open rate and returns its identity rate_id. */
    public long insertOpen(String productCode, Long agentId, BigDecimal ratePct, LocalDateTime effectiveFrom,
            String actor) {
        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO commission_rates"
                            + " (product_code, agent_id, rate_pct, effective_from, effective_to, created_by)"
                            + " VALUES (?, ?, ?, CAST(? AS DATE), NULL, ?)",
                    new String[] {"RATE_ID"});
            set(ps, 1, Types.VARCHAR, productCode);
            set(ps, 2, Types.NUMERIC, agentId);
            set(ps, 3, Types.NUMERIC, ratePct);
            set(ps, 4, Types.TIMESTAMP, effectiveFrom == null ? null : Timestamp.valueOf(effectiveFrom));
            set(ps, 5, Types.VARCHAR, actor);
            return ps;
        }, keys);
        return keys.getKey().longValue();
    }

    /** R10: closes every open rate of the scope at effectiveTo; the number of rows closed. */
    public int endOpen(String productCode, Long agentId, LocalDateTime effectiveTo) {
        return jdbc.update(
                "UPDATE commission_rates SET effective_to = CAST(? AS DATE)"
                        + " WHERE" + SCOPE + " AND effective_to IS NULL",
                date(effectiveTo), text(productCode), number(agentId));
    }

    /** R22: every rate of the product for the agent or the product default, unfiltered by date. */
    public List<RateRow> candidates(String productCode, Long agentId) {
        return jdbc.query(
                "SELECT rate_id, agent_id, effective_from, effective_to FROM commission_rates"
                        + " WHERE product_code = ? AND (agent_id = ? OR agent_id IS NULL)",
                (rs, i) -> new RateRow(
                        rs.getLong("rate_id"),
                        rs.getObject("agent_id") == null ? null : rs.getLong("agent_id"),
                        toLocal(rs.getTimestamp("effective_from")),
                        toLocal(rs.getTimestamp("effective_to"))),
                text(productCode), number(agentId));
    }

    private static LocalDateTime toLocal(Timestamp ts) {
        return ts == null ? null : ts.toLocalDateTime();
    }

    private static void set(PreparedStatement ps, int i, int type, Object value) throws java.sql.SQLException {
        if (value == null) {
            ps.setNull(i, type);
        } else {
            ps.setObject(i, value, type);
        }
    }

    private static SqlParameterValue text(String s) {
        return new SqlParameterValue(Types.VARCHAR, s);
    }

    private static SqlParameterValue number(Object n) {
        return new SqlParameterValue(Types.NUMERIC, n);
    }

    private static SqlParameterValue date(LocalDateTime d) {
        return new SqlParameterValue(Types.TIMESTAMP, d == null ? null : Timestamp.valueOf(d));
    }
}

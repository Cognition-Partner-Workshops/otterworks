package com.otterworks.commission.screens;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.ConnectionCallback;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/**
 * Read-only queries behind the Commission Pay screens. The SQL is the same on
 * Oracle and PostgreSQL; nothing here writes.
 */
@Repository
public class ScreensRepository {

    public record Agent(long agentId, String agentCode, String fullName, String status) {
    }

    /** One ledger row; calculatedBy is the actor of the latest COMMISSION_CALC audit row for the policy and period. */
    public record StatementRow(long ledgerId, long policyId, String policyNo, String productCode,
            BigDecimal annualPremium, long rateId, BigDecimal ratePct, BigDecimal splitPct,
            BigDecimal commission, LocalDateTime calculatedAt, String calculatedBy) {
    }

    public record RateRow(long rateId, String productCode, Long agentId, String agentCode, BigDecimal ratePct,
            LocalDate effectiveFrom, LocalDate effectiveTo) {
    }

    public record Database(String product, String url) {
    }

    static final String STATEMENT_SQL = "SELECT l.ledger_id, l.policy_id, p.policy_no, p.product_code,"
            + " l.base_premium, l.rate_id, r.rate_pct, l.split_pct, l.commission_amt, l.calculated_at,"
            + " (SELECT a.actor FROM rate_audit_log a WHERE a.audit_id ="
            + "   (SELECT MAX(b.audit_id) FROM rate_audit_log b WHERE b.action = 'COMMISSION_CALC'"
            + "     AND b.policy_id = l.policy_id AND b.detail LIKE l.period_month || ' %')) AS calculated_by"
            + " FROM commission_ledger l"
            + " JOIN policies p ON p.policy_id = l.policy_id"
            + " JOIN commission_rates r ON r.rate_id = l.rate_id"
            + " WHERE l.agent_id = ? AND l.period_month = ?"
            + " ORDER BY p.policy_no";

    static final String RATES_SQL = "SELECT r.rate_id, r.product_code, r.agent_id, a.agent_code, r.rate_pct,"
            + " r.effective_from, r.effective_to"
            + " FROM commission_rates r LEFT JOIN agents a ON a.agent_id = r.agent_id"
            + " WHERE r.agent_id = ? OR r.agent_id IS NULL"
            + " ORDER BY r.product_code, r.agent_id NULLS FIRST, r.effective_from, r.rate_id";

    private final JdbcTemplate jdbc;

    public ScreensRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Agent> findAgent(long agentId) {
        return jdbc.query("SELECT agent_id, agent_code, full_name, status FROM agents WHERE agent_id = ?",
                (rs, i) -> new Agent(rs.getLong(1), rs.getString(2), rs.getString(3), rs.getString(4)), agentId)
                .stream().findFirst();
    }

    public List<StatementRow> statement(long agentId, String periodMonth) {
        return jdbc.query(STATEMENT_SQL, (rs, i) -> new StatementRow(rs.getLong(1), rs.getLong(2), rs.getString(3),
                rs.getString(4), rs.getBigDecimal(5), rs.getLong(6), rs.getBigDecimal(7), rs.getBigDecimal(8),
                rs.getBigDecimal(9), toDateTime(rs.getTimestamp(10)), rs.getString(11)), agentId, periodMonth);
    }

    public List<RateRow> rateHistory(long agentId) {
        return jdbc.query(RATES_SQL, (rs, i) -> new RateRow(rs.getLong(1), rs.getString(2),
                (Long) rs.getObject(3) == null ? null : rs.getLong(3), rs.getString(4), rs.getBigDecimal(5),
                toDate(rs.getTimestamp(6)), toDate(rs.getTimestamp(7))), agentId);
    }

    public Database database() {
        return jdbc.execute((ConnectionCallback<Database>) c -> {
            String version = c.getMetaData().getDatabaseProductVersion();
            int nl = version.indexOf('\n');
            return new Database(c.getMetaData().getDatabaseProductName() + " "
                    + (nl < 0 ? version : version.substring(0, nl)), c.getMetaData().getURL());
        });
    }

    private static LocalDateTime toDateTime(Timestamp ts) {
        return ts == null ? null : ts.toLocalDateTime();
    }

    private static LocalDate toDate(Timestamp ts) {
        return ts == null ? null : ts.toLocalDateTime().toLocalDate();
    }
}

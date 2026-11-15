package com.otterworks.commission.calculation;

import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/** Reads and writes of calculate_policy_commission on policies, splits, rates and the ledger. */
@Repository
public class CalculationRepository {

    public record Policy(BigDecimal policyId, String productCode, BigDecimal annualPremium, String status) {
    }

    public record Split(long agentId, BigDecimal splitPct) {
    }

    private final JdbcTemplate jdbc;

    public CalculationRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public Optional<Policy> findPolicy(BigDecimal policyId) {
        List<Policy> rows = jdbc.query(
                "SELECT policy_id, product_code, annual_premium, status FROM policies WHERE policy_id = ?",
                (rs, i) -> new Policy(rs.getBigDecimal(1), rs.getString(2), rs.getBigDecimal(3), rs.getString(4)),
                policyId);
        return rows.stream().findFirst();
    }

    /**
     * LAST_DAY(TO_DATE(p_period_month, 'YYYY-MM')), evaluated by Oracle so the
     * accepted inputs and the error (e.g. ORA-01843) are Oracle's own.
     */
    public LocalDateTime lastDayOfPeriod(String periodMonth) {
        Timestamp ts = jdbc.queryForObject(
                "SELECT LAST_DAY(TO_DATE(?, 'YYYY-MM')) FROM dual", Timestamp.class, periodMonth);
        return ts == null ? null : ts.toLocalDateTime();
    }

    public int deleteLedger(BigDecimal policyId, String periodMonth) {
        return jdbc.update(
                "DELETE FROM commission_ledger WHERE policy_id = ? AND period_month = ?", policyId, periodMonth);
    }

    public List<Split> splitsInOrder(BigDecimal policyId) {
        return jdbc.query(
                "SELECT agent_id, split_pct FROM commission_splits WHERE policy_id = ?"
                        + " ORDER BY split_pct DESC, agent_id",
                (rs, i) -> new Split(rs.getLong(1), rs.getBigDecimal(2)),
                policyId);
    }

    public BigDecimal ratePct(long rateId) {
        return jdbc.queryForObject(
                "SELECT rate_pct FROM commission_rates WHERE rate_id = ?", BigDecimal.class, rateId);
    }

    public void insertLedger(BigDecimal policyId, long agentId, String periodMonth, long rateId,
            BigDecimal splitPct, BigDecimal basePremium, BigDecimal commissionAmt) {
        jdbc.update(
                "INSERT INTO commission_ledger (policy_id, agent_id, period_month, rate_id, split_pct,"
                        + " base_premium, commission_amt) VALUES (?, ?, ?, ?, ?, ?, ?)",
                policyId, agentId, periodMonth, rateId, splitPct, basePremium, commissionAmt);
    }
}

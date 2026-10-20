package com.otterworks.commission.common;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

/**
 * COMMISSION_PKG.log_action: one rate_audit_log row per change. The row belongs
 * to the rule's transaction (auto-commit is off), so a caller without one fails.
 */
@Component
public class AuditLog {

    private final JdbcTemplate jdbc;

    public AuditLog(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void log(String action, String productCode, Long agentId, Long policyId, String detail, String actor) {
        jdbc.update(
                "INSERT INTO rate_audit_log (action, product_code, agent_id, policy_id, detail, actor)"
                        + " VALUES (?, ?, ?, ?, ?, ?)",
                action, productCode, agentId, policyId, detail, actor);
    }
}

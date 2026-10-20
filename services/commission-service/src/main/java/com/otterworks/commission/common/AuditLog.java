package com.otterworks.commission.common;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** COMMISSION_PKG.log_action: one rate_audit_log row per change. */
@Component
public class AuditLog {

    private final JdbcTemplate jdbc;

    public AuditLog(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void log(String action, String productCode, Long agentId, Long policyId, String detail, String actor) {
        jdbc.update(
                "INSERT INTO rate_audit_log (action, product_code, agent_id, policy_id, detail, actor)"
                        + " VALUES (?, ?, ?, ?, ?, ?)",
                action, productCode, agentId, policyId, detail, actor);
    }
}

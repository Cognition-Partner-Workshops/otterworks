package com.otterworks.commission.common;

import java.util.List;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

/** COMMISSION_PKG.assert_product and assert_active_agent, shared by several rule groups. */
@Component
public class Guards {

    private final JdbcTemplate jdbc;

    public Guards(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public void assertProduct(String productCode) {
        Integer n = jdbc.queryForObject(
                "SELECT COUNT(*) FROM products WHERE product_code = ?", Integer.class, productCode);
        if (n == null || n == 0) {
            throw new OraException(-20004, "Unknown product: " + (productCode == null ? "" : productCode));
        }
    }

    public void assertActiveAgent(Long agentId) {
        List<String> status = jdbc.queryForList(
                "SELECT status FROM agents WHERE agent_id = ?", String.class, agentId);
        if (status.isEmpty()) {
            throw new OraException(-20002, "Unknown agent: " + OracleText.toChar(agentId));
        }
        if (!"ACTIVE".equals(status.get(0))) {
            throw new OraException(-20003, "Agent " + OracleText.toChar(agentId) + " is " + status.get(0));
        }
    }
}

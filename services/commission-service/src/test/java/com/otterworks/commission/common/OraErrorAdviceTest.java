package com.otterworks.commission.common;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.SQLException;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.UncategorizedSQLException;

class OraErrorAdviceTest {

    private final OraErrorAdvice advice = new OraErrorAdvice();

    @Test
    void ruleRejectionKeepsCodeAndMessage() {
        ResponseEntity<Map<String, Object>> r = advice.rule(new OraException(-20003, "Agent 4 is SUSPENDED"));
        assertThat(r.getStatusCode().value()).isEqualTo(422);
        assertThat(r.getBody()).containsEntry("ora_code", -20003).containsEntry("message", "Agent 4 is SUSPENDED");
    }

    @Test
    void databaseErrorReportsOracleCodeAndFirstLine() {
        SQLException sql = new SQLException(
                "ORA-02290: check constraint (COMMISSION_PAY.CK_RATES_RANGE) violated\n\n"
                        + "https://docs.oracle.com/error-help/db/ora-02290/", "23000", 2290);
        ResponseEntity<Map<String, Object>> r = advice.database(new UncategorizedSQLException("x", "sql", sql));
        assertThat(r.getBody())
                .containsEntry("ora_code", -2290)
                .containsEntry("message", "check constraint (COMMISSION_PAY.CK_RATES_RANGE) violated");
    }
}

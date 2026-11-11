package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.Assume;

class SnowflakeWarehouse implements ContractWarehouse {
    static final String DATABASE = "SFX_D1110_AFTER";
    static final String SCHEMA = "COMPAT";
    static final String QUERY_TAG =
            "{\"run\":\"sfx-d1110\",\"act\":\"consumers\",\"consumer\":\"report-service\"}";

    @Override
    public JsonNode execute(String sql, int period) {
        for (String key : new String[]{"ACCOUNT", "USER", "ROLE", "WAREHOUSE", "PRIVATE_KEY"}) {
            String value = System.getenv("SNOWFLAKE_" + key);
            Assume.assumeTrue("Missing SNOWFLAKE_" + key, value != null && !value.isEmpty());
        }
        throw new UnsupportedOperationException("Snowflake JDBC adapter not installed; execute the supplied DAL SQL "
                + "in " + DATABASE + "." + SCHEMA + " with session QUERY_TAG=" + QUERY_TAG);
    }
}

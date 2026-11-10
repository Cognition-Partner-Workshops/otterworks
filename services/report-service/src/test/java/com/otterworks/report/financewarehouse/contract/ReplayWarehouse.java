package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.financewarehouse.TeradataFinanceWarehouse;
import com.otterworks.report.financewarehouse.SnowflakeFinanceWarehouse;

import java.io.File;

class ReplayWarehouse implements ContractWarehouse {
    static String queryName(String sql) {
        if (TeradataFinanceWarehouse.SQL.equals(sql) || SnowflakeFinanceWarehouse.SQL.equals(sql)) {
            return "finance-reconciliation";
        }
        if (TeradataFinanceWarehouse.UNRECONCILED_SQL.equals(sql)
                || SnowflakeFinanceWarehouse.UNRECONCILED_SQL.equals(sql)) {
            return "unreconciled-invoices";
        }
        throw new IllegalArgumentException("Unknown contract SQL");
    }

    @Override
    public JsonNode execute(String sql, int period) throws Exception {
        return new ObjectMapper().readTree(new File("contract/recorded/teradata/" + queryName(sql) + ".json"));
    }
}

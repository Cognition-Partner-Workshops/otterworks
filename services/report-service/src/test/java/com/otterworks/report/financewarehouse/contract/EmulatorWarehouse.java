package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.financewarehouse.TeradataFinanceWarehouse;

import java.io.File;

class EmulatorWarehouse implements ContractWarehouse {
    @Override
    public JsonNode execute(String sql, int period) throws Exception {
        if (System.getenv("TD_EMULATOR_URL") != null) {
            return executeEndpoint(System.getenv("TD_EMULATOR_URL"), sql, period);
        }
        String query;
        if (TeradataFinanceWarehouse.SQL.equals(sql)) {
            query = "finance-reconciliation";
        } else if (TeradataFinanceWarehouse.UNRECONCILED_SQL.equals(sql)) {
            query = "unreconciled-invoices";
        } else {
            throw new IllegalArgumentException("Unknown contract SQL");
        }
        return new ObjectMapper().readTree(new File("contract/recorded/teradata/" + query + ".json"));
    }

    private JsonNode executeEndpoint(String endpoint, String sql, int period) {
        throw new UnsupportedOperationException("emulator endpoint not configured");
    }
}

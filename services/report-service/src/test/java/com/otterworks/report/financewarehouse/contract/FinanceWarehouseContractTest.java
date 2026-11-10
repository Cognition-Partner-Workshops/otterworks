package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.financewarehouse.TeradataFinanceWarehouse;
import org.junit.Test;

import java.io.File;
import java.math.BigDecimal;
import java.util.Iterator;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class FinanceWarehouseContractTest {
    @Test
    public void reconciliationMatchesRecordedContract() throws Exception {
        assertContract(TeradataFinanceWarehouse.SQL, "finance-reconciliation");
    }

    @Test
    public void unreconciledInvoicesMatchRecordedContract() throws Exception {
        assertContract(TeradataFinanceWarehouse.UNRECONCILED_SQL, "unreconciled-invoices");
    }

    private void assertContract(String sql, String query) throws Exception {
        String target = System.getenv("WAREHOUSE_CONTRACT_TARGET");
        ContractWarehouse warehouse;
        if (target == null || "teradata-emulator".equals(target)) {
            warehouse = new EmulatorWarehouse();
        } else if ("snowflake".equals(target)) {
            warehouse = new SnowflakeWarehouse();
        } else {
            throw new IllegalArgumentException("Unknown WAREHOUSE_CONTRACT_TARGET: " + target);
        }
        JsonNode actual = warehouse.execute(sql, 202601);
        JsonNode expected = new ObjectMapper().readTree(new File("contract/expected/" + query + ".json"));
        assertEquals(expected.get("query"), actual.get("query"));
        assertEquals(expected.get("row_count").asInt(), actual.get("rows").size());
        if (expected.has("keys")) {
            for (int i = 0; i < expected.get("keys").size(); i++) {
                assertEquals(expected.get("keys").get(i).asText(), actual.get("rows").get(i).get(0).asText());
            }
        }
        Iterator<Map.Entry<String, JsonNode>> sums = expected.get("sums").fields();
        while (sums.hasNext()) {
            Map.Entry<String, JsonNode> sum = sums.next();
            int column = -1;
            for (int i = 0; i < actual.get("columns").size(); i++) {
                if (sum.getKey().equals(actual.get("columns").get(i).asText())) {
                    column = i;
                }
            }
            assertTrue("Missing column " + sum.getKey(), column >= 0);
            BigDecimal total = BigDecimal.ZERO;
            for (JsonNode row : actual.get("rows")) {
                total = total.add(new BigDecimal(row.get(column).asText()));
            }
            assertEquals(sum.getKey(), 0, total.compareTo(new BigDecimal(sum.getValue().asText())));
        }
    }
}

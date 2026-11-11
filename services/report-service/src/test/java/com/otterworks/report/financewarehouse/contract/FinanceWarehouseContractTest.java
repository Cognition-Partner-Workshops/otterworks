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
    /** As-of date for CURRENT_DATE logic on every path: the seeded business date 20261109. */
    static final String AS_OF = "2026-11-09";

    @Test
    public void reconciliationMatchesRecordedContract() throws Exception {
        assertContract(TeradataFinanceWarehouse.SQL, "finance-reconciliation", 202611);
    }

    @Test
    public void unreconciledInvoicesMatchRecordedContract() throws Exception {
        assertContract(TeradataFinanceWarehouse.UNRECONCILED_SQL, "unreconciled-invoices", 202601);
    }

    private void assertContract(String sql, String query, int period) throws Exception {
        String target = System.getenv("WAREHOUSE_CONTRACT_TARGET");
        ContractWarehouse warehouse;
        if (target == null || "teradata-emulator".equals(target)) {
            warehouse = new EmulatorWarehouse("teradata-emulator");
        } else if ("snowflake-semantics".equals(target)) {
            warehouse = new EmulatorWarehouse(target);
        } else if ("replay".equals(target)) {
            warehouse = new ReplayWarehouse();
        } else if ("databricks".equals(target)) {
            warehouse = new DatabricksWarehouse();
        } else if ("snowflake".equals(target)) {
            warehouse = new SnowflakeWarehouse();
        } else {
            throw new IllegalArgumentException("Unknown WAREHOUSE_CONTRACT_TARGET: " + target);
        }
        JsonNode actual = warehouse.execute(sql, period);
        if ("databricks".equals(target) && "true".equals(System.getenv("CONTRACT_COMPARE_OLDPATH"))) {
            JsonNode oldPath = new EmulatorWarehouse("teradata-emulator").execute(sql, period);
            if ("true".equals(System.getenv("CONTRACT_SHOW"))) {
                System.out.println("OLD PATH (teradata-emulator) " + query + ": " + oldPath.get("rows"));
                System.out.println("NEW PATH (databricks)        " + query + ": " + actual.get("rows"));
            }
            assertSameResult(oldPath, actual);
        }
        JsonNode expected = new ObjectMapper().readTree(new File(System.getenv().getOrDefault("CONTRACT_EXPECTED_DIR", "contract/expected") + "/" + query + ".json"));
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

    /** Old read path vs new read path on the same data: same columns, same ordered rows, numeric-equal values. */
    static void assertSameResult(JsonNode oldPath, JsonNode newPath) {
        assertEquals(oldPath.get("columns"), newPath.get("columns"));
        assertEquals("row count", oldPath.get("rows").size(), newPath.get("rows").size());
        for (int r = 0; r < oldPath.get("rows").size(); r++) {
            for (int c = 0; c < oldPath.get("columns").size(); c++) {
                JsonNode before = oldPath.get("rows").get(r).get(c);
                JsonNode after = newPath.get("rows").get(r).get(c);
                String where = "row " + r + " " + oldPath.get("columns").get(c).asText();
                if (before.isNull() || after.isNull()) {
                    assertEquals(where, before.isNull(), after.isNull());
                } else if (isNumber(before.asText()) && isNumber(after.asText())) {
                    assertEquals(where, 0, new BigDecimal(before.asText()).compareTo(new BigDecimal(after.asText())));
                } else {
                    assertEquals(where, before.asText(), after.asText());
                }
            }
        }
    }

    private static boolean isNumber(String value) {
        return value.matches("-?\\d+(\\.\\d+)?");
    }
}

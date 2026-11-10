package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.otterworks.report.financewarehouse.TeradataFinanceWarehouse;
import com.otterworks.report.financewarehouse.SnowflakeFinanceWarehouse;
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
        assertContract(TeradataFinanceWarehouse.SQL, "finance-reconciliation", 202611);
    }

    @Test
    public void unreconciledInvoicesMatchRecordedContract() throws Exception {
        assertContract(TeradataFinanceWarehouse.UNRECONCILED_SQL, "unreconciled-invoices", 202601);
    }

    private void assertSnowflake(JsonNode actual, String query, int period, SnowflakeWarehouse warehouse)
            throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        JsonNode replay = new ReplayWarehouse().execute(
                "finance-reconciliation".equals(query) ? TeradataFinanceWarehouse.SQL
                        : TeradataFinanceWarehouse.UNRECONCILED_SQL, period);
        assertEquals(query, actual.get("query").asText());
        assertEquals(replay.get("columns"), actual.get("columns"));
        boolean reconciliation = "finance-reconciliation".equals(query);
        assertTrue(actual.get("rows").size() <= (reconciliation ? 1 : 25));
        if (reconciliation) {
            assertEquals(1, actual.get("rows").size());
        }
        int previousDays = Integer.MAX_VALUE;
        long previousId = Long.MIN_VALUE;
        for (JsonNode row : actual.get("rows")) {
            assertEquals(actual.get("columns").size(), row.size());
            for (int i = 0; i < row.size(); i++) {
                String column = actual.get("columns").get(i).asText();
                if ("PERIOD_ID".equals(column) || "DAYS_OVERDUE".equals(column)) {
                    assertTrue(column, row.get(i).isIntegralNumber());
                } else if ("INVOICE_DATE".equals(column)) {
                    assertTrue(row.get(i).isTextual());
                    assertEquals(row.get(i).asText(), java.time.LocalDate.parse(row.get(i).asText()).toString());
                } else if (column.endsWith("_NUMBER")) {
                    assertTrue(row.get(i).isTextual());
                } else {
                    assertTrue(column, row.get(i).isTextual() && row.get(i).asText().matches("-?\\d+\\.\\d{2}"));
                }
            }
            if (reconciliation) {
                assertEquals(period, row.get(0).asInt());
                BigDecimal variance = decimal(row, 1).subtract(decimal(row, 2)).subtract(decimal(row, 3));
                assertEquals(0, variance.compareTo(decimal(row, 4)));
            } else {
                int days = row.get(3).asInt();
                Long id = warehouse.invoiceIds.get(row.get(0).asText());
                assertTrue("Missing invoice ID", id != null);
                assertTrue("Ordering", days < previousDays || (days == previousDays && id > previousId));
                previousDays = days;
                previousId = id;
                assertTrue(decimal(row, 5).compareTo(decimal(row, 4)) < 0);
                for (JsonNode recorded : replay.get("rows")) {
                    if (recorded.get(0).equals(row.get(0))) {
                        assertEquals(recorded.get(1), row.get(1));
                        assertEquals(recorded.get(2), row.get(2));
                        assertEquals(0, decimal(recorded, 5).compareTo(decimal(row, 5)));
                    }
                }
            }
        }
        File baselineFile = new File("contract/recorded/snowflake/" + query + ".json");
        if ("true".equals(System.getenv("SNOWFLAKE_CONTRACT_RECORD"))) {
            mapper.writerWithDefaultPrettyPrinter().writeValue(baselineFile, actual);
        }
        JsonNode baseline = mapper.readTree(baselineFile);
        assertEquals(baseline.get("query"), actual.get("query"));
        assertEquals(baseline.get("columns"), actual.get("columns"));
        assertEquals(baseline.get("rows").size(), actual.get("rows").size());
        for (int r = 0; r < baseline.get("rows").size(); r++) {
            for (int c = 0; c < baseline.get("columns").size(); c++) {
                if (!"DAYS_OVERDUE".equals(baseline.get("columns").get(c).asText())) {
                    assertEquals(baseline.get("rows").get(r).get(c), actual.get("rows").get(r).get(c));
                }
            }
        }
    }

    private BigDecimal decimal(JsonNode row, int column) {
        return new BigDecimal(row.get(column).asText());
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
        } else if ("snowflake".equals(target)) {
            warehouse = new SnowflakeWarehouse();
            sql = "finance-reconciliation".equals(query)
                    ? SnowflakeFinanceWarehouse.SQL : SnowflakeFinanceWarehouse.UNRECONCILED_SQL;
        } else {
            throw new IllegalArgumentException("Unknown WAREHOUSE_CONTRACT_TARGET: " + target);
        }
        JsonNode actual = warehouse.execute(sql, period);
        if ("snowflake".equals(target)) {
            assertSnowflake(actual, query, period, (SnowflakeWarehouse) warehouse);
            return;
        }
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

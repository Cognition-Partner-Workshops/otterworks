package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.otterworks.report.financewarehouse.FinanceWarehouseConfig;
import net.snowflake.client.jdbc.SnowflakeStatement;
import org.junit.Assume;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.util.HashMap;
import java.util.Map;

class SnowflakeWarehouse implements ContractWarehouse {
    final Map<String, Long> invoiceIds = new HashMap<>();
    @Override
    public JsonNode execute(String sql, int period) throws Exception {
        for (String key : new String[]{"ACCOUNT", "USER", "ROLE", "PRIVATE_KEY"}) {
            String value = System.getenv("SNOWFLAKE_" + key);
            Assume.assumeTrue("Missing SNOWFLAKE_" + key, value != null && !value.isEmpty());
        }
        try (Connection connection = FinanceWarehouseConfig.dataSource(
                System.getenv("SNOWFLAKE_ACCOUNT"), System.getenv("SNOWFLAKE_USER"),
                System.getenv("SNOWFLAKE_ROLE"), System.getenv("SNOWFLAKE_PRIVATE_KEY"),
                "SFX_D1110_PARITY_WH").getConnection();
                PreparedStatement statement = connection.prepareStatement(sql)) {
            int count = "finance-reconciliation".equals(ReplayWarehouse.queryName(sql)) ? 4 : 1;
            for (int i = 1; i <= count; i++) {
                statement.setInt(i, period);
            }
            ObjectNode result = new ObjectMapper().createObjectNode();
            result.put("query", ReplayWarehouse.queryName(sql));
            ArrayNode columns = result.putArray("columns");
            ArrayNode rows = result.putArray("rows");
            try (ResultSet records = statement.executeQuery()) {
                System.out.println("Snowflake query ID: "
                        + statement.unwrap(SnowflakeStatement.class).getQueryID());
                ResultSetMetaData metadata = records.getMetaData();
                for (int i = 1; i <= metadata.getColumnCount(); i++) {
                    columns.add(metadata.getColumnLabel(i).toUpperCase(java.util.Locale.ROOT));
                }
                while (records.next()) {
                    ArrayNode row = rows.addArray();
                    for (int i = 1; i <= metadata.getColumnCount(); i++) {
                        Object value = records.getObject(i);
                        if (value == null) {
                            row.addNull();
                        } else if ("PERIOD_ID".equals(metadata.getColumnLabel(i))
                                || "DAYS_OVERDUE".equals(metadata.getColumnLabel(i))) {
                            row.add(records.getInt(i));
                        } else if (value instanceof Number) {
                            row.add(new BigDecimal(value.toString()).setScale(2).toPlainString());
                        } else {
                            row.add(value.toString());
                        }
                    }
                }
            }
            if ("unreconciled-invoices".equals(ReplayWarehouse.queryName(sql))) {
                try (PreparedStatement ids = connection.prepareStatement(
                        "SELECT INVOICE_NUMBER, INVOICE_ID FROM SFX_D1110_AFTER.COMPAT.INVOICE_HDR "
                        + "WHERE EXTRACT(YEAR FROM INVOICE_DT) * 100 + EXTRACT(MONTH FROM INVOICE_DT) = ?")) {
                    ids.setInt(1, period);
                    try (ResultSet records = ids.executeQuery()) {
                        System.out.println("Snowflake invoice-order query ID: "
                                + ids.unwrap(SnowflakeStatement.class).getQueryID());
                        while (records.next()) {
                            invoiceIds.put(records.getString(1), records.getLong(2));
                        }
                    }
                }
            }
            return result;
        }
    }
}

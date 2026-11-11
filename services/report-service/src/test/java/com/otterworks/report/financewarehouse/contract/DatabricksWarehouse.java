package com.otterworks.report.financewarehouse.contract;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.otterworks.report.financewarehouse.DatabricksFinanceWarehouse;
import com.otterworks.report.financewarehouse.DatabricksReadPath;
import com.otterworks.report.financewarehouse.TeradataFinanceWarehouse;
import org.junit.Assume;

import java.math.BigDecimal;
import java.sql.Connection;
import java.sql.Date;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.Types;

/** Live target: the consumer's native Databricks SQL against cpw.dbx_d1111_after over JDBC. */
class DatabricksWarehouse implements ContractWarehouse {
    @Override
    public JsonNode execute(String teradataSql, int period) throws Exception {
        for (String key : new String[]{"DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID"}) {
            String value = System.getenv(key);
            Assume.assumeTrue("Skipping live Databricks contract: missing " + key, value != null && !value.isEmpty());
        }
        String query = ReplayWarehouse.queryName(teradataSql);
        String step = System.getenv().getOrDefault("CONTRACT_STEP", "contract");
        boolean verbatim = "teradata".equals(System.getenv("CONTRACT_DATABRICKS_SQL"));
        String sql;
        Object[] binds;
        Date asOf = Date.valueOf(FinanceWarehouseContractTest.AS_OF);
        if (verbatim) {
            sql = teradataSql;
            binds = TeradataFinanceWarehouse.SQL.equals(teradataSql)
                    ? new Object[]{period, period, period, period} : new Object[]{period};
        } else if (TeradataFinanceWarehouse.SQL.equals(teradataSql)) {
            sql = DatabricksFinanceWarehouse.SQL;
            binds = new Object[]{period, period, period, period};
        } else {
            sql = DatabricksFinanceWarehouse.UNRECONCILED_SQL;
            binds = new Object[]{asOf, asOf, period};
        }
        try (Connection connection = DatabricksReadPath.connect();
             PreparedStatement statement = connection.prepareStatement(
                     DatabricksReadPath.tagged(step, "-- query=" + query + "\n" + sql))) {
            for (int i = 0; i < binds.length; i++) {
                statement.setObject(i + 1, binds[i]);
            }
            try (ResultSet rs = statement.executeQuery()) {
                return toJson(query, rs);
            }
        }
    }

    static JsonNode toJson(String query, ResultSet rs) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        ObjectNode result = mapper.createObjectNode();
        result.put("query", query);
        ArrayNode columns = result.putArray("columns");
        ResultSetMetaData meta = rs.getMetaData();
        for (int i = 1; i <= meta.getColumnCount(); i++) {
            columns.add(meta.getColumnLabel(i).toUpperCase());
        }
        ArrayNode rows = result.putArray("rows");
        while (rs.next()) {
            ArrayNode row = rows.addArray();
            for (int i = 1; i <= meta.getColumnCount(); i++) {
                Object value = rs.getObject(i);
                int type = meta.getColumnType(i);
                if (value == null) {
                    row.addNull();
                } else if (type == Types.DECIMAL || type == Types.NUMERIC) {
                    row.add(((BigDecimal) value).toPlainString());
                } else if (type == Types.INTEGER || type == Types.BIGINT || type == Types.SMALLINT) {
                    row.add(((Number) value).longValue());
                } else {
                    row.add(value.toString());
                }
            }
        }
        return result;
    }
}

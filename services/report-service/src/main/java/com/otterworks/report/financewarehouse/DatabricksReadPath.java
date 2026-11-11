package com.otterworks.report.financewarehouse;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.Properties;

/** Live JDBC transport. The migration owns SQL conversion and the consumer contract. */
public final class DatabricksReadPath {
    private DatabricksReadPath() { }

    public static Connection connect() throws SQLException {
        String host = required("DATABRICKS_HOST").replaceFirst("^https://", "").replaceAll("/$", "");
        String warehouse = required("DATABRICKS_WAREHOUSE_ID");
        if (!host.matches("[a-zA-Z0-9.-]+\\.databricks\\.com") || !warehouse.matches("[a-f0-9]+")) {
            throw new IllegalArgumentException("Invalid Databricks endpoint");
        }
        Properties properties = new Properties();
        properties.setProperty("UID", "token");
        properties.setProperty("PWD", required("DATABRICKS_TOKEN"));
        return DriverManager.getConnection("jdbc:databricks://" + host + ":443/default;transportMode=http;"
                + "ssl=1;AuthMech=3;httpPath=/sql/1.0/warehouses/" + warehouse
                + ";ConnCatalog=cpw;ConnSchema=dbx_d1111_after", properties);
    }

    public static String tagged(String nativeSql) {
        return tagged("contract", nativeSql);
    }

    public static String tagged(String step, String nativeSql) {
        if (!step.matches("[a-z0-9-]+")) {
            throw new IllegalArgumentException("Invalid step tag");
        }
        return "/* run=dbx-d1111 act=consumers step=" + step + " consumer=report-service */\n" + nativeSql;
    }

    private static String required(String key) {
        String value = System.getenv(key);
        if (value == null || value.isEmpty()) {
            throw new IllegalStateException("Missing " + key);
        }
        return value;
    }
}

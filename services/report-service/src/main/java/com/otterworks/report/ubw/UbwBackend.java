package com.otterworks.report.ubw;

import java.util.Locale;

/** Which Usage & Billing Warehouse the UBW reports read: the legacy SQL Server or Snowflake. */
public enum UbwBackend {
    SQLSERVER,
    SNOWFLAKE;

    public static UbwBackend parse(String value) {
        String normalised = value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
        if (normalised.isEmpty() || "sqlserver".equals(normalised)) {
            return SQLSERVER;
        }
        if ("snowflake".equals(normalised)) {
            return SNOWFLAKE;
        }
        throw new IllegalArgumentException("Unknown UBW_BACKEND: " + value + " (expected sqlserver or snowflake)");
    }

    public String label() {
        return name().toLowerCase(Locale.ROOT);
    }
}

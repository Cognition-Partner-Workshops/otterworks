package com.otterworks.report.ubw;

import org.junit.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

public class UbwReportCatalogTest {

    private final UbwReportCatalog catalog = new UbwReportCatalog();

    @Test
    public void holdsAllThirtyReportsWithBothQueries() {
        assertThat(catalog.all()).hasSize(30);
        for (UbwReportCatalog.Report report : catalog.all()) {
            assertThat(report.sqlserver.source).matches("(mart|fact)\\.\\w+");
            assertThat(report.snowflake.source).isEqualTo("REPORTS." + report.name.toUpperCase());
            assertThat(report.snowflake.query).contains("FROM REPORTS." + report.name.toUpperCase());
            assertThat(report.sqlserver.parameters).contains("BusinessDate");
            assertThat(report.snowflake.parameters).first().isEqualTo("BusinessDate");
        }
    }

    @Test
    public void planTierSummaryKeepsItsTierParameterOnBothBackends() {
        UbwReportCatalog.Report report = catalog.find("rpt_plan_tier_summary").get();
        assertThat(report.defaultFor("PlanTier")).isEqualTo("Growth");
        assertThat(report.queryFor(UbwBackend.SQLSERVER).parameters).containsExactly("BusinessDate", "PlanTier");
        assertThat(report.queryFor(UbwBackend.SNOWFLAKE).parameters).containsExactly("BusinessDate", "PlanTier");
        assertThat(report.queryFor(UbwBackend.SNOWFLAKE).query).endsWith("ORDER BY plan_tier");
    }

    @Test
    public void backendParsesTheTwoSupportedValues() {
        assertThat(UbwBackend.parse(null)).isEqualTo(UbwBackend.SQLSERVER);
        assertThat(UbwBackend.parse(" Snowflake ")).isEqualTo(UbwBackend.SNOWFLAKE);
        assertThatThrownBy(() -> UbwBackend.parse("oracle")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    public void snowflakeObjectsFollowTheRunToken() {
        assertThat(UbwDataSources.prefix("sfm-20261013-lv")).isEqualTo("OW_UBW_SFM_20261013_LV");
        assertThatThrownBy(() -> UbwDataSources.prefix("prod")).isInstanceOf(IllegalStateException.class);
    }
}

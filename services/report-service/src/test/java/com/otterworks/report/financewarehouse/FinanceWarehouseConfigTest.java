package com.otterworks.report.financewarehouse;

import org.junit.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.test.util.ReflectionTestUtils;
import java.security.KeyPairGenerator;
import java.util.Base64;
import static org.assertj.core.api.Assertions.assertThat;

public class FinanceWarehouseConfigTest {
    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withUserConfiguration(FinanceWarehouseConfig.class);

    @Test
    public void missingSettingsFailAtStartup() {
        runner.run(context -> assertThat(context.getStartupFailure())
                .hasRootCauseMessage("Missing finance warehouse settings: SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
                        + "SNOWFLAKE_ROLE, SNOWFLAKE_PRIVATE_KEY, SNOWFLAKE_WAREHOUSE. "
                        + "Set them or FINANCE_WAREHOUSE_ENABLED=false."));
    }

    @Test
    public void completeSettingsStartWithoutConnecting() throws Exception {
        KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        String pem = Base64.getEncoder().encodeToString(generator.generateKeyPair().getPrivate().getEncoded());
        runner.withPropertyValues("SNOWFLAKE_ACCOUNT=dummy", "SNOWFLAKE_USER=dummy", "SNOWFLAKE_ROLE=dummy",
                "SNOWFLAKE_PRIVATE_KEY=" + pem, "SNOWFLAKE_WAREHOUSE=dummy")
                .run(context -> {
                    assertThat(context).hasNotFailed().hasSingleBean(FinanceWarehouse.class);
                    assertThat(queryTag(context.getBean(FinanceWarehouse.class)))
                            .isEqualTo(FinanceWarehouseConfig.QUERY_TAG);
                });
        runner.withPropertyValues("SNOWFLAKE_ACCOUNT=dummy", "SNOWFLAKE_USER=dummy", "SNOWFLAKE_ROLE=dummy",
                "SNOWFLAKE_PRIVATE_KEY=" + pem, "SNOWFLAKE_WAREHOUSE=dummy", "SNOWFLAKE_QUERY_TAG=live-proof")
                .run(context -> {
                    assertThat(context).hasNotFailed();
                    assertThat(queryTag(context.getBean(FinanceWarehouse.class))).isEqualTo("live-proof");
                });
    }

    private String queryTag(FinanceWarehouse warehouse) {
        JdbcTemplate jdbc = (JdbcTemplate) ReflectionTestUtils.getField(warehouse, "jdbc");
        return ((DriverManagerDataSource) jdbc.getDataSource()).getConnectionProperties().getProperty("QUERY_TAG");
    }

    @Test
    public void disabledStartsWithoutSettings() {
        runner.withPropertyValues("finance.warehouse.enabled=false")
                .run(context -> assertThat(context).hasNotFailed().doesNotHaveBean(FinanceWarehouse.class));
    }

    @Test
    public void whitespaceIsMissingAndValuesAreNotDisclosed() {
        runner.withPropertyValues("SNOWFLAKE_ACCOUNT=  ", "SNOWFLAKE_USER=do-not-disclose")
                .run(context -> {
                    assertThat(context.getStartupFailure()).hasRootCauseMessage(
                            "Missing finance warehouse settings: SNOWFLAKE_ACCOUNT, SNOWFLAKE_ROLE, "
                            + "SNOWFLAKE_PRIVATE_KEY, SNOWFLAKE_WAREHOUSE. "
                            + "Set them or FINANCE_WAREHOUSE_ENABLED=false.");
                });
    }
}

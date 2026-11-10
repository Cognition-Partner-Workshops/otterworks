package com.otterworks.report.financewarehouse;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import javax.sql.DataSource;
import java.security.KeyFactory;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.Base64;
import java.util.Properties;

@Configuration
@ConditionalOnProperty(name = "finance.warehouse.enabled", havingValue = "true", matchIfMissing = true)
public class FinanceWarehouseConfig {
    public static final String QUERY_TAG =
            "{\"run\":\"sfx-d1110\",\"act\":\"consumers\",\"consumer\":\"report-service\"}";

    public static DataSource dataSource(String account, String user, String role, String pem,
            String warehouse) throws Exception {
        Properties properties = new Properties();
        properties.setProperty("user", user);
        properties.setProperty("role", role);
        properties.setProperty("authenticator", "snowflake_jwt");
        properties.setProperty("db", "SFX_D1110_AFTER");
        properties.setProperty("warehouse", warehouse);
        properties.setProperty("QUERY_TAG", QUERY_TAG);
        properties.setProperty("TIMEZONE", "UTC");
        properties.setProperty("JDBC_QUERY_RESULT_FORMAT", "JSON");
        if (!pem.isEmpty()) {
            String encoded = pem.replace("-----BEGIN PRIVATE KEY-----", "")
                    .replace("-----END PRIVATE KEY-----", "").replaceAll("\\s", "");
            properties.put("privateKey", KeyFactory.getInstance("RSA").generatePrivate(
                    new PKCS8EncodedKeySpec(Base64.getDecoder().decode(encoded))));
        }
        return new DriverManagerDataSource("jdbc:snowflake://" + account + ".snowflakecomputing.com", properties);
    }

    @Bean
    public FinanceWarehouse financeWarehouse(
            @Value("${SNOWFLAKE_ACCOUNT:}") String account,
            @Value("${SNOWFLAKE_USER:}") String user,
            @Value("${SNOWFLAKE_ROLE:}") String role,
            @Value("${SNOWFLAKE_PRIVATE_KEY:}") String pem,
            @Value("${finance.warehouse.warehouse:${SNOWFLAKE_WAREHOUSE:}}") String warehouse) throws Exception {
        return new SnowflakeFinanceWarehouse(new JdbcTemplate(dataSource(account, user, role, pem, warehouse)));
    }
}

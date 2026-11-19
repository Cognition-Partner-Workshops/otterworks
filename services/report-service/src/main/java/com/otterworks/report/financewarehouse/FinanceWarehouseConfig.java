package com.otterworks.report.financewarehouse;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

@Configuration
@PropertySource("classpath:com/otterworks/report/financewarehouse/teradata.properties")
@ConditionalOnProperty(name = "finance.warehouse.enabled", havingValue = "true", matchIfMissing = true)
public class FinanceWarehouseConfig {
    @Bean
    public FinanceWarehouse financeWarehouse(
            @Value("${finance.warehouse.url}") String url,
            @Value("${finance.warehouse.user}") String user,
            @Value("${finance.warehouse.password}") String password) {
        DriverManagerDataSource source = new DriverManagerDataSource(url, user, password);
        return new TeradataFinanceWarehouse(new JdbcTemplate(source));
    }
}

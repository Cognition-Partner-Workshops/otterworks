package com.halvergate.customeralerts;

import static org.assertj.core.api.Assertions.assertThat;

import org.apache.camel.CamelContext;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.bean.override.convention.TestBean;
import javax.sql.DataSource;
import org.h2.jdbcx.JdbcDataSource;

@SpringBootTest(properties = {"spring.artemis.password=unused", "spring.datasource.password=unused",
    "narayana.log-dir=target/transaction-logs", "camel.springboot.main-run-controller=false"})
class SkeletonTest {
    @TestBean(name = "dataSource", methodName = "h2DataSource")
    DataSource dataSource;

    static DataSource h2DataSource() {
        JdbcDataSource source = new JdbcDataSource();
        source.setURL("jdbc:h2:mem:skeleton;DB_CLOSE_DELAY=-1");
        return source;
    }

    @Autowired
    private CamelContext camelContext;

    @Test
    void startsWithNoRoutes() {
        assertThat(camelContext.getRoutes()).isEmpty();
    }
}

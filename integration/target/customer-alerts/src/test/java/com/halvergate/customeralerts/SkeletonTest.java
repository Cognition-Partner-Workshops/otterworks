package com.halvergate.customeralerts;

import static org.assertj.core.api.Assertions.assertThat;

import org.apache.camel.CamelContext;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;

@SpringBootTest(properties = {"spring.artemis.password=unused", "spring.datasource.password=unused", "camel.springboot.main-run-controller=false"})
class SkeletonTest {
    @Autowired
    private CamelContext camelContext;

    @Test
    void startsWithNoRoutes() {
        assertThat(camelContext.getRoutes()).isEmpty();
    }
}

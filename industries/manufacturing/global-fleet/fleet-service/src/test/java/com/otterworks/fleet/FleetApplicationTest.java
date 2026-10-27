package com.otterworks.fleet;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringBootTest
class FleetApplicationTest extends AbstractPostgresIntegrationTest {

    @Test
    void applicationContextStarts() {
        assertNotNull(FleetApplication.class);
    }
}

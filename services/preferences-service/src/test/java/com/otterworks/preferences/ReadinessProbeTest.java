package com.otterworks.preferences;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.test.web.servlet.MockMvc;

/** Database down: the pod must leave the Service (readiness) without being restarted (liveness). */
@SpringBootTest
@AutoConfigureMockMvc
class ReadinessProbeTest {

    @TestConfiguration
    static class DatabaseDown {
        @Bean("dbHealthContributor")
        HealthIndicator dbHealthContributor() {
            return () -> Health.down().withDetail("database", "unreachable").build();
        }
    }

    @Autowired private MockMvc mockMvc;

    @Test
    void readinessIsDownWhenTheDatabaseIs() throws Exception {
        mockMvc.perform(get("/actuator/health/readiness")).andExpect(status().isServiceUnavailable());
    }

    @Test
    void livenessAndHealthStayUp() throws Exception {
        mockMvc.perform(get("/actuator/health/liveness")).andExpect(status().isOk());
        mockMvc.perform(get("/health")).andExpect(status().isOk());
    }
}

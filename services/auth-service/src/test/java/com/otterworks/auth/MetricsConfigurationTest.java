package com.otterworks.auth;

import static org.assertj.core.api.Assertions.assertThat;

import io.micrometer.prometheus.PrometheusMeterRegistry;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.actuate.observability.AutoConfigureObservability;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@AutoConfigureObservability
@ActiveProfiles("test")
class MetricsConfigurationTest {

  @Autowired private PrometheusMeterRegistry registry;

  @Test
  void httpTimerExportsTheSloBucket() {
    registry.timer("http.server.requests", "uri", "/slo-probe").record(100, TimeUnit.MILLISECONDS);

    assertThat(
            registry
                .scrape()
                .lines()
                .anyMatch(
                    line ->
                        line.startsWith("http_server_requests_seconds_bucket{")
                            && line.contains("le=\"0.5\"")))
        .isTrue();
  }
}

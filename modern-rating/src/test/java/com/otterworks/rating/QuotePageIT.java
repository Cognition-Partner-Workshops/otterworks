package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.ApplicationContextInitializer;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.context.ContextConfiguration;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ContextConfiguration(initializers = QuotePageIT.SupportKeyEnvironment.class)
class QuotePageIT {

    private static final String TEST_SUPPORT_KEY = "test-${literal}-key";

    static class SupportKeyEnvironment implements ApplicationContextInitializer<ConfigurableApplicationContext> {
        @Override
        public void initialize(ConfigurableApplicationContext context) {
            String name = StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME;
            var properties = context.getEnvironment().getPropertySources();
            properties.replace(name, new SystemEnvironmentPropertySource(name, Map.of("RATING_SUPPORT_KEY", TEST_SUPPORT_KEY)));
        }
    }

    @Autowired
    private TestRestTemplate http;

    @Test
    void servesTheQuotePage() {
        var page = http.getForEntity("/", String.class);
        assertThat(page.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(page.getBody()).contains("Policy quote");
    }

    @Test
    void servesARatingTableWithTheConfiguredKey() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", TEST_SUPPORT_KEY);
        var table = http.exchange("/admin/tables/class-factors.dat", HttpMethod.GET,
                new HttpEntity<>(headers), String.class);
        assertThat(table.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(table.getBody()).contains("GL");
    }

    @Test
    void quotesThroughTheApiAsBefore() {
        String body = "{\"line\":\"GL\",\"state\":\"IL\",\"classCode\":\"91340\",\"territory\":\"001\","
                + "\"effective\":\"2026-03-15\",\"exposure\":\"210.00\",\"years\":5,\"claims\":0,"
                + "\"deductible\":500,\"multi\":false,\"schedule\":0,\"addl\":0,\"equipment\":false,"
                + "\"waiver\":false,\"hnoa\":false}";
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        var quote = http.postForEntity("/api/quotes", new HttpEntity<>(body, headers), String.class);
        assertThat(quote.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(quote.getBody()).contains("\"total\":819.35");
    }

    @Test
    void healthIsUp() {
        assertThat(http.getForObject("/actuator/health", String.class)).contains("UP");
    }
}

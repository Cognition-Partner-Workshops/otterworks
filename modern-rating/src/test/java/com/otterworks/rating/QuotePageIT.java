package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.config.RatingProperties;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
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
import org.springframework.http.ResponseEntity;
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

    @Autowired
    private RatingProperties properties;

    @Test
    void servesTheQuotePage() {
        var page = http.getForEntity("/", String.class);
        assertThat(page.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(page.getBody()).contains("Policy quote");
    }

    @ParameterizedTest
    @ValueSource(strings = {"class-factors.dat", "line-eligibility.dat", "minimum-premium.dat",
            "overrides.dat", "territory-factors.dat"})
    void servesTheExactRatingTableContentsToSupport(String name) throws Exception {
        var table = http.exchange("/admin/tables/" + name, HttpMethod.GET,
                supportRequest(), String.class);
        assertThat(table.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(table.getBody()).isEqualTo(Files.readString(Path.of(properties.tablesDir(), name)));
    }

    private HttpEntity<Void> supportRequest() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", TEST_SUPPORT_KEY);
        return new HttpEntity<>(headers);
    }

    @Test
    void restoresTheParkedQuoteReferenceAsBefore() {
        String quote = "{\"reference\":\"Q-123\",\"fields\":{\"line\":\"GL\"}}";
        String parked = Base64.getEncoder().encodeToString(quote.getBytes(StandardCharsets.UTF_8));
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", TEST_SUPPORT_KEY);
        ResponseEntity<String> restored = http.postForEntity("/admin/quotes/restore",
                new HttpEntity<>(parked, headers), String.class);
        assertThat(restored.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(restored.getBody()).isEqualTo("Q-123");
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

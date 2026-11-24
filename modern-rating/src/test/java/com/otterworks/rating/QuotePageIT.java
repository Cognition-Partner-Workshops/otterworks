package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.Base64;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class QuotePageIT {

    @Autowired
    private TestRestTemplate http;

    @Test
    void servesTheQuotePage() {
        var page = http.getForEntity("/", String.class);
        assertThat(page.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(page.getBody()).contains("Policy quote");
    }

    @Test
    void servesARatingTableToSupportAndRefusesWithoutTheKey() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", "insrules-support");
        var table = http.exchange("/admin/tables/class-factors.dat", HttpMethod.GET,
                new HttpEntity<>(headers), String.class);
        assertThat(table.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(table.getBody()).contains("GL");

        assertThat(http.getForEntity("/admin/tables/class-factors.dat", String.class).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void restoresTheParkedQuoteReferenceAsBefore() {
        String parked = parkedQuote("{\"reference\":\"Q-123\",\"fields\":{\"line\":\"GL\"}}");
        var restored = restoreQuote(" " + parked + "\n");
        assertThat(restored.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(restored.getBody()).isEqualTo("Q-123");

        assertThat(http.postForEntity("/admin/quotes/restore", parked, String.class).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
    }

    @ParameterizedTest
    @ValueSource(strings = {"not JSON", "{}", "{\"reference\":123}", "{\"reference\":\"Q-123\"} {}"})
    void refusesInvalidParkedQuoteContents(String contents) {
        var restored = restoreQuote(parkedQuote(contents));
        assertThat(restored.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(restored.getBody()).isNull();
    }

    @Test
    void refusesInvalidBase64() {
        assertThat(restoreQuote("not base64").getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    private static String parkedQuote(String contents) {
        return Base64.getEncoder().encodeToString(contents.getBytes(StandardCharsets.UTF_8));
    }

    private ResponseEntity<String> restoreQuote(String parked) {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", "insrules-support");
        return http.postForEntity("/admin/quotes/restore", new HttpEntity<>(parked, headers), String.class);
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

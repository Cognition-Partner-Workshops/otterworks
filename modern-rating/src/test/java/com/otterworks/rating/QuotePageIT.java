package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.config.RatingProperties;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class QuotePageIT {

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

    @Test
    void servesARatingTableToSupportAndRefusesWithoutTheKey() throws Exception {
        var table = http.exchange("/admin/tables/class-factors.dat", HttpMethod.GET,
                supportRequest(), String.class);
        assertThat(table.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(table.getBody()).contains("GL");
        assertThat(table.getBody()).isEqualTo(Files.readString(Path.of(properties.tablesDir(), "class-factors.dat")));

        assertThat(http.getForEntity("/admin/tables/class-factors.dat", String.class).getStatusCode())
                .isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    void refusesAnInvalidTableBasename() {
        var table = http.exchange("/admin/tables/class..dat", HttpMethod.GET,
                supportRequest(), String.class);
        assertThat(table.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(table.getBody()).isNull();
    }

    private HttpEntity<Void> supportRequest() {
        HttpHeaders headers = new HttpHeaders();
        headers.set("X-Support-Key", "insrules-support");
        return new HttpEntity<>(headers);
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

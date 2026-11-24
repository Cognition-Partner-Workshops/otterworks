package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import com.otterworks.rating.model.Quote;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.util.LinkedMultiValueMap;

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
    void healthIsUp() {
        assertThat(http.getForObject("/actuator/health", String.class)).contains("UP");
    }

    @ParameterizedTest
    @ValueSource(strings = {"2.10E+1", "2.10e-1", "10000000", "210.001"})
    void rejectsInvalidExposureOnTheQuotePage(String exposure) {
        var page = http.postForEntity("/", quoteForm(exposure), String.class);
        assertThat(page.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(page.getBody()).contains("Exposure must be a plain decimal with up to 7 whole digits and 2 decimal places")
                .doesNotContain("<table id=\"quote\">");
    }

    @ParameterizedTest
    @ValueSource(strings = {"2.10E+1", "\"2.10e-1\"", "10000000", "210.001"})
    void rejectsInvalidExposureInTheQuoteApi(String exposure) {
        var response = http.postForEntity("/api/quotes", quoteJson(exposure), String.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void ratesPlainDecimalExposureOnTheQuotePage() {
        var page = http.postForEntity("/", quoteForm("210.00"), String.class);
        assertThat(page.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(page.getBody()).contains("<table id=\"quote\">", "$819.35");
    }

    @ParameterizedTest
    @ValueSource(strings = {"210.00", "\"210.00\""})
    void ratesPlainDecimalExposureInTheQuoteApi(String exposure) {
        var response = http.postForEntity("/api/quotes", quoteJson(exposure), Quote.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().total()).isEqualByComparingTo("819.35");
    }

    @ParameterizedTest
    @CsvSource({".75, 3.11", "210., 871.50"})
    void ratesExposureWithDigitsOnOnlyOneSideOfThePoint(String exposure, String basePremium) {
        var page = http.postForEntity("/", quoteForm(exposure), String.class);
        assertThat(page.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(page.getBody()).contains("<table id=\"quote\">", "$" + basePremium);

        var response = http.postForEntity("/api/quotes", quoteJson("\"" + exposure + "\""), Quote.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().basePremium()).isEqualByComparingTo(basePremium);
    }

    private static LinkedMultiValueMap<String, String> quoteForm(String exposure) {
        var form = new LinkedMultiValueMap<String, String>();
        form.add("line", "GL");
        form.add("state", "IL");
        form.add("classCode", "91340");
        form.add("territory", "001");
        form.add("effective", "2026-03-15");
        form.add("years", "5");
        form.add("claims", "0");
        form.add("deductible", "500");
        form.add("schedule", "0");
        form.add("addl", "0");
        form.add("_multi", "on");
        form.add("_equipment", "on");
        form.add("_waiver", "on");
        form.add("_hnoa", "on");
        form.add("exposure", exposure);
        return form;
    }

    private static HttpEntity<String> quoteJson(String exposure) {
        var headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return new HttpEntity<>("""
                {"line":"GL","state":"IL","classCode":"91340","territory":"001",
                 "effective":"2026-03-15","years":5,"deductible":500,"exposure":%s}
                """.formatted(exposure), headers);
    }
}

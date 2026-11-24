package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = "rating.support-key=")
class SupportKeyUnsetIT {

    @Autowired
    private TestRestTemplate http;

    @Test
    void refusesSupportScreensWhenNoKeyIsConfigured() {
        for (String supplied : new String[] {"", "insrules-support"}) {
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-Support-Key", supplied);
            assertThat(http.exchange("/admin/tables/class-factors.dat", HttpMethod.GET,
                    new HttpEntity<>(headers), String.class).getStatusCode())
                    .isEqualTo(HttpStatus.FORBIDDEN);
        }
    }
}

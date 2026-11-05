package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {"server.ssl.enabled=false", "logging.file.name="})
class UploadMetricsTest {

    @org.junit.jupiter.api.io.TempDir
    static Path uploads;

    @DynamicPropertySource
    static void uploadDirectory(DynamicPropertyRegistry registry) {
        registry.add("kyc.upload-dir", () -> uploads.toString());
    }

    @Autowired
    TestRestTemplate client;

    @Test
    void multipartUploadExportsHistogramWithRouteAndTwoSecondBucket() {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("kind", "passport");
        body.add("file", new ByteArrayResource(new byte[42]) {
            @Override
            public String getFilename() {
                return "synthetic.pdf";
            }
        });
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        ResponseEntity<String> upload = client.postForEntity("/documents/SYNTH000001",
                new HttpEntity<>(body, headers), String.class);
        assertEquals(HttpStatus.CREATED, upload.getStatusCode());

        ResponseEntity<String> scrape = client.getForEntity("/actuator/prometheus", String.class);
        assertEquals(HttpStatus.OK, scrape.getStatusCode());
        assertNotNull(scrape.getBody());
        assertTrue(scrape.getBody().lines().anyMatch(line ->
                line.startsWith("http_server_requests_seconds_bucket{")
                        && line.contains("application=\"kyc-docs\"")
                        && line.contains("method=\"POST\"")
                        && line.contains("uri=\"/documents/{customer}\"")
                        && line.contains("le=\"2.0\"")
                        && line.endsWith(" 1.0")), scrape.getBody());
    }
}

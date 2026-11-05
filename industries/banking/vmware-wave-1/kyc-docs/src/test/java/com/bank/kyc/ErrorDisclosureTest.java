package com.bank.kyc;

import static org.junit.jupiter.api.Assertions.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.ResponseEntity;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
    "server.ssl.enabled=false", "kyc.upload-dir=target/fs09_http_documents"
})
class ErrorDisclosureTest {
    @Autowired TestRestTemplate http;

    @Test
    void unmappedAndMalformedRequestsDoNotExposeAccountPaths() {
        ResponseEntity<String> missing = http.getForEntity("/documents/HG611000001/missing", String.class);
        assertEquals(404, missing.getStatusCodeValue());
        assertFalse(missing.getBody().contains("HG611000001"), "Default error responses must not expose account-bearing paths");
        ResponseEntity<String> malformed = http.postForEntity("/documents/HG611000001?kind=passport", null, String.class);
        assertTrue(malformed.getStatusCodeValue() >= 400);
        assertFalse(malformed.getBody().contains("HG611000001"));
    }
}

package com.bank.kyc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;

@WebMvcTest(value = DocumentController.class, properties = "JWT_SECRET=kyc-test-secret-at-least-thirty-two-bytes")
class AccessTest {
    @Autowired MockMvc mvc;
    @MockBean DocumentStore store;
    private String token(String user, String role) {
        return io.jsonwebtoken.Jwts.builder().subject(user).claim("type", "access")
            .claim("roles", java.util.Collections.singletonList(role))
            .expiration(new java.util.Date(System.currentTimeMillis() + 60000))
            .signWith(io.jsonwebtoken.security.Keys.hmacShaKeyFor("kyc-test-secret-at-least-thirty-two-bytes".getBytes(java.nio.charset.StandardCharsets.UTF_8))).compact();
    }
    @Test void onlyComplianceCanReadDocuments() throws Exception {
        mvc.perform(get("/documents/CUSTOMER1").header("Authorization", "Bearer " + token("user", "USER")))
            .andExpect(status().isForbidden());
        mvc.perform(get("/documents/CUSTOMER1").header("Authorization", "Bearer " + token("auditor", "COMPLIANCE")))
            .andExpect(status().isOk());
    }
    @Test void onlyOnboardingCanUpload() throws Exception {
        mvc.perform(multipart("/documents/CUSTOMER1").file(new MockMultipartFile("file", "scan.pdf", "application/pdf", new byte[]{1})).param("kind", "passport")
            .header("Authorization", "Bearer " + token("other-service", "SERVICE")))
            .andExpect(status().isForbidden());
        mvc.perform(multipart("/documents/CUSTOMER1").file(new MockMultipartFile("file", "scan.pdf", "application/pdf", new byte[]{1})).param("kind", "passport")
            .header("Authorization", "Bearer " + token("onboarding-service", "SERVICE")))
            .andExpect(status().isCreated());
    }
    @Test void anonymousUploadIsRejected() throws Exception {
        mvc.perform(multipart("/documents/CUSTOMER1").file(new MockMultipartFile("file", "scan.pdf", "application/pdf", new byte[]{1})).param("kind", "passport"))
            .andExpect(status().isUnauthorized());
    }
    @Test void anonymousListingIsRejected() throws Exception {
        mvc.perform(get("/documents/CUSTOMER1")).andExpect(status().isUnauthorized());
    }
}

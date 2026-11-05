package com.otterworks.report.service;

import com.otterworks.report.config.AppConfig;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Date;
import org.junit.Test;
import org.springframework.http.MediaType;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

public class AuditReportAuthenticationTest {
    @Test
    public void auditFetchUsesShortLivedServiceCredential() {
        String secret = "report-access-test-secret-at-least-32-bytes-long";
        RestTemplate rest = new RestTemplate();
        AppConfig config = new AppConfig();
        ReflectionTestUtils.setField(config, "auditServiceUrl", "http://audit-service:8090");
        ReportDataFetcher fetcher = new ReportDataFetcher(rest, config);
        ReflectionTestUtils.setField(fetcher, "jwtSecret", secret);
        MockRestServiceServer server = MockRestServiceServer.bindTo(rest).build();
        server.expect(request -> {
            String header = request.getHeaders().getFirst("Authorization");
            assertTrue(header != null && header.startsWith("Bearer "));
            Claims claims = Jwts.parser().verifyWith(Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8)))
                    .build().parseSignedClaims(header.substring(7)).getPayload();
            assertEquals("report-service", claims.getSubject());
            assertEquals(Collections.singletonList("AUDITOR"), claims.get("roles"));
            assertEquals("access", claims.get("type"));
            assertTrue(claims.getExpiration().getTime() - System.currentTimeMillis() <= 60000);
        }).andRespond(withSuccess("{\"events\":[]}", MediaType.APPLICATION_JSON));
        fetcher.fetchAuditData(new Date(0), new Date(1000), Collections.emptyMap());
        server.verify();
    }
}

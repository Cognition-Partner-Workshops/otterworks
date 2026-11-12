package com.otterworks.report.security;

import org.junit.Test;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class ServiceTokenProviderTest {

    private static final String SECRET = "otterworks-test-jwt-secret-at-least-32-bytes";

    @Test
    public void mintsHs256TokenWithServiceRoleAndExpiry() throws Exception {
        ServiceTokenProvider provider = new ServiceTokenProvider(SECRET);

        String token = provider.mint(1_700_000_000L, 60);
        String[] parts = token.split("\\.");
        assertEquals(3, parts.length);

        String header = decode(parts[0]);
        String payload = decode(parts[1]);
        assertEquals("{\"alg\":\"HS256\",\"typ\":\"JWT\"}", header);
        assertTrue(payload, payload.contains("\"sub\":\"report-service\""));
        assertTrue(payload, payload.contains("\"roles\":[\"SERVICE\"]"));
        assertTrue(payload, payload.contains("\"type\":\"access\""));
        assertTrue(payload, payload.contains("\"iat\":1700000000"));
        assertTrue(payload, payload.contains("\"exp\":1700000060"));

        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(SECRET.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        byte[] expected = mac.doFinal((parts[0] + "." + parts[1]).getBytes(StandardCharsets.UTF_8));
        assertEquals(Base64.getUrlEncoder().withoutPadding().encodeToString(expected), parts[2]);
    }

    @Test
    public void returnsNullWhenSecretMissing() {
        ServiceTokenProvider provider = new ServiceTokenProvider("");

        assertFalse(provider.isConfigured());
        assertNull(provider.mint());
    }

    private static String decode(String segment) {
        return new String(Base64.getUrlDecoder().decode(segment), StandardCharsets.UTF_8);
    }
}

package com.otterworks.report.service;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Base64;

/**
 * Mints the HS256 access token audit-service expects (same claims the auth-service issues:
 * sub, roles, type=access) for service-to-service calls. Valid for one minute.
 */
final class ServiceToken {

    private static final long TTL_SECONDS = 60;

    private ServiceToken() {
    }

    static String mint(String secret, String serviceName) {
        long now = System.currentTimeMillis() / 1000;
        String header = base64Url("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
        String payload = base64Url(String.format(
                "{\"sub\":\"%s\",\"roles\":[\"ADMIN\"],\"type\":\"access\",\"iat\":%d,\"exp\":%d}",
                serviceName, now, now + TTL_SECONDS).getBytes(StandardCharsets.UTF_8));
        String signingInput = header + "." + payload;
        return signingInput + "." + base64Url(hmacSha256(secret, signingInput));
    }

    private static byte[] hmacSha256(String secret, String input) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return mac.doFinal(input.getBytes(StandardCharsets.UTF_8));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Unable to sign service token", e);
        }
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}

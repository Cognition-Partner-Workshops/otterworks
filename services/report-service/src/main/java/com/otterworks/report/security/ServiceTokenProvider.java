package com.otterworks.report.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.util.Base64;

/**
 * Mints short-lived HS256 service tokens signed with the platform's shared JWT secret.
 *
 * audit-service verifies every caller's JWT and only serves the audit log to the
 * ADMIN, AUDITOR or SERVICE roles, so report-service identifies itself with a
 * {@code roles: ["SERVICE"]} token rather than calling anonymously. Implemented with
 * javax.crypto so this Java 8 / Spring Boot 2.5 module does not take on a JWT library.
 */
@Component
public class ServiceTokenProvider {

    private static final Logger logger = LoggerFactory.getLogger(ServiceTokenProvider.class);

    static final String SUBJECT = "report-service";
    static final String ROLE = "SERVICE";
    private static final String HEADER = base64Url("{\"alg\":\"HS256\",\"typ\":\"JWT\"}".getBytes(StandardCharsets.UTF_8));
    private static final long DEFAULT_TTL_SECONDS = 60;

    private final String secret;

    public ServiceTokenProvider(@Value("${otterworks.jwt.secret:}") String secret) {
        this.secret = secret == null ? "" : secret;
        if (this.secret.isEmpty()) {
            logger.warn("otterworks.jwt.secret (JWT_SECRET) is not set; audit-service calls will be sent without a service token and be rejected");
        }
    }

    public boolean isConfigured() {
        return !secret.isEmpty();
    }

    /** A bearer token valid for the next minute, or {@code null} when no secret is configured. */
    public String mint() {
        return mint(System.currentTimeMillis() / 1000, DEFAULT_TTL_SECONDS);
    }

    String mint(long issuedAtEpochSeconds, long ttlSeconds) {
        if (!isConfigured()) {
            return null;
        }
        String payload = "{\"sub\":\"" + SUBJECT + "\",\"type\":\"access\",\"roles\":[\"" + ROLE + "\"]"
                + ",\"iat\":" + issuedAtEpochSeconds
                + ",\"exp\":" + (issuedAtEpochSeconds + ttlSeconds) + "}";
        String signingInput = HEADER + "." + base64Url(payload.getBytes(StandardCharsets.UTF_8));
        return signingInput + "." + base64Url(hmacSha256(signingInput));
    }

    private byte[] hmacSha256(String signingInput) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return mac.doFinal(signingInput.getBytes(StandardCharsets.UTF_8));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Unable to sign service token", e);
        }
    }

    private static String base64Url(byte[] bytes) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}

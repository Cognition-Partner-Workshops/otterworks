package com.otterworks.report.security;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;

/**
 * Mints tokens shaped like auth-service's JwtTokenProvider for tests. The secret is a
 * test-only fixture (64 chars, so jjwt signs HS512 as with deployed `openssl rand -hex 32`
 * secrets) and is supplied per test class, never from src/main/resources.
 */
public final class TestTokens {

    public static final String SECRET = "report-service-test-only-signing-key-0123456789abcdef0123456789";
    public static final String SECRET_PROPERTY = "otterworks.auth.jwt-secret=" + SECRET;

    private TestTokens() {
    }

    public static String accessToken(String userId, String... roles) {
        return token(SECRET, userId, "access", 3600_000L, roles);
    }

    public static String token(String secret, String userId, String type, long ttlMillis, String... roles) {
        SecretKey key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        long now = System.currentTimeMillis();
        return Jwts.builder()
                .subject(userId)
                .claim("roles", Arrays.asList(roles))
                .claim("type", type)
                .issuedAt(new Date(now - 1000L))
                .expiration(new Date(now + ttlMillis))
                .signWith(key)
                .compact();
    }

    public static RequestPostProcessor bearer(String token) {
        return request -> {
            request.addHeader("Authorization", "Bearer " + token);
            return request;
        };
    }

    public static RequestPostProcessor asUser(String userId) {
        return bearer(accessToken(userId, "EDITOR"));
    }

    public static RequestPostProcessor asAdmin(String userId) {
        return bearer(accessToken(userId, "ADMIN"));
    }
}

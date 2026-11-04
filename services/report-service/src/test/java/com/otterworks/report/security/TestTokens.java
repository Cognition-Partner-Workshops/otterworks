package com.otterworks.report.security;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;

/**
 * Mints HS256 tokens shaped like auth-service access tokens, for tests only.
 */
public final class TestTokens {

    public static final String SECRET = "report-service-test-only-jwt-secret-0123456789abcdef";
    public static final String PEER_SECRET = "report-service-test-only-peer-secret-fedcba9876543210";

    private TestTokens() {
    }

    public static String bearer(String userId, String... roles) {
        return "Bearer " + token(SECRET, userId, "access", roles);
    }

    public static String token(String secret, String userId, String type, String... roles) {
        return Jwts.builder()
                .subject(userId)
                .claim("roles", Arrays.asList(roles))
                .claim("type", type)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + 600_000L))
                .signWith(Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8)))
                .compact();
    }
}

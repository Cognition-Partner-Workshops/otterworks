package com.otterworks.report.security;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Date;

/**
 * Mints access tokens shaped like auth-service's ({@code sub} = user id, {@code roles} list)
 * and signed with the {@code jwt.secret} of the "test" profile.
 */
public final class TestTokens {

    public static final String SECRET = "report-service-test-jwt-secret-at-least-32-bytes";

    private TestTokens() {
    }

    public static String bearer(String userId, String... roles) {
        return "Bearer " + token(SECRET, userId, roles);
    }

    public static String bearerSignedWith(String secret, String userId, String... roles) {
        return "Bearer " + token(secret, userId, roles);
    }

    private static String token(String secret, String userId, String... roles) {
        long now = System.currentTimeMillis();
        return Jwts.builder()
                .subject(userId)
                .claim("roles", Arrays.asList(roles))
                .claim("type", "access")
                .issuedAt(new Date(now))
                .expiration(new Date(now + 3600_000L))
                .signWith(Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8)))
                .compact();
    }
}

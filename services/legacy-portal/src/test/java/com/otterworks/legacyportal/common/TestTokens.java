package com.otterworks.legacyportal.common;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.List;
import javax.crypto.SecretKey;

/** Mints tokens shaped like the auth-service access token for tests. */
public final class TestTokens {

    /** Matches the default of {@code portal.auth.jwt-secret} in application.yml. */
    public static final String SECRET = "dev-jwt-secret-otterworks-2024-change-in-production";

    private TestTokens() {}

    public static SecretKey key(String secret) {
        return Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    public static String accessToken(String userId, String... roles) {
        return accessTokenSignedWith(SECRET, userId, roles);
    }

    public static String accessTokenSignedWith(String secret, String userId, String... roles) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(userId)
                .claim("roles", List.of(roles))
                .claim("type", "access")
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(1, ChronoUnit.HOURS)))
                .signWith(key(secret))
                .compact();
    }

    public static String refreshToken(String userId) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(userId)
                .claim("type", "refresh")
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(1, ChronoUnit.HOURS)))
                .signWith(key(SECRET))
                .compact();
    }

    public static String bearer(String token) {
        return "Bearer " + token;
    }
}

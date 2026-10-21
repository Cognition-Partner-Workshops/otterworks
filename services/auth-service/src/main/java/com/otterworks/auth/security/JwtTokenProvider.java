package com.otterworks.auth.security;

import com.otterworks.auth.entity.User;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class JwtTokenProvider {

  /** Signing secrets that have been committed to this repository and must never be used. */
  static final Set<String> KNOWN_DEFAULT_SECRETS =
      Set.of(
          "otterworks-local-dev-jwt-secret-change-me-in-production",
          "dev-jwt-secret-otterworks-2024-change-in-production",
          "otterworks-dev-secret",
          "dev_jwt_secret_key",
          "changeme",
          "change-me",
          "secret");

  private final SecretKey key;
  private final long accessTokenExpiry;
  private final long refreshTokenExpiry;

  public JwtTokenProvider(
      @Value("${jwt.secret}") String secret,
      @Value("${jwt.access-token-expiry:3600}") long accessTokenExpiry,
      @Value("${jwt.refresh-token-expiry:2592000}") long refreshTokenExpiry) {
    this.key = Keys.hmacShaKeyFor(requireUsableSecret(secret).getBytes(StandardCharsets.UTF_8));
    this.accessTokenExpiry = accessTokenExpiry;
    this.refreshTokenExpiry = refreshTokenExpiry;
  }

  static String requireUsableSecret(String secret) {
    if (secret == null || secret.isBlank()) {
      throw new IllegalStateException(
          "jwt.secret must be configured: set the JWT_SECRET environment variable");
    }
    if (KNOWN_DEFAULT_SECRETS.contains(secret.trim())) {
      throw new IllegalStateException(
          "jwt.secret is a publicly known default value: set JWT_SECRET to a random secret"
              + " (e.g. openssl rand -hex 32)");
    }
    return secret;
  }

  public String generateAccessToken(User user) {
    Instant now = Instant.now();
    return Jwts.builder()
        .subject(user.getId().toString())
        .claim("email", user.getEmail())
        .claim("name", user.getDisplayName())
        .claim("roles", user.getRoles().stream().map(Enum::name).collect(Collectors.toList()))
        .claim("type", "access")
        .issuedAt(Date.from(now))
        .expiration(Date.from(now.plus(accessTokenExpiry, ChronoUnit.SECONDS)))
        .signWith(key)
        .compact();
  }

  public String generateRefreshToken(User user) {
    String jti = UUID.randomUUID().toString();
    Instant now = Instant.now();
    return Jwts.builder()
        .subject(user.getId().toString())
        .id(jti)
        .claim("type", "refresh")
        .issuedAt(Date.from(now))
        .expiration(Date.from(now.plus(refreshTokenExpiry, ChronoUnit.SECONDS)))
        .signWith(key)
        .compact();
  }

  public Claims validateAndGetClaims(String token) {
    return Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
  }

  public String validateTokenAndGetUserId(String token) {
    Claims claims = validateAndGetClaims(token);
    String type = claims.get("type", String.class);
    if ("refresh".equals(type)) {
      throw new IllegalArgumentException("Refresh token cannot be used as access token");
    }
    return claims.getSubject();
  }

  public String validateRefreshTokenAndGetUserId(String token) {
    Claims claims = validateAndGetClaims(token);
    String type = claims.get("type", String.class);
    if (!"refresh".equals(type)) {
      throw new IllegalArgumentException("Token is not a refresh token");
    }
    return claims.getSubject();
  }

  public String extractJti(String token) {
    Claims claims = validateAndGetClaims(token);
    return claims.getId();
  }

  public boolean isTokenValid(String token) {
    try {
      validateAndGetClaims(token);
      return true;
    } catch (JwtException | IllegalArgumentException e) {
      return false;
    }
  }

  public long getAccessTokenExpiry() {
    return accessTokenExpiry;
  }

  public long getRefreshTokenExpiry() {
    return refreshTokenExpiry;
  }
}

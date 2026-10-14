package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.security.JwtTokenProvider;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import io.jsonwebtoken.security.SignatureException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class QaJwtTokenProviderTest {

  private static final String SECRET =
      "test-jwt-secret-otterworks-must-be-at-least-32-bytes-long-for-hmac";
  private static final String OTHER_SECRET =
      "another-secret-otterworks-that-is-also-at-least-32-bytes-long";

  private JwtTokenProvider provider;
  private User user;

  @BeforeEach
  void setUp() {
    provider = new JwtTokenProvider(SECRET, 3600, 2592000);
    user = new User();
    user.setId(UUID.randomUUID());
    user.setEmail("qa@otterworks.dev");
    user.setDisplayName("QA User");
    user.setRoles(Set.of(User.Role.USER, User.Role.ADMIN));
  }

  private static String b64(String s) {
    return Base64.getUrlEncoder().withoutPadding().encodeToString(s.getBytes(StandardCharsets.UTF_8));
  }

  @Test
  void accessToken_expiryMatchesConfiguredSeconds() {
    Claims claims = provider.validateAndGetClaims(provider.generateAccessToken(user));
    long ttl = (claims.getExpiration().getTime() - claims.getIssuedAt().getTime()) / 1000;
    assertThat(ttl).isEqualTo(3600);
  }

  @Test
  void refreshToken_expiryMatchesConfiguredSeconds() {
    Claims claims = provider.validateAndGetClaims(provider.generateRefreshToken(user));
    long ttl = (claims.getExpiration().getTime() - claims.getIssuedAt().getTime()) / 1000;
    assertThat(ttl).isEqualTo(2592000);
  }

  @Test
  void accessToken_carriesAllRoles() {
    Claims claims = provider.validateAndGetClaims(provider.generateAccessToken(user));
    assertThat(claims.get("roles", List.class)).containsExactlyInAnyOrder("USER", "ADMIN");
  }

  @Test
  void refreshTokens_haveUniqueJti() {
    String a = provider.extractJti(provider.generateRefreshToken(user));
    String b = provider.extractJti(provider.generateRefreshToken(user));
    assertThat(a).isNotEqualTo(b);
  }

  @Test
  void accessToken_hasNoJti() {
    assertThat(provider.extractJti(provider.generateAccessToken(user))).isNull();
  }

  @Test
  void expiredToken_isRejected() {
    String token = new JwtTokenProvider(SECRET, -10, -10).generateAccessToken(user);
    assertThatThrownBy(() -> provider.validateAndGetClaims(token))
        .isInstanceOf(ExpiredJwtException.class);
    assertThat(provider.isTokenValid(token)).isFalse();
  }

  @Test
  void expiredRefreshToken_isRejectedByRefreshValidation() {
    String token = new JwtTokenProvider(SECRET, -10, -10).generateRefreshToken(user);
    assertThatThrownBy(() -> provider.validateRefreshTokenAndGetUserId(token))
        .isInstanceOf(ExpiredJwtException.class);
  }

  @Test
  void tokenSignedWithOtherSecret_isRejected() {
    String foreign = new JwtTokenProvider(OTHER_SECRET, 3600, 3600).generateAccessToken(user);
    assertThatThrownBy(() -> provider.validateAndGetClaims(foreign))
        .isInstanceOf(SignatureException.class);
    assertThat(provider.isTokenValid(foreign)).isFalse();
  }

  @Test
  void tamperedPayload_isRejected() {
    String[] parts = provider.generateAccessToken(user).split("\\.");
    String forged =
        parts[0]
            + "."
            + b64("{\"sub\":\"" + UUID.randomUUID() + "\",\"roles\":[\"ADMIN\"],\"type\":\"access\"}")
            + "."
            + parts[2];
    assertThat(provider.isTokenValid(forged)).isFalse();
  }

  @Test
  void unsignedAlgNoneToken_isRejected() {
    String token =
        b64("{\"alg\":\"none\"}") + "." + b64("{\"sub\":\"" + user.getId() + "\",\"type\":\"access\"}") + ".";
    assertThat(provider.isTokenValid(token)).isFalse();
  }

  @Test
  void garbageAndEmptyTokens_areInvalid() {
    assertThat(provider.isTokenValid("not-a-jwt")).isFalse();
    assertThat(provider.isTokenValid("")).isFalse();
  }

  @Test
  void refreshToken_cannotBeUsedAsAccessToken() {
    String refresh = provider.generateRefreshToken(user);
    assertThatThrownBy(() -> provider.validateTokenAndGetUserId(refresh))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void accessToken_cannotBeUsedAsRefreshToken() {
    String access = provider.generateAccessToken(user);
    assertThatThrownBy(() -> provider.validateRefreshTokenAndGetUserId(access))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void tokenWithoutTypeClaim_isRejectedAsRefreshToken() {
    String token =
        Jwts.builder()
            .subject(user.getId().toString())
            .issuedAt(new Date())
            .expiration(Date.from(Instant.now().plusSeconds(60)))
            .signWith(Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8)))
            .compact();
    assertThatThrownBy(() -> provider.validateRefreshTokenAndGetUserId(token))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void shortSecret_isRejectedAtConstruction() {
    assertThatThrownBy(() -> new JwtTokenProvider("too-short", 60, 60))
        .isInstanceOf(RuntimeException.class);
  }
}

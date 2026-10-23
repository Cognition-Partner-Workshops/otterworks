package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.security.JwtTokenProvider;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class JwtTokenProviderQaTest {

  private static final String SECRET =
      "test-jwt-secret-otterworks-must-be-at-least-32-bytes-long-for-hmac";

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

  @Test
  void accessTokenCarriesAllRolesAndAccessType() {
    Claims claims = provider.validateAndGetClaims(provider.generateAccessToken(user));
    @SuppressWarnings("unchecked")
    List<String> roles = claims.get("roles", List.class);
    assertThat(roles).containsExactlyInAnyOrder("USER", "ADMIN");
    assertThat(claims.get("type", String.class)).isEqualTo("access");
    assertThat(claims.getSubject()).isEqualTo(user.getId().toString());
  }

  @Test
  void accessTokenExpiryMatchesConfiguredLifetime() {
    Claims claims = provider.validateAndGetClaims(provider.generateAccessToken(user));
    long lifetime = (claims.getExpiration().getTime() - claims.getIssuedAt().getTime()) / 1000;
    assertThat(lifetime).isEqualTo(3600);
  }

  @Test
  void refreshTokenExpiryMatchesConfiguredLifetime() {
    Claims claims = provider.validateAndGetClaims(provider.generateRefreshToken(user));
    long lifetime = (claims.getExpiration().getTime() - claims.getIssuedAt().getTime()) / 1000;
    assertThat(lifetime).isEqualTo(2592000);
  }

  @Test
  void refreshTokenDoesNotLeakEmailOrRoles() {
    Claims claims = provider.validateAndGetClaims(provider.generateRefreshToken(user));
    assertThat(claims.get("email")).isNull();
    assertThat(claims.get("roles")).isNull();
  }

  @Test
  void eachRefreshTokenGetsAUniqueJti() {
    String first = provider.extractJti(provider.generateRefreshToken(user));
    String second = provider.extractJti(provider.generateRefreshToken(user));
    assertThat(first).isNotBlank().isNotEqualTo(second);
  }

  @Test
  void refreshTokenIsRejectedAsAccessToken() {
    String refresh = provider.generateRefreshToken(user);
    assertThatThrownBy(() -> provider.validateTokenAndGetUserId(refresh))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void accessTokenIsRejectedAsRefreshToken() {
    String access = provider.generateAccessToken(user);
    assertThatThrownBy(() -> provider.validateRefreshTokenAndGetUserId(access))
        .isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void refreshTokenValidationReturnsSubject() {
    String refresh = provider.generateRefreshToken(user);
    assertThat(provider.validateRefreshTokenAndGetUserId(refresh))
        .isEqualTo(user.getId().toString());
  }

  @Test
  void tokenSignedWithAnotherKeyIsRejected() {
    JwtTokenProvider other =
        new JwtTokenProvider("another-secret-that-is-also-at-least-32-bytes-long!!", 3600, 60);
    String foreign = other.generateAccessToken(user);
    assertThat(provider.isTokenValid(foreign)).isFalse();
    assertThatThrownBy(() -> provider.validateAndGetClaims(foreign))
        .isInstanceOf(JwtException.class);
  }

  @Test
  void tamperedPayloadIsRejected() {
    String[] parts = provider.generateAccessToken(user).split("\\.");
    String forgedPayload =
        Base64.getUrlEncoder()
            .withoutPadding()
            .encodeToString(
                ("{\"sub\":\"" + user.getId() + "\",\"roles\":[\"ADMIN\"],\"type\":\"access\"}")
                    .getBytes(StandardCharsets.UTF_8));
    String tampered = parts[0] + "." + forgedPayload + "." + parts[2];
    assertThat(provider.isTokenValid(tampered)).isFalse();
  }

  @Test
  void unsignedAlgNoneTokenIsRejected() {
    String unsigned =
        Jwts.builder()
            .subject(user.getId().toString())
            .claim("type", "access")
            .expiration(new Date(System.currentTimeMillis() + 60_000))
            .compact();
    assertThat(provider.isTokenValid(unsigned)).isFalse();
  }

  @Test
  void expiredTokenSignedWithRightKeyIsRejected() {
    String expired =
        Jwts.builder()
            .subject(user.getId().toString())
            .claim("type", "access")
            .issuedAt(new Date(System.currentTimeMillis() - 120_000))
            .expiration(new Date(System.currentTimeMillis() - 60_000))
            .signWith(Keys.hmacShaKeyFor(SECRET.getBytes(StandardCharsets.UTF_8)))
            .compact();
    assertThat(provider.isTokenValid(expired)).isFalse();
    assertThatThrownBy(() -> provider.validateTokenAndGetUserId(expired))
        .isInstanceOf(JwtException.class);
  }

  @Test
  void garbageAndEmptyTokensAreInvalid() {
    assertThat(provider.isTokenValid("")).isFalse();
    assertThat(provider.isTokenValid("a.b.c")).isFalse();
    assertThat(provider.isTokenValid("not-a-jwt")).isFalse();
  }
}

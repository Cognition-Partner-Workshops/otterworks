package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.otterworks.auth.dto.AuthResponse;
import com.otterworks.auth.dto.LoginRequest;
import com.otterworks.auth.dto.RegisterRequest;
import com.otterworks.auth.entity.RefreshToken;
import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import com.otterworks.auth.security.JwtTokenProvider;
import com.otterworks.auth.service.AuthService;
import io.jsonwebtoken.ExpiredJwtException;
import java.time.Instant;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class QaAuthServiceTest {

  private static final String SECRET =
      "test-jwt-secret-otterworks-must-be-at-least-32-bytes-long-for-hmac";

  @Mock private UserRepository userRepository;
  @Mock private RefreshTokenRepository refreshTokenRepository;

  private final PasswordEncoder encoder = new BCryptPasswordEncoder(4);
  private JwtTokenProvider jwt;
  private AuthService service;
  private User user;

  @BeforeEach
  void setUp() {
    jwt = new JwtTokenProvider(SECRET, 3600, 2592000);
    service = new AuthService(userRepository, encoder, jwt, refreshTokenRepository);
    user = new User();
    user.setId(UUID.randomUUID());
    user.setEmail("qa@otterworks.dev");
    user.setDisplayName("QA");
    user.setPasswordHash(encoder.encode("Passw0rd!23"));
    user.setRoles(Set.of(User.Role.USER));
    when(refreshTokenRepository.save(any())).thenAnswer(i -> i.getArgument(0));
    when(userRepository.save(any())).thenAnswer(i -> i.getArgument(0));
  }

  private RefreshToken stored(String jti, Instant expiresAt) {
    RefreshToken t = new RefreshToken();
    t.setUser(user);
    t.setTokenId(jti);
    t.setExpiresAt(expiresAt);
    return t;
  }

  private LoginRequest login(String email, String password) {
    LoginRequest req = new LoginRequest();
    req.setEmail(email);
    req.setPassword(password);
    return req;
  }

  @Test
  void register_hashesPasswordAndAssignsOnlyUserRole() {
    when(userRepository.existsByEmail("new@otterworks.dev")).thenReturn(false);
    when(userRepository.save(any()))
        .thenAnswer(
            i -> {
              User u = i.getArgument(0);
              u.setId(UUID.randomUUID());
              return u;
            });
    RegisterRequest req = new RegisterRequest();
    req.setEmail("new@otterworks.dev");
    req.setPassword("Passw0rd!23");
    req.setDisplayName("New");

    AuthResponse res = service.register(req);

    ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
    verify(userRepository).save(captor.capture());
    assertThat(captor.getValue().getPasswordHash()).isNotEqualTo("Passw0rd!23");
    assertThat(encoder.matches("Passw0rd!23", captor.getValue().getPasswordHash())).isTrue();
    assertThat(captor.getValue().getRoles()).containsExactly(User.Role.USER);
    assertThat(res.getTokenType()).isEqualTo("Bearer");
    assertThat(res.getExpiresIn()).isEqualTo(3600);
  }

  @Test
  void login_persistsRefreshTokenWithMatchingJti() {
    when(userRepository.findByEmail(user.getEmail())).thenReturn(Optional.of(user));
    AuthResponse res = service.login(login(user.getEmail(), "Passw0rd!23"));
    ArgumentCaptor<RefreshToken> captor = ArgumentCaptor.forClass(RefreshToken.class);
    verify(refreshTokenRepository).save(captor.capture());
    assertThat(captor.getValue().getTokenId()).isEqualTo(jwt.extractJti(res.getRefreshToken()));
    assertThat(captor.getValue().getExpiresAt()).isAfter(Instant.now().plusSeconds(2592000 - 60));
  }

  @Test
  void login_updatesLastLoginAt() {
    when(userRepository.findByEmail(user.getEmail())).thenReturn(Optional.of(user));
    service.login(login(user.getEmail(), "Passw0rd!23"));
    assertThat(user.getLastLoginAt()).isNotNull();
  }

  @Test
  void login_unknownUserAndWrongPassword_useSameMessage() {
    when(userRepository.findByEmail("ghost@otterworks.dev")).thenReturn(Optional.empty());
    when(userRepository.findByEmail(user.getEmail())).thenReturn(Optional.of(user));
    String a = catchThrowable(() -> service.login(login("ghost@otterworks.dev", "x"))).getMessage();
    String b = catchThrowable(() -> service.login(login(user.getEmail(), "wrong"))).getMessage();
    assertThat(a).isEqualTo(b).isEqualTo("Invalid credentials");
  }

  @Test
  void refresh_rotatesAndRevokesOldToken() {
    String refresh = jwt.generateRefreshToken(user);
    RefreshToken row = stored(jwt.extractJti(refresh), Instant.now().plusSeconds(600));
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse(row.getTokenId()))
        .thenReturn(Optional.of(row));
    when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));

    AuthResponse res = service.refreshToken(refresh);

    assertThat(row.isRevoked()).isTrue();
    assertThat(res.getRefreshToken()).isNotEqualTo(refresh);
    assertThat(jwt.validateTokenAndGetUserId(res.getAccessToken()))
        .isEqualTo(user.getId().toString());
  }

  @Test
  void refresh_rejectsRevokedOrUnknownToken() {
    String refresh = jwt.generateRefreshToken(user);
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse(any())).thenReturn(Optional.empty());
    assertThatThrownBy(() -> service.refreshToken(refresh))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("revoked");
  }

  @Test
  void refresh_rejectsTokenWhoseStoredRowIsExpired() {
    String refresh = jwt.generateRefreshToken(user);
    RefreshToken row = stored(jwt.extractJti(refresh), Instant.now().minusSeconds(1));
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse(row.getTokenId()))
        .thenReturn(Optional.of(row));
    assertThatThrownBy(() -> service.refreshToken(refresh))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("expired");
  }

  @Test
  void refresh_rejectsAccessToken() {
    String access = jwt.generateAccessToken(user);
    assertThatThrownBy(() -> service.refreshToken(access))
        .isInstanceOf(IllegalArgumentException.class);
    verify(refreshTokenRepository, never()).findByTokenIdAndRevokedFalse(any());
  }

  @Test
  void refresh_rejectsJwtExpiredToken() {
    String expired = new JwtTokenProvider(SECRET, -5, -5).generateRefreshToken(user);
    assertThatThrownBy(() -> service.refreshToken(expired)).isInstanceOf(ExpiredJwtException.class);
  }

  @Test
  void refresh_failsWhenUserDeleted() {
    String refresh = jwt.generateRefreshToken(user);
    RefreshToken row = stored(jwt.extractJti(refresh), Instant.now().plusSeconds(600));
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse(row.getTokenId()))
        .thenReturn(Optional.of(row));
    when(userRepository.findById(user.getId())).thenReturn(Optional.empty());
    assertThatThrownBy(() -> service.refreshToken(refresh))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("User not found");
  }

  @Test
  void logout_revokesAllRefreshTokensForUser() {
    service.logout(user.getId());
    verify(refreshTokenRepository).revokeAllByUserId(user.getId());
  }
}

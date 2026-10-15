package com.otterworks.auth.qa;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import com.otterworks.auth.dto.ChangePasswordRequest;
import com.otterworks.auth.dto.LoginRequest;
import com.otterworks.auth.dto.RegisterRequest;
import com.otterworks.auth.entity.RefreshToken;
import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import com.otterworks.auth.security.JwtTokenProvider;
import com.otterworks.auth.service.AuthService;
import java.time.Instant;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

@ExtendWith(MockitoExtension.class)
class AuthServiceQaTest {

  @Mock private UserRepository userRepository;
  @Mock private PasswordEncoder passwordEncoder;
  @Mock private JwtTokenProvider jwtTokenProvider;
  @Mock private RefreshTokenRepository refreshTokenRepository;

  @InjectMocks private AuthService authService;

  private User user;

  @BeforeEach
  void setUp() {
    user = new User();
    user.setId(UUID.randomUUID());
    user.setEmail("qa@otterworks.dev");
    user.setDisplayName("QA User");
    user.setPasswordHash("$2a$12$hash");
    user.setRoles(Set.of(User.Role.USER));
  }

  private void stubTokenIssuance() {
    when(jwtTokenProvider.generateAccessToken(any(User.class))).thenReturn("access");
    when(jwtTokenProvider.generateRefreshToken(any(User.class))).thenReturn("refresh");
    when(jwtTokenProvider.extractJti("refresh")).thenReturn("jti");
    when(jwtTokenProvider.getRefreshTokenExpiry()).thenReturn(2592000L);
    when(jwtTokenProvider.getAccessTokenExpiry()).thenReturn(3600L);
  }

  private static LoginRequest login(String email, String password) {
    LoginRequest request = new LoginRequest();
    request.setEmail(email);
    request.setPassword(password);
    return request;
  }

  @Test
  void registerStoresOnlyTheEncodedPasswordAndUserRole() {
    RegisterRequest request = new RegisterRequest();
    request.setEmail("new@otterworks.dev");
    request.setPassword("PlainText123!");
    request.setDisplayName("New");
    when(userRepository.existsByEmail("new@otterworks.dev")).thenReturn(false);
    when(passwordEncoder.encode("PlainText123!")).thenReturn("$2a$12$encoded");
    when(userRepository.save(any(User.class)))
        .thenAnswer(
            inv -> {
              User u = inv.getArgument(0);
              u.setId(UUID.randomUUID());
              return u;
            });
    stubTokenIssuance();

    authService.register(request);

    ArgumentCaptor<User> saved = ArgumentCaptor.forClass(User.class);
    verify(userRepository).save(saved.capture());
    assertThat(saved.getValue().getPasswordHash()).isEqualTo("$2a$12$encoded");
    assertThat(saved.getValue().getRoles()).containsExactly(User.Role.USER);
  }

  @Test
  void registerDuplicateEmailNeverSaves() {
    RegisterRequest request = new RegisterRequest();
    request.setEmail("qa@otterworks.dev");
    request.setPassword("PlainText123!");
    request.setDisplayName("Dup");
    when(userRepository.existsByEmail("qa@otterworks.dev")).thenReturn(true);

    assertThatThrownBy(() -> authService.register(request))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessage("Email already registered");
    verify(userRepository, never()).save(any());
  }

  @Test
  void loginUnknownEmailAndWrongPasswordGiveTheSameError() {
    when(userRepository.findByEmail("ghost@otterworks.dev")).thenReturn(Optional.empty());
    when(userRepository.findByEmail("qa@otterworks.dev")).thenReturn(Optional.of(user));
    when(passwordEncoder.matches("wrong", user.getPasswordHash())).thenReturn(false);

    Throwable unknown = catchThrowable(() -> authService.login(login("ghost@otterworks.dev", "x")));
    Throwable wrong = catchThrowable(() -> authService.login(login("qa@otterworks.dev", "wrong")));

    assertThat(unknown).isInstanceOf(IllegalArgumentException.class);
    assertThat(wrong).isInstanceOf(IllegalArgumentException.class);
    assertThat(unknown.getMessage()).isEqualTo(wrong.getMessage()).isEqualTo("Invalid credentials");
  }

  @Test
  void failedLoginDoesNotIssueTokensOrTouchLastLogin() {
    when(userRepository.findByEmail("qa@otterworks.dev")).thenReturn(Optional.of(user));
    when(passwordEncoder.matches("wrong", user.getPasswordHash())).thenReturn(false);

    catchThrowable(() -> authService.login(login("qa@otterworks.dev", "wrong")));

    verify(jwtTokenProvider, never()).generateAccessToken(any());
    verify(refreshTokenRepository, never()).save(any());
    assertThat(user.getLastLoginAt()).isNull();
  }

  @Test
  void successfulLoginRecordsLastLoginAndPersistsRefreshToken() {
    when(userRepository.findByEmail("qa@otterworks.dev")).thenReturn(Optional.of(user));
    when(passwordEncoder.matches("right", user.getPasswordHash())).thenReturn(true);
    when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));
    stubTokenIssuance();
    Instant before = Instant.now();

    authService.login(login("qa@otterworks.dev", "right"));

    assertThat(user.getLastLoginAt()).isAfterOrEqualTo(before);
    ArgumentCaptor<RefreshToken> stored = ArgumentCaptor.forClass(RefreshToken.class);
    verify(refreshTokenRepository).save(stored.capture());
    assertThat(stored.getValue().getTokenId()).isEqualTo("jti");
    assertThat(stored.getValue().getUser()).isSameAs(user);
    assertThat(stored.getValue().getExpiresAt()).isAfter(before.plusSeconds(2591000));
  }

  @Test
  void refreshRevokesTheConsumedTokenBeforeIssuingNewOnes() {
    RefreshToken stored = new RefreshToken();
    stored.setTokenId("old-jti");
    stored.setExpiresAt(Instant.now().plusSeconds(60));
    when(jwtTokenProvider.extractJti("old")).thenReturn("old-jti");
    when(jwtTokenProvider.validateRefreshTokenAndGetUserId("old"))
        .thenReturn(user.getId().toString());
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse("old-jti"))
        .thenReturn(Optional.of(stored));
    when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));
    stubTokenIssuance();

    authService.refreshToken("old");

    assertThat(stored.isRevoked()).isTrue();
    verify(refreshTokenRepository, times(2)).save(any(RefreshToken.class));
  }

  @Test
  void refreshWithRevokedOrUnknownTokenIsRejected() {
    when(jwtTokenProvider.extractJti("old")).thenReturn("old-jti");
    when(jwtTokenProvider.validateRefreshTokenAndGetUserId("old"))
        .thenReturn(user.getId().toString());
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse("old-jti"))
        .thenReturn(Optional.empty());

    assertThatThrownBy(() -> authService.refreshToken("old"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("revoked");
    verify(jwtTokenProvider, never()).generateAccessToken(any());
  }

  @Test
  void refreshWithExpiredStoredTokenIsRejected() {
    RefreshToken stored = new RefreshToken();
    stored.setTokenId("old-jti");
    stored.setExpiresAt(Instant.now().minusSeconds(1));
    when(jwtTokenProvider.extractJti("old")).thenReturn("old-jti");
    when(jwtTokenProvider.validateRefreshTokenAndGetUserId("old"))
        .thenReturn(user.getId().toString());
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse("old-jti"))
        .thenReturn(Optional.of(stored));

    assertThatThrownBy(() -> authService.refreshToken("old"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessage("Refresh token expired");
    verify(jwtTokenProvider, never()).generateAccessToken(any());
  }

  @Test
  void refreshForDeletedUserIsRejected() {
    RefreshToken stored = new RefreshToken();
    stored.setTokenId("old-jti");
    stored.setExpiresAt(Instant.now().plusSeconds(60));
    when(jwtTokenProvider.extractJti("old")).thenReturn("old-jti");
    when(jwtTokenProvider.validateRefreshTokenAndGetUserId("old"))
        .thenReturn(user.getId().toString());
    when(refreshTokenRepository.findByTokenIdAndRevokedFalse("old-jti"))
        .thenReturn(Optional.of(stored));
    when(userRepository.findById(user.getId())).thenReturn(Optional.empty());

    assertThatThrownBy(() -> authService.refreshToken("old"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessage("User not found");
  }

  @Test
  void changePasswordWithWrongCurrentPasswordKeepsHashAndSessions() {
    ChangePasswordRequest request = new ChangePasswordRequest();
    request.setCurrentPassword("wrong");
    request.setNewPassword("NewPassw0rd!");
    when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));
    when(passwordEncoder.matches("wrong", "$2a$12$hash")).thenReturn(false);

    assertThatThrownBy(() -> authService.changePassword(user.getId(), request))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessage("Current password is incorrect");
    assertThat(user.getPasswordHash()).isEqualTo("$2a$12$hash");
    verify(refreshTokenRepository, never()).revokeAllByUserId(any());
    verify(passwordEncoder, never()).encode(anyString());
  }

  @Test
  void changePasswordRevokesAllRefreshTokens() {
    ChangePasswordRequest request = new ChangePasswordRequest();
    request.setCurrentPassword("right");
    request.setNewPassword("NewPassw0rd!");
    when(userRepository.findById(user.getId())).thenReturn(Optional.of(user));
    when(passwordEncoder.matches("right", "$2a$12$hash")).thenReturn(true);
    when(passwordEncoder.encode("NewPassw0rd!")).thenReturn("$2a$12$new");

    authService.changePassword(user.getId(), request);

    assertThat(user.getPasswordHash()).isEqualTo("$2a$12$new");
    verify(refreshTokenRepository).revokeAllByUserId(user.getId());
  }

  @Test
  void logoutRevokesAllRefreshTokensForThatUserOnly() {
    authService.logout(user.getId());
    verify(refreshTokenRepository).revokeAllByUserId(user.getId());
    verifyNoMoreInteractions(refreshTokenRepository);
  }
}

package com.otterworks.auth.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

@ExtendWith(MockitoExtension.class)
class AdminBootstrapTest {
  private static final String EMAIL = "qa@example.test";

  @Mock private UserRepository userRepository;
  @Mock private RefreshTokenRepository refreshTokenRepository;
  private final BCryptPasswordEncoder passwordEncoder = new BCryptPasswordEncoder(4);
  private final String password = UUID.randomUUID().toString();

  @Test
  void unsetPasswordDoesNotTouchAccounts() {
    run(EMAIL, "");

    verifyNoInteractions(userRepository, refreshTokenRepository);
  }

  @Test
  void provisionHashesConfiguredPasswordAndGrantsAdminAndUserRoles() {
    when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.empty());

    run(EMAIL, password);

    var captured = ArgumentCaptor.forClass(User.class);
    verify(userRepository).save(captured.capture());
    User admin = captured.getValue();
    assertThat(admin.getEmail()).isEqualTo(EMAIL);
    assertThat(admin.getRoles()).containsExactlyInAnyOrder(User.Role.ADMIN, User.Role.USER);
    assertThat(passwordEncoder.matches(password, admin.getPasswordHash())).isTrue();
  }

  @Test
  void replacedPasswordRevokesRefreshTokens() {
    var admin = new User();
    admin.setId(UUID.randomUUID());
    admin.setRoles(Set.of(User.Role.ADMIN, User.Role.USER));
    admin.setPasswordHash("!revoked");
    when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(admin));

    run(EMAIL, password);

    assertThat(passwordEncoder.matches(password, admin.getPasswordHash())).isTrue();
    verify(refreshTokenRepository).revokeAllByUserId(admin.getId());
  }

  @Test
  void unchangedPasswordDoesNotRevokeSessions() {
    var admin = new User();
    admin.setRoles(Set.of(User.Role.ADMIN, User.Role.USER));
    String originalHash = passwordEncoder.encode(password);
    admin.setPasswordHash(originalHash);
    when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(admin));

    run(EMAIL, password);

    assertThat(admin.getPasswordHash()).isEqualTo(originalHash);
    verifyNoInteractions(refreshTokenRepository);
  }

  @Test
  void bootstrapDoesNotPromoteExistingRegularUser() {
    var user = new User();
    user.setRoles(Set.of(User.Role.USER));
    when(userRepository.findByEmail(EMAIL)).thenReturn(Optional.of(user));

    assertThatThrownBy(() -> run(EMAIL, password)).isInstanceOf(IllegalStateException.class);
    assertThat(user.getRoles()).containsExactly(User.Role.USER);
    verifyNoInteractions(refreshTokenRepository);
  }

  private void run(String email, String password) {
    new AdminBootstrap(email, password, userRepository, passwordEncoder, refreshTokenRepository)
        .run(new DefaultApplicationArguments());
  }
}

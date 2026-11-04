package com.otterworks.auth.bootstrap;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

@ExtendWith(MockitoExtension.class)
class DevAdminPasswordBootstrapTest {

  private static final String LOCKED_HASH = DevAdminPasswordBootstrap.LOCKED_PASSWORD_HASH;

  @Mock private UserRepository userRepository;
  @Mock private RefreshTokenRepository refreshTokenRepository;

  private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder(4);

  private User seededAdmin() {
    User admin = new User();
    admin.setId(DevAdminPasswordBootstrap.SEEDED_ADMIN_ID);
    admin.setEmail("admin@otterworks.dev");
    admin.setDisplayName("Admin User");
    admin.setPasswordHash(LOCKED_HASH);
    return admin;
  }

  @Test
  void lockedSeededAdmin_neverMatchesAnyPassword() {
    assertThat(passwordEncoder.matches("anything-at-all", LOCKED_HASH)).isFalse();
    assertThat(passwordEncoder.matches("", LOCKED_HASH)).isFalse();
  }

  @Test
  void blankPassword_leavesLockedAccountUntouched() {
    when(userRepository.findById(DevAdminPasswordBootstrap.SEEDED_ADMIN_ID))
        .thenReturn(Optional.of(seededAdmin()));

    new DevAdminPasswordBootstrap(userRepository, refreshTokenRepository, passwordEncoder, "")
        .run(null);
    new DevAdminPasswordBootstrap(userRepository, refreshTokenRepository, passwordEncoder, "   ")
        .run(null);

    verify(userRepository, never()).save(any());
    verify(refreshTokenRepository, never()).revokeAllByUserId(any());
  }

  @Test
  void blankPassword_relocksPreviouslyUnlockedAdmin() {
    User admin = seededAdmin();
    admin.setPasswordHash(passwordEncoder.encode("previous-dev-password"));
    when(userRepository.findById(DevAdminPasswordBootstrap.SEEDED_ADMIN_ID))
        .thenReturn(Optional.of(admin));

    new DevAdminPasswordBootstrap(userRepository, refreshTokenRepository, passwordEncoder, "")
        .run(null);

    verify(userRepository).save(admin);
    verify(refreshTokenRepository).revokeAllByUserId(DevAdminPasswordBootstrap.SEEDED_ADMIN_ID);
    assertThat(admin.getPasswordHash()).isEqualTo(LOCKED_HASH);
    assertThat(passwordEncoder.matches("previous-dev-password", admin.getPasswordHash())).isFalse();
  }

  @Test
  void shortPassword_failsFastWithoutTouchingTheAccount() {
    DevAdminPasswordBootstrap bootstrap =
        new DevAdminPasswordBootstrap(
            userRepository, refreshTokenRepository, passwordEncoder, "too-short");

    assertThatThrownBy(() -> bootstrap.run(null)).isInstanceOf(IllegalStateException.class);
    verify(userRepository, never()).save(any());
  }

  @Test
  void configuredPassword_setsBcryptHashOnSeededAdmin() {
    User admin = seededAdmin();
    when(userRepository.findById(DevAdminPasswordBootstrap.SEEDED_ADMIN_ID))
        .thenReturn(Optional.of(admin));

    new DevAdminPasswordBootstrap(
            userRepository, refreshTokenRepository, passwordEncoder, "local-dev-only-pass")
        .run(null);

    verify(userRepository).save(admin);
    assertThat(admin.getPasswordHash()).isNotEqualTo(LOCKED_HASH);
    assertThat(passwordEncoder.matches("local-dev-only-pass", admin.getPasswordHash())).isTrue();
    assertThat(passwordEncoder.matches("wrong-password-here", admin.getPasswordHash())).isFalse();
  }

  @Test
  void missingSeededAdmin_isIgnored() {
    when(userRepository.findById(DevAdminPasswordBootstrap.SEEDED_ADMIN_ID))
        .thenReturn(Optional.empty());

    new DevAdminPasswordBootstrap(
            userRepository, refreshTokenRepository, passwordEncoder, "local-dev-only-pass")
        .run(null);

    verify(userRepository, never()).save(any());
  }
}

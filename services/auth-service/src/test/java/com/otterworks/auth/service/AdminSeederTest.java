package com.otterworks.auth.service;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

import com.otterworks.auth.config.AdminSeedConfig;
import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.boot.DefaultApplicationArguments;
import org.springframework.security.crypto.password.PasswordEncoder;

@ExtendWith(MockitoExtension.class)
class AdminSeederTest {

  @Mock private UserRepository userRepository;
  @Mock private RefreshTokenRepository refreshTokenRepository;
  @Mock private PasswordEncoder passwordEncoder;

  private AdminSeedConfig seedConfig;
  private AdminSeeder adminSeeder;

  @BeforeEach
  void setUp() {
    seedConfig = new AdminSeedConfig();
    seedConfig.setEmail("admin@otterworks.dev");
    adminSeeder =
        new AdminSeeder(seedConfig, userRepository, refreshTokenRepository, passwordEncoder);
  }

  @Test
  void run_shouldSkipWhenNoPasswordConfigured() {
    seedConfig.setPassword("");

    adminSeeder.run(new DefaultApplicationArguments());

    verifyNoInteractions(userRepository, refreshTokenRepository, passwordEncoder);
  }

  @Test
  void run_shouldCreateAdminWithRuntimeHashWhenMissing() {
    seedConfig.setPassword("runtime-secret");
    when(userRepository.findByEmail("admin@otterworks.dev")).thenReturn(Optional.empty());
    when(passwordEncoder.encode("runtime-secret")).thenReturn("$2a$12$encoded");
    when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

    adminSeeder.run(new DefaultApplicationArguments());

    ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
    verify(userRepository).save(captor.capture());
    User saved = captor.getValue();
    assertThat(saved.getEmail()).isEqualTo("admin@otterworks.dev");
    assertThat(saved.getPasswordHash()).isEqualTo("$2a$12$encoded");
    assertThat(saved.getDisplayName()).isEqualTo("Admin User");
    assertThat(saved.isEmailVerified()).isTrue();
    assertThat(saved.getRoles()).containsExactlyInAnyOrder(User.Role.ADMIN, User.Role.USER);
    verifyNoInteractions(refreshTokenRepository);
  }

  @Test
  void run_shouldRekeyAndRevokeSessionsWhenStoredHashIsRevoked() {
    seedConfig.setPassword("runtime-secret");
    User existing = existingAdmin("!");
    when(userRepository.findByEmail("admin@otterworks.dev")).thenReturn(Optional.of(existing));
    when(passwordEncoder.matches("runtime-secret", "!")).thenReturn(false);
    when(passwordEncoder.encode("runtime-secret")).thenReturn("$2a$12$fresh");
    when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

    adminSeeder.run(new DefaultApplicationArguments());

    assertThat(existing.getPasswordHash()).isEqualTo("$2a$12$fresh");
    assertThat(existing.getRoles()).containsExactlyInAnyOrder(User.Role.ADMIN, User.Role.USER);
    verify(refreshTokenRepository).revokeAllByUserId(existing.getId());
    verify(userRepository).save(existing);
  }

  @Test
  void run_shouldLeaveMatchingHashUntouched() {
    seedConfig.setPassword("runtime-secret");
    User existing = existingAdmin("$2a$12$current");
    when(userRepository.findByEmail("admin@otterworks.dev")).thenReturn(Optional.of(existing));
    when(passwordEncoder.matches("runtime-secret", "$2a$12$current")).thenReturn(true);
    when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));

    adminSeeder.run(new DefaultApplicationArguments());

    assertThat(existing.getPasswordHash()).isEqualTo("$2a$12$current");
    verify(passwordEncoder, never()).encode(anyString());
    verifyNoInteractions(refreshTokenRepository);
  }

  private User existingAdmin(String passwordHash) {
    User user = new User();
    user.setId(UUID.randomUUID());
    user.setEmail("admin@otterworks.dev");
    user.setDisplayName("Admin User");
    user.setPasswordHash(passwordHash);
    user.setRoles(Set.of(User.Role.USER));
    return user;
  }
}

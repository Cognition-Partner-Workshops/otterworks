package com.otterworks.auth.config;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;

@ExtendWith(MockitoExtension.class)
class DevAdminSeederTest {

  private static final String ADMIN_EMAIL = "admin@otterworks.dev";

  @Mock private UserRepository userRepository;

  private final PasswordEncoder passwordEncoder = new BCryptPasswordEncoder(4);

  @BeforeEach
  void setUp() {
    lenient().when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));
  }

  @Test
  void run_shouldCreateAdminWithConfiguredPassword() {
    when(userRepository.existsByEmail(ADMIN_EMAIL)).thenReturn(false);
    DevAdminSeeder seeder =
        new DevAdminSeeder(
            userRepository, passwordEncoder, ADMIN_EMAIL, "Admin User", "s3cret-dev");

    seeder.run(null);

    ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
    verify(userRepository).save(captor.capture());
    User saved = captor.getValue();
    assertThat(saved.getEmail()).isEqualTo(ADMIN_EMAIL);
    assertThat(saved.getDisplayName()).isEqualTo("Admin User");
    assertThat(saved.isEmailVerified()).isTrue();
    assertThat(saved.getRoles()).containsExactlyInAnyOrder(User.Role.ADMIN, User.Role.USER);
    assertThat(passwordEncoder.matches("s3cret-dev", saved.getPasswordHash())).isTrue();
  }

  @Test
  void run_shouldGenerateRandomPasswordWhenNoneConfigured() {
    when(userRepository.existsByEmail(ADMIN_EMAIL)).thenReturn(false);
    DevAdminSeeder seeder =
        new DevAdminSeeder(userRepository, passwordEncoder, ADMIN_EMAIL, "Admin User", "");

    seeder.run(null);

    ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
    verify(userRepository).save(captor.capture());
    assertThat(passwordEncoder.matches("Admin123!", captor.getValue().getPasswordHash())).isFalse();
  }

  @Test
  void run_shouldSkipWhenAdminAlreadyExists() {
    when(userRepository.existsByEmail(ADMIN_EMAIL)).thenReturn(true);
    DevAdminSeeder seeder =
        new DevAdminSeeder(userRepository, passwordEncoder, ADMIN_EMAIL, "Admin User", "");

    seeder.run(null);

    verify(userRepository, never()).save(any(User.class));
  }

  @Test
  void generatePassword_shouldBeUniqueAndLongEnough() {
    String first = DevAdminSeeder.generatePassword();
    String second = DevAdminSeeder.generatePassword();

    assertThat(first).hasSizeGreaterThanOrEqualTo(24);
    assertThat(first).isNotEqualTo(second);
  }
}

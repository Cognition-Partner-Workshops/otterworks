package com.otterworks.auth.service;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.nio.charset.StandardCharsets;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
class AdminBootstrap implements ApplicationRunner {
  private final String email;
  private final String password;
  private final UserRepository userRepository;
  private final PasswordEncoder passwordEncoder;
  private final RefreshTokenRepository refreshTokenRepository;

  AdminBootstrap(
      @Value("${OTTERWORKS_ADMIN_EMAIL:}") String email,
      @Value("${OTTERWORKS_ADMIN_PASSWORD:}") String password,
      UserRepository userRepository,
      PasswordEncoder passwordEncoder,
      RefreshTokenRepository refreshTokenRepository) {
    this.email = email;
    this.password = password;
    this.userRepository = userRepository;
    this.passwordEncoder = passwordEncoder;
    this.refreshTokenRepository = refreshTokenRepository;
  }

  @Override
  @Transactional
  public void run(ApplicationArguments args) {
    if (password.isEmpty()) {
      return;
    }
    if (email.isBlank()
        || password.isBlank()
        || password.getBytes(StandardCharsets.UTF_8).length > 72) {
      throw new IllegalStateException("Invalid administrator bootstrap configuration");
    }

    User admin = userRepository.findByEmail(email).orElse(null);
    if (admin == null) {
      admin = new User();
      admin.setEmail(email);
      admin.setDisplayName("Admin User");
      admin.setEmailVerified(true);
      admin.setRoles(Set.of(User.Role.ADMIN, User.Role.USER));
      admin.setPasswordHash(passwordEncoder.encode(password));
      userRepository.save(admin);
      return;
    }
    if (!admin.getRoles().contains(User.Role.ADMIN)) {
      throw new IllegalStateException("Administrator bootstrap email belongs to a non-admin user");
    }
    if (!passwordEncoder.matches(password, admin.getPasswordHash())) {
      admin.setPasswordHash(passwordEncoder.encode(password));
      refreshTokenRepository.revokeAllByUserId(admin.getId());
    }
  }
}

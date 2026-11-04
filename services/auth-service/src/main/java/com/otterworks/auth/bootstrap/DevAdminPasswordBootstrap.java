package com.otterworks.auth.bootstrap;

import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

/**
 * Local-dev only: sets the seeded admin account's password from DEV_ADMIN_PASSWORD. The account
 * ships locked (V5 migration), so it stays unusable unless a developer opts in explicitly;
 * unsetting the variable locks it again on the next start.
 */
@Component
@Profile("dev")
public class DevAdminPasswordBootstrap implements ApplicationRunner {

  private static final Logger log = LoggerFactory.getLogger(DevAdminPasswordBootstrap.class);

  static final UUID SEEDED_ADMIN_ID = UUID.fromString("a0000000-0000-0000-0000-000000000001");
  static final int MIN_PASSWORD_LENGTH = 12;
  static final String LOCKED_PASSWORD_HASH = "{disabled}";

  private final UserRepository userRepository;
  private final RefreshTokenRepository refreshTokenRepository;
  private final PasswordEncoder passwordEncoder;
  private final String password;

  public DevAdminPasswordBootstrap(
      UserRepository userRepository,
      RefreshTokenRepository refreshTokenRepository,
      PasswordEncoder passwordEncoder,
      @Value("${otterworks.dev-admin.password:}") String password) {
    this.userRepository = userRepository;
    this.refreshTokenRepository = refreshTokenRepository;
    this.passwordEncoder = passwordEncoder;
    this.password = password;
  }

  @Override
  @Transactional
  public void run(ApplicationArguments args) {
    if (password == null || password.isBlank()) {
      lockSeededAdmin();
      return;
    }
    if (password.length() < MIN_PASSWORD_LENGTH) {
      throw new IllegalStateException(
          "DEV_ADMIN_PASSWORD must be at least " + MIN_PASSWORD_LENGTH + " characters");
    }
    userRepository
        .findById(SEEDED_ADMIN_ID)
        .ifPresentOrElse(
            admin -> {
              admin.setPasswordHash(passwordEncoder.encode(password));
              userRepository.save(admin);
              log.info("Seeded admin password set from DEV_ADMIN_PASSWORD");
            },
            () -> log.warn("Seeded admin account not found; DEV_ADMIN_PASSWORD ignored"));
  }

  private void lockSeededAdmin() {
    userRepository
        .findById(SEEDED_ADMIN_ID)
        .filter(admin -> !LOCKED_PASSWORD_HASH.equals(admin.getPasswordHash()))
        .ifPresentOrElse(
            admin -> {
              admin.setPasswordHash(LOCKED_PASSWORD_HASH);
              userRepository.save(admin);
              refreshTokenRepository.revokeAllByUserId(SEEDED_ADMIN_ID);
              log.info("DEV_ADMIN_PASSWORD not set; seeded admin account locked again");
            },
            () -> log.info("DEV_ADMIN_PASSWORD not set; seeded admin account stays locked"));
  }
}

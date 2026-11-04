package com.otterworks.auth.bootstrap;

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
 * ships locked (V5 migration), so it stays unusable unless a developer opts in explicitly.
 */
@Component
@Profile("dev")
public class DevAdminPasswordBootstrap implements ApplicationRunner {

  private static final Logger log = LoggerFactory.getLogger(DevAdminPasswordBootstrap.class);

  static final UUID SEEDED_ADMIN_ID = UUID.fromString("a0000000-0000-0000-0000-000000000001");
  static final int MIN_PASSWORD_LENGTH = 12;

  private final UserRepository userRepository;
  private final PasswordEncoder passwordEncoder;
  private final String password;

  public DevAdminPasswordBootstrap(
      UserRepository userRepository,
      PasswordEncoder passwordEncoder,
      @Value("${otterworks.dev-admin.password:}") String password) {
    this.userRepository = userRepository;
    this.passwordEncoder = passwordEncoder;
    this.password = password;
  }

  @Override
  @Transactional
  public void run(ApplicationArguments args) {
    if (password == null || password.isBlank()) {
      log.info("DEV_ADMIN_PASSWORD not set; seeded admin account stays locked");
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
}

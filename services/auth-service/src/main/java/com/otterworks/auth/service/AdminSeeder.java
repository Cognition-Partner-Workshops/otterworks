package com.otterworks.auth.service;

import com.otterworks.auth.config.AdminSeedConfig;
import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.RefreshTokenRepository;
import com.otterworks.auth.repository.UserRepository;
import java.util.EnumSet;
import java.util.HashSet;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

/**
 * Creates (or re-keys) the bootstrap admin from {@link AdminSeedConfig} at startup. The password
 * only ever exists as runtime configuration; the stored value is a bcrypt hash produced here.
 */
@Component
public class AdminSeeder implements ApplicationRunner {

  private static final Logger log = LoggerFactory.getLogger(AdminSeeder.class);
  private static final Set<User.Role> ADMIN_ROLES = EnumSet.of(User.Role.ADMIN, User.Role.USER);

  private final AdminSeedConfig seedConfig;
  private final UserRepository userRepository;
  private final RefreshTokenRepository refreshTokenRepository;
  private final PasswordEncoder passwordEncoder;

  public AdminSeeder(
      AdminSeedConfig seedConfig,
      UserRepository userRepository,
      RefreshTokenRepository refreshTokenRepository,
      PasswordEncoder passwordEncoder) {
    this.seedConfig = seedConfig;
    this.userRepository = userRepository;
    this.refreshTokenRepository = refreshTokenRepository;
    this.passwordEncoder = passwordEncoder;
  }

  @Override
  @Transactional
  public void run(ApplicationArguments args) {
    String password = seedConfig.getPassword();
    String email = seedConfig.getEmail();
    if (!StringUtils.hasText(password)) {
      log.info("ADMIN_SEED_PASSWORD not set; skipping bootstrap admin seeding");
      return;
    }
    if (!StringUtils.hasText(email)) {
      log.warn(
          "ADMIN_SEED_PASSWORD is set but ADMIN_SEED_EMAIL is empty; skipping bootstrap admin");
      return;
    }

    User admin =
        userRepository
            .findByEmail(email)
            .map(existing -> rekeyIfNeeded(existing, password))
            .orElseGet(() -> newAdmin(email, password));

    Set<User.Role> roles = new HashSet<>(admin.getRoles());
    roles.addAll(ADMIN_ROLES);
    admin.setRoles(roles);
    userRepository.save(admin);
    log.info("Bootstrap admin ensured: email={}", email);
  }

  private User rekeyIfNeeded(User existing, String password) {
    if (!passwordEncoder.matches(password, existing.getPasswordHash())) {
      existing.setPasswordHash(passwordEncoder.encode(password));
      refreshTokenRepository.revokeAllByUserId(existing.getId());
      log.info("Bootstrap admin password rotated: email={}", existing.getEmail());
    }
    return existing;
  }

  private User newAdmin(String email, String password) {
    User admin = new User();
    admin.setEmail(email);
    admin.setPasswordHash(passwordEncoder.encode(password));
    admin.setDisplayName(seedConfig.getDisplayName());
    admin.setEmailVerified(true);
    return admin;
  }
}

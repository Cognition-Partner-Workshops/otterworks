package com.otterworks.auth.config;

import com.otterworks.auth.entity.User;
import com.otterworks.auth.repository.UserRepository;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Profile;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * Creates a local-development admin account at startup. Only active under the {@code dev} profile,
 * so deployed environments (which run with {@code prod}) never get a seeded admin. The password
 * comes from {@code AUTH_DEV_ADMIN_PASSWORD}; when unset, a random one is generated and printed in
 * the startup log.
 */
@Component
@Profile("dev")
@ConditionalOnProperty(
    prefix = "auth.dev-admin",
    name = "enabled",
    havingValue = "true",
    matchIfMissing = true)
public class DevAdminSeeder implements ApplicationRunner {

  private static final Logger log = LoggerFactory.getLogger(DevAdminSeeder.class);
  private static final SecureRandom secureRandom = new SecureRandom();
  private static final int GENERATED_PASSWORD_BYTES = 18;

  private final UserRepository userRepository;
  private final PasswordEncoder passwordEncoder;
  private final String email;
  private final String displayName;
  private final String configuredPassword;

  public DevAdminSeeder(
      UserRepository userRepository,
      PasswordEncoder passwordEncoder,
      @Value("${auth.dev-admin.email}") String email,
      @Value("${auth.dev-admin.display-name}") String displayName,
      @Value("${auth.dev-admin.password:}") String configuredPassword) {
    this.userRepository = userRepository;
    this.passwordEncoder = passwordEncoder;
    this.email = email;
    this.displayName = displayName;
    this.configuredPassword = configuredPassword;
  }

  @Override
  public void run(ApplicationArguments args) {
    if (userRepository.existsByEmail(email)) {
      log.debug("Dev admin {} already exists, skipping seed", email);
      return;
    }

    boolean generated = configuredPassword == null || configuredPassword.isBlank();
    String password = generated ? generatePassword() : configuredPassword;

    User user = new User();
    user.setEmail(email);
    user.setPasswordHash(passwordEncoder.encode(password));
    user.setDisplayName(displayName);
    user.setEmailVerified(true);
    user.setRoles(Set.of(User.Role.ADMIN, User.Role.USER));
    userRepository.save(user);

    if (generated) {
      log.warn(
          "Seeded dev admin {} with generated password: {} "
              + "(set AUTH_DEV_ADMIN_PASSWORD to choose your own)",
          email,
          password);
    } else {
      log.info("Seeded dev admin {} with the password from AUTH_DEV_ADMIN_PASSWORD", email);
    }
  }

  static String generatePassword() {
    byte[] bytes = new byte[GENERATED_PASSWORD_BYTES];
    secureRandom.nextBytes(bytes);
    return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
  }
}

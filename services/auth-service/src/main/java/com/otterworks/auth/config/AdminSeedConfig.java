package com.otterworks.auth.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * Bootstrap admin account, supplied through the environment (ADMIN_SEED_EMAIL /
 * ADMIN_SEED_PASSWORD) and hashed at startup instead of being committed as a bcrypt hash in a
 * migration. Seeding is skipped entirely when no password is configured.
 */
@Configuration
@ConfigurationProperties(prefix = "auth.seed-admin")
@Getter
@Setter
public class AdminSeedConfig {
  private String email;
  private String password;
  private String displayName = "Admin User";
}

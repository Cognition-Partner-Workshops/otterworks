package com.otterworks.auth.config;

import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class FlywayConfig {

  /**
   * V1 was rewritten to drop a leaked bcrypt hash, so databases migrated before that change hold a
   * stale checksum for it. Repair realigns applied checksums with the files on the classpath before
   * migrating, so those databases keep starting instead of failing validation.
   */
  @Bean
  public FlywayMigrationStrategy repairThenMigrate() {
    return flyway -> {
      flyway.repair();
      flyway.migrate();
    };
  }
}

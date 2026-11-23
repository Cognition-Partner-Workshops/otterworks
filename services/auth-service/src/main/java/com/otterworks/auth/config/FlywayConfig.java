package com.otterworks.auth.config;

import java.util.Objects;
import org.flywaydb.core.Flyway;
import org.flywaydb.core.api.ErrorCode;
import org.flywaydb.core.api.MigrationVersion;
import org.springframework.boot.autoconfigure.flyway.FlywayMigrationStrategy;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
class FlywayConfig {
  private static final MigrationVersion USERS_SCHEMA = MigrationVersion.fromVersion("1");
  private static final int SEEDED_USERS_CHECKSUM = -1077113232;

  @Bean
  FlywayMigrationStrategy migrateAuthSchema() {
    return flyway -> {
      if (hasSeededUsersMigration(flyway) && onlyUsersChecksumMismatch(flyway)) {
        flyway.repair();
      }
      flyway.migrate();
    };
  }

  private boolean hasSeededUsersMigration(Flyway flyway) {
    for (var migration : flyway.info().applied()) {
      if (USERS_SCHEMA.equals(migration.getVersion())
          && Objects.equals(migration.getChecksum(), SEEDED_USERS_CHECKSUM)) {
        return true;
      }
    }
    return false;
  }

  private boolean onlyUsersChecksumMismatch(Flyway flyway) {
    var validation =
        Flyway.configure(flyway.getConfiguration().getClassLoader())
            .configuration(flyway.getConfiguration())
            .ignoreMigrationPatterns("*:pending")
            .load()
            .validateWithResult();
    return validation.invalidMigrations.size() == 1
        && USERS_SCHEMA.getVersion().equals(validation.invalidMigrations.get(0).version)
        && validation.invalidMigrations.get(0).errorDetails.errorCode
            == ErrorCode.CHECKSUM_MISMATCH;
  }
}

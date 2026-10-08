package com.otterworks.auth.migration;

import static org.assertj.core.api.Assertions.*;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/**
 * Guards against credentials being seeded through Flyway migrations, which run in every
 * environment.
 */
class MigrationScriptsTest {

  private static final Pattern BCRYPT_HASH = Pattern.compile("\\$2[abxy]\\$\\d{2}\\$");
  private static final Pattern USER_INSERT =
      Pattern.compile("INSERT\\s+INTO\\s+users\\b", Pattern.CASE_INSENSITIVE);

  @Test
  void migrations_shouldNotSeedUsersOrContainPasswordHashes() throws IOException {
    Resource[] migrations =
        new PathMatchingResourcePatternResolver().getResources("classpath:db/migration/*.sql");
    assertThat(migrations).isNotEmpty();

    for (Resource migration : migrations) {
      String sql = migration.getContentAsString(StandardCharsets.UTF_8);
      assertThat(sql)
          .as("%s must not contain a bcrypt password hash", migration.getFilename())
          .doesNotContainPattern(BCRYPT_HASH);
      assertThat(sql)
          .as("%s must not seed rows into users", migration.getFilename())
          .doesNotContainPattern(USER_INSERT);
    }
  }
}

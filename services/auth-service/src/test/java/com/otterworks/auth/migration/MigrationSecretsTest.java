package com.otterworks.auth.migration;

import static org.assertj.core.api.Assertions.*;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

/** Guards against committing credentials (SonarCloud secrets:S8215) in Flyway migrations. */
class MigrationSecretsTest {

  private static final Pattern BCRYPT_HASH =
      Pattern.compile("\\$2[abxy]?\\$\\d{2}\\$[./A-Za-z0-9]{53}");

  @Test
  void migrations_shouldNotContainPasswordHashes() throws IOException {
    Resource[] migrations =
        new PathMatchingResourcePatternResolver().getResources("classpath:db/migration/*.sql");
    assertThat(migrations).isNotEmpty();

    for (Resource migration : migrations) {
      String sql = migration.getContentAsString(StandardCharsets.UTF_8);
      assertThat(BCRYPT_HASH.matcher(sql).find())
          .as("%s must not contain a bcrypt password hash", migration.getFilename())
          .isFalse();
    }
  }
}

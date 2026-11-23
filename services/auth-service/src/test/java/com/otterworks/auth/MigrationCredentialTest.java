package com.otterworks.auth;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.regex.Pattern;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;

class MigrationCredentialTest {
  private static final Pattern BCRYPT = Pattern.compile("\\$2[aby]\\$[0-9]{2}\\$[./A-Za-z0-9]{53}");

  @Test
  void migrationsDoNotShipBcryptVerifiers() throws Exception {
    Resource[] migrations =
        new PathMatchingResourcePatternResolver().getResources("classpath*:db/migration/*.sql");
    assertThat(migrations).isNotEmpty();
    for (Resource migration : migrations) {
      assertThat(BCRYPT.matcher(migration.getContentAsString(StandardCharsets.UTF_8)).find())
          .as("bcrypt verifier in %s", migration.getFilename())
          .isFalse();
    }
  }
}

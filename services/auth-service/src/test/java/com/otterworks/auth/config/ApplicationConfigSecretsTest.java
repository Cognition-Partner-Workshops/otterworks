package com.otterworks.auth.config;

import static org.assertj.core.api.Assertions.*;

import java.io.IOException;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.env.MockEnvironment;

/**
 * Guards against committed credential fallbacks in application.yml: the JWT signing secret and the
 * datasource password must come from the environment, and startup must fail when they are absent.
 */
class ApplicationConfigSecretsTest {

  private MockEnvironment environment;

  @BeforeEach
  void loadApplicationYaml() throws IOException {
    environment = new MockEnvironment();
    List<PropertySource<?>> sources =
        new YamlPropertySourceLoader()
            .load("application", new ClassPathResource("application.yml"));
    sources.forEach(environment.getPropertySources()::addLast);
  }

  @Test
  void jwtSecret_shouldHaveNoFallbackWhenEnvUnset() {
    assertThat(rawProperty("jwt.secret")).isEqualTo("${JWT_SECRET}");
    assertThatThrownBy(() -> environment.getProperty("jwt.secret"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("JWT_SECRET");
  }

  @Test
  void datasourcePassword_shouldHaveNoFallbackWhenEnvUnset() {
    assertThat(rawProperty("spring.datasource.password"))
        .isEqualTo("${SPRING_DATASOURCE_PASSWORD}");
    assertThatThrownBy(() -> environment.getProperty("spring.datasource.password"))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessageContaining("SPRING_DATASOURCE_PASSWORD");
  }

  @Test
  void secrets_shouldResolveFromEnvironment() {
    environment.setProperty("JWT_SECRET", "from-env");
    environment.setProperty("SPRING_DATASOURCE_PASSWORD", "from-env-too");

    assertThat(environment.getProperty("jwt.secret")).isEqualTo("from-env");
    assertThat(environment.getProperty("spring.datasource.password")).isEqualTo("from-env-too");
  }

  private Object rawProperty(String key) {
    return environment.getPropertySources().get("application").getProperty(key);
  }
}

package com.otterworks.auth.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.context.PropertyPlaceholderAutoConfiguration;
import org.springframework.boot.test.context.ConfigDataApplicationContextInitializer;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;

class JwtStartupTest {

  private ApplicationContextRunner contextRunner(Map<String, Object> environment) {
    return new ApplicationContextRunner()
        .withPropertyValues(
            "spring.config.location=classpath:application.yml", "spring.profiles.active=dev")
        .withInitializer(
            context -> {
              var sources = context.getEnvironment().getPropertySources();
              sources.remove(StandardEnvironment.SYSTEM_PROPERTIES_PROPERTY_SOURCE_NAME);
              sources.replace(
                  StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME,
                  new SystemEnvironmentPropertySource(
                      StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME, environment));
              new ConfigDataApplicationContextInitializer().initialize(context);
            })
        .withConfiguration(AutoConfigurations.of(PropertyPlaceholderAutoConfiguration.class))
        .withUserConfiguration(JwtTokenProvider.class);
  }

  @Test
  void startupFailsWithoutJwtSecret() {
    contextRunner(Map.of())
        .run(
            context -> {
              assertThat(context).hasFailed();
              assertThat(context.getStartupFailure()).hasStackTraceContaining("JWT_SECRET");
            });
  }

  @ParameterizedTest
  @ValueSource(strings = {"", " ", "\t\n", "                                "})
  void startupFailsWithBlankJwtSecret(String secret) {
    contextRunner(Map.of("JWT_SECRET", secret))
        .run(
            context -> {
              assertThat(context).hasFailed();
              assertThat(context.getStartupFailure())
                  .hasRootCauseMessage("JWT_SECRET must be set and not blank");
            });
  }

  @Test
  void startupSucceedsWithExplicitJwtSecret() {
    contextRunner(Map.of("JWT_SECRET", "unit-test-only-signing-key-at-least-32-bytes"))
        .run(
            context -> {
              assertThat(context).hasNotFailed();
              assertThat(context).hasSingleBean(JwtTokenProvider.class);
            });
  }
}

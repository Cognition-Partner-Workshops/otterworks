package com.otterworks.commission.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.env.PropertySource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.env.MockPropertySource;

import com.otterworks.commission.common.DatasourceCredential;

class DatasourceCredentialConfigTest {

    private static final String PASSWORD = "spring.datasource.password";

    /** The packaged application*.yml files with only the given overrides (no OS env, no system properties). */
    private static StandardEnvironment environment(MockPropertySource overrides) throws IOException {
        StandardEnvironment env = new StandardEnvironment();
        env.getPropertySources().remove(StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME);
        env.getPropertySources().remove(StandardEnvironment.SYSTEM_PROPERTIES_PROPERTY_SOURCE_NAME);
        env.getPropertySources().addFirst(overrides);
        for (String file : List.of("application.yml", "application-oracle.yml", "application-postgres.yml")) {
            new YamlPropertySourceLoader().load(file, new ClassPathResource(file))
                    .forEach(env.getPropertySources()::addLast);
        }
        return env;
    }

    @Test
    void passwordHasNoLiteralFallback() throws IOException {
        StandardEnvironment env = environment(new MockPropertySource());
        int declared = 0;
        for (PropertySource<?> source : env.getPropertySources()) {
            Object raw = source.getProperty(PASSWORD);
            if (raw != null) {
                declared++;
                assertThat(raw.toString()).isEqualTo("${COMMISSION_DB_PASSWORD}");
            }
        }
        assertThat(declared).isEqualTo(1);
    }

    @Test
    void unsetPasswordStopsStartup() throws IOException {
        StandardEnvironment env = environment(new MockPropertySource());
        assertThatThrownBy(() -> new DatasourceCredential(env))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("COMMISSION_DB_PASSWORD");
    }

    @Test
    void blankPasswordStopsStartup() throws IOException {
        StandardEnvironment env = environment(new MockPropertySource().withProperty("COMMISSION_DB_PASSWORD", " "));
        assertThatThrownBy(() -> new DatasourceCredential(env)).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void passwordComesFromTheSecretStore() throws IOException {
        StandardEnvironment env = environment(new MockPropertySource().withProperty("COMMISSION_DB_PASSWORD", "from-secret"));
        assertThat(env.getProperty(PASSWORD)).isEqualTo("from-secret");
        assertThatCode(() -> new DatasourceCredential(env)).doesNotThrowAnyException();
    }
}

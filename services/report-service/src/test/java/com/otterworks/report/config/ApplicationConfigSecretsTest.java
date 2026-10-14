package com.otterworks.report.config;

import org.junit.Before;
import org.junit.Test;
import org.springframework.boot.env.PropertiesPropertySourceLoader;
import org.springframework.core.env.PropertySource;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.env.MockEnvironment;

import java.io.IOException;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

/**
 * Guards against a committed database password fallback in application.properties:
 * DB_PASSWORD must come from the environment and startup must fail when it is absent.
 */
public class ApplicationConfigSecretsTest {

    private MockEnvironment environment;

    @Before
    public void loadApplicationProperties() throws IOException {
        environment = new MockEnvironment();
        List<PropertySource<?>> sources = new PropertiesPropertySourceLoader()
                .load("application", new ClassPathResource("application.properties"));
        for (PropertySource<?> source : sources) {
            environment.getPropertySources().addLast(source);
        }
    }

    @Test
    public void datasourcePasswordHasNoFallbackWhenEnvUnset() {
        Object raw = environment.getPropertySources().get("application")
                .getProperty("spring.datasource.password");
        assertEquals("${DB_PASSWORD}", raw);
        try {
            environment.getProperty("spring.datasource.password");
            fail("expected unresolved DB_PASSWORD placeholder to fail");
        } catch (IllegalArgumentException e) {
            assertTrue(e.getMessage().contains("DB_PASSWORD"));
        }
    }

    @Test
    public void datasourcePasswordResolvesFromEnvironment() {
        environment.setProperty("DB_PASSWORD", "from-env");
        assertEquals("from-env", environment.getProperty("spring.datasource.password"));
    }
}

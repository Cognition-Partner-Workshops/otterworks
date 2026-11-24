package com.otterworks.rating;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import com.otterworks.rating.controller.AdminController;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.http.HttpStatus;
import org.springframework.mock.env.MockEnvironment;

class AdminControllerTest {

    private static final String TABLE_NAME = "class-factors.dat";
    private static final Path SHIPPED_TABLE = Path.of("../legacy-rating/tables", TABLE_NAME);
    private static final String SUPPORT_KEY = "test-key";

    @TempDir
    private Path tables;

    private AdminController controller;

    @BeforeEach
    void setUp() throws Exception {
        Files.copy(SHIPPED_TABLE, tables.resolve(TABLE_NAME));
        var environment = new MockEnvironment();
        String name = StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME;
        environment.getPropertySources().addFirst(new SystemEnvironmentPropertySource(name,
                Map.of("RATING_SUPPORT_KEY", SUPPORT_KEY)));
        controller = new AdminController(new RatingProperties(tables.toString(), null), mock(QuoteAuditStore.class),
                environment);
    }

    @ParameterizedTest
    @NullSource
    @ValueSource(strings = "invalid-support-key")
    void refusesTableAccessWithoutTheCorrectKey(String key) throws Exception {
        var response = controller.table(TABLE_NAME, key);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(response.getBody()).isNull();
    }

    @Test
    void rejectsAMalformedFilename() throws Exception {
        var response = controller.table("base rates.csv", SUPPORT_KEY);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNull();
    }

    @Test
    void reportsAMissingTable() throws Exception {
        var response = controller.table("missing.csv", SUPPORT_KEY);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(response.getBody()).isNull();
    }

    @Test
    void returnsTheExactTableContents() throws Exception {
        var response = controller.table(TABLE_NAME, SUPPORT_KEY);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isEqualTo(Files.readString(SHIPPED_TABLE));
    }
}

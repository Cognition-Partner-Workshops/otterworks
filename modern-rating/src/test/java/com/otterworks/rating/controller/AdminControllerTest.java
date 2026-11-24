package com.otterworks.rating.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import java.util.Map;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.NullSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.http.HttpStatus;
import org.springframework.mock.env.MockEnvironment;

class AdminControllerTest {

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = " ")
    void supportKeyCheckFailsClosedWithoutConfiguration(String configuredKey) {
        var admin = new AdminController(new RatingProperties(null, null), mock(QuoteAuditStore.class),
                environmentWithSupportKey(configuredKey));
        String suppliedKey = configuredKey == null ? "test-key" : configuredKey;

        assertThat(admin.allowed(suppliedKey)).isFalse();
    }

    @ParameterizedTest
    @NullSource
    @ValueSource(strings = "different-test-key")
    void deniesSupportRequestsWithMissingOrMismatchedKeys(String suppliedKey) throws Exception {
        var properties = mock(RatingProperties.class);
        var audit = mock(QuoteAuditStore.class);
        var admin = new AdminController(properties, audit, environmentWithSupportKey("test-key"));

        var table = admin.table("class-factors.dat", suppliedKey);
        assertThat(table.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(table.getBody()).isNull();
        assertThat(admin.quotes("RATE-000001", suppliedKey)).isEmpty();
        var restore = admin.restore(null, suppliedKey);
        assertThat(restore.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(restore.getBody()).isNull();
        verifyNoInteractions(properties, audit);
    }

    private static MockEnvironment environmentWithSupportKey(String configuredKey) {
        var environment = new MockEnvironment();
        String name = StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME;
        environment.getPropertySources().addFirst(new SystemEnvironmentPropertySource(name,
                configuredKey == null ? Map.of() : Map.of("RATING_SUPPORT_KEY", configuredKey)));
        return environment;
    }
}

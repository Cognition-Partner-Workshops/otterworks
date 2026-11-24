package com.otterworks.rating.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import java.util.Map;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.mock.env.MockEnvironment;

class AdminControllerTest {

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = " ")
    void supportKeyCheckFailsClosedWithoutConfiguration(String configuredKey) {
        var environment = new MockEnvironment();
        String name = StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME;
        environment.getPropertySources().addFirst(new SystemEnvironmentPropertySource(name,
                configuredKey == null ? Map.of() : Map.of("RATING_SUPPORT_KEY", configuredKey)));
        var admin = new AdminController(new RatingProperties(null, null), mock(QuoteAuditStore.class), environment);
        String suppliedKey = configuredKey == null ? "test-key" : configuredKey;

        assertThat(admin.allowed(suppliedKey)).isFalse();
    }
}

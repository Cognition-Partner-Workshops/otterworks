package com.otterworks.rating.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

import com.otterworks.rating.audit.QuoteAuditStore;
import com.otterworks.rating.config.RatingProperties;
import java.util.Map;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.NullAndEmptySource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.env.StandardEnvironment;
import org.springframework.core.env.SystemEnvironmentPropertySource;
import org.springframework.http.HttpStatus;
import org.springframework.mock.env.MockEnvironment;

class AdminControllerTest {

    @ParameterizedTest
    @NullAndEmptySource
    @ValueSource(strings = " ")
    void supportEndpointsAreClosedWhenTheKeyIsNotConfigured(String configuredKey) throws Exception {
        var environment = new MockEnvironment();
        String name = StandardEnvironment.SYSTEM_ENVIRONMENT_PROPERTY_SOURCE_NAME;
        environment.getPropertySources().addFirst(new SystemEnvironmentPropertySource(name,
                configuredKey == null ? Map.of() : Map.of("RATING_SUPPORT_KEY", configuredKey)));
        var audit = mock(QuoteAuditStore.class);
        var admin = new AdminController(new RatingProperties(null, null), audit, environment);
        String suppliedKey = configuredKey == null ? "test-key" : configuredKey;

        assertThat(admin.table("class-factors.dat", suppliedKey).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(admin.quotes("RATE-000001", suppliedKey)).isEmpty();
        assertThat(admin.restore("", suppliedKey).getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        verifyNoInteractions(audit);
    }
}

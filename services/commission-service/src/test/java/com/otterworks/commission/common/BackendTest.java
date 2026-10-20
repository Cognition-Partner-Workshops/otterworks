package com.otterworks.commission.common;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;

class BackendTest {

    private static Backend with(String... profiles) {
        MockEnvironment env = new MockEnvironment();
        env.setActiveProfiles(profiles);
        return new Backend(env);
    }

    @Test
    void oracleProfileSelectsOracle() {
        assertThat(with("oracle").kind()).isEqualTo(Backend.Kind.ORACLE);
    }

    @Test
    void postgresProfileSelectsPostgres() {
        assertThat(with("postgres", "local").isPostgres()).isTrue();
    }

    @Test
    void noBackendProfileFailsAtStartup() {
        assertThatThrownBy(() -> with("local")).isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("exactly one of oracle, postgres");
    }

    @Test
    void bothBackendProfilesFailAtStartup() {
        assertThatThrownBy(() -> with("oracle", "postgres")).isInstanceOf(IllegalStateException.class);
    }
}

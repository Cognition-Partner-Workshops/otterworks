package com.otterworks.commission.common;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class PostgresRateResolverTest {

    private static final LocalDateTime MARCH_31 = LocalDateTime.of(2026, 3, 31, 0, 0);
    private static final Timestamp TS = Timestamp.valueOf(MARCH_31);

    private final JdbcTemplate jdbc = mock(JdbcTemplate.class);
    private final PostgresRateResolver resolver = new PostgresRateResolver(jdbc);

    @Test
    void returnsFirstRowOfTheResolveRateOrder() {
        when(jdbc.queryForList(eq(PostgresRateResolver.SQL), eq(Long.class), eq("AUTO-STD"), eq(1L), eq(TS), eq(TS)))
                .thenReturn(List.of(7L));
        assertThat(resolver.resolve("AUTO-STD", 1L, MARCH_31)).isEqualTo(7L);
    }

    @Test
    void noRateRaisesOra20007WithPackageText() {
        when(jdbc.queryForList(eq(PostgresRateResolver.SQL), eq(Long.class), eq("LIFE-TERM"), eq(2L), eq(TS), eq(TS)))
                .thenReturn(List.of());
        assertThatThrownBy(() -> resolver.resolve("LIFE-TERM", 2L, MARCH_31))
                .isInstanceOfSatisfying(OraException.class, e -> assertThat(e.oraCode()).isEqualTo(-20007))
                .hasMessage("No rate in force for LIFE-TERM/agent 2 on 2026-03-31");
    }

    @Test
    void sqlKeepsAgentRateAheadOfDefaultAndLatestFirst() {
        assertThat(PostgresRateResolver.SQL).contains("ORDER BY agent_id NULLS LAST, effective_from DESC LIMIT 1");
    }

    @Test
    void nullPeriodMatchesNoWindowAndRaisesOra20007() {
        when(jdbc.queryForList(PostgresRateResolver.SQL, Long.class, "AUTO-STD", 1L, null, null))
                .thenReturn(List.of());
        assertThatThrownBy(() -> resolver.resolve("AUTO-STD", 1L, null))
                .isInstanceOfSatisfying(OraException.class, e -> assertThat(e.oraCode()).isEqualTo(-20007))
                .hasMessage("No rate in force for AUTO-STD/agent 1 on ");
    }
}

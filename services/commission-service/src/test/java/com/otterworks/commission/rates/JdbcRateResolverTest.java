package com.otterworks.commission.rates;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

import com.otterworks.commission.common.OraException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

class JdbcRateResolverTest {

    private RateRepository repo;
    private JdbcRateResolver resolver;
    private final List<RateRow> autoStd = new ArrayList<>();

    private static LocalDateTime d(String iso) {
        return iso == null ? null : LocalDateTime.parse(iso + "T00:00:00");
    }

    @BeforeEach
    void setUp() {
        repo = mock(RateRepository.class);
        resolver = new JdbcRateResolver(repo);
        // The seed: AUTO-STD default from 2024-01-01 (rate 1), agent 1 override from 2024-06-01 (rate 4).
        autoStd.add(new RateRow(1, null, d("2024-01-01"), null));
        autoStd.add(new RateRow(4, 1L, d("2024-06-01"), null));
    }

    private long resolve(Long agent, String asOf) {
        List<RateRow> mine = autoStd.stream()
                .filter(r -> r.agentId() == null || r.agentId().equals(agent)).toList();
        when(repo.candidates("AUTO-STD", agent)).thenReturn(mine);
        return resolver.resolve("AUTO-STD", agent, d(asOf));
    }

    private OraException fail(String product, Long agent, String asOf) {
        try {
            resolver.resolve(product, agent, d(asOf));
        } catch (OraException e) {
            return e;
        }
        throw new AssertionError("expected ORA-20007");
    }

    @ParameterizedTest(name = "agent {0} on {1} -> rate {2}")
    @CsvSource(value = {"1,2025-06-15,4", "2,2025-06-15,1", ",2025-06-15,1", "1,2024-05-31,1", "1,2024-06-01,4",
            "4,2025-06-15,1"})
    @DisplayName("R22/R23 agent-specific rate beats the product default inside its window")
    void agentBeatsDefault(Long agent, String asOf, long rateId) {
        assertThat(resolve(agent, asOf)).isEqualTo(rateId);
    }

    @Test
    @DisplayName("R22 window bounds are inclusive at both ends")
    void inclusiveWindow() {
        autoStd.set(0, new RateRow(1, null, d("2024-01-01"), d("2025-12-31")));
        autoStd.add(new RateRow(5, null, d("2026-01-01"), null));
        assertThat(resolve(2L, "2025-12-31")).isEqualTo(1);
        assertThat(resolve(2L, "2026-01-01")).isEqualTo(5);
        assertThat(resolve(2L, "2024-01-01")).isEqualTo(1);
    }

    @Test
    @DisplayName("R23 latest-starting rate wins within a scope; agent wins even if the default started later")
    void latestStartingWins() {
        autoStd.set(0, new RateRow(1, null, d("2024-01-01"), d("2026-12-31")));
        autoStd.add(new RateRow(5, null, d("2026-01-01"), null));
        assertThat(resolve(2L, "2026-06-15")).isEqualTo(5);
        assertThat(resolve(2L, "2025-06-15")).isEqualTo(1);
        assertThat(resolve(1L, "2026-06-15")).isEqualTo(4);
    }

    @Test
    @DisplayName("R24 nothing in force is ORA-20007 naming product, agent or 'default', and the day")
    void noRateInForce() {
        when(repo.candidates("AUTO-STD", 2L)).thenReturn(List.of(autoStd.get(0)));
        OraException e = fail("AUTO-STD", 2L, "2023-12-31");
        assertThat(e.oraCode()).isEqualTo(-20007);
        assertThat(e.getMessage()).isEqualTo("No rate in force for AUTO-STD/agent 2 on 2023-12-31");

        when(repo.candidates("NOPE", null)).thenReturn(List.of());
        assertThat(fail("NOPE", null, "2025-06-15").getMessage())
                .isEqualTo("No rate in force for NOPE/agent default on 2025-06-15");
    }
}

package com.otterworks.commission.rates;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import com.otterworks.commission.common.AuditLog;
import com.otterworks.commission.common.Guards;
import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.RateResolver;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.mockito.InOrder;

class RatesServiceTest {

    private static final LocalDateTime JAN_1 = LocalDateTime.of(2026, 1, 1, 0, 0);

    private RateRepository rates;
    private Guards guards;
    private AuditLog audit;
    private RateResolver resolver;
    private RatesService service;

    @BeforeEach
    void setUp() {
        rates = mock(RateRepository.class);
        guards = mock(Guards.class);
        audit = mock(AuditLog.class);
        resolver = mock(RateResolver.class);
        service = new RatesService(rates, guards, audit, resolver);
        // Mockito answers 0L for a Long; no same-day row is null.
        when(rates.amendSameDay(any(), any(), any(), any(), any())).thenReturn(null);
    }

    private static OraException ora(Runnable r) {
        try {
            r.run();
        } catch (OraException e) {
            return e;
        }
        throw new AssertionError("expected OraException");
    }

    @ParameterizedTest(name = "{0} -> {1}")
    @CsvSource({"0,0", "-1,-1", "-0.5,-.5", "50.01,50.01", "55,55", "50.001,50.001"})
    @DisplayName("R1/R38 rate outside (0, 50] is ORA-20001 with Oracle's TO_CHAR, before any other check")
    void rateOutOfBounds(String pct, String shown) {
        OraException e = ora(() -> service.upsert("NOPE", 999L, new BigDecimal(pct), JAN_1, "a"));
        assertThat(e.oraCode()).isEqualTo(-20001);
        assertThat(e.getMessage()).isEqualTo("Rate must be in (0, 50]: " + shown);
        verifyNoInteractions(guards, rates, audit);
    }

    @Test
    @DisplayName("R1 NULL rate is ORA-20001 'NULL'")
    void nullRate() {
        OraException e = ora(() -> service.upsert("AUTO-STD", null, null, JAN_1, "a"));
        assertThat(e.getMessage()).isEqualTo("Rate must be in (0, 50]: NULL");
    }

    @Test
    @DisplayName("R1/R37 0.001 passes the guard (the column constraint rejects it later)")
    void subCentPassesGuard() {
        when(rates.insertOpen(any(), any(), any(), any(), any())).thenReturn(5L);
        service.upsert("AUTO-STD", null, new BigDecimal("0.001"), JAN_1, "a");
        verify(rates).insertOpen("AUTO-STD", null, new BigDecimal("0.001"), JAN_1, "a");
    }

    @Test
    @DisplayName("R2/R3 product checked before agent; default scope skips the agent check")
    void productThenAgent() {
        doThrow(new OraException(-20004, "Unknown product: NOPE")).when(guards).assertProduct("NOPE");
        assertThat(ora(() -> service.upsert("NOPE", 999L, BigDecimal.ONE, JAN_1, "a")).oraCode()).isEqualTo(-20004);
        verify(guards, never()).assertActiveAgent(any());

        when(rates.insertOpen(any(), any(), any(), any(), any())).thenReturn(5L);
        service.upsert("AUTO-STD", null, BigDecimal.ONE, JAN_1, "a");
        verify(guards, never()).assertActiveAgent(any());
    }

    @Test
    @DisplayName("R4 inactive agent rejected before any write")
    void inactiveAgent() {
        doThrow(new OraException(-20003, "Agent 4 is SUSPENDED")).when(guards).assertActiveAgent(4L);
        assertThat(ora(() -> service.upsert("AUTO-STD", 4L, BigDecimal.TEN, JAN_1, "a")).getMessage())
                .isEqualTo("Agent 4 is SUSPENDED");
        verifyNoInteractions(rates, audit);
    }

    @Test
    @DisplayName("R5 same-day correction amends in place: no close, no insert")
    void sameDayCorrection() {
        when(rates.amendSameDay("AUTO-STD", 1L, new BigDecimal("9.75"), JAN_1, "a")).thenReturn(4L);
        assertThat(service.upsert("AUTO-STD", 1L, new BigDecimal("9.75"), JAN_1, "a")).isEqualTo(4L);
        verify(rates, never()).closeOpenStartedBefore(any(), any(), any(), any());
        verify(rates, never()).insertOpen(any(), any(), any(), any(), any());
        verify(audit).log("RATE_UPSERT", "AUTO-STD", 1L, null, "rate_id=4 pct=9.75 from=2026-01-01", "a");
    }

    @Test
    @DisplayName("R6/R7 supersede closes the prior open rate the day before, then inserts")
    void supersede() {
        LocalDateTime leapDay = LocalDateTime.of(2028, 3, 1, 0, 0);
        when(rates.insertOpen(any(), any(), any(), any(), any())).thenReturn(5L);
        assertThat(service.upsert("AUTO-STD", null, new BigDecimal("8.50"), leapDay, "a")).isEqualTo(5L);
        InOrder order = inOrder(rates, audit);
        order.verify(rates).amendSameDay("AUTO-STD", null, new BigDecimal("8.50"), leapDay, "a");
        order.verify(rates).closeOpenStartedBefore("AUTO-STD", null, leapDay, LocalDateTime.of(2028, 2, 29, 0, 0));
        order.verify(rates).insertOpen("AUTO-STD", null, new BigDecimal("8.50"), leapDay, "a");
        order.verify(audit).log(eq("RATE_UPSERT"), eq("AUTO-STD"), eq(null), eq(null), anyString(), eq("a"));
    }

    @ParameterizedTest(name = "{0} -> {1}")
    @CsvSource({"8.50,8.5", "0.5,.5", "0.01,.01", "50,50", "8.555,8.555"})
    @DisplayName("R8/R38 audit detail uses the unrounded input in default TO_CHAR")
    void auditDetail(String pct, String shown) {
        when(rates.insertOpen(any(), any(), any(), any(), any())).thenReturn(5L);
        service.upsert("HOME-PLUS", null, new BigDecimal(pct), LocalDateTime.of(2026, 2, 1, 0, 0), "a");
        verify(audit).log("RATE_UPSERT", "HOME-PLUS", null, null, "rate_id=5 pct=" + shown + " from=2026-02-01", "a");
    }

    @Test
    @DisplayName("R10/R12 end closes the open rate and audits RATE_END 'to=<date>'")
    void endRate() {
        LocalDateTime dec31 = LocalDateTime.of(2025, 12, 31, 0, 0);
        when(rates.endOpen("AUTO-STD", 1L, dec31)).thenReturn(1);
        service.end("AUTO-STD", 1L, dec31, "a");
        verify(audit).log("RATE_END", "AUTO-STD", 1L, null, "to=2025-12-31", "a");
    }

    @ParameterizedTest(name = "{0}/{1}")
    @CsvSource(value = {"TERM-20,2,No open rate for TERM-20/2", "NOPE,,No open rate for NOPE/default",
            ",,No open rate for /default"})
    @DisplayName("R11 nothing open is ORA-20007; product and agent are not validated")
    void endWithoutOpenRate(String product, Long agent, String message) {
        OraException e = ora(() -> service.end(product, agent, JAN_1, "a"));
        assertThat(e.oraCode()).isEqualTo(-20007);
        assertThat(e.getMessage()).isEqualTo(message);
        verifyNoInteractions(guards, audit);
    }

    @Test
    @DisplayName("R24 resolve goes through the RateResolver bean")
    void resolveDelegates() {
        when(resolver.resolve("AUTO-STD", 1L, JAN_1)).thenReturn(4L);
        assertThat(service.resolve("AUTO-STD", 1L, JAN_1)).isEqualTo(4L);
        doThrow(new OraException(-20007, "x")).when(resolver).resolve("NOPE", null, JAN_1);
        assertThatThrownBy(() -> service.resolve("NOPE", null, JAN_1)).isInstanceOf(OraException.class);
    }
}

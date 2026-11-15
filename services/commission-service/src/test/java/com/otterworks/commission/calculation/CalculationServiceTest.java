package com.otterworks.commission.calculation;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;
import org.springframework.transaction.annotation.Transactional;

import com.otterworks.commission.calculation.CalculationRepository.Policy;
import com.otterworks.commission.calculation.CalculationRepository.Split;
import com.otterworks.commission.common.AuditLog;
import com.otterworks.commission.common.OraException;
import com.otterworks.commission.common.RateResolver;

class CalculationServiceTest {

    private static final BigDecimal P4 = new BigDecimal("4");
    private static final LocalDateTime JUNE_30 = LocalDateTime.of(2025, 6, 30, 0, 0);

    private CalculationRepository repo;
    private RateResolver rates;
    private AuditLog audit;
    private CalculationService service;

    @BeforeEach
    void setUp() {
        repo = mock(CalculationRepository.class);
        rates = mock(RateResolver.class);
        audit = mock(AuditLog.class);
        service = new CalculationService(repo, rates, audit);
        when(repo.lastDayOfPeriod("2025-06")).thenReturn(JUNE_30);
    }

    private void policy(String status) {
        when(repo.findPolicy(P4)).thenReturn(Optional.of(new Policy(P4, "AUTO-STD", new BigDecimal("9600.00"), status)));
    }

    private void threeWaySplit() {
        policy("IN_FORCE");
        when(repo.splitsInOrder(P4)).thenReturn(List.of(
                new Split(1, new BigDecimal("50")), new Split(2, new BigDecimal("30")), new Split(3, new BigDecimal("20"))));
        when(rates.resolve("AUTO-STD", 1L, JUNE_30)).thenReturn(4L);
        when(rates.resolve("AUTO-STD", 2L, JUNE_30)).thenReturn(1L);
        when(rates.resolve("AUTO-STD", 3L, JUNE_30)).thenReturn(1L);
        when(repo.ratePct(4L)).thenReturn(new BigDecimal("9.5"));
        when(repo.ratePct(1L)).thenReturn(new BigDecimal("8"));
    }

    @Test
    @DisplayName("R25 unknown policy raises ORA-20005 with TO_CHAR(p_policy_id)")
    void unknownPolicy() {
        when(repo.findPolicy(new BigDecimal("999"))).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.calculate(new BigDecimal("999"), "999", "2025-06", "char"))
                .isInstanceOf(OraException.class)
                .hasMessage("Unknown policy: 999")
                .extracting(e -> ((OraException) e).oraCode()).isEqualTo(-20005);
        verify(repo, never()).deleteLedger(any(), any());
    }

    @Test
    @DisplayName("R25 NULL policy id raises ORA-20005 with an empty id")
    void nullPolicy() {
        assertThatThrownBy(() -> service.calculate(null, "", "2025-06", "char"))
                .hasMessage("Unknown policy: ");
    }

    @Test
    @DisplayName("R26 a policy not IN_FORCE raises ORA-20008 before the period is parsed")
    void lapsedPolicy() {
        policy("LAPSED");
        assertThatThrownBy(() -> service.calculate(P4, "4", "2025-13", "char"))
                .hasMessage("Policy 4 is LAPSED")
                .extracting(e -> ((OraException) e).oraCode()).isEqualTo(-20008);
        verify(repo, never()).lastDayOfPeriod(anyString());
        verify(repo, never()).deleteLedger(any(), any());
    }

    @Test
    @DisplayName("R27 R32 rates resolve on the last day of the period; rows record rate, split and premium")
    void threeWayLedger() {
        threeWaySplit();
        assertThat(service.calculate(P4, "4", "2025-06", "char").rows()).isEqualTo(3);
        verify(repo).insertLedger(P4, 1, "2025-06", 4, new BigDecimal("50"), new BigDecimal("9600.00"), new BigDecimal("38.00"));
        verify(repo).insertLedger(P4, 2, "2025-06", 1, new BigDecimal("30"), new BigDecimal("9600.00"), new BigDecimal("19.20"));
        verify(repo).insertLedger(P4, 3, "2025-06", 1, new BigDecimal("20"), new BigDecimal("9600.00"), new BigDecimal("12.80"));
    }

    @Test
    @DisplayName("R28 R29 the period's rows are deleted first, then written in split order")
    void deleteThenInsertInOrder() {
        threeWaySplit();
        service.calculate(P4, "4", "2025-06", "char");
        InOrder o = inOrder(repo, audit);
        o.verify(repo).deleteLedger(P4, "2025-06");
        o.verify(repo).insertLedger(any(), eq(1L), any(), anyLong(), any(), any(), any());
        o.verify(repo).insertLedger(any(), eq(2L), any(), anyLong(), any(), any(), any());
        o.verify(repo).insertLedger(any(), eq(3L), any(), anyLong(), any(), any(), any());
        o.verify(audit).log("COMMISSION_CALC", "AUTO-STD", null, 4L, "2025-06 rows=3", "char");
    }

    @Test
    @DisplayName("R33 no split allocation raises ORA-20006 after the delete, with no audit row")
    void noSplits() {
        policy("IN_FORCE");
        when(repo.splitsInOrder(P4)).thenReturn(List.of());
        assertThatThrownBy(() -> service.calculate(P4, "4", "2025-06", "char"))
                .hasMessage("Policy 4 has no split allocation")
                .extracting(e -> ((OraException) e).oraCode()).isEqualTo(-20006);
        verify(repo).deleteLedger(P4, "2025-06");
        verify(audit, never()).log(any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("R34 audit detail is '<period> rows=<n>'; NULL period concatenates as empty")
    void auditDetailWithNullPeriod() {
        policy("IN_FORCE");
        when(repo.lastDayOfPeriod(null)).thenReturn(null);
        when(repo.splitsInOrder(P4)).thenReturn(List.of(new Split(2, new BigDecimal("100"))));
        when(rates.resolve("AUTO-STD", 2L, null)).thenReturn(1L);
        when(repo.ratePct(1L)).thenReturn(new BigDecimal("8"));
        service.calculate(P4, "4", null, "char");
        verify(audit).log("COMMISSION_CALC", "AUTO-STD", null, 4L, " rows=1", "char");
    }

    @Test
    @DisplayName("R24 R35 a rate failure midway propagates and the transaction rolls back")
    void failureMidwayPropagates() throws Exception {
        threeWaySplit();
        when(rates.resolve("AUTO-STD", 2L, JUNE_30))
                .thenThrow(new OraException(-20007, "No rate in force for AUTO-STD/agent 2 on 2025-06-30"));
        assertThatThrownBy(() -> service.calculate(P4, "4", "2025-06", "char"))
                .hasMessage("No rate in force for AUTO-STD/agent 2 on 2025-06-30");
        verify(audit, never()).log(any(), any(), any(), any(), any(), any());
        assertThat(CalculationService.class.getMethod("calculate", BigDecimal.class, String.class, String.class, String.class)
                .getAnnotation(Transactional.class)).isNotNull();
    }
}

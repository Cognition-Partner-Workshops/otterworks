package com.otterworks.commission.splits;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import com.otterworks.commission.common.AuditLog;
import com.otterworks.commission.common.Guards;
import com.otterworks.commission.common.OraException;

class SplitsServiceTest {

    private SplitsRepository repo;
    private Guards guards;
    private AuditLog audit;
    private SplitsService service;

    @BeforeEach
    void setUp() {
        repo = mock(SplitsRepository.class);
        guards = mock(Guards.class);
        audit = mock(AuditLog.class);
        service = new SplitsService(repo, guards, audit);
        when(repo.policyStatus(any())).thenReturn(Optional.of("ACTIVE"));
    }

    private static SplitAllocation s(Long agent, String pct) {
        return new SplitAllocation(agent, pct == null ? null : new BigDecimal(pct));
    }

    private void rejects(List<SplitAllocation> splits, int code, String message) {
        assertThatThrownBy(() -> service.setSplits(4L, splits, "char"))
                .isInstanceOfSatisfying(OraException.class, e -> {
                    assertThat(e.oraCode()).isEqualTo(code);
                    assertThat(e.getMessage()).isEqualTo(message);
                });
        verify(repo, never()).deleteSplits(any());
        verify(audit, never()).log(any(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("R13 unknown policy is rejected before the allocation is looked at")
    void unknownPolicy() {
        when(repo.policyStatus(999L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.setSplits(999L, List.of(), "char"))
                .isInstanceOf(OraException.class).hasMessage("Unknown policy: 999");
    }

    @Test
    @DisplayName("R13 policy status is read but not checked (LAPSED accepted)")
    void lapsedAccepted() {
        when(repo.policyStatus(5L)).thenReturn(Optional.of("LAPSED"));
        assertThat(service.setSplits(5L, List.of(s(1L, "100")), "char")).isEqualTo(1);
    }

    @Test
    @DisplayName("R14 NULL or empty allocation is rejected")
    void emptyOrNull() {
        rejects(null, -20006, "At least one split allocation is required");
        rejects(List.of(), -20006, "At least one split allocation is required");
    }

    @Test
    @DisplayName("R15 duplicate agent (and NULL agent) is rejected before any pct check")
    void duplicates() {
        rejects(List.of(s(1L, "50"), s(1L, "50")), -20006, "Duplicate agent in split allocation");
        rejects(List.of(s(1L, "0"), s(1L, "100")), -20006, "Duplicate agent in split allocation");
        rejects(List.of(s(null, "100")), -20006, "Duplicate agent in split allocation");
    }

    @Test
    @DisplayName("R16 each pct must be non-NULL and in (0, 100]")
    void pctBounds() {
        rejects(List.of(s(1L, "0"), s(2L, "100")), -20006, "Split pct must be in (0, 100]: agent 1");
        rejects(List.of(s(1L, "-5"), s(2L, "105")), -20006, "Split pct must be in (0, 100]: agent 1");
        rejects(List.of(s(1L, "100.01")), -20006, "Split pct must be in (0, 100]: agent 1");
        rejects(List.of(s(1L, "50"), s(2L, null)), -20006, "Split pct must be in (0, 100]: agent 2");
    }

    @Test
    @DisplayName("R17 agent checks run per item after that item's pct check")
    void agentPerItem() {
        doThrow(new OraException(-20003, "Agent 4 is SUSPENDED")).when(guards).assertActiveAgent(4L);
        rejects(List.of(s(4L, "50"), s(1L, "0")), -20003, "Agent 4 is SUSPENDED");
        rejects(List.of(s(1L, "0"), s(4L, "50")), -20006, "Split pct must be in (0, 100]: agent 1");
    }

    @Test
    @DisplayName("R18 R38 total must be exactly 100; message uses default TO_CHAR")
    void total() {
        rejects(List.of(s(1L, "60.00"), s(2L, "39.99")), -20006, "Split percentages must total 100.00, got 99.99");
        rejects(List.of(s(1L, "70"), s(2L, "40")), -20006, "Split percentages must total 100.00, got 110");
        rejects(List.of(s(1L, "50"), s(2L, "49.5")), -20006, "Split percentages must total 100.00, got 99.5");
        rejects(List.of(s(1L, "60.01"), s(2L, "40.00")), -20006, "Split percentages must total 100.00, got 100.01");
    }

    @Test
    @DisplayName("R18 R37 total is checked on unrounded input with exact decimals")
    void unroundedTotal() {
        assertThat(service.setSplits(3L, List.of(s(1L, "33.333"), s(2L, "33.333"), s(3L, "33.334")), "char"))
                .isEqualTo(3);
    }

    @Test
    @DisplayName("R19 R20 allocation replaced wholesale in collection order, then audited")
    void replaceInOrder() {
        List<SplitAllocation> splits = Arrays.asList(s(3L, "35"), s(2L, "65"));
        service.setSplits(4L, splits, "char");
        InOrder o = inOrder(repo, audit);
        o.verify(repo).deleteSplits(4L);
        o.verify(repo).insertSplit(4L, splits.get(0));
        o.verify(repo).insertSplit(4L, splits.get(1));
        o.verify(audit).log("SPLIT_SET", null, null, 4L, "2 agents", "char");
    }

    @Test
    @DisplayName("R21 a rejection writes nothing")
    void atomic() {
        doThrow(new OraException(-20002, "Unknown agent: 999")).when(guards).assertActiveAgent(999L);
        rejects(List.of(s(1L, "50"), s(999L, "50")), -20002, "Unknown agent: 999");
        verify(repo, never()).insertSplit(anyLong(), any());
    }
}

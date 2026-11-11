package com.halvergate.payments;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.util.concurrent.atomic.AtomicBoolean;
import javax.transaction.xa.XAException;
import javax.transaction.xa.XAResource;
import javax.transaction.xa.Xid;
import org.junit.jupiter.api.Test;

class CommitHoldXAResourceTest {
    @Test
    void holdsOnlyFirstTwoPhaseCommitAndDelegatesBothCommits() throws Exception {
        var delegate = mock(XAResource.class);
        var held = new AtomicBoolean();
        var first = mock(Xid.class);
        var second = mock(Xid.class);
        new CommitHoldXAResource(delegate, 1, held, () -> true).commit(first, false);
        assertThat(held).isTrue();
        new CommitHoldXAResource(delegate, 1, held, () -> true).commit(second, false);
        verify(delegate).commit(first, false);
        verify(delegate).commit(second, false);
    }

    @Test
    void onePhaseCommitDoesNotConsumePreparedCommitBarrier() throws Exception {
        var delegate = mock(XAResource.class);
        var held = new AtomicBoolean();
        var xid = mock(Xid.class);
        new CommitHoldXAResource(delegate, 1, held, () -> true).commit(xid, true);
        assertThat(held).isFalse();
        verify(delegate).commit(xid, true);
    }

    @Test
    void interruptedHoldKeepsTheInterruptAndLeavesCommitForRecovery() {
        var resource = new CommitHoldXAResource(mock(XAResource.class), 1, new AtomicBoolean(), () -> true);
        Thread.currentThread().interrupt();
        try {
            assertThatThrownBy(() -> resource.commit(mock(Xid.class), false))
                .isInstanceOfSatisfying(XAException.class,
                    failure -> assertThat(failure.errorCode).isEqualTo(XAException.XAER_RMFAIL));
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }

    @Test
    void emptyReceiveTransactionDoesNotConsumeCommitBarrier() throws Exception {
        var delegate = mock(XAResource.class);
        var held = new AtomicBoolean();
        var xid = mock(Xid.class);
        new CommitHoldXAResource(delegate, 1, held, () -> false).commit(xid, false);
        assertThat(held).isFalse();
        verify(delegate).commit(xid, false);
    }
}

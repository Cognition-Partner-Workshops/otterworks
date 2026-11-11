package com.halvergate.payments;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.BooleanSupplier;
import javax.transaction.xa.XAException;
import javax.transaction.xa.XAResource;
import javax.transaction.xa.Xid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

final class CommitHoldXAResource implements XAResource {
    private static final Logger LOG = LoggerFactory.getLogger(CommitHoldXAResource.class);
    private final XAResource delegate;
    private final long holdMs;
    private final AtomicBoolean held;
    private final BooleanSupplier published;

    CommitHoldXAResource(XAResource delegate, long holdMs, AtomicBoolean held, BooleanSupplier published) {
        this.delegate = delegate;
        this.holdMs = holdMs;
        this.held = held;
        this.published = published;
    }

    @Override
    public void commit(Xid xid, boolean onePhase) throws XAException {
        if (!onePhase && published.getAsBoolean() && held.compareAndSet(false, true)) {
            LOG.info("prepared, holding before status commit xid={} holdMs={}", xid, holdMs);
            try {
                Thread.sleep(holdMs);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                var failure = new XAException(XAException.XAER_RMFAIL);
                failure.initCause(e);
                throw failure;
            }
        }
        delegate.commit(xid, onePhase);
    }

    @Override
    public void start(Xid xid, int flags) throws XAException { delegate.start(xid, flags); }
    @Override
    public void end(Xid xid, int flags) throws XAException { delegate.end(xid, flags); }
    @Override
    public int prepare(Xid xid) throws XAException { return delegate.prepare(xid); }
    @Override
    public void rollback(Xid xid) throws XAException { delegate.rollback(xid); }
    @Override
    public void forget(Xid xid) throws XAException { delegate.forget(xid); }
    @Override
    public Xid[] recover(int flags) throws XAException { return delegate.recover(flags); }
    @Override
    public boolean isSameRM(XAResource other) { return other == this; }
    @Override
    public int getTransactionTimeout() throws XAException { return delegate.getTransactionTimeout(); }
    @Override
    public boolean setTransactionTimeout(int seconds) throws XAException { return delegate.setTransactionTimeout(seconds); }
}

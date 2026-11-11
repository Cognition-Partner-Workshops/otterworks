package com.halvergate.payments;

import com.arjuna.ats.internal.jta.recovery.arjunacore.XARecoveryModule;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import javax.transaction.xa.XAException;
import javax.transaction.xa.Xid;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.jboss.narayana.jta.jms.ConnectionManager;
import org.jboss.narayana.jta.jms.JmsXAResourceRecoveryHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class StatusXaRecovery extends JmsXAResourceRecoveryHelper {
    private static final Logger LOG = LoggerFactory.getLogger(StatusXaRecovery.class);
    private final XARecoveryModule recovery;
    private final ConnectionManager connections;

    @Autowired
    public StatusXaRecovery(@Qualifier("nonXaJmsConnectionFactory") ActiveMQXAConnectionFactory factory,
                            XARecoveryModule recovery) {
        this(new ConnectionManager(factory, null, null), recovery);
    }

    private StatusXaRecovery(ConnectionManager connections, XARecoveryModule recovery) {
        super(connections);
        this.connections = connections;
        this.recovery = recovery;
    }

    @PostConstruct
    void register() {
        recovery.addXAResourceRecoveryHelper(this);
        LOG.info("Registered status publisher XA recovery with Narayana");
    }

    @PreDestroy
    void close() {
        recovery.removeXAResourceRecoveryHelper(this);
        connections.disconnect();
    }

    @Override
    public Xid[] recover(int flags) throws XAException {
        var xids = super.recover(flags);
        for (var xid : xids) {
            LOG.info("Status XA recovery found prepared xid={}", xid);
        }
        return xids;
    }

    @Override
    public void commit(Xid xid, boolean onePhase) throws XAException {
        super.commit(xid, onePhase);
        LOG.info("Status XA recovery committed xid={}", xid);
    }
}

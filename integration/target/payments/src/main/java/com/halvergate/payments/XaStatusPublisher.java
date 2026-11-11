package com.halvergate.payments;

import jakarta.jms.XAConnection;
import jakarta.jms.XASession;
import jakarta.annotation.PreDestroy;
import jakarta.transaction.Synchronization;
import jakarta.transaction.TransactionManager;
import jakarta.transaction.Transaction;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import org.springframework.beans.factory.annotation.Value;
import org.apache.activemq.artemis.api.core.client.ClientMessage;
import org.apache.activemq.artemis.api.core.client.ClientSession;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.api.core.ActiveMQQueueExistsException;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.jms.client.ActiveMQConnection;
import org.apache.activemq.artemis.jms.client.ActiveMQXAConnectionFactory;
import org.apache.activemq.artemis.reader.TextMessageUtil;
import org.apache.camel.Exchange;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.context.annotation.DependsOn;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
@DependsOn("statusXaRecovery")
public class XaStatusPublisher {
    private static final Logger LOG = LoggerFactory.getLogger(XaStatusPublisher.class);
    private final ActiveMQXAConnectionFactory factory;
    private final TransactionManager transactions;
    private final long commitHoldMs;
    private final AtomicBoolean commitHeld = new AtomicBoolean();
    private final Set<Transaction> published = ConcurrentHashMap.newKeySet();
    private XAConnection connection;
    private final ConcurrentHashMap<Transaction, XASession> sessions = new ConcurrentHashMap<>();

    public XaStatusPublisher(@Qualifier("nonXaJmsConnectionFactory") ActiveMQXAConnectionFactory factory,
                             TransactionManager transactions,
                             @Value("${payments.commit-hold-ms:0}") long commitHoldMs) {
        this.factory = factory;
        this.transactions = transactions;
        this.commitHoldMs = commitHoldMs;
    }

    synchronized XAConnection connect() throws Exception {
        if (connection == null || ((ActiveMQConnection) connection).getInitialSession().isClosed()) {
            close();
            connection = factory.createXAConnection();
            try {
                ensureStatusQueue(((ActiveMQConnection) connection).getInitialSession());
            } catch (Exception e) {
                close();
                throw e;
            }
        }
        return connection;
    }

    @PreDestroy
    synchronized void close() {
        if (connection != null) {
            try {
                connection.close();
            } catch (Exception e) {
                LOG.warn("XA publish connection cleanup failed", e);
            } finally {
                connection = null;
            }
        }
    }

    synchronized XASession prepare() throws Exception {
        var transaction = transactions.getTransaction();
        if (transaction == null) {
            throw new IllegalStateException("Status publish requires an active XA transaction");
        }
        XASession existing = sessions.get(transaction);
        if (existing != null) {
            return existing;
        }
        XASession xaSession = null;
        boolean registered = false;
        try {
            xaSession = connect().createXASession();
            XASession sessionToClose = xaSession;
            transaction.registerSynchronization(new Synchronization() {
                @Override
                public void beforeCompletion() { }

                @Override
                public void afterCompletion(int status) {
                    sessions.remove(transaction);
                    published.remove(transaction);
                    try {
                        sessionToClose.close();
                    } catch (Exception e) {
                        LOG.warn("XA publish session cleanup failed", e);
                    }
                }
            });
            registered = true;
            var resource = xaSession.getXAResource();
            if (commitHoldMs > 0) {
                resource = new CommitHoldXAResource(resource, commitHoldMs, commitHeld, () -> published.contains(transaction));
            }
            if (!transaction.enlistResource(resource)) {
                throw new IllegalStateException("Could not enlist status publish");
            }
            ensureStatusQueue(((ActiveMQSession) xaSession).getCoreSession());
            sessions.put(transaction, xaSession);
            return xaSession;
        } finally {
            if (!registered) {
                if (xaSession != null) {
                    xaSession.close();
                }
            }
        }
    }

    private void ensureStatusQueue(ClientSession core) throws Exception {
        if (!core.queueQuery(SimpleString.of("HB.PAYMENT.STATUS")).isExists()) {
            try {
                core.createQueue(QueueConfiguration.of("HB.PAYMENT.STATUS").setAddress("HB.PAYMENT.STATUS")
                    .setRoutingType(RoutingType.ANYCAST).setDurable(true).setAutoCreated(false).setAutoDelete(false));
            } catch (ActiveMQQueueExistsException ignored) { }
        }
        var queue = core.queueQuery(SimpleString.of("HB.PAYMENT.STATUS"));
        if (!queue.isExists() || !queue.isDurable() || queue.isAutoDelete()
                || queue.getRoutingType() != RoutingType.ANYCAST) {
            throw new IllegalStateException("HB.PAYMENT.STATUS must be durable, non-auto-delete and ANYCAST");
        }
    }

    public void publish(Exchange exchange) throws Exception {
        ClientSession core = ((ActiveMQSession) prepare()).getCoreSession();
        ClientMessage message = core.createMessage(org.apache.activemq.artemis.api.core.Message.TEXT_TYPE, true);
        TextMessageUtil.writeBodyText(message.getBodyBuffer(),
            org.apache.activemq.artemis.api.core.SimpleString.of(exchange.getMessage().getBody(String.class)));
        for (String property : new String[]{"requestId", "accountId", "JMSXGroupID", "sequence"}) {
            message.putStringProperty(property, exchange.getMessage().getHeader(property, String.class));
        }
        try (var producer = core.createProducer("HB.PAYMENT.STATUS")) {
            producer.send(message);
            if (commitHoldMs > 0) {
                published.add(transactions.getTransaction());
            }
        }
    }
}

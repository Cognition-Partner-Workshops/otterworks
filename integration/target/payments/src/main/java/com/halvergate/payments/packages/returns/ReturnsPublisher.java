package com.halvergate.payments.packages.returns;

import org.apache.activemq.artemis.api.core.ActiveMQQueueExistsException;
import org.apache.activemq.artemis.api.core.Message;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.api.core.client.ClientMessage;
import org.apache.activemq.artemis.api.core.client.ClientSession;
import org.apache.activemq.artemis.jms.client.ActiveMQConnection;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.reader.TextMessageUtil;
import org.apache.camel.Exchange;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Persistent, non-transacted publish to the output queue through an Artemis core session so the
 * literal contract properties (including JMSXGroupID) reach consumers unchanged.
 */
public class ReturnsPublisher implements AutoCloseable {
    static final String[] CONTRACT_PROPERTIES = {"requestId", "accountId", "JMSXGroupID", "sequence"};
    private static final Logger LOG = LoggerFactory.getLogger(ReturnsPublisher.class);
    private final ActiveMQConnectionFactory factory;
    private final String destination;
    private ActiveMQConnection connection;
    private ClientSession core;

    public ReturnsPublisher(ActiveMQConnectionFactory factory, String destination) {
        this.factory = factory;
        this.destination = destination;
    }

    String destination() {
        return destination;
    }

    synchronized ClientSession connect() throws Exception {
        if (core == null || core.isClosed() || connection.getInitialSession().isClosed()) {
            close();
            connection = (ActiveMQConnection) factory.createConnection();
            var session = (ActiveMQSession) connection.createSession(false, jakarta.jms.Session.AUTO_ACKNOWLEDGE);
            core = session.getCoreSession();
            ensureQueue(core);
        }
        return core;
    }

    public synchronized void publish(Exchange exchange) throws Exception {
        try {
            ClientSession session = connect();
            ClientMessage message = session.createMessage(Message.TEXT_TYPE, true);
            TextMessageUtil.writeBodyText(message.getBodyBuffer(),
                SimpleString.of(exchange.getMessage().getBody(String.class)));
            for (String property : CONTRACT_PROPERTIES) {
                message.putStringProperty(property, exchange.getMessage().getHeader(property, String.class));
            }
            try (var producer = session.createProducer(destination)) {
                producer.send(message);
            }
        } catch (Exception e) {
            close();
            throw e;
        }
    }

    private void ensureQueue(ClientSession session) throws Exception {
        if (!session.queueQuery(SimpleString.of(destination)).isExists()) {
            try {
                session.createQueue(QueueConfiguration.of(destination).setAddress(destination)
                    .setRoutingType(RoutingType.ANYCAST).setDurable(true).setAutoCreated(false).setAutoDelete(false));
            } catch (ActiveMQQueueExistsException ignored) { }
        }
    }

    @Override
    public synchronized void close() {
        if (connection != null) {
            try {
                connection.close();
            } catch (Exception e) {
                LOG.warn("payment-returns publish connection cleanup failed", e);
            } finally {
                connection = null;
                core = null;
            }
        }
    }
}

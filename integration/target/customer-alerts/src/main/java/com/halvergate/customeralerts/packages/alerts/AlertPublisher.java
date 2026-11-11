package com.halvergate.customeralerts.packages.alerts;

import jakarta.jms.XAConnection;
import jakarta.jms.XAConnectionFactory;
import jakarta.transaction.Synchronization;
import jakarta.transaction.TransactionManager;
import org.apache.activemq.artemis.api.core.Message;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.reader.TextMessageUtil;
import org.apache.camel.Exchange;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

@Component
public class AlertPublisher {
    private static final Logger LOG = LoggerFactory.getLogger(AlertPublisher.class);
    private final XAConnectionFactory factory;
    private final TransactionManager transactions;

    public AlertPublisher(@Qualifier("nonXaJmsConnectionFactory") XAConnectionFactory factory,
                          TransactionManager transactions) {
        this.factory = factory;
        this.transactions = transactions;
    }

    public void publish(Exchange exchange, String destination) throws Exception {
        var transaction = transactions.getTransaction();
        if (transaction == null) {
            throw new IllegalStateException("Alert publish requires a JMS transaction");
        }
        XAConnection connection = factory.createXAConnection();
        boolean registered = false;
        try {
            var session = connection.createXASession();
            transaction.registerSynchronization(new Synchronization() {
                @Override
                public void beforeCompletion() { }

                @Override
                public void afterCompletion(int status) {
                    try {
                        connection.close();
                    } catch (Exception e) {
                        LOG.warn("Alert publish connection cleanup failed", e);
                    }
                }
            });
            registered = true;
            if (!transaction.enlistResource(session.getXAResource())) {
                throw new IllegalStateException("Could not enlist alert publish");
            }
            var core = ((ActiveMQSession) session).getCoreSession();
            var message = core.createMessage(Message.TEXT_TYPE, true);
            TextMessageUtil.writeBodyText(message.getBodyBuffer(),
                SimpleString.of(exchange.getMessage().getBody(String.class)));
            for (String property : new String[]{"requestId", "accountId", "JMSXGroupID", "sequence"}) {
                String value = exchange.getMessage().getHeader(property, String.class);
                if (value != null) {
                    message.putStringProperty(property, value);
                }
            }
            try (var producer = core.createProducer(destination)) {
                producer.send(message);
            }
        } finally {
            if (!registered) {
                connection.close();
            }
        }
    }
}

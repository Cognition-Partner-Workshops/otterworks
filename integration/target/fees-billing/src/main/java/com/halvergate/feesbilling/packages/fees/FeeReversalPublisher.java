package com.halvergate.feesbilling.packages.fees;

import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.reader.TextMessageUtil;
import org.apache.camel.Exchange;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class FeeReversalPublisher {
    private final String url;
    private final String user;
    private final String password;

    public FeeReversalPublisher(@Value("${spring.artemis.broker-url}") String url,
            @Value("${spring.artemis.user}") String user,
            @Value("${spring.artemis.password}") String password) {
        this.url = url;
        this.user = user;
        this.password = password;
    }

    public void publish(Exchange exchange) throws Exception {
        try (var factory = new ActiveMQConnectionFactory(url);
             var connection = factory.createConnection(user, password);
             var session = connection.createSession(false, jakarta.jms.Session.AUTO_ACKNOWLEDGE)) {
            var core = ((ActiveMQSession) session).getCoreSession();
            var message = core.createMessage(org.apache.activemq.artemis.api.core.Message.TEXT_TYPE, true);
            TextMessageUtil.writeBodyText(message.getBodyBuffer(),
                SimpleString.of(exchange.getMessage().getBody(String.class)));
            for (String property : new String[]{"requestId", "accountId", "JMSXGroupID", "sequence"}) {
                message.putStringProperty(property, exchange.getMessage().getHeader(property, String.class));
            }
            try (var producer = core.createProducer("HB.FEE.REVERSED")) {
                producer.send(message);
            }
        }
    }
}

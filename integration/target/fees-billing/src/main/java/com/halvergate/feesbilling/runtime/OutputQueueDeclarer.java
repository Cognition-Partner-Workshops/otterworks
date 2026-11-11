package com.halvergate.feesbilling.runtime;

import jakarta.annotation.PreDestroy;
import java.util.List;
import java.util.Map;
import org.apache.activemq.artemis.api.core.ActiveMQQueueExistsException;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@EnableConfigurationProperties(OutputQueueDeclarer.Destinations.class)
public class OutputQueueDeclarer {
    private final ActiveMQConnectionFactory factory;
    private final Destinations destinations;

    @Autowired
    public OutputQueueDeclarer(@Value("${spring.artemis.broker-url}") String brokerUrl,
            @Value("${spring.artemis.user}") String user,
            @Value("${spring.artemis.password}") String password, Destinations destinations) {
        this(new ActiveMQConnectionFactory(brokerUrl, user, password), destinations);
    }

    OutputQueueDeclarer(ActiveMQConnectionFactory factory, Destinations destinations) {
        this.factory = factory;
        this.destinations = destinations;
    }

    public void declare() throws Exception {
        List<String> queues = destinations.getOutputQueues().values().stream()
            .flatMap(List::stream).distinct().toList();
        if (queues.isEmpty()) {
            return;
        }
        try (var connection = factory.createConnection();
             var session = connection.createSession(false, jakarta.jms.Session.AUTO_ACKNOWLEDGE)) {
            var core = ((ActiveMQSession) session).getCoreSession();
            for (String queue : queues) {
                if (!core.queueQuery(SimpleString.of(queue)).isExists()) {
                    try {
                        core.createQueue(QueueConfiguration.of(queue).setAddress(queue)
                            .setRoutingType(RoutingType.ANYCAST).setDurable(true)
                            .setAutoCreated(false).setAutoDelete(false));
                    } catch (ActiveMQQueueExistsException ignored) { }
                }
                var configuration = core.queueQuery(SimpleString.of(queue));
                if (!configuration.isExists() || !configuration.isDurable() || configuration.isAutoDelete()
                        || configuration.getRoutingType() != RoutingType.ANYCAST) {
                    throw new IllegalStateException(queue + " must be durable, non-auto-delete and ANYCAST");
                }
            }
        }
    }

    @PreDestroy
    public void close() {
        factory.close();
    }

    @ConfigurationProperties("runtime")
    public static class Destinations {
        private Map<String, List<String>> outputQueues = Map.of();

        public Map<String, List<String>> getOutputQueues() { return outputQueues; }
        public void setOutputQueues(Map<String, List<String>> outputQueues) { this.outputQueues = outputQueues; }
    }
}

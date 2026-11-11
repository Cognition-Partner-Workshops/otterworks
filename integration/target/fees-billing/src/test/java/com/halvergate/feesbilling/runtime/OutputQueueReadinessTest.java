package com.halvergate.feesbilling.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import org.apache.activemq.artemis.api.core.QueueConfiguration;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.config.impl.ConfigurationImpl;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.camel.impl.DefaultCamelContext;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.springframework.beans.factory.InitializingBean;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

class OutputQueueReadinessTest {
    private static final AtomicInteger BROKER_IDS = new AtomicInteger(2000);

    enum UnsafeQueue { AUTO_DELETE, NON_DURABLE, MULTICAST }

    @ParameterizedTest
    @EnumSource(UnsafeQueue.class)
    void unsafeQueueFailsSpringReadinessWithoutChangingQueue(UnsafeQueue unsafe) throws Exception {
        var broker = new EmbeddedActiveMQ();
        String url = "vm://" + BROKER_IDS.incrementAndGet();
        broker.setConfiguration(new ConfigurationImpl().setPersistenceEnabled(false)
            .setSecurityEnabled(false).addAcceptorConfiguration("invm", url));
        broker.start();
        try (var factory = new ActiveMQConnectionFactory(url);
             var context = new AnnotationConfigApplicationContext();
             var camel = new DefaultCamelContext()) {
            String name = "HB.W0.UNSAFE." + unsafe;
            var configuration = QueueConfiguration.of(name).setAddress(name)
                .setDurable(unsafe != UnsafeQueue.NON_DURABLE)
                .setRoutingType(unsafe == UnsafeQueue.MULTICAST ? RoutingType.MULTICAST : RoutingType.ANYCAST)
                .setAutoCreated(true).setAutoDelete(unsafe == UnsafeQueue.AUTO_DELETE)
                .setAutoDeleteDelay(60000L);
            var original = broker.getActiveMQServer().createQueue(configuration);
            var destinations = new OutputQueueDeclarer.Destinations();
            destinations.setOutputQueues(Map.of("probe", List.of(name)));
            context.registerBean(OutputQueueDeclarer.class, () -> new OutputQueueDeclarer(factory, destinations));
            context.registerBean("readiness", InitializingBean.class, () -> () ->
                new TransactionConfiguration().outputQueueReadiness(context.getBean(OutputQueueDeclarer.class))
                    .beforeApplicationStart(camel));
            assertThatThrownBy(context::refresh)
                .hasRootCauseInstanceOf(IllegalStateException.class)
                .hasRootCauseMessage(name + " must be durable, non-auto-delete and ANYCAST");
            var unchanged = broker.getActiveMQServer().locateQueue(SimpleString.of(name));
            assertThat(unchanged).isSameAs(original);
            assertThat(unchanged.isDurable()).isEqualTo(configuration.isDurable());
            assertThat(unchanged.isAutoDelete()).isEqualTo(configuration.isAutoDelete());
            assertThat(unchanged.getRoutingType()).isEqualTo(configuration.getRoutingType());
            System.out.printf("PROBE %s readiness rejected; original queue unchanged: durable=%s autoDelete=%s routingType=%s%n",
                name, unchanged.isDurable(), unchanged.isAutoDelete(), unchanged.getRoutingType());
        } finally {
            broker.stop();
        }
    }
}

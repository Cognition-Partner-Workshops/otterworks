package com.halvergate.customeralerts.packages.alerts;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.List;
import com.halvergate.customeralerts.runtime.IsolatedRuntimeTestConfiguration;
import com.halvergate.customeralerts.runtime.OutputQueueDeclarer;
import jakarta.jms.ConnectionFactory;
import jakarta.jms.Session;
import jakarta.transaction.Status;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.camel.CamelContext;
import org.jboss.narayana.jta.jms.ConnectionFactoryProxy;
import org.jboss.narayana.jta.jms.ConnectionProxy;
import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Import;
import org.springframework.transaction.jta.JtaTransactionManager;
import org.springframework.test.util.ReflectionTestUtils;

@SpringBootTest(properties = {"spring.datasource.password=unused",
    "narayana.log-dir=target/transaction-logs", "camel.springboot.main-run-controller=false"})
@Import(IsolatedRuntimeTestConfiguration.class)
class AlertReadinessTest {
    private static final Logger LOG = LoggerFactory.getLogger(AlertReadinessTest.class);
    private static final List<String> OUTPUTS = List.of("HB.DISPUTE.RECEIVED",
        "HB.LARGE.TRANSACTION.ALERTED", "HB.LOW.BALANCE.ALERTED");

    @Autowired
    private ConnectionFactory factory;
    @Autowired
    private JtaTransactionManager transactions;
    @Autowired
    private ConfigurableApplicationContext applicationContext;
    @Autowired
    private CamelContext camelContext;
    @Autowired
    private EmbeddedActiveMQ broker;
    @Autowired
    private OutputQueueDeclarer declarer;
    @Autowired
    private OutputQueueDeclarer.Destinations destinations;

    @Test
    void declaresOutputsOutsideTransactionThroughWrappedPrimaryFactory() throws Exception {
        assertThat(applicationContext.isActive()).isTrue();
        assertThat(camelContext.isStarted()).isTrue();
        assertThat(camelContext.getRouteController().getRouteStatus("customer-alerts.card-dispute").isStarted())
            .isTrue();
        assertThat(destinations.getOutputQueues().get("alerts")).containsExactlyElementsOf(OUTPUTS);
        assertThat(transactions.getTransactionManager().getStatus()).isEqualTo(Status.STATUS_NO_TRANSACTION);
        assertThat(factory).isInstanceOf(ConnectionFactoryProxy.class);
        try (var connection = factory.createConnection();
             var session = connection.createSession(false, Session.AUTO_ACKNOWLEDGE)) {
            LOG.info("Readiness classes: factory={} connection={} session={}", factory.getClass().getName(),
                connection.getClass().getName(), session.getClass().getName());
            assertThat(connection).isInstanceOf(ConnectionProxy.class);
            assertThat(session).isInstanceOf(ActiveMQSession.class);
        }
        assertOutputs();
        var adminFactory = (ActiveMQConnectionFactory) ReflectionTestUtils.getField(declarer, "factory");
        assertThat(adminFactory).isNotNull().isNotSameAs(factory);
        try (var connection = adminFactory.createConnection();
             var session = connection.createSession(false, Session.AUTO_ACKNOWLEDGE)) {
            LOG.info("Readiness admin classes: factory={} connection={} session={}",
                adminFactory.getClass().getName(), connection.getClass().getName(), session.getClass().getName());
            assertThat(session).isInstanceOf(ActiveMQSession.class);
        }
        var existing = OUTPUTS.stream().map(name -> broker.getActiveMQServer().locateQueue(name)).toList();
        declarer.declare();
        assertOutputs();
        for (int i = 0; i < OUTPUTS.size(); i++) {
            assertThat(broker.getActiveMQServer().locateQueue(OUTPUTS.get(i))).isSameAs(existing.get(i));
        }
        LOG.info("Readiness assertions passed: context and package routes started; repeated declare is idempotent");
    }

    private void assertOutputs() {
        for (String name : OUTPUTS) {
            var queue = broker.getActiveMQServer().locateQueue(SimpleString.of(name));
            assertThat(queue).as(name).isNotNull();
            assertThat(queue.getRoutingType()).isEqualTo(RoutingType.ANYCAST);
            assertThat(queue.isDurable()).isTrue();
            assertThat(queue.isAutoCreated()).isFalse();
            assertThat(queue.isAutoDelete()).isFalse();
            assertThat(queue.getMessagesAdded()).isZero();
            LOG.info("Readiness queue={} routing={} durable={} autoCreated={} autoDelete={} messagesAdded={}",
                name, queue.getRoutingType(), queue.isDurable(), queue.isAutoCreated(), queue.isAutoDelete(),
                queue.getMessagesAdded());
        }
    }
}

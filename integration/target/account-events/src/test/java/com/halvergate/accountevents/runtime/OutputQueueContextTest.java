package com.halvergate.accountevents.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import java.util.List;
import java.util.Map;
import jakarta.jms.ConnectionFactory;
import jakarta.jms.Session;
import jakarta.transaction.Status;
import jakarta.transaction.TransactionManager;
import com.arjuna.ats.internal.jta.transaction.arjunacore.TransactionImple;
import org.apache.activemq.artemis.api.core.RoutingType;
import org.apache.activemq.artemis.api.core.SimpleString;
import org.apache.activemq.artemis.core.server.embedded.EmbeddedActiveMQ;
import org.apache.activemq.artemis.jms.client.ActiveMQConnectionFactory;
import org.apache.activemq.artemis.jms.client.ActiveMQSession;
import org.apache.camel.CamelContext;
import org.apache.camel.builder.RouteBuilder;
import org.apache.camel.component.jms.JmsComponent;
import org.apache.camel.spring.boot.CamelContextConfiguration;
import org.jboss.narayana.jta.jms.ConnectionFactoryProxy;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.jta.JtaTransactionManager;

@SpringBootTest(properties = {
    "narayana.log-dir=target/transaction-logs",
    "camel.springboot.main-run-controller=false",
    "runtime.output-queues.probe[0]=HB.W0.PROBE.OUT"})
@Import({IsolatedRuntimeTestConfiguration.class, OutputQueueContextTest.ProbeConfiguration.class})
class OutputQueueContextTest {
    @Autowired
    private ConfigurableApplicationContext applicationContext;

    @Autowired
    private CamelContext context;

    @Autowired
    private ConnectionFactory factory;

    @Autowired
    private TransactionManager transactions;

    @Autowired
    private JtaTransactionManager springTransactions;

    @Autowired
    private OutputQueueDeclarer declarer;

    @Autowired
    private OutputQueueDeclarer.Destinations destinations;

    @Autowired
    private EmbeddedActiveMQ broker;

    @Autowired
    private ProbeRoutes probe;

    @Test
    void nonemptyOutputsStartWithWrappedPrimaryFactoryAndNativeAdministration() throws Exception {
        assertThat(context.isStarted()).isTrue();
        assertThat(factory).isInstanceOf(ConnectionFactoryProxy.class);
        var jms = context.getComponent("jms", JmsComponent.class).getConfiguration();
        assertThat(jms.getConnectionFactory()).isSameAs(factory);
        assertThat(jms.getTransactionManager()).isSameAs(springTransactions);
        assertThat(jms.isTransacted()).isTrue();
        var nativeFactory = (ActiveMQConnectionFactory) ReflectionTestUtils.getField(declarer, "factory");
        assertThat(nativeFactory).isNotSameAs(factory);
        assertThat(nativeFactory.getClass()).isEqualTo(ActiveMQConnectionFactory.class);
        try (var connection = factory.createConnection();
             var session = connection.createSession(false, Session.AUTO_ACKNOWLEDGE);
             var nativeConnection = nativeFactory.createConnection();
             var nativeSession = nativeConnection.createSession(false, Session.AUTO_ACKNOWLEDGE)) {
            assertThat(((ActiveMQSession) nativeSession).getCoreSession().isXA()).isFalse();
            System.out.printf("PROBE primary factory=%s session=%s admin factory=%s session=%s adminXA=false%n",
                factory.getClass().getName(), session.getClass().getName(),
                nativeFactory.getClass().getName(), nativeSession.getClass().getName());
        }
        applicationContext.getBean("outputQueueReadiness", CamelContextConfiguration.class)
            .beforeApplicationStart(context);
        assertQueue("HB.W0.PROBE.OUT");
    }

    @Test
    void declarationInsideJtaDoesNotEnlistAndSurvivesRollback() throws Exception {
        var original = destinations.getOutputQueues();
        destinations.setOutputQueues(Map.of("probe", List.of("HB.W0.PROBE.TX.OUT")));
        transactions.begin();
        try {
            var transaction = (TransactionImple) transactions.getTransaction();
            assertThat(transaction.getResources()).isEmpty();
            declarer.declare();
            declarer.declare();
            assertThat(transactions.getTransaction()).isSameAs(transaction);
            assertThat(transactions.getStatus()).isEqualTo(Status.STATUS_ACTIVE);
            assertThat(transaction.getResources()).isEmpty();
            System.out.println("PROBE active JTA declaration succeeded; enlisted XA resources=0");
        } finally {
            transactions.rollback();
            destinations.setOutputQueues(original);
        }
        assertQueue("HB.W0.PROBE.TX.OUT");
        System.out.println("PROBE HB.W0.PROBE.TX.OUT still exists after JTA rollback");
    }

    @Test
    void packageStyleRouteBuilderRunsReadinessWithoutHidingRoutes() {
        assertThat(probe.readinessCalls).isPositive();
        assertThat(context.getRoute("w0-admin-probe")).isNotNull();
        assertQueue("HB.W0.PROBE.OUT");
        System.out.println("PROBE package-style RouteBuilder readiness executed; route present");
    }

    private void assertQueue(String name) {
        var queue = broker.getActiveMQServer().locateQueue(SimpleString.of(name));
        assertThat(queue).isNotNull();
        assertThat(queue.isDurable()).isTrue();
        assertThat(queue.isAutoDelete()).isFalse();
        assertThat(queue.getRoutingType()).isEqualTo(RoutingType.ANYCAST);
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class ProbeConfiguration {
        @Bean
        ProbeRoutes packageStyleReadiness(OutputQueueDeclarer declarer) {
            return new ProbeRoutes(declarer);
        }
    }

    static class ProbeRoutes extends RouteBuilder implements CamelContextConfiguration {
        private final OutputQueueDeclarer declarer;
        private int readinessCalls;

        ProbeRoutes(OutputQueueDeclarer declarer) {
            this.declarer = declarer;
        }

        @Override
        public void configure() {
            from("jms:queue:HB.W0.PROBE.IN?transacted=true")
                .routeId("w0-admin-probe").autoStartup(false).transacted("required")
                .process(exchange -> { });
        }

        @Override
        public void beforeApplicationStart(CamelContext context) {
            try {
                declarer.declare();
                readinessCalls++;
            } catch (Exception e) {
                throw new IllegalStateException("Probe dependencies are not ready", e);
            }
        }

        @Override
        public void afterApplicationStart(CamelContext context) { }
    }
}
